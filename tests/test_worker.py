from bnkg.ui.worker import AcquisitionWorker


def test_invalid_address_returns_to_disconnected(qtbot):
    worker = AcquisitionWorker()
    statuses, errors = [], []
    worker.status.connect(lambda mode, detail: statuses.append(mode))
    worker.failure.connect(errors.append)
    worker.command("connect", "bad host")
    assert statuses[-1] == "disconnected"
    assert errors
    assert worker.device is None


def test_three_failures_stop_acquisition_and_close_device(qtbot):
    class BrokenDevice:
        closed = False

        def read(self):
            raise RuntimeError("connection lost")

        def close(self):
            self.closed = True

    worker = AcquisitionWorker()
    device = BrokenDevice()
    worker.device = device
    worker.mode = "instrument"
    statuses = []
    worker.status.connect(lambda mode, detail: statuses.append(mode))
    for _ in range(3):
        worker.poll()
    assert statuses.count("stale") == 3
    assert statuses[-1] == "disconnected"
    assert device.closed
    assert worker.device is None
