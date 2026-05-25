"""
TRADE STATE MACHINE - Professional trade execution with confirmation phases
Prevents false signals with multi-phase entry validation
"""

import logging
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TradeState(Enum):
    """Trade execution state phases"""
    SCANNING = "SCANNING"           # Initial signal detection
    ARMED = "ARMED"                 # Setup detected, waiting for confirmation
    CONFIRMATION = "CONFIRMATION"   # Pullback/retracement observed
    ENTRY_WINDOW = "ENTRY_WINDOW"   # Breakout zone active
    ENTERED = "ENTERED"             # Trade executed
    CLOSED = "CLOSED"               # Trade closed


@dataclass
class TradeSetup:
    """Represents a trade setup in progress"""
    symbol: str
    action: str  # BUY or SELL
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    reasoning: str
    regime: str

    # State tracking
    state: TradeState = TradeState.SCANNING
    armed_time: datetime = None
    confirmation_candles: int = 0
    required_confirmations: int = 2  # 1-3 candles confirmation
    window_start_time: datetime = None
    window_bars_elapsed: int = 0
    max_window_bars: int = 20  # Maximum bars to wait for breakout
    entry_price_at_arm: float = None

    def __hash__(self):
        return hash(self.symbol)

    def __eq__(self, other):
        if isinstance(other, TradeSetup):
            return self.symbol == other.symbol
        return False


