"""Original vector wordmarks and accessible project/support links."""

import sys
from html import escape

from PySide6.QtCore import QByteArray, Qt, Signal
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from bnkg import FULL_NAME, __version__

GITHUB = "https://github.com/GGadash/"
REPOSITORY = "https://github.com/GGadash/BnKG"
RELATED = "https://github.com/GGadash/HBKG"
DISCUSSIONS = REPOSITORY + "/discussions"
KOFI_PRODUCT = "https://ko-fi.com/s/06caf1c2f0"
KOFI = "https://ko-fi.com/gadash"
CONSTRUCTION = (
    "This app is under construction. Some information may be incomplete, delayed or "
    "displayed incorrectly. Double-check readings and settings on the instrument "
    "and against its official documentation. Updates and related releases: "
)
LINKS = (
    ("Developer GitHub", GITHUB),
    ("B&KG project and releases", REPOSITORY),
    ("HBKG related edition", RELATED),
    ("Questions and discussions", DISCUSSIONS),
    ("Support the developer on Ko-fi", KOFI),
    ("B&KG / HBKG product on Ko-fi", KOFI_PRODUCT),
)
WORDMARK = b"""<svg xmlns="http://www.w3.org/2000/svg" width="920" height="155" viewBox="0 0 920 155">
<rect width="920" height="155" rx="4" fill="#21352b"/>
<path d="M24 132H896 M24 22V132" stroke="#617d68" fill="none"/>
<path d="M650 125V95h18v30m12 0V71h18v54m12 0V47h18v78m12 0V82h18v43m12 0V108h18v17" stroke="#a3c88d" stroke-width="4" fill="none"/>
<g font-family="Segoe UI, sans-serif" font-weight="700" fill="#c7dfb3">
<text x="45" y="87" font-size="64">HBK<tspan font-size="34" fill="#d4a366">-</tspan>G</text>
<text x="352" y="81" font-size="46">H<tspan font-size="25" fill="#d4a366">-</tspan>B<tspan font-size="25" fill="#d4a366">&amp;</tspan>K<tspan font-size="25" fill="#d4a366">-</tspan>G</text>
</g><text x="47" y="117" font-size="12" letter-spacing="3" font-family="Segoe UI, sans-serif" fill="#b7c6ba">INDEPENDENT SOUND LEVEL METER STUDIO / GADASH</text></svg>"""


def construction_banner():
    text = QLabel(CONSTRUCTION + f'<a href="{GITHUB}">{GITHUB}</a>')
    text.setWordWrap(True)
    text.setOpenExternalLinks(True)
    text.setObjectName("construction")
    return text


