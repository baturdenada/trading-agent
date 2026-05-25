"""
SELF-MODIFICATION SYSTEM - Trading system improves itself based on performance
Analyzes code, suggests improvements, applies approved changes
"""

import logging
import json
import os
import re
import subprocess
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import requests
from api_helper import send_telegram_reliable, call_deepseek_reliable
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

class SelfModifier:
    def __init__(self):
        Config.validate_credentials()
        self.client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_API_URL)
        self.telegram_token = Config.TELEGRAM_TOKEN
        self.telegram_chat_id = Config.TELEGRAM_CHAT_ID
        self.memory_path = Config.TRADING_MEMORY_PATH
        self.project_path = Config.PROJECT_ROOT
        self.approved_changes = []
        logger.info("Self-Modification System initialized")

    def send(self, msg):
        """Send Telegram message"""
        send_telegram_reliable(self.telegram_token, self.telegram_chat_id, msg, max_retries=2)

    def analyze_performance(self):
        """Analyze trading performance metrics"""
        try:
            trade_file = os.path.join(self.memory_path, "trade_history.json")
            if not os.path.exists(trade_file):
                return None

            with open(trade_file, 'r') as f:
                trades = json.load(f)

            wins = [t for t in trades if t.get('is_win', False)]
            losses = [t for t in trades if not t.get('is_win', False)]

            return {
                'total_trades': len(trades),
                'wins': len(wins),
                'losses': len(losses),
                'win_rate': len(wins) / len(trades) * 100 if trades else 0,
                'net_profit': sum(t.get('profit', 0) for t in wins) - sum(abs(t.get('profit', 0)) for t in losses),
                'avg_win': sum(t.get('profit', 0) for t in wins) / len(wins) if wins else 0,
                'avg_loss': sum(abs(t.get('profit', 0)) for t in losses) / len(losses) if losses else 0,
                'recent_trades': trades[-20:]
            }
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return None

    def read_code_file(self, filename):
        """Read a Python code file"""
        filepath = os.path.join(self.project_path, filename)
        try:
            with open(filepath, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Read error: {e}")
            return None

    def generate_suggestions(self, performance, code_file):
        """Use AI to suggest code improvements"""
        perf = performance
        code = code_file

        prompt = f"""You are a professional trading system expert. Analyze this trading system's code and performance.

PERFORMANCE METRICS:
- Total Trades: {perf['total_trades']}
- Win Rate: {perf['win_rate']:.1f}%
- Net Profit: ${perf['net_profit']:+.2f}
- Average Win: ${perf['avg_win']:+.2f}
- Average Loss: ${perf['avg_loss']:+.2f}

CURRENT CODE (excerpts):
{code[:2000]}...

Based on the performance metrics, provide 3-5 specific code improvements that would likely increase profitability.

For each suggestion:
1. Identify the specific parameter or logic to change
2. Current value/behavior
3. Proposed new value/behavior
4. Expected impact (e.g., "Reduce drawdowns by 20%")
5. Difficulty level (Easy/Medium/Hard)

Output as JSON array:
[
  {{
    "id": 1,
    "title": "Improvement title",
    "parameter": "Parameter name",
    "current": "Current value",
    "proposed": "Proposed value",
    "reasoning": "Why this helps",
    "impact": "Expected improvement",
    "difficulty": "Easy"
  }}
]"""

        try:
            content = call_deepseek_reliable(
                self.client,
                prompt,
                fallback='[]'
            )

            if content:
                import re
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    suggestions = json.loads(json_match.group(0))
                    return suggestions
        except Exception as e:
            logger.error(f"Generation error: {e}")

        return []

    def format_suggestions_for_approval(self, suggestions):
        """Format suggestions for user approval"""
        msg = "🧠 SELF-IMPROVEMENT SUGGESTIONS\n\n"

        for i, sugg in enumerate(suggestions, 1):
            msg += f"#{i} {sugg.get('title', 'Improvement')}\n"
            msg += f"   📍 Parameter: {sugg.get('parameter', 'N/A')}\n"
            msg += f"   ↳ Current: {sugg.get('current', 'N/A')}\n"
            msg += f"   ↳ Proposed: {sugg.get('proposed', 'N/A')}\n"
            msg += f"   📈 Impact: {sugg.get('impact', 'N/A')}\n"
            msg += f"   ⚙️ Difficulty: {sugg.get('difficulty', 'N/A')}\n\n"

        msg += "Reply with suggestion numbers to approve (e.g., '1,3,5')\nOr reply 'none' to skip"

        return msg

    def apply_suggestion(self, suggestion, code_content):
        """Apply a single suggestion to code"""
        parameter = suggestion.get('parameter', '')
        current = suggestion.get('current', '')
        proposed = suggestion.get('proposed', '')

        try:
            # Simple parameter replacement
            updated_code = code_content.replace(current, proposed)

            if updated_code == code_content:
                return {
                    'success': False,
                    'error': f'Could not find "{current}" in code'
                }

            return {
                'success': True,
                'original': current,
                'replacement': proposed,
                'updated_code': updated_code
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def backup_file(self, filepath):
        """Create backup of file before modification"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = os.path.join(self.project_path, "backups")
            os.makedirs(backup_dir, exist_ok=True)

            filename = os.path.basename(filepath)
            backup_path = os.path.join(backup_dir, f"{filename}.backup_{timestamp}")

            with open(filepath, 'r') as f:
                content = f.read()

            with open(backup_path, 'w') as f:
                f.write(content)

            logger.info(f"Backup created: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Backup error: {e}")
            return None

    def analyze_and_suggest(self, code_file='ultimate_trader.py'):
        """Main entry point: analyze system and suggest improvements"""
        logger.info("Starting self-analysis...")
        self.send("🤖 Starting self-analysis...")

        # 1. Analyze performance
        performance = self.analyze_performance()
        if not performance:
            msg = "❌ Could not analyze performance. Need at least 10 trades."
            self.send(msg)
            return msg

        # 2. Read code
        code = self.read_code_file(code_file)
        if not code:
            return f"❌ Could not read code file: {code_file}"

        # 3. Generate suggestions
        logger.info("Generating suggestions...")
        suggestions = self.generate_suggestions(performance, code)

        if not suggestions:
            return "❌ Could not generate suggestions"

        # 4. Format for user
        approval_msg = self.format_suggestions_for_approval(suggestions)
        self.send(approval_msg)

        return {
            'status': 'awaiting_approval',
            'suggestions': suggestions,
            'code_file': code_file,
            'performance': performance
        }

    def apply_approved_changes(self, suggestion_ids, code_file):
        """Apply user-approved suggestions"""
        logger.info(f"Applying suggestions: {suggestion_ids}")

        code_path = os.path.join(self.project_path, code_file)
        self.backup_file(code_path)

        with open(code_path, 'r') as f:
            code_content = f.read()

        # Get suggestions (in real implementation, fetch from stored state)
        performance = self.analyze_performance()
        code = self.read_code_file(code_file)
        suggestions = self.generate_suggestions(performance, code)

        applied = []
        failed = []

        for sugg_id in suggestion_ids:
            suggestion = next((s for s in suggestions if s.get('id') == sugg_id), None)
            if not suggestion:
                failed.append(sugg_id)
                continue

            result = self.apply_suggestion(suggestion, code_content)
            if result['success']:
                code_content = result['updated_code']
                applied.append(sugg_id)
            else:
                failed.append(sugg_id)

        # Save updated code
        try:
            with open(code_path, 'w') as f:
                f.write(code_content)

            msg = f"✅ Applied {len(applied)} suggestion(s)\n"
            if failed:
                msg += f"❌ Failed: {failed}\n"

            msg += f"\n📝 Code updated. Restart agent to activate.\n"
            msg += f"Backup saved to: /backups/\n"

            self.send(msg)
            return {'applied': applied, 'failed': failed}

        except Exception as e:
            self.send(f"❌ Save error: {str(e)}")
            return {'applied': [], 'failed': suggestion_ids}

    def get_optimization_report(self):
        """Generate optimization report"""
        perf = self.analyze_performance()
        if not perf:
            return "Not enough data for report"

        suggestions = []

        if perf['win_rate'] < 50:
            suggestions.append("❌ Win rate below 50% - consider reducing position size")
        elif perf['win_rate'] > 75:
            suggestions.append("✅ Excellent win rate - consider increasing position size")

        if perf['avg_loss'] > perf['avg_win'] * 2:
            suggestions.append("⚠️ Losses are too large - tighten stop loss")

        if perf['total_trades'] > 100:
            if perf['net_profit'] / perf['total_trades'] < 5:
                suggestions.append("📊 Average profit per trade is low - improve entry signals")

        report = f"""📊 OPTIMIZATION REPORT

Stats:
• Trades: {perf['total_trades']}
• Win Rate: {perf['win_rate']:.1f}%
• Net Profit: ${perf['net_profit']:+.2f}
• Avg Win: ${perf['avg_win']:+.2f}
• Avg Loss: ${perf['avg_loss']:+.2f}

Recommendations:
{chr(10).join(suggestions) if suggestions else '✅ System performing well'}"""

        return report

if __name__ == "__main__":
    modifier = SelfModifier()

    # Run self-analysis
    result = modifier.analyze_and_suggest('ultimate_trader.py')
    print(json.dumps(result, indent=2, default=str))

    # Example of applying changes (would need user approval in real scenario)
    # modifier.apply_approved_changes([1, 3], 'ultimate_trader.py')

    # Get optimization report
    report = modifier.get_optimization_report()
    print("\n" + report)