class TradeStateMachine:
    """Manages trade execution phases with confirmation"""

    def __init__(self, min_confirmation_candles: int = 1, max_confirmation_candles: int = 3):
        """
        Args:
            min_confirmation_candles: Minimum candles before entry (1-2 is good)
            max_confirmation_candles: Maximum candles to wait (2-3 is good)
        """
        self.pending_setups = {}  # symbol -> TradeSetup
        self.min_confirmation = min_confirmation_candles
        self.max_confirmation = max_confirmation_candles
        logger.info(f"Trade State Machine initialized: {min_confirmation_candles}-{max_confirmation_candles} candle confirmation")

    def detect_signal(self, symbol: str, decision: dict) -> TradeSetup:
        """Detect and arm a new trade signal"""
        if symbol in self.pending_setups:
            return self.pending_setups[symbol]

        setup = TradeSetup(
            symbol=symbol,
            action=decision.get('action', 'BUY'),
            entry_price=decision.get('entry_price', 0),
            stop_loss=decision.get('stop_loss', 0),
            take_profit=decision.get('take_profit', 0),
            confidence=decision.get('confidence', 50),
            reasoning=decision.get('reasoning', ''),
            regime=decision.get('regime', 'UNKNOWN'),
            required_confirmations=self.min_confirmation
        )

        self.pending_setups[symbol] = setup
        logger.info(f"📍 ARMED: {symbol} | Action: {setup.action} | Confidence: {setup.confidence}% | Entry: ${setup.entry_price:.4f}")
        setup.state = TradeState.ARMED
        setup.armed_time = datetime.now()
        setup.entry_price_at_arm = setup.entry_price

        return setup

    def process_confirmation(self, symbol: str, current_price: float, current_candle_dir: str) -> dict:
        """
        Process pullback/retracement confirmation

        Returns:
            {
                'ready_to_enter': bool,
                'setup': TradeSetup or None,
                'reason': str
            }
        """
        if symbol not in self.pending_setups:
            return {'ready_to_enter': False, 'setup': None, 'reason': 'No armed setup'}

        setup = self.pending_setups[symbol]

        if setup.state == TradeState.ARMED:
            # Check for pullback (price retraces towards stop loss side)
            if setup.action == "BUY":
                # For buy, pullback means price moves down (closer to SL)
                if current_price < setup.entry_price_at_arm:
                    setup.confirmation_candles += 1
                    setup.state = TradeState.CONFIRMATION
                    logger.info(f"✓ Pullback detected on {symbol}: {setup.confirmation_candles} candle(s)")
            else:  # SELL
                # For sell, pullback means price moves up (closer to SL)
                if current_price > setup.entry_price_at_arm:
                    setup.confirmation_candles += 1
                    setup.state = TradeState.CONFIRMATION
                    logger.info(f"✓ Pullback detected on {symbol}: {setup.confirmation_candles} candle(s)")

        # Check if confirmation requirements met
        if setup.state == TradeState.CONFIRMATION:
            if setup.confirmation_candles >= setup.required_confirmations:
                setup.state = TradeState.ENTRY_WINDOW
                setup.window_start_time = datetime.now()
                logger.info(f"🎯 ENTRY WINDOW OPEN for {symbol} - awaiting breakout")
                return {
                    'ready_to_enter': True,
                    'setup': setup,
                    'reason': f'Pullback confirmed ({setup.confirmation_candles} candles)'
                }

        # Check for timeout (too long waiting)
        if setup.state == TradeState.ARMED:
            time_elapsed = (datetime.now() - setup.armed_time).total_seconds() / 60  # minutes
            if time_elapsed > 60:  # 1 hour timeout
                del self.pending_setups[symbol]
                logger.warning(f"⏰ Setup timeout for {symbol} - setup expired")
                return {'ready_to_enter': False, 'setup': None, 'reason': 'Setup timeout'}

        return {'ready_to_enter': False, 'setup': setup, 'reason': 'Awaiting confirmation'}

    def check_entry_window(self, symbol: str, current_price: float) -> dict:
        """
        Check if breakout condition is met for entry

        Returns:
            {'should_enter': bool, 'setup': TradeSetup, 'reason': str}
        """
        if symbol not in self.pending_setups:
            return {'should_enter': False, 'setup': None, 'reason': 'No setup'}

        setup = self.pending_setups[symbol]

        if setup.state != TradeState.ENTRY_WINDOW:
            return {'should_enter': False, 'setup': setup, 'reason': f'State is {setup.state.value}'}

        # Check for breakout above/below entry
        if setup.action == "BUY":
            if current_price > setup.entry_price:  # Price breaks above entry
                setup.state = TradeState.ENTERED
                logger.info(f"⚡ BREAKOUT CONFIRMED for {symbol} - ENTERING NOW")
                return {'should_enter': True, 'setup': setup, 'reason': f'Breakout above ${setup.entry_price:.4f}'}
        else:  # SELL
            if current_price < setup.entry_price:  # Price breaks below entry
                setup.state = TradeState.ENTERED
                logger.info(f"⚡ BREAKOUT CONFIRMED for {symbol} - ENTERING NOW")
                return {'should_enter': True, 'setup': setup, 'reason': f'Breakout below ${setup.entry_price:.4f}'}

        # Track window bars
        setup.window_bars_elapsed += 1

        # Check for window timeout
        if setup.window_bars_elapsed > setup.max_window_bars:
            del self.pending_setups[symbol]
            logger.warning(f"⏰ Entry window timeout for {symbol} - signal expired")
            return {'should_enter': False, 'setup': None, 'reason': 'Entry window timeout'}

        return {
            'should_enter': False,
            'setup': setup,
            'reason': f'Awaiting breakout ({setup.window_bars_elapsed}/{setup.max_window_bars} bars)'
        }

    def close_setup(self, symbol: str):
        """Close a pending setup"""
        if symbol in self.pending_setups:
            del self.pending_setups[symbol]
            logger.info(f"Setup closed for {symbol}")

    def get_pending_setups(self):
        """Get all pending setups"""
        return list(self.pending_setups.values())

    def get_setup_stats(self):
        """Get statistics on pending setups"""
        stats = {
            'total_setups': len(self.pending_setups),
            'by_state': {}
        }
        for state in TradeState:
            count = sum(1 for s in self.pending_setups.values() if s.state == state)
            if count > 0:
                stats['by_state'][state.value] = count
        return stats
