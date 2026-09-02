import threading

from app.automation.coordinator import CollectionCoordinator


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
