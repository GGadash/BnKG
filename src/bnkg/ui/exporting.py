"""Export ownership is independent of acquisition and its SQLite connection."""

import time

from PySide6.QtCore import QThread, Signal

from bnkg.core.export import ExportCancelled, export_session


class ExportJob(QThread):
    completed = Signal(str, int)
    failed = Signal(str)
    progress = Signal(int, int, str)
    cancelled = Signal()

    def __init__(self, database, target, format_name, options=None, parent=None):
        super().__init__(parent)
        self.database, self.target, self.format_name = database, target, format_name
        self.options = dict(options or {})

    def run(self):
        last_notice, last_phase = 0.0, ""

        def notify(done, total, phase):
            nonlocal last_notice, last_phase
            now = time.monotonic()
            if now - last_notice >= 0.1 or done == total or phase != last_phase:
                self.progress.emit(done, total, phase)
                last_notice, last_phase = now, phase

        try:
            count = export_session(
                self.database,
                self.target,
                self.format_name,
                cancelled=self.isInterruptionRequested,
                progress=notify,
                **self.options,
            )
            self.completed.emit(str(self.target), count)
        except ExportCancelled:
            self.cancelled.emit()
        except Exception as exc:
            if self.isInterruptionRequested():
                self.cancelled.emit()
            else:
                self.failed.emit(str(exc))
