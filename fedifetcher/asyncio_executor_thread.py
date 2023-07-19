# asyncio_executor_thread.py
"""Example of using an executor to run a task in a thread pool."""
import asyncio
import concurrent.futures
import logging
from types import FunctionType


class AsyncIOExecutorThread:
    """A class to run tasks in a thread pool."""

    def __init__(self, max_workers: int = 3) -> None:
        """Initialize the AsyncIOExecutorThread.

        Parameters
        ----------
        max_workers : int, optional
            The maximum number of workers in the thread pool, by default 3

        """
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
        )

    async def run_blocking_tasks(self, blocks: FunctionType) -> None:
        """Run the blocking tasks in a thread pool."""
        log = logging.getLogger("run_blocking_tasks")
        log.info("starting")

        log.info("creating executor tasks")
        loop = asyncio.get_event_loop()
        blocking_tasks = [
            loop.run_in_executor(self.executor, blocks, i)
            for i in range(6)
        ]
        log.info("waiting for executor tasks")
        completed, pending = await asyncio.wait(blocking_tasks)
        results = [t.result() for t in completed]
        log.info(f"results: {results!r}")

        log.info("exiting")
