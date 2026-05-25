"""
MULTI-TIMEFRAME ANALYZER - Validate signals across timeframes
Prevents trades that contradict higher timeframe trends
H1 trend + M30 trend + M15 trend must align for execution
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional, List
import MetaTrader5 as mt5
import numpy as np

logger = logging.getLogger(__name__)


class TimeframeAlignment(Enum):
    """Alignment between timeframes"""
    STRONG_ALIGN = "STRONG_ALIGN"       # All 3 timeframes agree (H1, M30, M15)
    WEAK_ALIGN = "WEAK_ALIGN"           # 2/3 timeframes agree
    NEUTRAL = "NEUTRAL"                 # Mixed/conflicting signals
    CONFLICTED = "CONFLICTED"           # Signals contradict (e.g., H1 up, M30 down)


@dataclass
class TimeframeAnalysis:
    """Analysis for a single timeframe"""
    timeframe: str  # 'H1', 'M30', 'M15'
    trend: str  # 'STRONG_UP', 'WEAK_UP', 'NEUTRAL', 'WEAK_DOWN', 'STRONG_DOWN'
    rsi: float  # 0-100
    macd_signal: str  # 'UP', 'DOWN', 'NEUTRAL'
    support: float
    resistance: float
    atr: float
    close_price: float


@dataclass
class MultiTimeframeDecision:
    """Final multi-timeframe validation result"""
    symbol: str
    signal_action: str  # The proposed BUY/SELL from H1
    alignment: TimeframeAlignment
    confidence_adjustment: float  # 0-1.0 multiplier to apply to original confidence
    reasoning: str
    timeframe_analyses: Dict[str, TimeframeAnalysis]
    should_proceed: bool  # True if signal is confirmed by multi-timeframe analysis


class MultiTimeframeAnalyzer:
    """Analyzes signals across H1, M30, and M15 timeframes"""

    def __init__(self):
        """Initialize the analyzer"""
        self.alignment_thresholds = {
            'STRONG_ALIGN': {'proceed': True, 'confidence_mult': 1.2},
            'WEAK_ALIGN': {'proceed': True, 'confidence_mult': 1.0},
            'NEUTRAL': {'proceed': True, 'confidence_mult': 0.8},
            'CONFLICTED': {'proceed': False, 'confidence_mult': 0.5}
        }
        logger.info("Multi-Timeframe Analyzer initialized")

    def analyze_signal(self, symbol: str, signal_action: str,
                      h1_rates: np.ndarray, h1_indicators: Dict) -> MultiTimeframeDecision:
        """
        Validate H1 signal across M30 and M15 timeframes

        Args:
            symbol: Trading symbol (e.g., 'XAUUSD.s')
            signal_action: 'BUY' or 'SELL' from H1 analysis
            h1_rates: H1 candle data (from mt5.copy_rates_from_pos)
            h1_indicators: H1 indicators dict with 'trend', 'rsi', 'macd_signal'

        Returns:
            MultiTimeframeDecision with alignment verdict and confidence adjustment
        """
        # Get M30 and M15 rates
        m30_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M30, 0, 50)
        m15_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 50)

        if m30_rates is None or m15_rates is None:
            logger.warning(f"Could not get M30/M15 data for {symbol} - skipping multi-timeframe check")
            return MultiTimeframeDecision(
                symbol=symbol,
                signal_action=signal_action,
                alignment=TimeframeAlignment.NEUTRAL,
                confidence_adjustment=1.0,
                reasoning="Could not retrieve M30/M15 data",
                timeframe_analyses={},
                should_proceed=True  # Proceed anyway if data unavailable
            )

        # Analyze all timeframes
        h1_analysis = self._analyze_timeframe(symbol, 'H1', h1_rates, h1_indicators)
        m30_analysis = self._analyze_timeframe(symbol, 'M30', m30_rates)
        m15_analysis = self._analyze_timeframe(symbol, 'M15', m15_rates)

        # Determine alignment
        alignment, reasoning = self._determine_alignment(
            signal_action, h1_analysis, m30_analysis, m15_analysis
        )

        # Get confidence adjustment
        threshold_info = self.alignment_thresholds.get(alignment.value, {'proceed': True, 'confidence_mult': 0.8})
        confidence_mult = threshold_info['confidence_mult']
        should_proceed = threshold_info['proceed']

        return MultiTimeframeDecision(
            symbol=symbol,
            signal_action=signal_action,
            alignment=alignment,
            confidence_adjustment=confidence_mult,
            reasoning=reasoning,
            timeframe_analyses={
                'H1': h1_analysis,
                'M30': m30_analysis,
                'M15': m15_analysis
            },
            should_proceed=should_proceed
        )

    def _analyze_timeframe(self, symbol: str, timeframe: str,
                          rates: np.ndarray, indicators: Dict = None) -> TimeframeAnalysis:
        """Analyze a single timeframe"""
        if rates is None or len(rates) < 2:
            return TimeframeAnalysis(
                timeframe=timeframe,
                trend='NEUTRAL',
                rsi=50,
                macd_signal='NEUTRAL',
                support=0,
                resistance=0,
                atr=0,
                close_price=0
            )

        # Extract OHLC data
        closes = rates['close']
        highs = rates['high']
        lows = rates['low']
        current_close = closes[-1]
        prev_close = closes[-2] if len(closes) > 1 else closes[-1]

        # Calculate simple trend
        sma_fast = np.mean(closes[-5:]) if len(closes) >= 5 else np.mean(closes)
        sma_slow = np.mean(closes[-20:]) if len(closes) >= 20 else np.mean(closes)

        if sma_fast > sma_slow:
            trend = 'STRONG_UP' if (sma_fast - sma_slow) / sma_slow > 0.005 else 'WEAK_UP'
        elif sma_fast < sma_slow:
            trend = 'STRONG_DOWN' if (sma_slow - sma_fast) / sma_slow > 0.005 else 'WEAK_DOWN'
        else:
            trend = 'NEUTRAL'

        # Calculate RSI
        rsi = self._calculate_rsi(closes[-14:]) if len(closes) >= 14 else 50

        # Calculate MACD signal
        macd_signal = self._calculate_macd_signal(closes[-26:]) if len(closes) >= 26 else 'NEUTRAL'

        # Support/Resistance (last 20 candles)
        recent = closes[-20:] if len(closes) >= 20 else closes
        support = np.min(recent)
        resistance = np.max(recent)

        # ATR (Average True Range)
        atr = self._calculate_atr(highs[-14:], lows[-14:], closes[-14:]) if len(closes) >= 14 else 0

        # Use provided indicators if available (for H1)
        if indicators:
            rsi = indicators.get('rsi', rsi)
            macd_signal = indicators.get('macd_signal', macd_signal)
            trend = indicators.get('trend', trend)

        return TimeframeAnalysis(
            timeframe=timeframe,
            trend=trend,
            rsi=rsi,
            macd_signal=macd_signal,
            support=support,
            resistance=resistance,
            atr=atr,
            close_price=current_close
        )

    def _calculate_rsi(self, closes: np.ndarray, period: int = 14) -> float:
        """Calculate RSI"""
        if len(closes) < period:
            return 50

        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100 if avg_gain > 0 else 50

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    def _calculate_macd_signal(self, closes: np.ndarray) -> str:
        """Calculate MACD signal"""
        if len(closes) < 26:
            return 'NEUTRAL'

        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd_line = ema12 - ema26

        signal_line = self._ema(np.array([macd_line]), 9) if len(closes) >= 26 else macd_line
        histogram = macd_line - signal_line

        if histogram > 0:
            return 'UP'
        elif histogram < 0:
            return 'DOWN'
        else:
            return 'NEUTRAL'

    def _ema(self, data: np.ndarray, period: int) -> float:
        """Calculate EMA for last value"""
        if len(data) < period:
            return np.mean(data)

        multiplier = 2 / (period + 1)
        ema = np.mean(data[:period])

        for i in range(period, len(data)):
            ema = (data[i] - ema) * multiplier + ema

        return ema

    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray) -> float:
        """Calculate ATR"""
        if len(highs) < 1 or len(lows) < 1 or len(closes) < 1:
            return 0

        tr_values = []
        for i in range(len(highs)):
            h = highs[i]
            l = lows[i]
            c = closes[i - 1] if i > 0 else closes[i]

            tr = max(h - l, abs(h - c), abs(l - c))
            tr_values.append(tr)

        return float(np.mean(tr_values[-14:]))

    def _determine_alignment(self, signal_action: str,
                            h1: TimeframeAnalysis,
                            m30: TimeframeAnalysis,
                            m15: TimeframeAnalysis) -> tuple:
        """Determine how well timeframes align with the signal"""

        # Map trend to direction
        def trend_to_direction(trend: str) -> str:
            if 'UP' in trend:
                return 'UP'
            elif 'DOWN' in trend:
                return 'DOWN'
            else:
                return 'NEUTRAL'

        h1_dir = trend_to_direction(h1.trend)
        m30_dir = trend_to_direction(m30.trend)
        m15_dir = trend_to_direction(m15.trend)
        signal_dir = 'UP' if signal_action == 'BUY' else 'DOWN'

        # Count agreements
        agreement_count = 0
        reasoning_parts = []

        # H1 is always aligned (it's the signal source)
        agreement_count += 1
        reasoning_parts.append(f"H1: {h1.trend} (RSI {h1.rsi:.0f})")

        # M30 alignment
        if m30_dir == signal_dir or m30_dir == 'NEUTRAL':
            agreement_count += 1
            reasoning_parts.append(f"M30: {m30.trend} ✓")
        else:
            reasoning_parts.append(f"M30: {m30.trend} ✗ (conflicts)")

        # M15 alignment
        if m15_dir == signal_dir or m15_dir == 'NEUTRAL':
            agreement_count += 1
            reasoning_parts.append(f"M15: {m15.trend} ✓")
        else:
            reasoning_parts.append(f"M15: {m15.trend} ✗ (conflicts)")

        # Determine alignment level
        if agreement_count == 3:
            alignment = TimeframeAlignment.STRONG_ALIGN
            reasoning = "All timeframes aligned: " + " | ".join(reasoning_parts)
        elif agreement_count == 2:
            alignment = TimeframeAlignment.WEAK_ALIGN
            reasoning = "Two timeframes aligned: " + " | ".join(reasoning_parts)
        elif m30_dir == signal_dir and m15_dir != signal_dir:
            alignment = TimeframeAlignment.WEAK_ALIGN
            reasoning = "Higher timeframe (M30) aligned: " + " | ".join(reasoning_parts)
        elif agreement_count == 1:
            # Check if contradictions are severe
            if (m30_dir == 'UP' and m15_dir == 'DOWN') or (m30_dir == 'DOWN' and m15_dir == 'UP'):
                alignment = TimeframeAlignment.CONFLICTED
                reasoning = "Timeframes in conflict: " + " | ".join(reasoning_parts)
            else:
                alignment = TimeframeAlignment.NEUTRAL
                reasoning = "Mixed timeframe signals: " + " | ".join(reasoning_parts)
        else:
            alignment = TimeframeAlignment.CONFLICTED
            reasoning = "Timeframes contradict signal: " + " | ".join(reasoning_parts)

        return alignment, reasoning

    def log_analysis(self, decision: MultiTimeframeDecision):
        """Log multi-timeframe analysis"""
        emoji = "✅" if decision.should_proceed else "🚫"
        logger.info(
            f"{emoji} MTF {decision.symbol} | Signal: {decision.signal_action} | "
            f"Alignment: {decision.alignment.value} | "
            f"Confidence: x{decision.confidence_adjustment:.2f} | "
            f"{decision.reasoning}"
        )
