import threading

from app.automation.coordinator import CollectionCoordinator
from app.price_sheets.coordinator import PriceSheetCoordinator


class BlockingExecutor:
    def __init__(self) -> None:
        self.calls: list[int] = []
        self.active = 0
        self.max_active = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished_two = threading.Event()
        self._lock = threading.Lock()

    def execute(self, run_id: int) -> None:
        with self._lock:
            self.calls.append(run_id)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.started.set()
        self.release.wait(timeout=5)
        with self._lock:
            self.active -= 1
            if len(self.calls) == 2 and self.active == 0:
                self.finished_two.set()


def test_coordinator_deduplicates_active_run_and_uses_one_worker() -> None:
    executor = BlockingExecutor()
    coordinator = CollectionCoordinator(executor)
    try:
        assert coordinator.submit(1) is True
        assert executor.started.wait(timeout=2)
        assert coordinator.submit(1) is False
        assert coordinator.submit(2) is True

        executor.release.set()
        assert executor.finished_two.wait(timeout=2)

        assert executor.calls == [1, 2]
        assert executor.max_active == 1
    finally:
        coordinator.close()


def test_coordinator_releases_run_id_after_execution() -> None:
    executor = BlockingExecutor()
    executor.release.set()
    coordinator = CollectionCoordinator(executor)
    try:
        assert coordinator.submit(7) is True
        assert executor.started.wait(timeout=2)
        for _attempt in range(100):
            if coordinator.submit(7):
                break
            threading.Event().wait(0.01)
        else:
            raise AssertionError("已完成的采集任务编号没有释放")
    finally:
        coordinator.close()


def test_collection_types_share_one_browser_execution_slot() -> None:
    first = BlockingExecutor()
    second = BlockingExecutor()
    collection = CollectionCoordinator(first)
    price_sheet = PriceSheetCoordinator(second)
    try:
        assert collection.submit(1) is True
        assert first.started.wait(timeout=2)
        assert price_sheet.submit(2) is True
        assert second.started.wait(timeout=0.1) is False

        first.release.set()
        assert second.started.wait(timeout=2)
        second.release.set()
    finally:
        first.release.set()
        second.release.set()
        collection.close()
        price_sheet.close()
