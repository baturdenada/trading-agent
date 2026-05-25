"""
ML FEEDBACK LOOP - Self-learning from trade outcomes
Analyzes historical trades to identify winning setups and adjust confidence
Uses simple pattern recognition instead of heavy ML to stay lightweight
"""

import logging
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TradeOutcome:
    """Represents a completed trade for learning"""
    symbol: str
    setup_type: str          # 'RSI_EXTREME', 'TREND_REVERSAL', etc.
    entry_signal: str        # 'BUY' or 'SELL'
    entry_price: float
    exit_price: float
    profit: float
    profit_pct: float
    duration_minutes: int    # How long trade was open
    win: bool                # True if profitable
    market_regime: str       # 'TRENDING', 'RANGING', etc.
    initial_confidence: float
    timestamp: datetime

    def to_dict(self):
        return {
            'symbol': self.symbol,
            'setup_type': self.setup_type,
            'entry_signal': self.entry_signal,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'profit': self.profit,
            'profit_pct': self.profit_pct,
            'duration_minutes': self.duration_minutes,
            'win': self.win,
            'market_regime': self.market_regime,
            'initial_confidence': self.initial_confidence,
            'timestamp': self.timestamp.isoformat()
        }


class PatternAnalyzer:
    """Analyzes patterns in trade outcomes"""

    def __init__(self, history_file: str = "trade_outcomes.json"):
        self.history_file = Path(history_file)
        self.outcomes: List[TradeOutcome] = []
        self.patterns: Dict = {}
        self.load_history()
        logger.info(f"PatternAnalyzer initialized with {len(self.outcomes)} historical trades")

    def load_history(self):
        """Load trade history from disk"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    for trade_dict in data:
                        outcome = TradeOutcome(
                            symbol=trade_dict['symbol'],
                            setup_type=trade_dict['setup_type'],
                            entry_signal=trade_dict['entry_signal'],
                            entry_price=trade_dict['entry_price'],
                            exit_price=trade_dict['exit_price'],
                            profit=trade_dict['profit'],
                            profit_pct=trade_dict['profit_pct'],
                            duration_minutes=trade_dict['duration_minutes'],
                            win=trade_dict['win'],
                            market_regime=trade_dict['market_regime'],
                            initial_confidence=trade_dict['initial_confidence'],
                            timestamp=datetime.fromisoformat(trade_dict['timestamp'])
                        )
                        self.outcomes.append(outcome)
                logger.info(f"Loaded {len(self.outcomes)} trades from history")
            except Exception as e:
                logger.error(f"Error loading trade history: {e}")

    def save_history(self):
        """Save trade history to disk"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump([o.to_dict() for o in self.outcomes], f, indent=2)
            logger.debug(f"Saved {len(self.outcomes)} trades to history")
        except Exception as e:
            logger.error(f"Error saving trade history: {e}")

    def record_trade(self, outcome: TradeOutcome):
        """Record a completed trade"""
        self.outcomes.append(outcome)
        self.save_history()
        logger.info(f"Recorded trade: {outcome.setup_type} {outcome.entry_signal} ${outcome.profit:+.2f}")

    def get_setup_stats(self, setup_type: str) -> Dict:
        """Get statistics for a specific setup type"""
        matching = [o for o in self.outcomes if o.setup_type == setup_type]

        if not matching:
            return {
                'setup_type': setup_type,
                'total_trades': 0,
                'win_rate': 0,
                'avg_profit': 0,
                'avg_duration': 0,
                'confidence_multiplier': 1.0
            }

        wins = sum(1 for o in matching if o.win)
        win_rate = (wins / len(matching)) * 100
        avg_profit = np.mean([o.profit for o in matching])
        avg_duration = np.mean([o.duration_minutes for o in matching])

        # Calculate confidence multiplier based on win rate
        # Good setups (>55% win rate) get bonus, poor (<45%) get penalty
        if win_rate > 65:
            confidence_mult = 1.3  # Boost by 30%
        elif win_rate > 55:
            confidence_mult = 1.15  # Boost by 15%
        elif win_rate > 45:
            confidence_mult = 1.0   # No change
        elif win_rate > 35:
            confidence_mult = 0.8   # Reduce by 20%
        else:
            confidence_mult = 0.5   # Reduce by 50%

        return {
            'setup_type': setup_type,
            'total_trades': len(matching),
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'avg_duration': avg_duration,
            'confidence_multiplier': confidence_mult
        }

    def get_symbol_stats(self, symbol: str) -> Dict:
        """Get statistics for a specific symbol"""
        matching = [o for o in self.outcomes if o.symbol == symbol]

        if not matching:
            return {
                'symbol': symbol,
                'total_trades': 0,
                'win_rate': 0,
                'avg_profit': 0,
                'profitability': 'UNKNOWN'
            }

        wins = sum(1 for o in matching if o.win)
        win_rate = (wins / len(matching)) * 100
        avg_profit = np.mean([o.profit for o in matching])
        total_profit = sum(o.profit for o in matching)

        # Profitability rating
        if total_profit > avg_profit * len(matching) * 0.5:
            profitability = 'PROFITABLE'
        elif total_profit < -avg_profit * len(matching) * 0.3:
            profitability = 'LOSING'
        else:
            profitability = 'NEUTRAL'

        return {
            'symbol': symbol,
            'total_trades': len(matching),
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'total_profit': total_profit,
            'profitability': profitability
        }

    def get_regime_stats(self, regime: str) -> Dict:
        """Get statistics for trades in specific market regime"""
        matching = [o for o in self.outcomes if o.market_regime == regime]

        if not matching:
            return {
                'regime': regime,
                'total_trades': 0,
                'win_rate': 0,
                'avg_profit': 0
            }

        wins = sum(1 for o in matching if o.win)
        win_rate = (wins / len(matching)) * 100
        avg_profit = np.mean([o.profit for o in matching])

        return {
            'regime': regime,
            'total_trades': len(matching),
            'win_rate': win_rate,
            'avg_profit': avg_profit
        }

    def get_confidence_adjustment(self, setup_type: str, symbol: str, regime: str) -> float:
        """Get confidence adjustment based on historical performance"""
        multiplier = 1.0

        # Setup type performance
        setup_stats = self.get_setup_stats(setup_type)
        multiplier *= setup_stats['confidence_multiplier']

        # Symbol performance (lighter weight)
        symbol_stats = self.get_symbol_stats(symbol)
        if symbol_stats['profitability'] == 'PROFITABLE':
            multiplier *= 1.1
        elif symbol_stats['profitability'] == 'LOSING':
            multiplier *= 0.9

        # Regime performance (lighter weight)
        regime_stats = self.get_regime_stats(regime)
        if regime_stats['win_rate'] > 60:
            multiplier *= 1.05
        elif regime_stats['win_rate'] < 40:
            multiplier *= 0.95

        # Clamp between 0.5 and 1.5
        return max(0.5, min(1.5, multiplier))

    def should_skip_setup(self, setup_type: str, threshold: float = 0.35) -> bool:
        """Check if a setup type should be skipped due to poor performance"""
        stats = self.get_setup_stats(setup_type)

        # Skip if we have enough data and win rate is very low
        if stats['total_trades'] >= 10 and stats['win_rate'] < (threshold * 100):
            logger.warning(f"Skipping {setup_type}: win rate {stats['win_rate']:.1f}% too low")
            return True

        return False

    def get_latest_outcomes(self, hours: int = 24) -> List[TradeOutcome]:
        """Get trades from last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [o for o in self.outcomes if o.timestamp > cutoff]

    def get_daily_summary(self) -> Dict:
        """Get summary of today's trades"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_trades = [o for o in self.outcomes if o.timestamp > today_start]

        if not today_trades:
            return {
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'total_profit': 0
            }

        wins = sum(1 for o in today_trades if o.win)
        losses = len(today_trades) - wins
        total_profit = sum(o.profit for o in today_trades)

        return {
            'trades': len(today_trades),
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / len(today_trades)) * 100,
            'total_profit': total_profit
        }

    def print_analytics(self):
        """Print trading analytics"""
        logger.info("\n" + "="*60)
        logger.info("TRADING ANALYTICS")
        logger.info("="*60)

        if not self.outcomes:
            logger.info("No trade history available")
            return

        # Overall stats
        total_trades = len(self.outcomes)
        total_wins = sum(1 for o in self.outcomes if o.win)
        total_profit = sum(o.profit for o in self.outcomes)
        avg_profit = np.mean([o.profit for o in self.outcomes])

        logger.info(f"\nOVERALL")
        logger.info(f"  Total Trades: {total_trades}")
        logger.info(f"  Win Rate: {(total_wins/total_trades)*100:.1f}%")
        logger.info(f"  Total Profit: ${total_profit:+.2f}")
        logger.info(f"  Avg Profit: ${avg_profit:+.2f}")

        # Setup types
        logger.info(f"\nBY SETUP TYPE")
        setup_types = set(o.setup_type for o in self.outcomes)
        for setup in sorted(setup_types):
            stats = self.get_setup_stats(setup)
            logger.info(f"  {setup}: {stats['total_trades']} trades, "
                       f"{stats['win_rate']:.1f}% win rate, "
                       f"${stats['avg_profit']:+.2f} avg")

        # Symbols
        logger.info(f"\nBY SYMBOL")
        symbols = set(o.symbol for o in self.outcomes)
        for symbol in sorted(symbols):
            stats = self.get_symbol_stats(symbol)
            logger.info(f"  {symbol}: {stats['total_trades']} trades, "
                       f"{stats['profitability']}, "
                       f"${stats['total_profit']:+.2f} total")

        # Daily summary
        daily = self.get_daily_summary()
        logger.info(f"\nTODAY")
        logger.info(f"  Trades: {daily['trades']}")
        logger.info(f"  Win Rate: {daily['win_rate']:.1f}%")
        logger.info(f"  Profit: ${daily['total_profit']:+.2f}")

        logger.info("="*60 + "\n")


# Global analyzer instance
_analyzer = None


def get_analyzer() -> PatternAnalyzer:
    """Get or create global analyzer"""
    global _analyzer
    if _analyzer is None:
        _analyzer = PatternAnalyzer()
    return _analyzer
