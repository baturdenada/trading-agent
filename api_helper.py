"""
API Helper - Resilient API calls with exponential backoff and retry logic
Provides retry decorators and helper functions for external API calls
"""

import logging
import time
import requests
from functools import wraps
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

class APIRetryConfig:
    """Configuration for API retry behavior"""
    def __init__(self, max_retries=3, backoff_base=2, timeout=10):
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout

DEFAULT_CONFIG = APIRetryConfig()

def retry_on_exception(
    max_retries: int = 3,
    backoff_base: int = 2,
    timeout: int = 10,
    fatal_exceptions: tuple = ()
):
    """
    Decorator to add retry logic with exponential backoff to functions

    Args:
        max_retries: Number of retries (default 3)
        backoff_base: Base for exponential backoff (default 2)
        timeout: Timeout per attempt in seconds (default 10)
        fatal_exceptions: Exceptions that should not be retried
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_error = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)

                except fatal_exceptions as e:
                    # Don't retry fatal exceptions
                    logger.error(f"Fatal error in {func.__name__}: {e}")
                    raise

                except requests.Timeout as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_base ** attempt
                        logger.warning(f"{func.__name__} timeout on attempt {attempt+1}/{max_retries}, retry in {wait_time}s")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} timeout after {max_retries} attempts")

                except requests.ConnectionError as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_base ** attempt
                        logger.warning(f"{func.__name__} connection error on attempt {attempt+1}/{max_retries}, retry in {wait_time}s")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} connection failed after {max_retries} attempts")

                except Exception as e:
                    last_error = e
                    logger.error(f"Unexpected error in {func.__name__}: {e}")
                    raise

            # All retries exhausted
            logger.error(f"{func.__name__} failed after {max_retries} attempts: {last_error}")
            raise last_error

        return wrapper
    return decorator

def send_telegram_reliable(token: str, chat_id: str, message: str, max_retries: int = 2) -> bool:
    """
    Send Telegram message with retry logic

    Args:
        token: Telegram bot token
        chat_id: Telegram chat ID
        message: Message to send
        max_retries: Number of retries

    Returns:
        True if sent successfully, False otherwise
    """
    for attempt in range(max_retries):
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            response = requests.post(
                url,
                json={"chat_id": chat_id, "text": message},
                timeout=5
            )

            if response.status_code == 200:
                return True

            logger.warning(f"Telegram returned {response.status_code}")

            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

        except requests.Timeout:
            logger.warning(f"Telegram timeout on attempt {attempt+1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(2)

        except requests.ConnectionError as e:
            logger.warning(f"Telegram connection error on attempt {attempt+1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)

        except Exception as e:
            logger.error(f"Unexpected Telegram error: {e}")
            return False

    logger.error(f"Failed to send Telegram message after {max_retries} attempts")
    return False

def call_deepseek_reliable(client, prompt: str, model: str = "deepseek-chat", max_retries: int = 3, fallback: Optional[str] = None) -> Optional[str]:
    """
    Call DeepSeek API with retry logic and fallback

    Args:
        client: OpenAI client configured for DeepSeek
        prompt: Prompt to send
        model: Model name (default deepseek-chat)
        max_retries: Number of retries
        fallback: Fallback response if all retries fail

    Returns:
        Response text or fallback
    """
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                timeout=30
            )
            return response.choices[0].message.content

        except requests.Timeout:
            logger.warning(f"DeepSeek timeout on attempt {attempt+1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

        except requests.ConnectionError as e:
            logger.warning(f"DeepSeek connection error on attempt {attempt+1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            if fallback:
                logger.info("Using fallback response")
                return fallback
            raise

    # All retries exhausted
    logger.error(f"DeepSeek API failed after {max_retries} attempts")
    if fallback:
        logger.info("Using fallback response")
        return fallback
    return None
