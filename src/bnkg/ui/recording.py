"""Independent bounded recorder thread and local-only controls."""

import queue
import threading
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.media_tools import DOWNLOAD_URL, OFFICIAL_URL, media_tools
from bnkg.core.recording import FrameArchive, RecordingCancelled, png_size


class RecordingJob(QThread):
    ready = Signal(str)
    progress = Signal(str)
    capture_ended = Signal()
    result = Signal(str)

    def __init__(
        self, parent_folder, *, ffmpeg="", ffprobe="", profile="high", crf=18, sync_id=None
    ):
        super().__init__()
        self.parent_folder = parent_folder
        self.sync_id = sync_id
        self.ffmpeg, self.ffprobe = ffmpeg, ffprobe
        self.profile, self.crf = profile, crf
        self.frames = queue.Queue(maxsize=8)
        self.stop_capture = threading.Event()
        self.cancelled = threading.Event()
        self.reason = "Stopped by user"
        self.dropped = 0

    def submit(self, data, timing):
        # Called directly in acquisition thread: no UI, I/O or waiting.
        if self.stop_capture.is_set() or self.cancelled.is_set():
            return
        if len(data) > 8 * 1024 * 1024:
            self.stop("Oversized frame rejected")
            return
        try:
            self.frames.put_nowait((data, timing))
        except queue.Full:
            self.dropped += 1
            self.stop("Frame queue full; recording stopped without blocking monitoring")

    def stop(self, reason="Stopped by user"):
        self.reason = reason
        self.stop_capture.set()

    def cancel(self):
        self.cancelled.set()
        self.stop("Cancelled or app closing; originals retained")

    def run(self):
        archive = None
        try:
            archive = FrameArchive(
                self.parent_folder, profile=self.profile, crf=self.crf, sync_id=self.sync_id
            )
            self.ready.emit(str(archive.folder))
            started = last_frame = time.monotonic()
            while not self.stop_capture.is_set() or not self.frames.empty():
                if self.cancelled.is_set():
                    break
                now = time.monotonic()
                if not self.stop_capture.is_set() and (
                    now - started >= 3600 or now - last_frame >= 30
                ):
                    self.stop("Duration limit or no new frames for 30 seconds")
                    continue
                try:
                    data, timing = self.frames.get(timeout=0.1)
                except queue.Empty:
                    continue
                png_size(data)  # Bound dimensions before allocating decoded pixels.
                if QImage.fromData(data, "PNG").isNull():
                    raise ValueError("Invalid PNG; recording stopped.")
                row = archive.append(data, timing)
                last_frame = time.monotonic()
                self.progress.emit(
                    f"Recording: {len(archive.rows)} frames · {archive.bytes / 1048576:.1f} MiB"
                    + (" · unchanged image" if row["unchanged"] else "")
                )
            self.capture_ended.emit()
            archive.finish_capture(self.reason, self.dropped)
            if self.cancelled.is_set():
                archive.write_manifest(status="cancelled", reason=self.reason)
            elif self.ffmpeg and archive.rows:
                self.progress.emit("Encoding MP4; originals retained. Cancel remains available.")
                archive.encode(self.ffmpeg, self.ffprobe, self.cancelled.is_set)
            self.result.emit(f"{archive.manifest['status']}: {archive.folder}")
        except Exception as exc:
            if archive:
                try:
                    archive.finish_capture(str(exc), self.dropped)
                    archive.write_manifest(
                        status="cancelled" if isinstance(exc, RecordingCancelled) else "incomplete"
                    )
                except OSError:
                    pass  # Existing frames and append-only receipt ledger remain recoverable.
            self.result.emit(
                f"Recording stopped: {exc}"
                + (f" · Recovery folder: {archive.folder}" if archive else "")
            )
        finally:
            self.stop_capture.set()
            self.capture_ended.emit()


