"""Local playback and cancellable media exports; no device communication."""

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from bnkg.core.media_export import export_media


class MediaJob(QThread):
    result = Signal(str, bool)

    def __init__(self, args, options):
        super().__init__()
        self.args, self.options = args, options

    def run(self):
        try:
            output = export_media(
                *self.args, **self.options, cancelled=self.isInterruptionRequested
            )
            self.result.emit(str(output), True)
        except Exception as exc:
            self.result.emit(str(exc), False)


class MediaPanel(QWidget):
    idle = Signal()

    def __init__(self, recording_panel, default_folder):
        super().__init__()
        self.recording_panel, self.default_folder = recording_panel, default_folder
        self.audio_path = None
        self.video_folder = None
        self.job = None
        self.closing = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("PLAYBACK AND MEDIA EXPORT")
        title.setObjectName("subheading")
        layout.addWidget(title)
        self.sources = QLabel(
            "Open a local recording or finish a capture. Nothing plays automatically."
        )
        self.sources.setWordWrap(True)
        layout.addWidget(self.sources)
        row = QHBoxLayout()
        open_audio = QPushButton("Open audio…")
        open_video = QPushButton("Select screen recording…")
        open_media = QPushButton("Play another media file…")
        open_audio.clicked.connect(self.choose_audio)
        open_video.clicked.connect(self.choose_video)
        open_media.clicked.connect(self.choose_playback)
        for item in (open_audio, open_video, open_media):
            row.addWidget(item)
        layout.addLayout(row)
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.output.setVolume(0.25)
        self.player.setAudioOutput(self.output)
        self.video = QVideoWidget(self)
        self.video.setMinimumHeight(160)
        self.player.setVideoOutput(self.video)
        self.video.hide()
        layout.addWidget(self.video)
        row = QHBoxLayout()
        self.play = QPushButton("Play")
        self.pause = QPushButton("Pause")
        self.stop_button = QPushButton("Stop playback")
        self.play.clicked.connect(self.player.play)
        self.pause.clicked.connect(self.player.pause)
        self.stop_button.clicked.connect(self.player.stop)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(25)
        self.volume.setMaximumWidth(120)
        self.volume.valueChanged.connect(lambda v: self.output.setVolume(v / 100))
        for item in (self.play, self.pause, self.stop_button, QLabel("Volume"), self.volume):
            row.addWidget(item)
        layout.addLayout(row)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderReleased.connect(lambda: self.player.setPosition(self.seek.value()))
        self.player.positionChanged.connect(self.position)
        self.player.durationChanged.connect(lambda d: self.seek.setRange(0, int(d)))
        self.player.seekableChanged.connect(self.seek.setEnabled)
        self.player.hasVideoChanged.connect(self.video.setVisible)
        self.player.errorOccurred.connect(
            lambda *a: self.status.setText("Playback: " + self.player.errorString())
        )
        layout.addWidget(self.seek)
        self.time_label = QLabel("0.0 / 0.0 s")
        layout.addWidget(self.time_label)
        row = QHBoxLayout()
        self.aac = QPushButton("Export AAC (.m4a)…")
        self.opus = QPushButton("Export Opus…")
        self.av = QPushButton("Export paired MP4…")
        self.cancel = QPushButton("Cancel export")
        self.aac.clicked.connect(lambda: self.start_export("aac"))
        self.opus.clicked.connect(lambda: self.start_export("opus"))
        self.av.clicked.connect(lambda: self.start_export("aac", paired=True))
        self.cancel.clicked.connect(self.cancel_export)
        for item in (self.aac, self.opus, self.av, self.cancel):
            row.addWidget(item)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.correction = QDoubleSpinBox()
        self.correction.setRange(-30000, 30000)
        self.correction.setDecimals(1)
        self.correction.setSuffix(" ms")
        row.addWidget(QLabel("A/V correction (+ delays audio):"))
        row.addWidget(self.correction)
        layout.addLayout(row)
        note = QLabel(
            "AAC/Opus are lossy and resampled to 48 kHz; originals remain unchanged. "
            "Paired MP4 uses estimated PC receipt-time alignment from one paired capture. "
            "Instrument/network/display latency is unknown; adjust the offset if needed. "
            "Silence fills periods without audio. No acoustic values are calculated. "
            "FFmpeg/ffprobe selections and download help are in the screen-recording controls above."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.status = QLabel("Ready. Playback uses the system audio device; volume starts at 25%.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.update_buttons()

    def position(self, value):
        if not self.seek.isSliderDown():
            self.seek.setValue(int(value))
        self.time_label.setText(f"{value / 1000:.1f} / {self.player.duration() / 1000:.1f} s")

    def update_buttons(self):
        ready = self.audio_path is not None and self.job is None and not self.closing
        self.aac.setEnabled(ready)
        self.opus.setEnabled(ready)
        self.av.setEnabled(ready and self.video_folder is not None)
        self.cancel.setEnabled(self.job is not None)
        playable = not self.player.source().isEmpty() and not self.closing
        for button in (self.play, self.pause, self.stop_button):
            button.setEnabled(playable)
        self.correction.setEnabled(self.job is None)

    def load_playback(self, path):
        if self.closing:
            return
        path = Path(path).resolve()
        if (
            path.suffix.lower() not in {".flac", ".wav", ".m4a", ".opus", ".mp3", ".mp4"}
            or not path.is_file()
        ):
            self.status.setText("Choose a supported local audio/video file.")
            return
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.status.setText("Loaded for playback: " + str(path))
        self.update_buttons()

    def choose_playback(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open local media",
            str(self.default_folder),
            "Media (*.flac *.wav *.m4a *.opus *.mp3 *.mp4)",
        )
        if path:
            self.load_playback(path)

    def choose_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open audio source",
            str(self.default_folder),
            "Audio (*.flac *.wav *.m4a *.opus *.mp3)",
        )
        if path:
            self.set_audio(path)

    def set_audio(self, path):
        self.audio_path = Path(path).resolve()
        self.load_playback(path)
        self.show_sources()

    def audio_saved(self, folder):
        path = Path(folder) / "audio.flac"
        if path.is_file():
            self.set_audio(path)

    def choose_video(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select finalized BnKG screen-recording folder", str(self.default_folder)
        )
        if folder:
            self.video_saved(folder)

    def video_saved(self, folder):
        self.video_folder = Path(folder).resolve()
        self.show_sources()

    def show_sources(self):
        self.sources.setText(
            f"Audio: {self.audio_path or 'none'}\nScreen recording: {self.video_folder or 'none'}"
        )
        self.update_buttons()

    def start_export(self, codec, paired=False):
        if self.job or not self.audio_path or self.closing:
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Choose parent folder for a new media export", str(self.default_folder)
        )
        if not folder:
            return
        self.job = MediaJob(
            (
                self.audio_path,
                folder,
                self.recording_panel.ffmpeg.text().strip(),
                self.recording_panel.ffprobe.text().strip(),
            ),
            {
                "codec": codec,
                "video_folder": self.video_folder if paired else None,
                "correction_ms": self.correction.value(),
            },
        )
        self.job.result.connect(self.export_result)
        self.job.finished.connect(self.finished)
        self.status.setText("Exporting in background; originals preserved…")
        self.update_buttons()
        self.job.start()

    def export_result(self, text, success):
        self.status.setText(("Saved: " if success else "Export stopped: ") + text)
        if success and not self.closing:
            self.load_playback(text)

    def cancel_export(self):
        if self.job:
            self.job.requestInterruption()

    def shutdown(self):
        self.closing = True
        self.player.stop()
        self.player.setSource(QUrl())
        self.cancel_export()
        self.update_buttons()

    def finished(self):
        self.job.deleteLater()
        self.job = None
        self.update_buttons()
        self.idle.emit()
