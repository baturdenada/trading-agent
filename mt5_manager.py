"""
MT5 Manager - Resilient MetaTrader5 connection with exponential backoff and circuit breaker
Provides automatic reconnection and error recovery
"""

import logging
import time
import MetaTrader5 as mt5
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MT5Manager:
    def __init__(self, path=None, login=None, password=None, server=None):
        self.path = path or os.getenv("MT5_PATH")
        self.login = login or int(os.getenv("MT5_LOGIN", 0))
        self.password = password or os.getenv("MT5_PASSWORD")
        self.server = server or os.getenv("MT5_SERVER")

        # Retry configuration
        self.max_retries = 5
        self.backoff_base = 2  # 2^n seconds: 1s, 2s, 4s, 8s, 16s
        self.consecutive_failures = 0

        # Circuit breaker
        self.circuit_open = False
        self.circuit_open_time = None
        self.circuit_timeout = 60  # Reset after 60 seconds

        # Connection state
        self.is_connected = False
        self.last_connection_attempt = None
        self.last_error = None

        logger.info("MT5Manager initialized")

    def _reset_circuit(self):
        """Reset circuit breaker if timeout has passed"""
        if self.circuit_open and self.circuit_open_time:
            elapsed = (datetime.now() - self.circuit_open_time).total_seconds()
            if elapsed > self.circuit_timeout:
                logger.info(f"Circuit breaker reset after {elapsed}s")
                self.circuit_open = False
                self.circuit_open_time = None
                self.consecutive_failures = 0

    def connect(self):
        """Connect to MT5 with exponential backoff and circuit breaker"""

        # Check circuit breaker
        self._reset_circuit()
        if self.circuit_open:
            elapsed = (datetime.now() - self.circuit_open_time).total_seconds()
            remaining = self.circuit_timeout - elapsed
            logger.error(f"Circuit breaker OPEN - waiting {remaining:.0f}s before retry")
            return False

        # Try to connect
        for attempt in range(self.max_retries):
            try:
                self.last_connection_attempt = datetime.now()

                # Initialize MT5
                init_result = mt5.initialize(
                    path=self.path,
                    login=self.login,
                    password=self.password,
                    server=self.server
                )

                if not init_result:
                    raise ConnectionError(f"MT5 initialization failed: {mt5.last_error()}")

                # Test connection
                account = mt5.account_info()
                if not account:
                    raise ConnectionError("MT5 account info failed")

                # Success
                self.is_connected = True
                self.consecutive_failures = 0
                self.last_error = None
                logger.info(f"MT5 connected successfully on attempt {attempt+1}")
                return True

            except ConnectionError as e:
                self.last_error = str(e)
                self.consecutive_failures += 1

                if self.consecutive_failures >= 3:
                    self.circuit_open = True
                    self.circuit_open_time = datetime.now()
                    logger.error(f"MT5 CIRCUIT BREAKER OPENED after {self.consecutive_failures} failures")
                    return False

                wait_time = self.backoff_base ** attempt
                logger.warning(f"MT5 connection attempt {attempt+1}/{self.max_retries} failed: {e}")
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)

            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Unexpected MT5 error: {e}")
                return False

        # All retries exhausted
        self.is_connected = False
        logger.error(f"MT5 connection failed after {self.max_retries} attempts")
        return False

    def ensure_connected(self):
        """Ensure MT5 is connected, reconnect if needed"""
        if not self.is_connected:
            return self.connect()

        # Test connection
        try:
            if mt5.account_info():
                return True
        except:
            pass

        # Connection lost, reconnect
        logger.warning("MT5 connection lost, attempting to reconnect...")
        return self.connect()

    def disconnect(self):
        """Disconnect from MT5"""
        try:
            mt5.shutdown()
            self.is_connected = False
            logger.info("MT5 disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting MT5: {e}")

    def get_status(self):
        """Get connection status"""
        return {
            'connected': self.is_connected,
            'circuit_open': self.circuit_open,
            'consecutive_failures': self.consecutive_failures,
            'last_error': self.last_error,
            'last_attempt': self.last_connection_attempt.isoformat() if self.last_connection_attempt else None
        }

    def get_account_info(self):
        """Get MT5 account information"""
        try:
            if self.ensure_connected():
                return mt5.account_info()
            return None
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None

# Global instance for shared use
_mt5_manager = None

def get_mt5_manager(path=None, login=None, password=None, server=None):
    """Get or create MT5 manager singleton"""
    global _mt5_manager
    if _mt5_manager is None:
        _mt5_manager = MT5Manager(path, login, password, server)
    return _mt5_manager
