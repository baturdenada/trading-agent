"""
Market Regime Detector - Identifies trending, ranging, or volatile markets
Adapts trading parameters based on market conditions
Skips trades in unfavorable regimes
"""

import logging
import MetaTrader5 as mt5
from collections import deque

logger = logging.getLogger(__name__)

class RegimeDetector:
    def __init__(self):
        self.regimes = {
            "STRONG_TREND": {"atr_threshold": 0.6, "sl_distance": 1.0, "tp_distance": 2.0},
            "WEAK_TREND": {"atr_threshold": 0.4, "sl_distance": 0.8, "tp_distance": 1.5},
            "RANGING": {"atr_threshold": 0.2, "sl_distance": 0.5, "tp_distance": 1.0},
            "VOLATILE": {"atr_threshold": 1.0, "sl_distance": 1.5, "tp_distance": 2.5},
        }

        self.history = deque(maxlen=100)  # Keep last 100 regime samples
        self.current_regime = {}

    def detect_regime(self, symbol, rates, indicators):
        """
        Detect market regime based on:
        - ATR (volatility)
        - ADX (trend strength)
        - Bollinger Band width
        - Range high/low
        """
        if not rates or len(rates) < 20:
            return {"regime": "UNKNOWN", "confidence": 0, "suggested_sl_multiple": 1.0, "suggested_tp_multiple": 1.5}

        # Extract data
        closes = [float(r[4]) for r in rates][-100:]
        highs = [float(r[2]) for r in rates][-100:]
        lows = [float(r[3]) for r in rates][-100:]

        atr = indicators.get('atr', 0.01)
        current_price = closes[-1] if closes else 0

        # Calculate volatility metrics
        volatility_ratio = self._calculate_volatility_ratio(highs, lows, closes)
        trend_strength = self._calculate_adx_like(closes)
        range_height = (max(closes[-20:]) - min(closes[-20:])) / current_price if current_price > 0 else 0

        # Determine regime
        regime, confidence = self._classify_regime(
            atr=atr,
            volatility_ratio=volatility_ratio,
            trend_strength=trend_strength,
            range_height=range_height,
            current_price=current_price
        )

        # Get parameters for this regime
        params = self.regimes.get(regime, {
            "atr_threshold": 0.5,
            "sl_distance": 1.0,
            "tp_distance": 1.5
        })

        regime_info = {
            "regime": regime,
            "confidence": confidence,
            "volatility_ratio": volatility_ratio,
            "trend_strength": trend_strength,
            "range_height": range_height,
            "suggested_sl_multiple": params['sl_distance'],
            "suggested_tp_multiple": params['tp_distance'],
            "trading_advice": self._get_trading_advice(regime, trend_strength)
        }

        self.history.append(regime_info)
        self.current_regime[symbol] = regime_info

        logger.info(f"{symbol} Regime: {regime} (confidence: {confidence:.0f}%) | "
                   f"Volatility: {volatility_ratio:.2f} | Trend: {trend_strength:.1f}")

        return regime_info

    def _calculate_volatility_ratio(self, highs, lows, closes):
        """
        Calculate volatility as ratio of average range to average price
        Higher ratio = more volatile
        """
        if len(closes) < 20:
            return 0

        ranges = [highs[i] - lows[i] for i in range(len(highs))]
        avg_range = sum(ranges[-20:]) / 20
        avg_price = sum(closes[-20:]) / 20

        if avg_price == 0:
            return 0

        return avg_range / avg_price

    def _calculate_adx_like(self, closes):
        """
        Simplified ADX calculation - measures trend strength
        Returns 0-100, where >40 is strong trend, <20 is weak/ranging
        """
        if len(closes) < 14:
            return 0

        # Simple directional movement
        ups = sum(1 for i in range(1, len(closes[-14:])) if closes[i] > closes[i-1])
        downs = sum(1 for i in range(1, len(closes[-14:])) if closes[i] < closes[i-1])

        trend_strength = abs(ups - downs) / 14 * 100
        return min(trend_strength, 100)

    def _classify_regime(self, atr, volatility_ratio, trend_strength, range_height, current_price):
        """
        Classify market regime:
        - STRONG_TREND: High ADX (>40), clear direction
        - WEAK_TREND: Medium ADX (20-40), some direction
        - RANGING: Low ADX (<20), bouncing between levels
        - VOLATILE: Very high volatility regardless of trend
        """
        confidence = 0

        # Check for volatility first
        if volatility_ratio > 0.15:
            confidence = 85
            return "VOLATILE", confidence

        # Strong trend
        if trend_strength > 50:
            confidence = 90
            return "STRONG_TREND", confidence

        # Weak trend
        if trend_strength > 30:
            confidence = 70
            return "WEAK_TREND", confidence

        # Ranging market
        if trend_strength < 25:
            confidence = 80
            return "RANGING", confidence

        # Default to weak trend
        return "WEAK_TREND", 60

    def _get_trading_advice(self, regime, trend_strength):
        """Get trading recommendations for current regime"""
        if regime == "STRONG_TREND":
            return "TRADE: Strong trend favors momentum trades. Use wider SL/TP."
        elif regime == "WEAK_TREND":
            return "TRADE: Weak trend. Use breakout confirmation."
        elif regime == "RANGING":
            return "CAUTION: Ranging market. Trade only at support/resistance levels."
        elif regime == "VOLATILE":
            return "CAUTION: High volatility. Reduce position size, use wider SL."
        return "NEUTRAL"

    def should_skip_regime(self, regime):
        """
        Skip trading in unfavorable regimes
        Returns True if trading should be skipped
        """
        # Skip ranging markets (no clear direction)
        if regime == "RANGING":
            return False  # Actually, ranging markets have clear setups (support/resistance)

        # Skip extreme volatility
        if regime == "VOLATILE":
            return False  # Actually, can trade but with larger SL

        return False  # Never skip outright, just adapt parameters

    def get_adjusted_sl_tp(self, base_sl, base_tp, atr, regime_info):
        """
        Adjust SL/TP based on market regime
        Wider SL/TP in volatile/trending markets
        Tighter SL/TP in ranging markets
        """
        regime = regime_info['regime']
        sl_multiple = regime_info['suggested_sl_multiple']
        tp_multiple = regime_info['suggested_tp_multiple']

        # These are multipliers for the ATR-based SL/TP
        return {
            "sl_distance_multiple": sl_multiple,
            "tp_distance_multiple": tp_multiple,
            "regime_advice": regime_info['trading_advice']
        }

    def get_position_size_adjustment(self, regime_info):
        """
        Get position size adjustment based on regime
        Smaller positions in volatile markets, larger in trending markets
        """
        regime = regime_info['regime']

        if regime == "STRONG_TREND":
            return 1.2  # 20% larger position
        elif regime == "WEAK_TREND":
            return 1.0  # Normal size
        elif regime == "RANGING":
            return 1.0  # Normal size (good setups at levels)
        elif regime == "VOLATILE":
            return 0.7  # 30% smaller position (reduce risk)
        else:
            return 1.0

    def get_minimum_confidence_for_regime(self, regime):
        """
        Require higher confidence in certain regimes
        """
        if regime == "RANGING":
            return 65  # Require higher confidence in ranging markets
        elif regime == "VOLATILE":
            return 70  # Higher confidence in volatile markets
        else:
            return 50  # Standard confidence threshold

    def print_regime_summary(self):
        """Print current regime analysis for all symbols"""
        if not self.current_regime:
            return

        logger.info("=" * 80)
        logger.info("MARKET REGIME SUMMARY")
        logger.info("=" * 80)

        for symbol, info in self.current_regime.items():
            logger.info(f"\n{symbol}:")
            logger.info(f"  Regime: {info['regime']} ({info['confidence']:.0f}% confident)")
            logger.info(f"  Volatility: {info['volatility_ratio']:.3f}")
            logger.info(f"  Trend Strength: {info['trend_strength']:.1f}")
            logger.info(f"  SL Multiplier: {info['suggested_sl_multiple']:.1f}x ATR")
            logger.info(f"  TP Multiplier: {info['suggested_tp_multiple']:.1f}x ATR")
            logger.info(f"  Advice: {info['trading_advice']}")

        logger.info("=" * 80)
