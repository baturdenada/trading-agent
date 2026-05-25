"""
Trade History Analyzer - Learns from closed trades
Tracks win rates by setup type, symbol, and market conditions
Uses data to adapt confidence thresholds and skip bad patterns
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

class TradeHistorian:
    def __init__(self, memory_path="C:/trading-memory"):
        self.memory_path = Path(memory_path)
        self.memory_path.mkdir(parents=True, exist_ok=True)
        self.history_file = self.memory_path / "trade_history.json"
        self.analysis_file = self.memory_path / "win_rate_analysis.json"
        self.trades = self.load_history()
        self.analysis = self.load_analysis()

    def load_history(self):
        """Load trade history from disk"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def load_analysis(self):
        """Load win rate analysis from disk"""
        if self.analysis_file.exists():
            try:
                with open(self.analysis_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_history(self):
        """Save trade history to disk"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save trade history: {e}")

    def save_analysis(self):
        """Save analysis to disk"""
        try:
            with open(self.analysis_file, 'w') as f:
                json.dump(self.analysis, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save analysis: {e}")

    def log_trade(self, symbol, entry_price, exit_price, entry_time, exit_time,
                  profit, setup_type, rsi_value, trend, confidence, win=True):
        """Log a completed trade with all details"""
        trade = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "entry_time": entry_time,
            "exit_time": exit_time,
            "profit": float(profit),
            "profit_pct": float(profit) / float(entry_price) * 100 if entry_price > 0 else 0,
            "setup_type": setup_type,  # e.g., "RSI_EXTREME", "TREND_REVERSAL", "MOMENTUM_BREAKOUT"
            "rsi_value": float(rsi_value),
            "trend": trend,
            "confidence": int(confidence),
            "duration_seconds": int((datetime.fromisoformat(exit_time) -
                                    datetime.fromisoformat(entry_time)).total_seconds()),
            "win": win,
            "market_regime": self._detect_regime_at_time(entry_time)
        }

        self.trades.append(trade)
        self.save_history()
        self.analyze_trades()

        logger.info(f"Logged trade: {symbol} {'+' if win else '-'}{abs(profit):.2f} ({setup_type})")

    def analyze_trades(self):
        """Analyze all trades to identify patterns"""
        if len(self.trades) < 10:
            logger.info(f"Need 10+ trades for analysis (currently {len(self.trades)})")
            return

        self.analysis = {
            "total_trades": len(self.trades),
            "win_rate": sum(1 for t in self.trades if t['win']) / len(self.trades) * 100,
            "by_setup_type": self._analyze_by_setup(),
            "by_symbol": self._analyze_by_symbol(),
            "by_rsi_range": self._analyze_by_rsi(),
            "by_trend": self._analyze_by_trend(),
            "by_confidence": self._analyze_by_confidence(),
            "by_market_regime": self._analyze_by_regime(),
            "recommendations": self._generate_recommendations()
        }

        self.save_analysis()
        self._log_analysis()

    def _analyze_by_setup(self):
        """Win rate by setup type"""
        by_setup = defaultdict(lambda: {"wins": 0, "total": 0, "avg_profit": 0})

        for trade in self.trades:
            setup = trade['setup_type']
            by_setup[setup]['total'] += 1
            if trade['win']:
                by_setup[setup]['wins'] += 1
            by_setup[setup]['avg_profit'] += trade['profit']

        result = {}
        for setup, data in by_setup.items():
            result[setup] = {
                "total": data['total'],
                "wins": data['wins'],
                "win_rate": data['wins'] / data['total'] * 100 if data['total'] > 0 else 0,
                "avg_profit": data['avg_profit'] / data['total'] if data['total'] > 0 else 0,
                "recommendation": "GOOD" if data['wins'] / data['total'] > 0.6 else "SKIP" if data['wins'] / data['total'] < 0.4 else "OK"
            }

        return result

    def _analyze_by_symbol(self):
        """Win rate by trading symbol"""
        by_symbol = defaultdict(lambda: {"wins": 0, "total": 0})

        for trade in self.trades:
            symbol = trade['symbol']
            by_symbol[symbol]['total'] += 1
            if trade['win']:
                by_symbol[symbol]['wins'] += 1

        result = {}
        for symbol, data in by_symbol.items():
            result[symbol] = {
                "win_rate": data['wins'] / data['total'] * 100 if data['total'] > 0 else 0,
                "total_trades": data['total'],
                "recommendation": "FOCUS" if data['wins'] / data['total'] > 0.65 else "REDUCE" if data['wins'] / data['total'] < 0.45 else "NEUTRAL"
            }

        return result

    def _analyze_by_rsi(self):
        """Win rate by RSI ranges"""
        ranges = {
            "extremely_overbought (>85)": {"wins": 0, "total": 0},
            "overbought (70-85)": {"wins": 0, "total": 0},
            "neutral_high (50-70)": {"wins": 0, "total": 0},
            "neutral_low (30-50)": {"wins": 0, "total": 0},
            "oversold (15-30)": {"wins": 0, "total": 0},
            "extremely_oversold (<15)": {"wins": 0, "total": 0},
        }

        for trade in self.trades:
            rsi = trade['rsi_value']
            if rsi > 85:
                key = "extremely_overbought (>85)"
            elif rsi > 70:
                key = "overbought (70-85)"
            elif rsi > 50:
                key = "neutral_high (50-70)"
            elif rsi > 30:
                key = "neutral_low (30-50)"
            elif rsi > 15:
                key = "oversold (15-30)"
            else:
                key = "extremely_oversold (<15)"

            ranges[key]['total'] += 1
            if trade['win']:
                ranges[key]['wins'] += 1

        result = {}
        for key, data in ranges.items():
            if data['total'] > 0:
                result[key] = {
                    "win_rate": data['wins'] / data['total'] * 100,
                    "total_trades": data['total']
                }

        return result

    def _analyze_by_trend(self):
        """Win rate by market trend at entry"""
        by_trend = defaultdict(lambda: {"wins": 0, "total": 0})

        for trade in self.trades:
            trend = trade['trend']
            by_trend[trend]['total'] += 1
            if trade['win']:
                by_trend[trend]['wins'] += 1

        result = {}
        for trend, data in by_trend.items():
            if data['total'] > 0:
                result[trend] = {
                    "win_rate": data['wins'] / data['total'] * 100,
                    "total_trades": data['total'],
                    "recommendation": "PRIORITIZE" if data['wins'] / data['total'] > 0.65 else "AVOID" if data['wins'] / data['total'] < 0.40 else "NEUTRAL"
                }

        return result

    def _analyze_by_confidence(self):
        """Win rate by AI confidence levels"""
        confidence_ranges = {
            "very_high (90-100)": {"wins": 0, "total": 0},
            "high (75-90)": {"wins": 0, "total": 0},
            "medium (60-75)": {"wins": 0, "total": 0},
            "low (45-60)": {"wins": 0, "total": 0},
        }

        for trade in self.trades:
            conf = trade['confidence']
            if conf >= 90:
                key = "very_high (90-100)"
            elif conf >= 75:
                key = "high (75-90)"
            elif conf >= 60:
                key = "medium (60-75)"
            else:
                key = "low (45-60)"

            confidence_ranges[key]['total'] += 1
            if trade['win']:
                confidence_ranges[key]['wins'] += 1

        result = {}
        for key, data in confidence_ranges.items():
            if data['total'] > 0:
                result[key] = {
                    "win_rate": data['wins'] / data['total'] * 100,
                    "total_trades": data['total']
                }

        return result

    def _analyze_by_regime(self):
        """Win rate by market regime"""
        by_regime = defaultdict(lambda: {"wins": 0, "total": 0})

        for trade in self.trades:
            regime = trade.get('market_regime', 'unknown')
            by_regime[regime]['total'] += 1
            if trade['win']:
                by_regime[regime]['wins'] += 1

        result = {}
        for regime, data in by_regime.items():
            if data['total'] > 0:
                result[regime] = {
                    "win_rate": data['wins'] / data['total'] * 100,
                    "total_trades": data['total']
                }

        return result

    def _generate_recommendations(self):
        """Generate trading recommendations based on analysis"""
        recommendations = []

        # Check setup types
        setups = self.analysis.get('by_setup_type', {})
        for setup, stats in setups.items():
            if stats['recommendation'] == 'GOOD':
                recommendations.append(f"INCREASE: {setup} has {stats['win_rate']:.1f}% win rate - prioritize this setup")
            elif stats['recommendation'] == 'SKIP':
                recommendations.append(f"SKIP: {setup} has only {stats['win_rate']:.1f}% win rate - avoid this setup")

        # Check symbols
        symbols = self.analysis.get('by_symbol', {})
        for symbol, stats in symbols.items():
            if stats['recommendation'] == 'FOCUS':
                recommendations.append(f"FOCUS: {symbol} has {stats['win_rate']:.1f}% win rate and {stats['total_trades']} trades - this is your best pair")
            elif stats['recommendation'] == 'REDUCE':
                recommendations.append(f"REDUCE: {symbol} has {stats['win_rate']:.1f}% win rate - trade smaller or less frequently")

        # Check trends
        trends = self.analysis.get('by_trend', {})
        for trend, stats in trends.items():
            if stats['recommendation'] == 'PRIORITIZE':
                recommendations.append(f"PRIORITIZE: {trend} trend has {stats['win_rate']:.1f}% win rate - focus on this trend type")
            elif stats['recommendation'] == 'AVOID':
                recommendations.append(f"AVOID: {trend} trend has {stats['win_rate']:.1f}% win rate - skip trades in this trend")

        return recommendations

    def _detect_regime_at_time(self, timestamp_str):
        """Detect market regime at a given time (simplified)"""
        # In production, would check volatility at that time
        return "unknown"

    def _log_analysis(self):
        """Log analysis summary"""
        logger.info("=" * 80)
        logger.info("TRADE ANALYSIS SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total trades: {self.analysis.get('total_trades', 0)}")
        logger.info(f"Overall win rate: {self.analysis.get('win_rate', 0):.1f}%")
        logger.info("\nRECOMMENDATIONS:")
        for rec in self.analysis.get('recommendations', []):
            logger.info(f"  → {rec}")
        logger.info("=" * 80)

    def get_setup_confidence(self, setup_type):
        """Get adjusted confidence threshold for a setup type"""
        setups = self.analysis.get('by_setup_type', {})
        if setup_type in setups:
            win_rate = setups[setup_type]['win_rate']
            if win_rate > 65:
                return 45  # Lower threshold for proven winners
            elif win_rate < 40:
                return 80  # Much higher threshold for losers
        return 60  # Default threshold

    def should_skip_setup(self, setup_type):
        """Check if this setup should be skipped based on historical win rate"""
        setups = self.analysis.get('by_setup_type', {})
        if setup_type in setups:
            if setups[setup_type]['win_rate'] < 35:  # Less than 35% win rate
                return True
        return False

    def get_symbol_priority(self, symbol):
        """Get trading priority for a symbol (0-1 scale)"""
        symbols = self.analysis.get('by_symbol', {})
        if symbol in symbols:
            win_rate = symbols[symbol]['win_rate']
            return win_rate / 100  # 0.65 for 65% win rate
        return 0.5  # Neutral if unknown

    def get_trend_score(self, trend):
        """Score a trend type based on historical performance"""
        trends = self.analysis.get('by_trend', {})
        if trend in trends:
            win_rate = trends[trend]['win_rate']
            return win_rate / 100
        return 0.5
