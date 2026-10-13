"""Explicit asynchronous instrument audio capture; no automatic measurement control."""

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.audio import AudioClient
from bnkg.core.audio_capture import capture_audio


class AudioJob(QThread):
    result = Signal(object)
    progress = Signal(str)

    def __init__(self, connection, options=None):
        super().__init__()
        self.connection, self.options = dict(connection), options

    def run(self):
        try:
            if self.options is None:
                client = AudioClient(**self.connection)
                try:
                    self.result.emit({"preview": client.inspect_audio()})
                finally:
                    client.close()
            else:
                folder, manifest = capture_audio(
                    self.connection,
                    **self.options,
                    cancelled=self.isInterruptionRequested,
                    progress=self.progress.emit,
                )
                self.result.emit({"folder": str(folder), "manifest": manifest})
        except Exception as exc:
            self.result.emit({"error": str(exc)})


class AudioPanel(QWidget):
    saved = Signal(str)
    idle = Signal()

    def __init__(self, default_folder, recording_panel=None):
        super().__init__()
        self.default_folder = default_folder
        self.recording_panel = recording_panel
        self.owns_recording = False
        if recording_panel:
            recording_panel.polling.connect(self.screen_polling)
        self.connection = None
        self.job = None
        self.preview = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("INSTRUMENT AUDIO")
        title.setObjectName("subheading")
        layout.addWidget(title)
        note = QLabel(
            "Records private FLAC audio separately from screen video. No measurement Start/Stop. "
            "Quality is unverified; audio is not a calibrated sound-level measurement. "
            "Sample rate is calculated from instrument timestamps and frame sample counts, with provenance saved. "
            "Original stream and timing are retained. Maximum 60 minutes or 192 MiB of stream data."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.inspect_button = QPushButton("Inspect audio")
        self.start_button = QPushButton("Capture FLAC…")
        self.stop_button = QPushButton("Stop audio")
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 60)
        self.minutes.setSuffix(" min")
        for item in (self.inspect_button, self.start_button, self.stop_button, self.minutes):
            row.addWidget(item)
        layout.addLayout(row)
        self.paired = QCheckBox("Pair audio with screen recording")
        self.paired.setEnabled(recording_panel is not None)
        layout.addWidget(self.paired)
        self.status = QLabel("Connect to an instrument, then inspect audio availability.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.inspect_button.clicked.connect(self.inspect_audio)
        self.start_button.clicked.connect(self.start_audio)
        self.stop_button.clicked.connect(self.stop)
        self.update_buttons()

    def screen_polling(self, active):
        if not active and self.owns_recording:
            self.stop()

    def set_connection(self, connection):
        if connection != self.connection:
            self.stop()
            self.preview = None
        self.connection = dict(connection) if connection else None
        self.update_buttons()

    def update_buttons(self):
        self.inspect_button.setEnabled(bool(self.connection) and self.job is None)
        self.start_button.setEnabled(bool(self.connection and self.preview) and self.job is None)
        self.stop_button.setEnabled(self.job is not None)
        self.minutes.setEnabled(self.job is None)
        self.paired.setEnabled(self.recording_panel is not None and self.job is None)

    def launch(self, options=None):
        self.job = AudioJob(self.connection, options)
        self.job.result.connect(self.receive)
        self.job.progress.connect(self.status.setText)
        self.job.finished.connect(self.finished)
        self.update_buttons()
        self.job.start()

    def inspect_audio(self):
        if self.connection and self.job is None:
            self.preview = None
            self.status.setText("Inspecting advertised audio settings and sequences…")
            self.launch()

    def start_audio(self):
        if not self.connection or not self.preview or self.job:
            return
        if self.paired.isChecked():
            panel = self.recording_panel
            if (
                panel.job
                or not panel.connected
                or not all(Path(p.text().strip()).is_file() for p in (panel.ffmpeg, panel.ffprobe))
            ):
                self.status.setText(
                    "Paired capture needs an idle connected screen recorder and FFmpeg/ffprobe. Check the tools above."
                )
                return
        enabled = any(s["format"] == "flac" for s in self.preview["sequences"])
        temporary = not enabled
        if temporary and (
            self.preview["state"] != "Activated"
            or self.preview["setup"].get("AudioRecordingAnalysisQuality") != 0
        ):
            self.status.setText(
                "No FLAC sequence. Temporary enable is available only when idle (Activated) and Analysis quality is Disabled."
            )
            return
        if temporary:
            if (
                QMessageBox.question(
                    self,
                    "Temporary instrument setting",
                    "Enable Analysis quality: Disabled → Continuous, then restore Disabled when capture ends? "
                    "This also enables instrument-side audio recording during measurement. B&KG will not start a measurement. "
                    "If the device disconnects or changes state, restoration may need your attention.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        if (
            QMessageBox.question(
                self,
                "Confirm private audio capture",
                "Create one receive-only audio stream and save local audio, which may contain conversations? "
                + (
                    "Confirm the temporary Analysis quality change and restoration."
                    if temporary
                    else "Existing audio settings will be preserved."
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Choose parent folder for private audio", str(self.default_folder)
        )
        if not folder:
            return
        sync_id = uuid4().hex if self.paired.isChecked() else None
        if sync_id:
            self.recording_panel.mp4.setChecked(True)
            self.recording_panel.start_recording(parent_folder=folder, sync_id=sync_id)
            if self.recording_panel.job is None:
                self.status.setText("Screen recording did not start; audio was not enabled.")
                return
            self.owns_recording = True
        self.status.setText("Preparing confirmed audio capture…")
        self.launch(
            {
                "parent": folder,
                "preview": self.preview,
                "temporary_analysis": temporary,
                "seconds": self.minutes.value() * 60,
                "sync_id": sync_id,
            }
        )

    def receive(self, result):
        if "preview" in result:
            if self.connection and self.job and not self.job.isInterruptionRequested():
                self.preview = result["preview"]
                self.status.setText(
                    f"State: {self.preview['state']} · {len(self.preview['sequences'])} audio sequence(s). Capture will preview any required temporary setting change."
                )
        elif "manifest" in result:
            self.preview = None
            m = result["manifest"]
            if m.get("audio", {}).get("startup_frames_omitted"):
                m["conversion_note"] = (
                    "One startup frame with an incompatible timestamp was omitted from playback; all original bytes are retained."
                )
            if m.get("status") == "complete":
                self.saved.emit(result["folder"])
            details = " · ".join(
                str(m[k])
                for k in (
                    "error",
                    "conversion_error",
                    "conversion_note",
                    "restore_error",
                    "cleanup_error",
                )
                if k in m
            )
            self.status.setText(
                f"Audio {m['status']}: {result['folder']}" + (" · " + details if details else "")
            )
            if m.get("restore_error") or m.get("cleanup_error"):
                QMessageBox.warning(self, "Instrument audio needs attention", details)
        else:
            self.status.setText("Audio: " + result.get("error", "Unknown result"))

    def stop(self):
        if self.job:
            self.job.requestInterruption()
            self.status.setText("Stopping audio and checking instrument restoration…")

    def finished(self):
        if self.owns_recording:
            self.recording_panel.stop("Paired audio capture ended")
            self.owns_recording = False
        self.job.deleteLater()
        self.job = None
        self.update_buttons()
        self.idle.emit()