class AboutPage(QWidget):
    help_requested = Signal()

    def __init__(self, disclaimer):
        super().__init__()
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        layout = QVBoxLayout(content)
        layout.addWidget(construction_banner())
        art = QSvgWidget()
        art.load(QByteArray(WORDMARK))
        art.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        art.setFixedHeight(120)
        art.setAccessibleName("B&KG — original independent wordmark artwork")
        layout.addWidget(art)
        improvement = QLabel(
            "B&KG = BnKG. Visit the project on GitHub for releases, source code and improvements. You are welcome to contribute fixes and ideas. Explore the developer page for similar releases and help improve those projects too. Look for HBKG, a related edition with more features; availability depends on its repository access. Use Discussions for questions and feedback. Optional support and the B&KG / HBKG product are linked below."
        )
        improvement.setWordWrap(True)
        layout.addWidget(improvement)
        self.feedback = QLabel("")
        for title, url in LINKS:
            row = QHBoxLayout()
            link = QLabel(f'{title}: <a href="{url}">{url}</a>')
            link.setOpenExternalLinks(True)
            link.setWordWrap(True)
            row.addWidget(link, 1)
            copy = QPushButton("⧉ Copy link")
            copy.setAccessibleName("Copy " + title + " link")
            copy.clicked.connect(lambda checked=False, value=url: self.copy_link(value))
            row.addWidget(copy)
            layout.addLayout(row)
        layout.addWidget(self.feedback)
        help_button = QPushButton("Workflow help and current capabilities")
        help_button.clicked.connect(self.help_requested.emit)
        layout.addWidget(help_button)
        text = QTextBrowser()
        text.setOpenExternalLinks(True)
        text.setMinimumHeight(420)
        build = (
            ("Windows executable" if sys.platform == "win32" else "Linux executable")
            if getattr(sys, "frozen", False)
            else "Python source"
        )
        text.setHtml(f"""<h2>B&amp;KG · {__version__}</h2><p>{escape(FULL_NAME)}</p><p>Build: {build} · Release channel: development alpha. Source and release notes: github.com/GGadash/BnKG.</p><p>{escape(disclaimer)}</p>
        <h3>Getting started</h3><p>Use Connection to type or discover the current SLM address. SLM Screen is second in navigation. Dashboard and Frequency Analysis show SLM values; Metadata lets you select instrument fields. Demo Lab is separate. Local capture and logging are optional in Data table. Python 3.12 minimum; install the dependencies in RUN_PYTHON.md.</p>
        <h3>Safety and limitations</h3><p>Arm SLM controls only for a deliberate action. Routine Start/Pause/Stop do not repeat confirmation dialogs once controls are armed; reviewed setting changes retain appropriate confirmations. Identify briefly lights the display and light ring; it is not a guaranteed power wake. No automatic action retry. Calibration/service and generic settings writes remain blocked. Metadata offers a guarded location-text transfer to an already enabled slot; it does not update native GPS. No verified GPS-coordinate injection or project-name setter is provided. Displayed information can be incomplete, delayed or incorrect. Double-check values, units, configuration and interpretation on the physical SLM and in its official documentation before relying on them. This software does not establish measurement or regulatory compliance.</p>
        <h3>Current source capabilities</h3><p>Direct instrument Frequency with current/cumulative/verified-interval labels, frozen and saved sources; isolated Demo; read-only session history; independent exports including basic HTML; original-file downloads; local screen viewing/recording and optional external FFmpeg. Short 2255 live recording and external encoder checks passed; long-run, physical sleep/wake and other-model/platform acceptance remain pending. Limited validated 2255 BKC totals, FLAC capture, playback and optional AAC/Opus/estimated paired MP4 exports are available. Automatic PC/phone location, native GPS/marker uploads and PDF/DOCX reports remain unavailable.</p>
        <p>Connection provides locally assembled support summaries with device identity omitted by default. Metadata separates received instrument fields, local report drafts and the existing guarded location transfer. Local report details apply to new logs only.</p>
        <h3>Credits and licences</h3><p>Original B&KG code and wordmark artwork: MIT, Copyright © 2026 Gadash (Akila DJ). Provided without warranty; retain required notices in copies and forks. Created by Gadash (Akila DJ), using OpenAI (Sol 5.6, Astra 6.0, etc), ChatGPT and Codex.</p>
        <h3>Tools used</h3><p>Runtime and interface: Python, Qt/PySide6. Instrument HTTP: Requests. Charts and numeric data: NumPy and pyqtgraph. Local storage: SQLite. Spreadsheet export: openpyxl. Network discovery: zeroconf and ifaddr. Development checks: pytest, pytest-qt and Ruff; local version history: Git.</p><p>These third-party components retain their own licences. See THIRD_PARTY_NOTICES.md and third-party-licenses. No manufacturer artwork is included.</p>
        <h3>Privacy</h3><p>Local sessions and preferences. No telemetry, cloud account or automatic update check. Measurement files can contain location and operator information; review before sharing.</p>
        <h3>Documentation</h3><p>See CONNECTION_GUIDE.md, docs/METADATA_CAPABILITIES.md, RUN_PYTHON.md and README-INFO.md in the project. Editions include Python Portable, Windows executable Portable and Standalone EXE, and Ubuntu Linux Portable; check repository releases for availability and validation. See Readme-info-which-relese-to-get.txt for requirements and differences.</p>""")
        layout.addWidget(text, 1)

    def copy_link(self, url):
        QApplication.clipboard().setText(url)
        self.feedback.setText("Link copied to clipboard")
