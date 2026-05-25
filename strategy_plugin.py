"""
STRATEGY PLUGIN ARCHITECTURE - Modular strategy system
Allows independent strategy implementation without modifying core trader
Each strategy is a plugin that returns standardized SignalOutput
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    """Confidence in the signal"""
    STRONG = "STRONG"      # High conviction setup
    MODERATE = "MODERATE"  # Decent setup
    WEAK = "WEAK"          # Low conviction, use for confirmation only


@dataclass
class SignalOutput:
    """Standard output from any strategy plugin"""
    action: str                    # 'BUY', 'SELL', or 'HOLD'
    confidence: float              # 0-100
    entry_price: float            # Suggested entry level
    stop_loss: float              # Stop loss level
    take_profit: float            # Take profit level
    signal_strength: SignalStrength  # STRONG/MODERATE/WEAK
    reasoning: str                # Explanation of the signal
    technical_levels: Dict        # Support/resistance/pivot data
    setup_type: str               # e.g., 'RSI_EXTREME', 'TREND_REVERSAL', 'MOMENTUM'


class StrategyPlugin(ABC):
    """Base class for all trading strategy plugins"""

    def __init__(self, name: str, enabled: bool = True):
        """
        Args:
            name: Unique strategy identifier
            enabled: Whether this strategy is active
        """
        self.name = name
        self.enabled = enabled
        logger.info(f"Strategy '{name}' initialized (enabled={enabled})")

    @abstractmethod
    def analyze(self, symbol: str, indicators: Dict, account_info: Dict) -> SignalOutput:
        """
        Analyze market and generate signal

        Args:
            symbol: Trading symbol
            indicators: Dict with technical indicators (trend, rsi, macd, etc.)
            account_info: Account information for position sizing context

        Returns:
            SignalOutput with trade signal or HOLD
        """
        pass

    def validate_signal(self, signal: SignalOutput) -> bool:
        """Validate signal before returning"""
        # Check required fields
        if not signal.action in ['BUY', 'SELL', 'HOLD']:
            logger.error(f"Invalid action: {signal.action}")
            return False

        if signal.action in ['BUY', 'SELL']:
            if signal.confidence < 0 or signal.confidence > 100:
                logger.error(f"Invalid confidence: {signal.confidence}")
                return False

            if signal.entry_price <= 0:
                logger.error(f"Invalid entry price: {signal.entry_price}")
                return False

            if signal.action == 'BUY' and signal.stop_loss >= signal.entry_price:
                logger.error(f"BUY SL must be below entry")
                return False

            if signal.action == 'SELL' and signal.stop_loss <= signal.entry_price:
                logger.error(f"SELL SL must be above entry")
                return False

        return True


class RSIExtremePlugin(StrategyPlugin):
    """RSI Overbought/Oversold reversal strategy"""

    def __init__(self):
        super().__init__("RSI_Extreme", enabled=True)

    def analyze(self, symbol: str, indicators: Dict, account_info: Dict) -> SignalOutput:
        """Check for RSI extreme levels"""
        rsi = indicators.get('rsi', 50)
        atr = indicators.get('atr', 0)
        trend = indicators.get('trend', 'NEUTRAL')
        entry = indicators.get('price', 0)
        support = indicators.get('support', 0)
        resistance = indicators.get('resistance', 0)

        # RSI overbought
        if rsi > 80 and trend not in ['STRONG_UP']:
            signal = SignalOutput(
                action='SELL',
                confidence=min(100, 40 + (rsi - 80) * 2),
                entry_price=entry,
                stop_loss=entry + (atr * 1.5),
                take_profit=entry - (atr * 2),
                signal_strength=SignalStrength.MODERATE,
                reasoning=f"RSI overbought at {rsi:.0f} suggests pullback",
                technical_levels={'support': support, 'resistance': resistance},
                setup_type='RSI_EXTREME'
            )
            return signal if self.validate_signal(signal) else self._hold()

        # RSI oversold
        if rsi < 20 and trend not in ['STRONG_DOWN']:
            signal = SignalOutput(
                action='BUY',
                confidence=min(100, 40 + (20 - rsi) * 2),
                entry_price=entry,
                stop_loss=entry - (atr * 1.5),
                take_profit=entry + (atr * 2),
                signal_strength=SignalStrength.MODERATE,
                reasoning=f"RSI oversold at {rsi:.0f} suggests bounce",
                technical_levels={'support': support, 'resistance': resistance},
                setup_type='RSI_EXTREME'
            )
            return signal if self.validate_signal(signal) else self._hold()

        return self._hold()

    def _hold(self):
        return SignalOutput(
            action='HOLD',
            confidence=0,
            entry_price=0,
            stop_loss=0,
            take_profit=0,
            signal_strength=SignalStrength.WEAK,
            reasoning="No RSI extreme signal",
            technical_levels={},
            setup_type='NEUTRAL'
        )


class TrendReversalPlugin(StrategyPlugin):
    """Trend reversal strategy using moving average crossovers"""

    def __init__(self):
        super().__init__("Trend_Reversal", enabled=True)

    def analyze(self, symbol: str, indicators: Dict, account_info: Dict) -> SignalOutput:
        """Check for trend reversals"""
        trend = indicators.get('trend', 'NEUTRAL')
        rsi = indicators.get('rsi', 50)
        atr = indicators.get('atr', 0)
        entry = indicators.get('price', 0)
        support = indicators.get('support', 0)
        resistance = indicators.get('resistance', 0)

        # Downtrend reversal
        if trend in ['WEAK_DOWN'] and rsi < 30:
            signal = SignalOutput(
                action='BUY',
                confidence=65,
                entry_price=entry,
                stop_loss=entry - (atr * 2),
                take_profit=entry + (atr * 3),
                signal_strength=SignalStrength.MODERATE,
                reasoning=f"Weak downtrend with oversold RSI suggests reversal",
                technical_levels={'support': support, 'resistance': resistance},
                setup_type='TREND_REVERSAL'
            )
            return signal if self.validate_signal(signal) else self._hold()

        # Uptrend reversal
        if trend in ['WEAK_UP'] and rsi > 70:
            signal = SignalOutput(
                action='SELL',
                confidence=65,
                entry_price=entry,
                stop_loss=entry + (atr * 2),
                take_profit=entry - (atr * 3),
                signal_strength=SignalStrength.MODERATE,
                reasoning=f"Weak uptrend with overbought RSI suggests reversal",
                technical_levels={'support': support, 'resistance': resistance},
                setup_type='TREND_REVERSAL'
            )
            return signal if self.validate_signal(signal) else self._hold()

        return self._hold()

    def _hold(self):
        return SignalOutput(
            action='HOLD',
            confidence=0,
            entry_price=0,
            stop_loss=0,
            take_profit=0,
            signal_strength=SignalStrength.WEAK,
            reasoning="No trend reversal signal",
            technical_levels={},
            setup_type='NEUTRAL'
        )


class LevelBouncePlugin(StrategyPlugin):
    """Support/Resistance bounce strategy"""

    def __init__(self):
        super().__init__("Level_Bounce", enabled=True)

    def analyze(self, symbol: str, indicators: Dict, account_info: Dict) -> SignalOutput:
        """Check for bounces off support/resistance"""
        entry = indicators.get('price', 0)
        support = indicators.get('support', 0)
        resistance = indicators.get('resistance', 0)
        atr = indicators.get('atr', 0)
        rsi = indicators.get('rsi', 50)
        trend = indicators.get('trend', 'NEUTRAL')

        # Distance to support/resistance
        dist_to_support = (entry - support) / atr if atr > 0 else 0
        dist_to_resistance = (resistance - entry) / atr if atr > 0 else 0

        # Bounce off support
        if dist_to_support < 1.5 and trend in ['WEAK_DOWN', 'NEUTRAL'] and rsi > 30:
            signal = SignalOutput(
                action='BUY',
                confidence=60,
                entry_price=entry,
                stop_loss=support - (atr * 0.5),
                take_profit=resistance,
                signal_strength=SignalStrength.MODERATE,
                reasoning=f"Price near support ({support:.4f}), ready to bounce",
                technical_levels={'support': support, 'resistance': resistance},
                setup_type='LEVEL_BOUNCE'
            )
            return signal if self.validate_signal(signal) else self._hold()

        # Bounce off resistance
        if dist_to_resistance < 1.5 and trend in ['WEAK_UP', 'NEUTRAL'] and rsi < 70:
            signal = SignalOutput(
                action='SELL',
                confidence=60,
                entry_price=entry,
                stop_loss=resistance + (atr * 0.5),
                take_profit=support,
                signal_strength=SignalStrength.MODERATE,
                reasoning=f"Price near resistance ({resistance:.4f}), ready to pullback",
                technical_levels={'support': support, 'resistance': resistance},
                setup_type='LEVEL_BOUNCE'
            )
            return signal if self.validate_signal(signal) else self._hold()

        return self._hold()

    def _hold(self):
        return SignalOutput(
            action='HOLD',
            confidence=0,
            entry_price=0,
            stop_loss=0,
            take_profit=0,
            signal_strength=SignalStrength.WEAK,
            reasoning="No level bounce signal",
            technical_levels={},
            setup_type='NEUTRAL'
        )


class StrategyPluginManager:
    """Manages all active strategy plugins"""

    def __init__(self):
        """Initialize with built-in strategies"""
        self.strategies: Dict[str, StrategyPlugin] = {}
        self.register_default_strategies()
        logger.info(f"Strategy Manager initialized with {len(self.strategies)} plugins")

    def register_default_strategies(self):
        """Register built-in strategy plugins"""
        self.register(RSIExtremePlugin())
        self.register(TrendReversalPlugin())
        self.register(LevelBouncePlugin())

    def register(self, strategy: StrategyPlugin):
        """Register a new strategy plugin"""
        self.strategies[strategy.name] = strategy
        logger.info(f"Registered strategy: {strategy.name}")

    def unregister(self, name: str):
        """Unregister a strategy"""
        if name in self.strategies:
            del self.strategies[name]
            logger.info(f"Unregistered strategy: {name}")

    def get_strategy(self, name: str) -> Optional[StrategyPlugin]:
        """Get a specific strategy"""
        return self.strategies.get(name)

    def analyze_with_all(self, symbol: str, indicators: Dict, account_info: Dict) -> Dict[str, SignalOutput]:
        """Run all enabled strategies and return their signals"""
        signals = {}

        for name, strategy in self.strategies.items():
            if not strategy.enabled:
                continue

            try:
                signal = strategy.analyze(symbol, indicators, account_info)
                signals[name] = signal
                logger.debug(f"{name}: {signal.action} (confidence {signal.confidence}%)")
            except Exception as e:
                logger.error(f"Error in {name}: {e}")
                continue

        return signals

    def enable_strategy(self, name: str):
        """Enable a strategy"""
        if name in self.strategies:
            self.strategies[name].enabled = True
            logger.info(f"Enabled strategy: {name}")

    def disable_strategy(self, name: str):
        """Disable a strategy"""
        if name in self.strategies:
            self.strategies[name].enabled = False
            logger.info(f"Disabled strategy: {name}")

    def list_strategies(self) -> Dict[str, bool]:
        """List all strategies and their enabled status"""
        return {name: strategy.enabled for name, strategy in self.strategies.items()}
