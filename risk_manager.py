"""
Risk Manager - Professional risk management with position sizing caps and loss limits
Prevents account blowups with hard stops and emergency shutdown
"""

import logging
import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class RiskManager:
    """Professional risk management system for live trading"""

    def __init__(self, initial_balance: float, daily_loss_limit_pct: float = 0.05,
                 weekly_loss_limit_pct: float = 0.10, max_position_size_pct: float = 0.10,
                 max_risk_per_trade_pct: float = 0.02, max_concurrent_positions: int = 5):
        """
        Initialize risk manager with strict limits

        Args:
            initial_balance: Starting account balance
            daily_loss_limit_pct: Max daily loss (default 5% = account wipeout protection)
            weekly_loss_limit_pct: Max weekly loss (default 10%)
            max_position_size_pct: Max position size (default 10% of balance)
            max_risk_per_trade_pct: Max risk per trade (default 2%)
            max_concurrent_positions: Max open positions allowed (default 5)
        """
        self.initial_balance = initial_balance
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.weekly_loss_limit_pct = weekly_loss_limit_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_concurrent_positions = max_concurrent_positions

        # Calculated limits
        self.daily_loss_limit = initial_balance * -daily_loss_limit_pct
        self.weekly_loss_limit = initial_balance * -weekly_loss_limit_pct
        self.max_position_size = initial_balance * max_position_size_pct
        self.max_risk_per_trade = initial_balance * max_risk_per_trade_pct

        # State tracking
        self.daily_start_time = datetime.now()
        self.daily_start_balance = initial_balance
        self.trading_suspended = False
        self.suspension_reason = None
        self.emergency_shutdown_triggered = False

        logger.info(f"Risk Manager initialized:")
        logger.info(f"  Daily loss limit: {self.daily_loss_limit:.2f} ({daily_loss_limit_pct*100}%)")
        logger.info(f"  Weekly loss limit: {self.weekly_loss_limit:.2f} ({weekly_loss_limit_pct*100}%)")
        logger.info(f"  Max position size: {self.max_position_size:.2f}")
        logger.info(f"  Max risk per trade: {self.max_risk_per_trade:.2f}")
        logger.info(f"  Max concurrent positions: {max_concurrent_positions}")

    def calculate_position_size(self, balance: float, risk_percentage: float, atr: float,
                               pip_value: float, confidence: float = 70.0) -> Tuple[float, float]:
        """
        Calculate position size with hard caps applied

        Args:
            balance: Current account balance
            risk_percentage: Base risk percentage (0.01 = 1%)
            atr: Average True Range (volatility measure)
            pip_value: Pip value for the symbol
            confidence: Strategy confidence (0-100)

        Returns:
            Tuple of (position_size, actual_risk_pct)
        """
        # Dynamic adjustments
        confidence_multiplier = 0.5 + (confidence / 100)  # 0.5 to 1.5
        volatility_adjustment = 1.0
        if atr > 2.0:
            volatility_adjustment = 0.5  # High volatility = smaller positions
        elif atr > 1.5:
            volatility_adjustment = 0.7

        # Base calculation
        calculated_risk = risk_percentage * confidence_multiplier * volatility_adjustment
        calculated_position = balance * calculated_risk

        # Apply hard caps
        max_position = min(
            self.max_position_size,           # Never > 10% of balance
            self.max_risk_per_trade,          # Never > 2% risk per trade
            calculated_position,
            balance * 0.05                    # Additional safety: 5% max
        )

        actual_risk_pct = max_position / balance if balance > 0 else 0

        logger.info(f"Position sizing: {max_position:.2f} ({actual_risk_pct*100:.2f}% risk)")
        logger.debug(f"  Calculated: {calculated_position:.2f}, ATR: {atr:.4f}, Confidence: {confidence}%")

        return max_position, actual_risk_pct

    def check_daily_loss_limit(self, current_balance: float, current_equity: float) -> Tuple[bool, Optional[str]]:
        """
        Check if daily loss limit has been exceeded

        Args:
            current_balance: Current account balance
            current_equity: Current account equity

        Returns:
            Tuple of (limit_exceeded, reason)
        """
        # Check if we've entered a new day
        if (datetime.now() - self.daily_start_time).days > 0:
            self.daily_start_time = datetime.now()
            self.daily_start_balance = current_balance
            logger.info(f"Daily reset: new balance {current_balance:.2f}")
            return False, None

        daily_pnl = current_balance - self.daily_start_balance

        if daily_pnl < self.daily_loss_limit:
            reason = f"Daily loss limit exceeded: {daily_pnl:.2f} < {self.daily_loss_limit:.2f}"
            logger.critical(reason)
            return True, reason

        # Warning threshold (80% of limit)
        warning_threshold = self.daily_loss_limit * 0.8
        if daily_pnl < warning_threshold:
            logger.warning(f"Approaching daily loss limit: {daily_pnl:.2f} (threshold: {warning_threshold:.2f})")

        return False, None

    def check_weekly_loss_limit(self, current_balance: float) -> Tuple[bool, Optional[str]]:
        """
        Check if weekly loss limit has been exceeded

        Args:
            current_balance: Current account balance

        Returns:
            Tuple of (limit_exceeded, reason)
        """
        weekly_pnl = current_balance - self.initial_balance

        if weekly_pnl < self.weekly_loss_limit:
            reason = f"Weekly loss limit exceeded: {weekly_pnl:.2f} < {self.weekly_loss_limit:.2f}"
            logger.critical(reason)
            return True, reason

        return False, None

    def check_max_positions(self, open_positions_count: int) -> Tuple[bool, Optional[str]]:
        """
        Check if max concurrent positions limit has been exceeded

        Args:
            open_positions_count: Number of currently open positions

        Returns:
            Tuple of (limit_exceeded, reason)
        """
        if open_positions_count >= self.max_concurrent_positions:
            reason = f"Max positions ({self.max_concurrent_positions}) reached: {open_positions_count} open"
            logger.warning(reason)
            return True, reason

        return False, None

    def check_correlation_risk(self, open_positions: List[Dict], max_correlated: int = 2) -> Tuple[bool, Optional[str]]:
        """
        Check if too many correlated positions are open

        Args:
            open_positions: List of open position dicts with 'symbol' field
            max_correlated: Max number of correlated positions allowed

        Returns:
            Tuple of (limit_exceeded, reason)
        """
        # Define correlated symbol groups
        correlated_groups = {
            'metals': ['XAUUSD.s', 'XAGUSD.s'],
            'majors': ['EURUSD.s', 'GBPUSD.s', 'AUDUSD.s'],
            'usd': ['USDCAD.s', 'USDJPY.s', 'USDCHF.s'],
            'indices': ['SP500.s', 'NAS100.s']
        }

        symbols = [p.get('symbol', '') for p in open_positions]

        for group_name, group_symbols in correlated_groups.items():
            count = sum(1 for s in symbols if s in group_symbols)
            if count > max_correlated:
                reason = f"Too many {group_name} positions: {count} > {max_correlated}"
                logger.warning(reason)
                return True, reason

        return False, None

    def get_account_status(self, account_info) -> Dict:
        """Get detailed account risk status"""
        daily_loss_exceeded, daily_reason = self.check_daily_loss_limit(account_info.balance, account_info.equity)
        weekly_loss_exceeded, weekly_reason = self.check_weekly_loss_limit(account_info.balance)

        daily_pnl = account_info.balance - self.daily_start_balance
        daily_loss_pct = (daily_pnl / self.daily_start_balance * 100) if self.daily_start_balance > 0 else 0

        return {
            'balance': account_info.balance,
            'equity': account_info.equity,
            'daily_pnl': daily_pnl,
            'daily_loss_pct': daily_loss_pct,
            'daily_loss_limit': self.daily_loss_limit,
            'daily_loss_exceeded': daily_loss_exceeded,
            'daily_reason': daily_reason,
            'weekly_loss_exceeded': weekly_loss_exceeded,
            'weekly_reason': weekly_reason,
            'trading_suspended': self.trading_suspended,
            'suspension_reason': self.suspension_reason,
            'emergency_shutdown': self.emergency_shutdown_triggered
        }

    def suspend_trading(self, reason: str):
        """Suspend trading (still allows closing positions)"""
        self.trading_suspended = True
        self.suspension_reason = reason
        logger.critical(f"TRADING SUSPENDED: {reason}")

    def trigger_emergency_shutdown(self, reason: str):
        """Trigger complete emergency shutdown"""
        self.emergency_shutdown_triggered = True
        self.trading_suspended = True
        self.suspension_reason = reason
        logger.critical(f"EMERGENCY SHUTDOWN: {reason}")

    def reset_daily_limits(self, current_balance: float):
        """Reset daily tracking (call at market open)"""
        self.daily_start_time = datetime.now()
        self.daily_start_balance = current_balance
        logger.info(f"Daily limits reset at {current_balance:.2f}")

    def is_trading_allowed(self) -> Tuple[bool, Optional[str]]:
        """Check if trading is currently allowed"""
        if self.emergency_shutdown_triggered:
            return False, "Emergency shutdown active"
        if self.trading_suspended:
            return False, self.suspension_reason
        return True, None