class RecordingPanel(QWidget):
    saved = Signal(str)
    polling = Signal(bool)
    idle = Signal()
    activity = Signal(str)

    def __init__(self, settings, default_folder):
        super().__init__()
        self.settings, self.default_folder = settings, default_folder
        self.job = None
        self.connected = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("LOCAL SCREEN RECORDING")
        title.setObjectName("subheading")
        layout.addWidget(title)
        note = QLabel(
            "Records new received PNGs and timing into a new folder. Continues on other pages. MP4 holds frames across gaps; check its timing sidecar. No audio or automatic wake."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.mp4 = QCheckBox("Also create processed MP4 after Stop")
        layout.addWidget(self.mp4)
        self.options = QWidget()
        grid = QGridLayout(self.options)
        grid.setContentsMargins(0, 0, 0, 0)
        encoder, probe = media_tools(
            str(settings.value("ffmpeg_path", "")), str(settings.value("ffprobe_path", ""))
        )
        self.ffmpeg = QLineEdit(encoder)
        self.ffprobe = QLineEdit(probe)
        self.ffmpeg.setPlaceholderText("External FFmpeg executable")
        self.ffprobe.setPlaceholderText("External ffprobe executable")
        for i, (label, edit) in enumerate((("FFmpeg", self.ffmpeg), ("ffprobe", self.ffprobe))):
            button = QPushButton("Browse " + label + "…")
            button.clicked.connect(lambda _, e=edit: self.choose_tool(e))
            grid.addWidget(edit, i, 0)
            grid.addWidget(button, i, 1)
        self.profile = QComboBox()
        self.profile.addItems(["high", "main", "baseline"])
        self.crf = QSpinBox()
        self.crf.setRange(1, 51)
        self.crf.setValue(18)
        self.crf.setPrefix("CRF ")
        self.crf.setToolTip(
            "Lossy quality: lower is higher quality/larger. Original PNGs remain unchanged."
        )
        grid.addWidget(self.profile, 2, 0)
        grid.addWidget(self.crf, 2, 1)
        self.tool_status = QLabel()
        self.tool_status.setWordWrap(True)
        grid.addWidget(self.tool_status, 3, 0, 1, 2)
        help_text = QLabel(
            "FFmpeg is optional and supplied separately. Windows: download the Release "
            "Essentials ZIP from Gyan, verify its SHA-256, then extract it. Place its bin "
            "folder at external-tools/ffmpeg/bin beside B&KG (keep the licence and README), "
            "or use Browse to select ffmpeg.exe and ffprobe.exe from the same build. "
            "Restart B&KG after installing, or browse now. On Linux, install your distribution's "
            "FFmpeg package and select ffmpeg and ffprobe. MP4 needs libx264. Native AAC "
            "is used by the separate media export controls; FLAC capture does not require FFmpeg."
        )
        help_text.setWordWrap(True)
        grid.addWidget(help_text, 4, 0, 1, 2)
        for row, (label, url) in enumerate(
            (("Windows builds", DOWNLOAD_URL), ("Other platforms", OFFICIAL_URL)), start=5
        ):
            links = QHBoxLayout()
            link = QLabel(f'{label}: <a href="{url}">{url}</a>')
            link.setWordWrap(True)
            link.setOpenExternalLinks(True)
            links.addWidget(link, 1)
            copy = QPushButton("Copy link")
            copy.clicked.connect(lambda _, value=url: QApplication.clipboard().setText(value))
            links.addWidget(copy)
            grid.addLayout(links, row, 0, 1, 2)
        self.ffmpeg.textChanged.connect(self.update_tool_status)
        self.ffprobe.textChanged.connect(self.update_tool_status)
        self.update_tool_status()
        self.options.hide()
        self.mp4.toggled.connect(self.options.setVisible)
        layout.addWidget(self.options)
        self.start_button = QPushButton("Start screen recording…")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_recording)
        self.stop_button = QPushButton("Stop and finish")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop)
        self.cancel_button = QPushButton("Cancel; keep originals")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        buttons = QGridLayout()
        buttons.addWidget(self.start_button, 0, 0, 1, 2)
        buttons.addWidget(self.stop_button, 1, 0)
        buttons.addWidget(self.cancel_button, 1, 1)
        layout.addLayout(buttons)
        self.status = QLabel(
            "Requires a connected SLM. Limits: 1 hour / 3,600 frames / 512 MiB PNGs; stops at low disk space. External encoder is optional and is not bundled."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def update_tool_status(self):
        available = all(Path(edit.text().strip()).is_file() for edit in (self.ffmpeg, self.ffprobe))
        self.tool_status.setText(
            "Tool files found. Encoding will check libx264 and validate the MP4."
            if available
            else "FFmpeg / ffprobe is missing. Download and locate both tools below, "
            "or leave MP4 off to keep recording original PNGs."
        )

    def set_status(self, text):
        self.status.setText(text)
        self.activity.emit(text)

    def choose_tool(self, edit):
        path, _ = QFileDialog.getOpenFileName(self, "Choose external encoder/probe executable")
        if path:
            edit.setText(path)
            if edit is self.ffmpeg:
                candidate = Path(path).with_name("ffprobe" + Path(path).suffix)
                if candidate.is_file():
                    self.ffprobe.setText(str(candidate))
            self.settings.setValue("ffmpeg_path", self.ffmpeg.text())
            self.settings.setValue("ffprobe_path", self.ffprobe.text())

    def set_connected(self, connected):
        self.connected = connected
        self.start_button.setEnabled(connected and self.job is None)
        if not connected:
            self.stop("Connection ended or changed; originals retained")

    def start_recording(self, checked=False, *, parent_folder=None, sync_id=None):
        if self.job or not self.connected:
            return
        ffmpeg = self.ffmpeg.text().strip() if self.mp4.isChecked() else ""
        ffprobe = self.ffprobe.text().strip() if self.mp4.isChecked() else ""
        if self.mp4.isChecked() and not all(Path(p).is_file() for p in (ffmpeg, ffprobe)):
            self.set_status(
                "FFmpeg / ffprobe is missing. Use the download instructions and Browse buttons below, or turn off MP4 to save original frames only."
            )
            return
        folder = parent_folder or QFileDialog.getExistingDirectory(
            self, "Choose parent folder for a new recording", str(self.default_folder)
        )
        if not folder:
            return
        self.settings.setValue("ffmpeg_path", self.ffmpeg.text())
        self.settings.setValue("ffprobe_path", self.ffprobe.text())
        self.job = RecordingJob(
            folder,
            ffmpeg=str(Path(ffmpeg).resolve()) if ffmpeg else "",
            ffprobe=str(Path(ffprobe).resolve()) if ffprobe else "",
            profile=self.profile.currentText(),
            crf=self.crf.value(),
            sync_id=sync_id,
        )
        self.job.ready.connect(self.ready)
        self.job.progress.connect(self.set_status)
        self.job.result.connect(self.set_status)
        self.job.capture_ended.connect(self.capture_ended)
        self.job.finished.connect(self.finished)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.options.setEnabled(False)
        self.mp4.setEnabled(False)
        self.set_status("Preparing local recording folder…")
        self.job.start()

    def ready(self, folder):
        self.last_folder = folder
        self.set_status("Recording originals: " + folder)
        if self.job and not self.job.stop_capture.is_set() and self.connected:
            self.polling.emit(True)

    def submit(self, data, timing):
        job = self.job
        if job:
            job.submit(data, timing)

    def stop(self, reason="Stopped by user"):
        if self.job:
            self.job.stop(reason if isinstance(reason, str) else "Stopped by user")
            self.capture_ended()

    def cancel(self):
        if self.job:
            self.job.cancel()
            self.capture_ended()

    def capture_ended(self):
        self.polling.emit(False)
        self.stop_button.setEnabled(False)

    def finished(self):
        if hasattr(self, "last_folder"):
            self.saved.emit(self.last_folder)
        self.job.deleteLater()
        self.job = None
        self.start_button.setEnabled(self.connected)
        self.cancel_button.setEnabled(False)
        self.options.setEnabled(True)
        self.mp4.setEnabled(True)
        self.idle.emit()
