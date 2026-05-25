"""
NEWS AGENT - Monitors forex calendar, news, and market events
"""

import logging
import time
import json
import requests
import feedparser
from datetime import datetime, timedelta
from openai import OpenAI
import os
import urllib.request
from dotenv import load_dotenv
from memory_helper import memory
from api_helper import send_telegram_reliable, call_deepseek_reliable
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
load_dotenv()

class NewsAgent:
    def __init__(self):
        # Load configuration
        Config.validate_credentials()

        self.client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_API_URL)

        # Telegram
        self.telegram_token = Config.TELEGRAM_TOKEN
        self.telegram_chat_id = Config.TELEGRAM_CHAT_ID

        self.last_update_id = 0

        # Memory
        self.memory_path = Config.TRADING_MEMORY_PATH
        
        # Symbols to track news for
        self.symbols = ["XAUUSD", "XAGUSD", "EURUSD", "USDCAD", "USDJPY", "USDCHF", "USOUSD", "SP500", "NAS100"]
        
        # Cache for alerts
        self.last_alert_time = {}
        
        logger.info("News Agent initialized")
        self.send("📰 NEWS AGENT ONLINE\nMonitoring forex calendar and market news\nCommands: calendar, news, alerts, help")
    
    def send(self, msg):
        send_telegram_reliable(self.telegram_token, self.telegram_chat_id, msg, max_retries=2)
    
    def get_forex_calendar(self):
        """Get today's high-impact news events with GMT+3 timezone"""
        try:
            now_local = datetime.now()
            weekday = now_local.weekday()
            
            if weekday >= 5:
                days_until_sunday = (6 - weekday) if weekday == 5 else 0
                next_open = now_local + timedelta(days=days_until_sunday)
                next_open = next_open.replace(hour=1, minute=0, second=0, microsecond=0)
                
                return [{
                    'time': 'Weekend',
                    'currency': 'N/A',
                    'event': f'Market closed. Next session: Sunday 22:00 GMT (Monday 01:00 GMT+3)',
                    'date': next_open.strftime('%Y-%m-%d')
                }]
            
            known_events = [
                {'time': '14:30', 'currency': 'USD', 'event': 'Non-Farm Payrolls (NFP)', 'impact': 'High', 'schedule': 'First Friday of month'},
                {'time': '14:30', 'currency': 'USD', 'event': 'CPI Inflation Data', 'impact': 'High', 'schedule': 'Monthly'},
                {'time': '14:30', 'currency': 'USD', 'event': 'FOMC Rate Decision', 'impact': 'High', 'schedule': '8 times/year'},
                {'time': '14:30', 'currency': 'USD', 'event': 'Unemployment Rate', 'impact': 'High', 'schedule': 'Monthly'}
            ]
            
            try:
                api_url = "https://economic-calendar.tradingview.com/events?from=" + now_local.strftime('%Y-%m-%d')
                req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    
                    high_impact = []
                    for event in data.get('events', [])[:10]:
                        impact = event.get('impact', '')
                        if impact in ['High', 'high', '3']:
                            event_time = event.get('date', '')
                            event_currency = event.get('currency', '')
                            event_title = event.get('title', '')
                            
                            try:
                                if event_time:
                                    dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                                    dt_local = dt + timedelta(hours=3)
                                    event_time = dt_local.strftime('%H:%M')
                            except:
                                pass
                            
                            high_impact.append({
                                'time': event_time if event_time else 'TBD',
                                'currency': event_currency,
                                'event': event_title,
                                'date': now_local.strftime('%Y-%m-%d')
                            })
                    
                    if high_impact:
                        return high_impact
            except Exception as e:
                logger.warning(f"Calendar API error: {e}")
            
            result = []
            for event in known_events[:5]:
                result.append({
                    'time': event['time'],
                    'currency': event['currency'],
                    'event': f"{event['event']} ({event['schedule']})",
                    'date': event['schedule']
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Calendar error: {e}")
            return [{'time': 'N/A', 'currency': 'N/A', 'event': f'Calendar error', 'date': datetime.now().strftime('%Y-%m-%d')}]
    
    def get_market_news(self):
        """Get recent market news using RSS feeds"""
        news_items = []
        feeds = [
            "https://www.forexlive.com/feed/news/",
            "https://feeds.bloomberg.com/markets/news.rss"
        ]
        
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    news_items.append({
                        'title': entry.title,
                        'summary': entry.summary[:200] if hasattr(entry, 'summary') else '',
                        'published': entry.published if hasattr(entry, 'published') else '',
                        'link': entry.link
                    })
            except Exception as e:
                logger.error(f"Feed error {feed_url}: {e}")
                continue
        
        return news_items
    
    def analyze_news_impact(self, news):
        """Use AI to analyze how news might affect symbols"""
        prompt = f"""Analyze this news and determine which of these symbols might be affected:
{self.symbols}

News: {news.get('title', '')} - {news.get('summary', '')[:150]}

Output JSON:
{{
    "affected_symbols": ["XAUUSD", "EURUSD"],
    "sentiment": "BULLISH/BEARISH/NEUTRAL",
    "confidence": 0-100,
    "recommendation": "brief trading advice"
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )
            content = response.choices[0].message.content
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                
                # Save to Obsidian
                memory.save_news_impact({
                    'title': news.get('title', 'News')[:100],
                    'summary': news.get('summary', '')[:200],
                    'sentiment': result.get('sentiment', 'NEUTRAL'),
                    'confidence': result.get('confidence', 0),
                    'affected_symbols': result.get('affected_symbols', []),
                    'recommendation': result.get('recommendation', 'Monitor'),
                    'link': news.get('link', '')
                })
                
                return result
        except:
            pass
        return {'affected_symbols': [], 'sentiment': 'NEUTRAL', 'confidence': 0, 'recommendation': 'Monitor price action'}
    
    def get_updates(self):
        """DISABLED - Intelligence Hub handles Telegram routing"""
        return True
    
    def process_command(self, msg):
        msg_lower = msg.lower().strip()
        
        logger.info(f"Processing: {msg_lower}")
        
        if msg_lower == "calendar":
            self.cmd_calendar()
        elif msg_lower == "news":
            self.cmd_news()
        elif msg_lower == "alerts":
            self.cmd_alerts()
        elif msg_lower == "help":
            self.cmd_help()
        else:
            self.send(f"Unknown: {msg_lower}\nTry: calendar, news, alerts, help")
    
    def cmd_calendar(self):
        events = self.get_forex_calendar()
        if events:
            message = "📅 FOREX CALENDAR (GMT+3)\n━━━━━━━━━━━━━━━━━━━━━\n"
            for e in events:
                time_str = e.get('time', 'N/A')
                currency = e.get('currency', 'N/A')
                event_name = e.get('event', 'Unknown')
                
                if 'Weekend' in time_str:
                    message += f"\n🔒 {event_name}\n   {e.get('date', '')}\n"
                else:
                    message += f"🕐 {time_str} | {currency}\n   📰 {event_name}\n"
            self.send(message)
        else:
            self.send("No high-impact news found")
    
    def cmd_news(self):
        self.send("📰 Fetching latest market news...")
        
        news_items = self.get_market_news()
        
        if news_items:
            for item in news_items[:3]:
                analysis = self.analyze_news_impact(item)
                message = f"📰 {item['title'][:60]}\n"
                message += f"💡 Impact: {analysis.get('sentiment', 'NEUTRAL')}\n"
                message += f"🎯 Affects: {', '.join(analysis.get('affected_symbols', ['None'])[:4])}\n"
                message += f"📊 Confidence: {analysis.get('confidence', 0)}%\n"
                self.send(message)
                time.sleep(1)
            self.send("💾 News analysis saved to Obsidian vault")
        else:
            self.send("📰 No recent news found.\nTry 'calendar' for economic events.")
    
    def cmd_alerts(self):
        self.send("🔔 ALERTS ACTIVE\n\nI will notify you of:\n• High-impact news events\n• Major market moves\n• Sentiment changes\n\nTo receive alerts, keep this agent running 24/7.")
    
    def cmd_help(self):
        help_text = """📰 NEWS AGENT COMMANDS

calendar - High-impact economic events (GMT+3)
news - Latest market news with AI analysis
alerts - Alert settings
help - This menu

All news analysis is saved to Obsidian vault for future reference."""
        self.send(help_text)
    
    def run(self):
        logger.info("News agent running in background mode (Telegram disabled)")
        try:
            while True:
                # Background task: periodically fetch and analyze news
                self.cmd_news()
                time.sleep(300)  # Fetch news every 5 minutes

                # Periodic calendar check
                self.cmd_calendar()
                time.sleep(600)  # Check calendar every 10 minutes
        except KeyboardInterrupt:
            logger.info("News agent stopped")

if __name__ == "__main__":
    agent = NewsAgent()
    agent.run()