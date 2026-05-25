"""
WORKFLOW ENGINE - n8n-style markdown workflow automation
Execute complex trading workflows defined in markdown
"""

import logging
import json
import re
import os
import sys
import subprocess
import requests
from datetime import datetime, timedelta
from pathlib import Path
from openai import OpenAI
import MetaTrader5 as mt5
from dotenv import load_dotenv
from jinja2 import Template
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

class WorkflowEngine:
    def __init__(self):
        Config.validate_credentials()
        self.client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_API_URL)
        self.telegram_token = Config.TELEGRAM_TOKEN
        self.telegram_chat_id = Config.TELEGRAM_CHAT_ID
        self.workflows_path = Config.get_file_path("workflows")
        self.memory_path = Config.TRADING_MEMORY_PATH
        self.execution_logs = []

        os.makedirs(self.workflows_path, exist_ok=True)
        logger.info("Workflow Engine initialized")

    def parse_workflow(self, workflow_content):
        """Parse markdown workflow into structured format"""
        lines = workflow_content.split('\n')

        # Extract frontmatter
        metadata = {}
        in_frontmatter = False
        content_start = 0

        for i, line in enumerate(lines):
            if line.strip() == '---':
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    content_start = i + 1
                    break
            elif in_frontmatter and ':' in line:
                key, value = line.split(':', 1)
                metadata[key.strip()] = value.strip()

        # Extract steps
        steps = []
        current_step = None

        for line in lines[content_start:]:
            if line.startswith('## Step'):
                if current_step:
                    steps.append(current_step)
                current_step = {'name': line.replace('## Step ', '').strip(), 'config': {}}
            elif current_step and line.startswith('- '):
                key_value = line[2:].strip()
                if ':' in key_value:
                    key, value = key_value.split(':', 1)
                    current_step['config'][key.strip()] = value.strip()

        if current_step:
            steps.append(current_step)

        return {
            'metadata': metadata,
            'steps': steps
        }

    def execute_workflow(self, workflow_file, inputs=None):
        """Execute a workflow from file"""
        if not os.path.exists(workflow_file):
            return f"❌ Workflow not found: {workflow_file}"

        with open(workflow_file, 'r') as f:
            workflow_content = f.read()

        workflow = self.parse_workflow(workflow_content)
        metadata = workflow['metadata']
        steps = workflow['steps']

        logger.info(f"Executing workflow: {metadata.get('name', 'Unknown')}")

        # Initialize execution context
        context = {
            'inputs': inputs or {},
            'outputs': {},
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S')
        }

        # Execute each step
        for i, step in enumerate(steps):
            logger.info(f"Executing step {i+1}: {step['name']}")
            self.log_execution(f"Step {i+1}: {step['name']}")

            try:
                result = self.execute_step(step, context)

                if not result['success']:
                    if step['config'].get('on_error') == 'continue':
                        logger.warning(f"Step failed but continuing: {result['error']}")
                        self.log_execution(f"⚠️ Step failed (continuing): {result['error']}")
                        continue
                    else:
                        logger.error(f"Step failed: {result['error']}")
                        self.log_execution(f"❌ Step failed: {result['error']}")
                        return f"❌ Workflow failed at step {i+1}: {result['error']}"

                context['outputs'][step['name']] = result['output']
                logger.info(f"Step {i+1} completed")
                self.log_execution(f"✅ Step {i+1} completed")

            except Exception as e:
                logger.error(f"Step execution error: {e}")
                self.log_execution(f"❌ Error: {str(e)}")
                return f"❌ Error at step {i+1}: {str(e)}"

        return f"✅ Workflow completed successfully\n\n{self.format_outputs(context['outputs'])}"

    def execute_step(self, step, context):
        """Execute a single workflow step"""
        action = step['config'].get('action', '').lower()

        if action == 'api_call':
            return self.step_api_call(step, context)
        elif action == 'python_script':
            return self.step_python_script(step, context)
        elif action == 'ai_summary':
            return self.step_ai_summary(step, context)
        elif action == 'write_file':
            return self.step_write_file(step, context)
        elif action == 'telegram_send':
            return self.step_telegram_send(step, context)
        elif action == 'get_account':
            return self.step_get_account(step, context)
        elif action == 'get_candles':
            return self.step_get_candles(step, context)
        else:
            return {'success': False, 'error': f'Unknown action: {action}'}

    def step_api_call(self, step, context):
        """Execute API call step"""
        try:
            url = self.interpolate(step['config'].get('url', ''), context)
            method = step['config'].get('method', 'POST').upper()
            body = step['config'].get('body', '{}')
            body = self.interpolate(body, context)
            body_json = json.loads(body)

            if method == 'POST':
                response = requests.post(url, json=body_json, timeout=30)
            elif method == 'GET':
                response = requests.get(url, timeout=30)

            return {
                'success': response.status_code == 200,
                'output': response.json() if response.text else {'status': 'ok'}
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def step_python_script(self, step, context):
        """Execute Python script step"""
        try:
            script_path = self.interpolate(step['config'].get('script', ''), context)

            # Handle both standalone scripts and builtin ones
            if script_path == 'backtest_strategy.py':
                # Run backtest with parameters
                symbol = self.interpolate(step['config'].get('symbol', 'XAUUSD.s'), context)
                days = int(self.interpolate(step['config'].get('days', '30'), context))
                tp = int(self.interpolate(step['config'].get('tp', '400'), context))
                sl = int(self.interpolate(step['config'].get('sl', '6000'), context))

                # Call backtest
                result = self.run_backtest(symbol, days, tp, sl)
                return {'success': True, 'output': result}
            else:
                # Run arbitrary Python script
                result = subprocess.run(['python', script_path], capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    return {'success': True, 'output': result.stdout}
                else:
                    return {'success': False, 'error': result.stderr}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def step_ai_summary(self, step, context):
        """Use AI to summarize data"""
        try:
            input_data = self.interpolate(step['config'].get('input', ''), context)
            prompt = self.interpolate(step['config'].get('prompt', ''), context)

            full_prompt = f"{prompt}\n\nData:\n{input_data}"

            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.5,
                max_tokens=500
            )

            return {
                'success': True,
                'output': response.choices[0].message.content
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def step_write_file(self, step, context):
        """Write data to file"""
        try:
            path = self.interpolate(step['config'].get('path', ''), context)
            content = self.interpolate(step['config'].get('content', ''), context)

            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)

            return {'success': True, 'output': f'File written: {path}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def step_telegram_send(self, step, context):
        """Send message via Telegram"""
        try:
            message = self.interpolate(step['config'].get('message', ''), context)

            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            requests.post(url, json={"chat_id": self.telegram_chat_id, "text": message}, timeout=10)

            return {'success': True, 'output': 'Message sent'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def step_get_account(self, step, context):
        """Get MT5 account info"""
        try:
            mt5.initialize(
                path=Config.MT5_PATH,
                login=Config.MT5_LOGIN,
                password=Config.MT5_PASSWORD,
                server=Config.MT5_SERVER
            )
            account = mt5.account_info()
            mt5.shutdown()

            return {
                'success': True,
                'output': {
                    'balance': account.balance,
                    'equity': account.equity,
                    'profit': account.profit,
                    'margin': account.margin
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def step_get_candles(self, step, context):
        """Get historical candles"""
        try:
            symbol = self.interpolate(step['config'].get('symbol', 'XAUUSD.s'), context)
            days = int(self.interpolate(step['config'].get('days', '30'), context))

            mt5.initialize(
                path=Config.MT5_PATH,
                login=Config.MT5_LOGIN,
                password=Config.MT5_PASSWORD,
                server=Config.MT5_SERVER
            )

            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, days)
            mt5.shutdown()

            if rates is None:
                return {'success': False, 'error': f'Failed to get candles for {symbol}'}

            candles = []
            for r in rates:
                candles.append({
                    'date': datetime.fromtimestamp(r[0]).strftime('%Y-%m-%d'),
                    'open': r[1],
                    'high': r[2],
                    'low': r[3],
                    'close': r[4]
                })

            return {'success': True, 'output': candles}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def run_backtest(self, symbol, days, tp, sl):
        """Run backtest simulation"""
        try:
            mt5.initialize(
                path=Config.MT5_PATH,
                login=Config.MT5_LOGIN,
                password=Config.MT5_PASSWORD,
                server=Config.MT5_SERVER
            )

            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, days)
            mt5.shutdown()

            if rates is None:
                return {'success': False, 'error': 'Failed to fetch candles'}

            wins, losses, profit = 0, 0, 0

            for i in range(1, len(rates)):
                prev_high = float(rates[i-1][2])
                prev_low = float(rates[i-1][3])
                today_high = float(rates[i][2])
                today_low = float(rates[i][3])

                # Long breakout
                if today_high > prev_high:
                    if today_high >= prev_high + tp:
                        wins += 1
                        profit += tp
                    elif today_low <= prev_high - sl:
                        losses += 1
                        profit -= sl

                # Short breakout
                if today_low < prev_low:
                    if today_low <= prev_low - tp:
                        wins += 1
                        profit += tp
                    elif today_high >= prev_low + sl:
                        losses += 1
                        profit -= sl

            total = wins + losses
            return {
                'wins': wins,
                'losses': losses,
                'total': total,
                'win_rate': (wins / total * 100) if total > 0 else 0,
                'net_profit': profit
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def interpolate(self, text, context):
        """Interpolate variables using Jinja2"""
        try:
            template = Template(text)
            return template.render(context)
        except:
            return text

    def log_execution(self, message):
        """Log execution step"""
        self.execution_logs.append({
            'timestamp': datetime.now().isoformat(),
            'message': message
        })

    def format_outputs(self, outputs):
        """Format output results"""
        result = "📊 Workflow Outputs:\n"
        for name, output in outputs.items():
            if isinstance(output, dict):
                result += f"\n{name}:\n"
                for k, v in output.items():
                    result += f"  • {k}: {v}\n"
            else:
                result += f"\n{name}: {output}\n"
        return result

    def save_execution_log(self):
        """Save execution log to Obsidian"""
        log_path = f"{self.memory_path}\\obsidian-vault\\Workflow-Logs\\execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        content = f"""# Workflow Execution Log
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Steps
"""
        for log in self.execution_logs:
            content += f"- {log['message']}\n"

        with open(log_path, 'w') as f:
            f.write(content)

        return log_path

if __name__ == "__main__":
    engine = WorkflowEngine()

    # Example: Execute a workflow
    workflow_file = "C:\\Users\\user\\Desktop\\DS trading agent\\workflows\\analyze-strategy.md"
    if len(sys.argv) > 1:
        workflow_file = sys.argv[1]

    result = engine.execute_workflow(workflow_file, {
        'symbol': 'XAUUSD.s',
        'days': 30,
        'tp': 400,
        'sl': 6000
    })

    print(result)
    engine.save_execution_log()
