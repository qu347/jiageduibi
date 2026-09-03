from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from app.automation.browser_slot import BROWSER_AUTOMATION_LOCK
from app.automation.executor import CollectionExecutor


class CollectionCoordinator:
    def __init__(self, executor: CollectionExecutor) -> None:
        self._executor = executor
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="collection")
        self._submitted: set[int] = set()
        self._lock = Lock()
        self._closed = False

    def submit(self, run_id: int) -> bool:
        with self._lock:
            if self._closed or run_id in self._submitted:
                return False
            self._submitted.add(run_id)
        try:
            self._pool.submit(self._execute_and_release, run_id)
        except RuntimeError:
            with self._lock:
                self._submitted.discard(run_id)
            return False
        return True

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _execute_and_release(self, run_id: int) -> None:
        try:
            with BROWSER_AUTOMATION_LOCK:
                self._executor.execute(run_id)
        finally:
            with self._lock:
                self._submitted.discard(run_id)
