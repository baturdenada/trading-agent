"""
ASYNC EXECUTOR - Non-blocking trade execution
Uses asyncio + threading for concurrent trade operations
Prevents UI/monitoring from blocking on slow MT5 calls
"""

import asyncio
import logging
import time
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


class ExecutionPriority(Enum):
    """Task priority levels"""
    CRITICAL = 1    # Emergency positions, stop losses
    HIGH = 2        # New entries, take profits
    NORMAL = 3      # Information gathering, monitoring
    LOW = 4         # Logging, reporting


@dataclass
class ExecutionTask:
    """Represents a task to be executed"""
    task_id: str
    action: str                 # 'OPEN', 'CLOSE', 'MODIFY', 'INFO'
    priority: ExecutionPriority
    mt5_request: Dict
    callback: Optional[Callable] = None
    timeout: float = 10.0
    retries: int = 3
    created_at: datetime = None
    started_at: datetime = None
    completed_at: datetime = None
    result: Any = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class ExecutionResult:
    """Result of task execution"""
    task_id: str
    success: bool
    data: Any
    error: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0


class AsyncExecutor:
    """Non-blocking executor for MT5 operations"""

    def __init__(self, max_workers: int = 5, queue_size: int = 100):
        """
        Args:
            max_workers: Number of worker threads for concurrent execution
            queue_size: Maximum pending tasks
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.task_queue = asyncio.Queue(maxsize=queue_size)
        self.task_results = {}
        self.running = False
        self.max_workers = max_workers
        self.active_tasks = 0

        logger.info(f"AsyncExecutor initialized: {max_workers} workers, queue size {queue_size}")

    async def start(self):
        """Start the executor loop"""
        self.running = True
        logger.info("AsyncExecutor started")

        # Create worker tasks
        workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.max_workers)
        ]

        await asyncio.gather(*workers)

    async def stop(self):
        """Stop the executor gracefully"""
        self.running = False
        logger.info("AsyncExecutor stopping...")

        # Wait for queue to drain
        max_wait = 30
        elapsed = 0
        while not self.task_queue.empty() and elapsed < max_wait:
            await asyncio.sleep(0.5)
            elapsed += 0.5

        if not self.task_queue.empty():
            logger.warning(f"Queue not fully drained after {max_wait}s, forcing shutdown")

        self.executor.shutdown(wait=False)
        logger.info("AsyncExecutor stopped")

    async def submit_task(self, task: ExecutionTask) -> str:
        """
        Submit a task for execution

        Returns:
            task_id for tracking results
        """
        try:
            await asyncio.wait_for(
                self.task_queue.put(task),
                timeout=5.0
            )
            logger.debug(f"Task submitted: {task.task_id} ({task.action})")
            return task.task_id
        except asyncio.TimeoutError:
            logger.error(f"Failed to submit task {task.task_id}: Queue full")
            raise

    async def _worker(self, worker_id: int):
        """Worker coroutine that processes tasks"""
        logger.info(f"Worker {worker_id} started")

        while self.running:
            try:
                # Get next task (wait max 1 second)
                task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )

                self.active_tasks += 1
                logger.debug(f"Worker {worker_id} processing: {task.task_id}")

                # Execute in thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.executor,
                    self._execute_mt5_operation,
                    task
                )

                # Store result
                self.task_results[task.task_id] = result

                # Call callback if provided
                if task.callback:
                    try:
                        if asyncio.iscoroutinefunction(task.callback):
                            await task.callback(result)
                        else:
                            task.callback(result)
                    except Exception as e:
                        logger.error(f"Callback error for {task.task_id}: {e}")

                self.active_tasks -= 1
                logger.debug(f"Task completed: {task.task_id}")

            except asyncio.TimeoutError:
                # No task in queue, continue
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                self.active_tasks = max(0, self.active_tasks - 1)

    def _execute_mt5_operation(self, task: ExecutionTask) -> ExecutionResult:
        """Execute MT5 operation (runs in thread pool)"""
        task.started_at = datetime.now()
        retry_count = 0
        last_error = None

        while retry_count < task.retries:
            try:
                if task.action == 'OPEN':
                    result = mt5.order_send(task.mt5_request)
                    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                        error = result.comment if result else "No result"
                        raise Exception(f"Order failed: {error}")
                    return ExecutionResult(
                        task_id=task.task_id,
                        success=True,
                        data={'order': result.order, 'retcode': result.retcode},
                        execution_time=(datetime.now() - task.started_at).total_seconds(),
                        retry_count=retry_count
                    )

                elif task.action == 'CLOSE':
                    result = mt5.order_send(task.mt5_request)
                    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                        error = result.comment if result else "No result"
                        raise Exception(f"Close failed: {error}")
                    return ExecutionResult(
                        task_id=task.task_id,
                        success=True,
                        data={'order': result.order},
                        execution_time=(datetime.now() - task.started_at).total_seconds(),
                        retry_count=retry_count
                    )

                elif task.action == 'MODIFY':
                    result = mt5.order_send(task.mt5_request)
                    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                        error = result.comment if result else "No result"
                        raise Exception(f"Modify failed: {error}")
                    return ExecutionResult(
                        task_id=task.task_id,
                        success=True,
                        data={'modified': True},
                        execution_time=(datetime.now() - task.started_at).total_seconds(),
                        retry_count=retry_count
                    )

                elif task.action == 'INFO':
                    # Information gathering (no MT5 request needed)
                    return ExecutionResult(
                        task_id=task.task_id,
                        success=True,
                        data=task.mt5_request,
                        execution_time=(datetime.now() - task.started_at).total_seconds(),
                        retry_count=retry_count
                    )

                else:
                    raise ValueError(f"Unknown action: {task.action}")

            except Exception as e:
                last_error = str(e)
                retry_count += 1

                if retry_count < task.retries:
                    logger.warning(f"Task {task.task_id} retry {retry_count}/{task.retries}: {last_error}")
                    time.sleep(1.0)  # Wait before retry
                else:
                    logger.error(f"Task {task.task_id} failed after {task.retries} retries: {last_error}")

        task.completed_at = datetime.now()
        return ExecutionResult(
            task_id=task.task_id,
            success=False,
            data=None,
            error=last_error,
            execution_time=(datetime.now() - task.started_at).total_seconds(),
            retry_count=retry_count
        )

    async def get_result(self, task_id: str, timeout: float = 30.0) -> Optional[ExecutionResult]:
        """
        Wait for task result with timeout

        Returns:
            ExecutionResult or None if timeout
        """
        start_time = time.time()

        while True:
            if task_id in self.task_results:
                return self.task_results.pop(task_id)

            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning(f"Timeout waiting for task {task_id}")
                return None

            await asyncio.sleep(0.1)

    async def wait_all(self, timeout: float = 60.0) -> bool:
        """Wait for all pending tasks to complete"""
        start_time = time.time()

        while not self.task_queue.empty() or self.active_tasks > 0:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning(f"Timeout waiting for all tasks (elapsed: {elapsed:.1f}s)")
                return False

            await asyncio.sleep(0.5)

        logger.info("All tasks completed")
        return True

    def get_status(self) -> Dict:
        """Get executor status"""
        return {
            'running': self.running,
            'queue_size': self.task_queue.qsize(),
            'active_tasks': self.active_tasks,
            'max_workers': self.max_workers,
            'pending_results': len(self.task_results)
        }


# Global async executor instance
_executor = None


async def get_executor() -> AsyncExecutor:
    """Get or create global executor instance"""
    global _executor
    if _executor is None:
        _executor = AsyncExecutor(max_workers=5, queue_size=100)
    return _executor


async def execute_trade_order(
    symbol: str,
    volume: float,
    action: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    comment: str = "Async_Trade",
    timeout: float = 10.0
) -> ExecutionResult:
    """
    Execute a trade order asynchronously

    Returns:
        ExecutionResult with order details
    """
    executor = await get_executor()

    order_type = mt5.ORDER_TYPE_BUY if action == 'BUY' else mt5.ORDER_TYPE_SELL
    tick = mt5.symbol_info_tick(symbol)

    if not tick:
        return ExecutionResult(
            task_id='invalid',
            success=False,
            data=None,
            error=f"Cannot get price for {symbol}"
        )

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": tick.ask if action == 'BUY' else tick.bid,
        "sl": round(stop_loss, 5),
        "tp": round(take_profit, 5),
        "deviation": 20,
        "magic": 987654,
        "comment": comment,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    task = ExecutionTask(
        task_id=f"trade_{symbol}_{datetime.now().timestamp()}",
        action='OPEN',
        priority=ExecutionPriority.HIGH,
        mt5_request=request,
        timeout=timeout
    )

    task_id = await executor.submit_task(task)
    result = await executor.get_result(task_id, timeout=timeout)

    return result or ExecutionResult(
        task_id=task_id,
        success=False,
        data=None,
        error="Timeout"
    )


async def close_position_async(
    ticket: int,
    symbol: str,
    volume: float,
    position_type: int,
    timeout: float = 10.0
) -> ExecutionResult:
    """Close a position asynchronously"""
    executor = await get_executor()

    order_type = mt5.ORDER_TYPE_SELL if position_type == 0 else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(symbol)

    if not tick:
        return ExecutionResult(
            task_id='invalid',
            success=False,
            data=None,
            error=f"Cannot get price for {symbol}"
        )

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "position": ticket,
        "price": tick.bid if position_type == 0 else tick.ask,
        "deviation": 20,
        "magic": 987654,
        "comment": "Async_Close",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    task = ExecutionTask(
        task_id=f"close_{ticket}_{datetime.now().timestamp()}",
        action='CLOSE',
        priority=ExecutionPriority.HIGH,
        mt5_request=request,
        timeout=timeout
    )

    task_id = await executor.submit_task(task)
    result = await executor.get_result(task_id, timeout=timeout)

    return result or ExecutionResult(
        task_id=task_id,
        success=False,
        data=None,
        error="Timeout"
    )
