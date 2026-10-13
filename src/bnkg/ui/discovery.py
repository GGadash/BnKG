"""Discovery owns a cancellable background thread, separate from acquisition."""

import threading

from PySide6.QtCore import QThread, Signal

from bnkg.core.discovery import discover_mdns, scan_subnet


class DiscoveryThread(QThread):
    found = Signal(object)
    progress = Signal(str)
    failed = Signal(str)

    def __init__(self, subnet: str | None, parent=None):
        super().__init__(parent)
        self.subnet = subnet
        self.cancel = threading.Event()

    def run(self):
        try:
            if self.subnet is None:
                discover_mdns(self.cancel, self.found.emit, self.progress.emit)
            else:
                scan_subnet(self.subnet, self.cancel, self.found.emit, self.progress.emit)
        except Exception as exc:
            self.failed.emit(str(exc))
