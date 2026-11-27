"""StereoForge Modern Desktop GUI (Qt 6 / PySide6).

Imagined by writesimply.bcc • Coded by Gemini
"""

import sys
from pathlib import Path
from typing import Optional, Dict, List, Any

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFileDialog, QSlider, QComboBox, QCheckBox,
        QProgressBar, QTextEdit, QGroupBox, QSplitter, QLineEdit,
        QScrollArea, QFrame, QSizePolicy, QTabWidget, QTableWidget,
        QTableWidgetItem, QHeaderView, QAbstractItemView
    )
    from PySide6.QtCore import Qt, QThread, Signal, QSettings
    from PySide6.QtGui import QIcon, QFont, QColor, QClipboard
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False

from stereoforge import __version__
from stereoforge.pipeline.orchestrator import StereoForgePipeline, EncodeJob, BatchProgress, JobResult
from stereoforge.pipeline.ingest import IngestionEngine, StereoFormat, find_matching_eye_file
from stereoforge.pipeline.pass1_base import detect_best_h264_encoder
from stereoforge.pipeline.muxer import find_tsmuxer
from stereoforge.cli import scan_batch_jobs
from stereoforge_core.python.native_bridge import NativeMVCEngine
from stereoforge.ui.preview import AnaglyphPreviewDialog


THEMES: Dict[str, Dict[str, str]] = {
    # Light Themes (4 Options)
    "☀️ Clean Light": {
        "bg": "#F8FAFC",
        "card_bg": "#FFFFFF",
        "input_bg": "#F1F5F9",
        "border": "#CBD5E1",
        "accent": "#0284C7",
        "accent_hover": "#0369A1",
        "text": "#0F172A",
        "text_dim": "#64748B",
        "header_color": "#0284C7",
        "btn_text": "#FFFFFF",
        "console_bg": "#0F172A",
        "console_text": "#38BDF8",
    },
    "🏛️ Nordic Frost": {
        "bg": "#EDF2F7",
        "card_bg": "#FFFFFF",
        "input_bg": "#E2E8F0",
        "border": "#CBD5E0",
        "accent": "#3182CE",
        "accent_hover": "#2B6CB0",
        "text": "#1A202C",
        "text_dim": "#718096",
        "header_color": "#2B6CB0",
        "btn_text": "#FFFFFF",
        "console_bg": "#1A202C",
        "console_text": "#63B3ED",
    },
    "🌅 Warm Sandstone": {
        "bg": "#FAF7F2",
        "card_bg": "#FFFFFF",
        "input_bg": "#F3EFE6",
        "border": "#E6DFD3",
        "accent": "#D97706",
        "accent_hover": "#B45309",
        "text": "#292524",
        "text_dim": "#78716C",
        "header_color": "#B45309",
        "btn_text": "#FFFFFF",
        "console_bg": "#292524",
        "console_text": "#FBBF24",
    },
    "🌿 Mint Paper": {
        "bg": "#F2F9F5",
        "card_bg": "#FFFFFF",
        "input_bg": "#E6F4EC",
        "border": "#CCE7D8",
        "accent": "#059669",
        "accent_hover": "#047857",
        "text": "#064E3B",
        "text_dim": "#4B7B6B",
        "header_color": "#047857",
        "btn_text": "#FFFFFF",
        "console_bg": "#064E3B",
        "console_text": "#34D399",
    },
    # Dark Themes (4 Options)
    "🌌 Cyber Neon": {
        "bg": "#0B132B",
        "card_bg": "#141D38",
        "input_bg": "#1C2541",
        "border": "#2E3B5B",
        "accent": "#00F5FF",
        "accent_hover": "#38BDF8",
        "text": "#E2E8F0",
        "text_dim": "#8D99AE",
        "header_color": "#00F5FF",
        "btn_text": "#0B132B",
        "console_bg": "#080E20",
        "console_text": "#00F5FF",
    },
    "🎬 Studio Slate": {
        "bg": "#1E222B",
        "card_bg": "#252B37",
        "input_bg": "#2F3646",
        "border": "#3E4759",
        "accent": "#4D96FF",
        "accent_hover": "#6BA6FF",
        "text": "#F1F5F9",
        "text_dim": "#94A3B8",
        "header_color": "#60A5FA",
        "btn_text": "#FFFFFF",
        "console_bg": "#171A21",
        "console_text": "#93C5FD",
    },
    "🌘 Midnight OLED": {
        "bg": "#000000",
        "card_bg": "#0F0F0F",
        "input_bg": "#181818",
        "border": "#2E2E2E",
        "accent": "#38BDF8",
        "accent_hover": "#60A5FA",
        "text": "#FFFFFF",
        "text_dim": "#A3A3A3",
        "header_color": "#38BDF8",
        "btn_text": "#000000",
        "console_bg": "#080808",
        "console_text": "#38BDF8",
    },
    "⚡ Obsidian Amber": {
        "bg": "#18181B",
        "card_bg": "#202024",
        "input_bg": "#27272A",
        "border": "#3F3F46",
        "accent": "#F59E0B",
        "accent_hover": "#FBBF24",
        "text": "#F4F4F5",
        "text_dim": "#A1A1AA",
        "header_color": "#F59E0B",
        "btn_text": "#18181B",
        "console_bg": "#101012",
        "console_text": "#FCD34D",
    }
}


class WorkerThread(QThread if HAS_PYSIDE6 else object):
    """Background worker for non-blocking encoding."""
    if HAS_PYSIDE6:
        progress_signal = Signal(str, float)
        finished_signal = Signal(bool, str)

    def __init__(self, job: EncodeJob):
        if HAS_PYSIDE6:
            super().__init__()
        self.job = job

    def run(self):
        pipeline = StereoForgePipeline()
        def on_progress(msg: str, pct: float):
            if HAS_PYSIDE6:
                self.progress_signal.emit(msg, pct)

        try:
            success = pipeline.run(self.job, progress_cb=on_progress)
            if HAS_PYSIDE6:
                self.finished_signal.emit(success, str(self.job.output_file))
        except Exception as e:
            if HAS_PYSIDE6:
                self.progress_signal.emit(f"❌ Error during encode: {e}", 0.0)
                self.finished_signal.emit(False, str(e))


class BatchWorkerThread(QThread if HAS_PYSIDE6 else object):
    """Background worker for batch queue processing."""
    if HAS_PYSIDE6:
        batch_progress_signal = Signal(object)
        job_progress_signal = Signal(int, str, float)
        batch_finished_signal = Signal(list)

    def __init__(self, jobs):
        if HAS_PYSIDE6:
            super().__init__()
        self.jobs = jobs
        self.pipeline = StereoForgePipeline()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        def on_batch_prog(bp: BatchProgress):
            if HAS_PYSIDE6 and not self._is_cancelled:
                self.batch_progress_signal.emit(bp)

        def on_job_prog(msg: str, pct: float):
            pass

        try:
            results = self.pipeline.run_batch(
                self.jobs,
                batch_progress_cb=on_batch_prog,
                job_progress_cb=on_job_prog,
                stop_on_error=False
            )
            if HAS_PYSIDE6:
                self.batch_finished_signal.emit(results)
        except Exception as e:
            if HAS_PYSIDE6:
                self.batch_finished_signal.emit([])


class StereoForgeWindow(QMainWindow if HAS_PYSIDE6 else object):
    """Main Application Window for StereoForge."""

    def __init__(self):
        if not HAS_PYSIDE6:
            raise RuntimeError("PySide6 is required to run the graphical interface.")
        super().__init__()

        self.settings = QSettings("StereoForge", "StereoForgeGUI")
        self.setWindowTitle(f"StereoForge v{__version__} - Stereoscopic 3D MVC Suite")
        self.resize(1200, 780)
        self.setMinimumSize(960, 640)

        self.input_file: Optional[Path] = None
        self.right_file: Optional[Path] = None
        self.worker: Optional[WorkerThread] = None

        self.batch_jobs = []
        self.batch_worker = None

        self.init_ui()

        # Load persisted theme (Default: ☀️ Clean Light)
        saved_theme = self.settings.value("theme", "☀️ Clean Light")
        if saved_theme in THEMES:
            idx = list(THEMES.keys()).index(saved_theme)
            self.theme_combo.setCurrentIndex(idx)
            self.apply_theme(saved_theme)
        else:
            self.apply_theme("☀️ Clean Light")

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        root_layout = QVBoxLayout(main_widget)
        root_layout.setSpacing(10)
        root_layout.setContentsMargins(16, 14, 16, 14)

        # Top Bar: Header + Theme Switcher
        top_bar = QHBoxLayout()
        header_vbox = QVBoxLayout()
        header_vbox.setSpacing(2)

        self.header_label = QLabel("StereoForge")
        self.header_label.setFont(QFont("Segoe UI", 22, QFont.Bold))
        header_vbox.addWidget(self.header_label)

        self.subhead_label = QLabel("Imagined by writesimply.bcc • Coded by Gemini")
        self.subhead_label.setFont(QFont("Segoe UI", 10))
        header_vbox.addWidget(self.subhead_label)
        top_bar.addLayout(header_vbox, stretch=1)

        # Theme Selector in Top Bar
        theme_box = QHBoxLayout()
        theme_lbl = QLabel("🎨 Theme:")
        theme_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES.keys()))
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        self.theme_combo.setFixedWidth(165)
        theme_box.addWidget(theme_lbl)
        theme_box.addWidget(self.theme_combo)
        top_bar.addLayout(theme_box)

        root_layout.addLayout(top_bar)

        # Hardware & Native Engine Status Bar
        engine_bar = QHBoxLayout()
        engine_bar.setSpacing(10)

        hw_enc = detect_best_h264_encoder()
        gpu_badge = f"⚡ GPU: {hw_enc.upper()} Active" if hw_enc != "libx264" else "💻 CPU: libx264"
        self.gpu_status_lbl = QLabel(gpu_badge)
        self.gpu_status_lbl.setStyleSheet("background: rgba(34, 197, 94, 0.15); color: #16A34A; font-weight: bold; font-size: 11px; padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(34, 197, 94, 0.3);")

        c_available = NativeMVCEngine.is_available()
        c_badge = "⚡ stereoforge-core (C/C++): Active" if c_available else "⚠️ stereoforge-core: Inactive"
        self.c_status_lbl = QLabel(c_badge)
        self.c_status_lbl.setStyleSheet("background: rgba(14, 165, 233, 0.15); color: #0284C7; font-weight: bold; font-size: 11px; padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(14, 165, 233, 0.3);")

        tsmuxer_bin = find_tsmuxer()
        import shutil
        ts_ok = shutil.which(tsmuxer_bin) is not None or Path(tsmuxer_bin).is_file()
        ts_badge = "💿 tsMuxeR: Ready (3D BD / ISO)" if ts_ok else "💿 tsMuxeR: Not Found"
        self.ts_status_lbl = QLabel(ts_badge)
        self.ts_status_lbl.setStyleSheet("background: rgba(168, 85, 247, 0.15); color: #9333EA; font-weight: bold; font-size: 11px; padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(168, 85, 247, 0.3);")

        engine_bar.addWidget(self.gpu_status_lbl)
        engine_bar.addWidget(self.c_status_lbl)
        engine_bar.addWidget(self.ts_status_lbl)
        engine_bar.addStretch()

        root_layout.addLayout(engine_bar)

        # Main Splitter (Left Column ~50%, Right Column ~50%)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # ==========================================
        # LEFT COLUMN: Pipeline Configuration
        # ==========================================
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(10)

        # 1. Input 3D Media Box
        drop_box = QGroupBox("📁 1. Input 3D Media")
        drop_layout = QVBoxLayout(drop_box)
        drop_layout.setSpacing(8)

        file_row = QHBoxLayout()
        self.file_label = QLabel("Left Eye: No file selected")
        self.file_label.setStyleSheet("font-size: 13px; font-weight: 500;")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        file_row.addWidget(self.file_label, stretch=1)
        file_row.addWidget(browse_btn)
        drop_layout.addLayout(file_row)

        right_row = QHBoxLayout()
        self.right_file_label = QLabel("Right Eye: (Auto-detected or packed)")
        self.right_file_label.setStyleSheet("font-size: 12px;")
        browse_right_btn = QPushButton("Browse Right...")
        browse_right_btn.clicked.connect(self.browse_right_file)
        right_row.addWidget(self.right_file_label, stretch=1)
        right_row.addWidget(browse_right_btn)
        drop_layout.addLayout(right_row)

        layout_row = QHBoxLayout()
        layout_row.addWidget(QLabel("3D Layout:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems([
            "Auto-Detect (Aspect ratio & filename)",
            "Side-by-Side (SBS / Half-SBS / 4K SBS)",
            "Top-and-Bottom (TAB / Over-Under / 4K TAB)",
            "Separate Left & Right Files (Dual Files)"
        ])
        layout_row.addWidget(self.layout_combo, stretch=1)
        drop_layout.addLayout(layout_row)

        preview_row = QHBoxLayout()
        self.preview_btn = QPushButton("👓 Preview 3D Anaglyph (Check Eye Orientation)")
        self.preview_btn.setFixedHeight(34)
        self.preview_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.preview_btn.clicked.connect(self.open_anaglyph_preview)
        preview_row.addWidget(self.preview_btn)
        drop_layout.addLayout(preview_row)

        left_layout.addWidget(drop_box)

        # 2. Encoding Profile & Bitrate Box
        settings_box = QGroupBox("⚙️ 2. Encoding Profile & Bitrate")
        set_layout = QVBoxLayout(settings_box)
        set_layout.setSpacing(8)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "VR & Home Streaming (CRF / 20 Mbps) - Recommended",
            "Strict BD-50 Disc (40 Mbps VBV Cap)",
            "Strict BD-25 Disc (23 Mbps VBV Cap)",
            "Custom / Uncapped Bitrate"
        ])
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        preset_row.addWidget(self.preset_combo, stretch=1)
        set_layout.addLayout(preset_row)

        slider_row = QHBoxLayout()
        self.bitrate_label = QLabel("Target Bitrate: 35 Mbps (Left: 24.5 Mbps | Right: 10.5 Mbps)")
        slider_row.addWidget(self.bitrate_label)
        set_layout.addLayout(slider_row)

        self.bitrate_slider = QSlider(Qt.Horizontal)
        self.bitrate_slider.setRange(5, 120)
        self.bitrate_slider.setValue(35)
        self.bitrate_slider.valueChanged.connect(self.on_bitrate_changed)
        set_layout.addWidget(self.bitrate_slider)

        engine_row = QHBoxLayout()
        engine_row.addWidget(QLabel("Engine Mode:"))
        self.engine_mode_combo = QComboBox()
        self.engine_mode_combo.addItems([
            "🔬 True MVC Inter-View Engine (stereoforge-core) - Recommended",
            "🚀 GPU Hardware Turbo (Fastest Simulcast, No Inter-View Savings)"
        ])
        engine_row.addWidget(self.engine_mode_combo, stretch=1)
        set_layout.addLayout(engine_row)

        opts_row = QHBoxLayout()
        self.auto_fix_inverted_cb = QCheckBox("Auto-Fix Inverted Eyes")
        self.auto_fix_inverted_cb.setChecked(True)
        self.auto_fix_inverted_cb.setToolTip("Automatically tests stereoscopic convergence and flips reversed channels")
        self.swap_eyes_cb = QCheckBox("Force Swap Eyes")
        self.bluray_cap_cb = QCheckBox("Strict Blu-ray VBV Cap (Max 40 Mbps)")
        self.bluray_cap_cb.setChecked(False)
        opts_row.addWidget(self.auto_fix_inverted_cb)
        opts_row.addWidget(self.swap_eyes_cb)
        opts_row.addWidget(self.bluray_cap_cb)
        opts_row.addStretch()
        set_layout.addLayout(opts_row)

        left_layout.addWidget(settings_box)

        # 3. Output Destination & Metadata Box
        output_box = QGroupBox("💾 3. Output Settings & Destination")
        out_layout = QVBoxLayout(output_box)
        out_layout.setSpacing(8)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Output Container:"))
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems([
            "3D MVC Matroska (.mkv) — Meta Quest, Vision Pro, 4XVR, VLC",
            "3D Blu-ray ISO (.iso) — Physical 3D Disc & Projectors (tsMuxeR)",
            "3D Blu-ray Folder (BDMV) — Directory Structure (tsMuxeR)"
        ])
        self.output_format_combo.currentIndexChanged.connect(self.on_output_format_changed)
        fmt_row.addWidget(self.output_format_combo, stretch=1)
        out_layout.addLayout(fmt_row)

        self.format_note_lbl = QLabel("💡 Matroska (.mkv): Universal dual-track/MVC for Quest, Vision Pro, 4XVR, VLC. Supports arbitrary framerates (24, 30, 48, 60 fps).")
        self.format_note_lbl.setWordWrap(True)
        self.format_note_lbl.setStyleSheet("font-size: 11px; color: #64748B; padding: 2px 4px;")
        out_layout.addWidget(self.format_note_lbl)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Save To:"))
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select input file or click Browse...")
        browse_out_btn = QPushButton("Browse...")
        browse_out_btn.clicked.connect(self.browse_output_file)
        dest_row.addWidget(self.output_path_edit, stretch=1)
        dest_row.addWidget(browse_out_btn)
        out_layout.addLayout(dest_row)

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("Title (Optional):"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Leave blank to display filename in players...")
        title_row.addWidget(self.title_edit, stretch=1)
        out_layout.addLayout(title_row)

        left_layout.addWidget(output_box)
        left_layout.addStretch()

        # Wrap left side in a scroll area to guarantee nothing ever gets clipped
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setWidget(left_container)
        splitter.addWidget(left_scroll)

        # ==========================================
        # RIGHT COLUMN: Action & Real-Time Monitor
        # ==========================================
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)

        monitor_box = QGroupBox("🚀 4. Process & Real-Time Monitor")
        mon_layout = QVBoxLayout(monitor_box)
        mon_layout.setSpacing(10)

        # Giant Start Button
        self.start_btn = QPushButton("🚀 Start 3D Encode")
        self.start_btn.setFixedHeight(50)
        self.start_btn.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self.start_encode)
        mon_layout.addWidget(self.start_btn)

        # Status Label + Progress Bar
        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: Ready to encode")
        self.status_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        status_row.addWidget(self.status_label)
        mon_layout.addLayout(status_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(26)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        mon_layout.addWidget(self.progress_bar)

        # Console Header + Action Buttons
        log_header = QHBoxLayout()
        log_lbl = QLabel("Execution Log:")
        log_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        log_header.addWidget(log_lbl)
        log_header.addStretch()

        copy_btn = QPushButton("📋 Copy Log")
        copy_btn.setFixedHeight(26)
        copy_btn.clicked.connect(self.copy_log)
        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self.clear_log)
        log_header.addWidget(copy_btn)
        log_header.addWidget(clear_btn)
        mon_layout.addLayout(log_header)

        # Expandable Real-Time Console Log
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 10))
        self.console.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        mon_layout.addWidget(self.console, stretch=1)

        right_layout.addWidget(monitor_box)
        splitter.addWidget(right_container)

        # 50/50 initial proportion
        splitter.setSizes([550, 550])

        # Main Tab Widget (Single File vs Batch Queue)
        self.tab_widget = QTabWidget()

        # Tab 1: Single File
        single_tab = QWidget()
        single_layout = QVBoxLayout(single_tab)
        single_layout.setContentsMargins(0, 8, 0, 0)
        single_layout.addWidget(splitter)
        self.tab_widget.addTab(single_tab, "🎬 Single File")

        # Tab 2: Batch Queue
        batch_tab = self.create_batch_tab()
        self.tab_widget.addTab(batch_tab, "📋 Batch Queue")

        root_layout.addWidget(self.tab_widget, stretch=1)

    def create_batch_tab(self) -> QWidget:
        batch_widget = QWidget()
        batch_layout = QVBoxLayout(batch_widget)
        batch_layout.setSpacing(10)
        batch_layout.setContentsMargins(0, 8, 0, 0)

        # Batch Toolbar
        batch_top_bar = QHBoxLayout()
        batch_top_bar.setSpacing(8)

        add_files_btn = QPushButton("➕ Add Video Files...")
        add_files_btn.clicked.connect(self.batch_add_files)
        add_folder_btn = QPushButton("📂 Add Folder...")
        add_folder_btn.clicked.connect(self.batch_add_folder)
        remove_btn = QPushButton("❌ Remove Selected")
        remove_btn.clicked.connect(self.batch_remove_selected)
        clear_btn = QPushButton("🧹 Clear All")
        clear_btn.clicked.connect(self.batch_clear_all)

        batch_top_bar.addWidget(add_files_btn)
        batch_top_bar.addWidget(add_folder_btn)
        batch_top_bar.addWidget(remove_btn)
        batch_top_bar.addWidget(clear_btn)
        batch_top_bar.addSpacing(16)

        # Batch settings: Format, Engine, Bitrate, Auto-Fix
        fmt_lbl = QLabel("Format:")
        self.batch_fmt_combo = QComboBox()
        self.batch_fmt_combo.addItems(["3D Matroska (.mkv)", "3D Blu-ray ISO (.iso)"])
        self.batch_fmt_combo.currentIndexChanged.connect(self.on_batch_settings_changed)

        eng_lbl = QLabel("Engine:")
        self.batch_eng_combo = QComboBox()
        self.batch_eng_combo.addItems(["True MVC (stereoforge-core)", "GPU Hardware Turbo"])
        self.batch_eng_combo.currentIndexChanged.connect(self.on_batch_settings_changed)

        bitrate_lbl = QLabel("Bitrate:")
        self.batch_bitrate_combo = QComboBox()
        self.batch_bitrate_combo.addItems(["20 Mbps (VR)", "23 Mbps (BD-25)", "35 Mbps (Standard)", "40 Mbps (BD-50)"])
        self.batch_bitrate_combo.setCurrentIndex(2)
        self.batch_bitrate_combo.currentIndexChanged.connect(self.on_batch_settings_changed)

        self.batch_auto_fix_cb = QCheckBox("Auto-Fix Inverted Eyes")
        self.batch_auto_fix_cb.setChecked(True)
        self.batch_auto_fix_cb.stateChanged.connect(self.on_batch_settings_changed)

        batch_top_bar.addWidget(fmt_lbl)
        batch_top_bar.addWidget(self.batch_fmt_combo)
        batch_top_bar.addWidget(eng_lbl)
        batch_top_bar.addWidget(self.batch_eng_combo)
        batch_top_bar.addWidget(bitrate_lbl)
        batch_top_bar.addWidget(self.batch_bitrate_combo)
        batch_top_bar.addWidget(self.batch_auto_fix_cb)
        batch_top_bar.addStretch()

        batch_layout.addLayout(batch_top_bar)

        # Table Widget
        self.batch_table = QTableWidget()
        self.batch_table.setColumnCount(7)
        self.batch_table.setHorizontalHeaderLabels([
            "#", "Status", "Input Media", "3D Format", "Audio Streams", "Engine", "Target Output"
        ])
        self.batch_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.batch_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.batch_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.batch_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.batch_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.batch_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.batch_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.batch_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.batch_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        batch_layout.addWidget(self.batch_table, stretch=1)

        # Bottom Batch Monitor & Action Area
        bottom_box = QVBoxLayout()
        bottom_box.setSpacing(6)

        status_row = QHBoxLayout()
        self.batch_status_lbl = QLabel("Batch Queue: 0 jobs queued (Idle)")
        self.batch_status_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        status_row.addWidget(self.batch_status_lbl)
        status_row.addStretch()

        self.batch_open_output_btn = QPushButton("📂 Open Output Folder")
        self.batch_open_output_btn.setEnabled(False)
        self.batch_open_output_btn.clicked.connect(self.open_batch_output_folder)
        status_row.addWidget(self.batch_open_output_btn)
        bottom_box.addLayout(status_row)

        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setFixedHeight(24)
        self.batch_progress_bar.setRange(0, 100)
        self.batch_progress_bar.setValue(0)
        bottom_box.addWidget(self.batch_progress_bar)

        btn_row = QHBoxLayout()
        self.batch_start_btn = QPushButton("🚀 Start Batch Queue")
        self.batch_start_btn.setFixedHeight(44)
        self.batch_start_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.batch_start_btn.clicked.connect(self.start_batch_encode)
        btn_row.addWidget(self.batch_start_btn, stretch=3)

        self.batch_stop_btn = QPushButton("⏹️ Cancel Batch")
        self.batch_stop_btn.setFixedHeight(44)
        self.batch_stop_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.batch_stop_btn.setEnabled(False)
        self.batch_stop_btn.clicked.connect(self.stop_batch_encode)
        btn_row.addWidget(self.batch_stop_btn, stretch=1)

        bottom_box.addLayout(btn_row)
        batch_layout.addLayout(bottom_box)

        return batch_widget

    def batch_add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select 3D Video Files for Batch Queue",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.mts *.m2ts *.ts)"
        )
        if not paths:
            return

        output_format = "mkv" if self.batch_fmt_combo.currentIndex() == 0 else "iso"
        engine_mode = "native_mvc" if self.batch_eng_combo.currentIndex() == 0 else "gpu_turbo"
        bitrates = [20, 23, 35, 40]
        bitrate = bitrates[self.batch_bitrate_combo.currentIndex()]
        auto_fix = self.batch_auto_fix_cb.isChecked()

        for p_str in paths:
            p = Path(p_str)
            if any(j.input_file == p for j in self.batch_jobs):
                continue

            matched_right = find_matching_eye_file(p)
            paired = None
            if matched_right and matched_right.exists() and matched_right != p:
                paired = matched_right

            out_dir = p.parent / "StereoForge_Output"
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = p.stem.replace("_left", "").replace("_Left", "").replace("_L", "")
            out_file = out_dir / f"{stem}_3D.{output_format}"

            job = EncodeJob(
                input_file=p,
                output_file=out_file,
                right_file=paired,
                target_bitrate_mbps=bitrate,
                strict_bluray=(output_format == "iso" or bitrate in (23, 40)),
                auto_detect_inverted_eyes=auto_fix,
                engine_mode=engine_mode
            )
            self.batch_jobs.append(job)

        self.refresh_batch_table()

    def batch_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Containing 3D Videos")
        if not folder:
            return

        folder_path = Path(folder)
        output_format = "mkv" if self.batch_fmt_combo.currentIndex() == 0 else "iso"
        engine_mode = "native_mvc" if self.batch_eng_combo.currentIndex() == 0 else "gpu_turbo"
        bitrates = [20, 23, 35, 40]
        bitrate = bitrates[self.batch_bitrate_combo.currentIndex()]
        auto_fix = self.batch_auto_fix_cb.isChecked()
        out_dir = folder_path / "StereoForge_Output"
        out_dir.mkdir(parents=True, exist_ok=True)

        scanned = scan_batch_jobs(
            batch_dir=folder_path,
            output_dir=out_dir,
            output_format=output_format,
            bitrate=bitrate,
            strict_bluray=(output_format == "iso" or bitrate in (23, 40)),
            auto_detect_inverted_eyes=auto_fix,
            engine_mode=engine_mode
        )
        for job in scanned:
            if not any(j.input_file == job.input_file for j in self.batch_jobs):
                self.batch_jobs.append(job)

        self.refresh_batch_table()

    def batch_remove_selected(self):
        selected_rows = sorted(set(idx.row() for idx in self.batch_table.selectedIndexes()), reverse=True)
        for row in selected_rows:
            if 0 <= row < len(self.batch_jobs):
                del self.batch_jobs[row]
        self.refresh_batch_table()

    def batch_clear_all(self):
        if self.batch_worker and self.batch_worker.isRunning():
            self.stop_batch_encode()
        self.batch_jobs.clear()
        self.refresh_batch_table()

    def on_batch_settings_changed(self):
        output_format = "mkv" if self.batch_fmt_combo.currentIndex() == 0 else "iso"
        engine_mode = "native_mvc" if self.batch_eng_combo.currentIndex() == 0 else "gpu_turbo"
        bitrates = [20, 23, 35, 40]
        bitrate = bitrates[self.batch_bitrate_combo.currentIndex()]
        auto_fix = self.batch_auto_fix_cb.isChecked()

        for j in self.batch_jobs:
            j.engine_mode = engine_mode
            j.target_bitrate_mbps = bitrate
            j.auto_detect_inverted_eyes = auto_fix
            j.strict_bluray = (output_format == "iso" or bitrate in (23, 40))
            stem = j.output_file.stem
            j.output_file = j.output_file.with_suffix(f".{output_format}")

        self.refresh_batch_table()

    def refresh_batch_table(self):
        self.batch_table.setRowCount(len(self.batch_jobs))
        for row, job in enumerate(self.batch_jobs):
            idx_item = QTableWidgetItem(f"{row+1:02d}")
            idx_item.setTextAlignment(Qt.AlignCenter)
            self.batch_table.setItem(row, 0, idx_item)

            status_item = QTableWidgetItem("⏳ Pending")
            status_item.setTextAlignment(Qt.AlignCenter)
            self.batch_table.setItem(row, 1, status_item)

            pair_suffix = f" ➕ [{job.right_file.name}]" if job.right_file else ""
            in_item = QTableWidgetItem(f"{job.input_file.name}{pair_suffix}")
            self.batch_table.setItem(row, 2, in_item)

            format_desc = "3D Video"
            audio_desc = "Stereo"
            try:
                prof = IngestionEngine().probe(job.input_file)
                format_desc = f"{prof.stereo_format.value.upper()} ({prof.width}x{prof.height})"
                if prof.audio_streams:
                    tracks = [f"{a.get('codec', '').upper()} ({a.get('language', 'und')})" for a in prof.audio_streams]
                    audio_desc = f"{len(prof.audio_streams)} trk: " + ", ".join(tracks[:2])
                else:
                    audio_desc = "1 trk (Stereo)"
            except Exception:
                pass

            fmt_item = QTableWidgetItem(format_desc)
            self.batch_table.setItem(row, 3, fmt_item)

            aud_item = QTableWidgetItem(audio_desc)
            self.batch_table.setItem(row, 4, aud_item)

            eng_str = "🔬 True MVC" if job.engine_mode == "native_mvc" else "🚀 GPU Turbo"
            eng_item = QTableWidgetItem(eng_str)
            eng_item.setTextAlignment(Qt.AlignCenter)
            self.batch_table.setItem(row, 5, eng_item)

            out_item = QTableWidgetItem(str(job.output_file.name))
            self.batch_table.setItem(row, 6, out_item)

        self.batch_status_lbl.setText(f"Batch Queue: {len(self.batch_jobs)} jobs queued (Idle)")
        if self.batch_jobs:
            self.batch_open_output_btn.setEnabled(True)
        else:
            self.batch_open_output_btn.setEnabled(False)

    def start_batch_encode(self):
        if not self.batch_jobs:
            self.batch_status_lbl.setText("⚠️ Please add video files to the batch queue first.")
            return

        self.batch_start_btn.setEnabled(False)
        self.batch_stop_btn.setEnabled(True)
        self.batch_progress_bar.setValue(0)
        self.batch_status_lbl.setText(f"Starting batch queue execution (1 of {len(self.batch_jobs)})...")

        self.batch_worker = BatchWorkerThread(self.batch_jobs)
        self.batch_worker.batch_progress_signal.connect(self.on_batch_progress)
        self.batch_worker.batch_finished_signal.connect(self.on_batch_finished)
        self.batch_worker.start()

    def stop_batch_encode(self):
        if self.batch_worker:
            self.batch_worker.cancel()
            self.batch_status_lbl.setText("⏹️ Batch execution cancellation requested...")
            self.batch_stop_btn.setEnabled(False)

    def on_batch_progress(self, bp: BatchProgress):
        pct = int(bp.overall_progress * 100)
        self.batch_progress_bar.setValue(pct)
        cur_idx = bp.current_job_index

        for r_idx in range(len(self.batch_jobs)):
            if r_idx < cur_idx:
                it = self.batch_table.item(r_idx, 1)
                if it:
                    it.setText("✅ Done")
            elif r_idx == cur_idx:
                it = self.batch_table.item(r_idx, 1)
                if it:
                    it.setText(f"🔄 Encoding ({pct}%)")
            else:
                it = self.batch_table.item(r_idx, 1)
                if it and it.text() != "✅ Done":
                    it.setText("⏳ Pending")

        self.batch_status_lbl.setText(
            f"Batch Progress: Job {cur_idx + 1} of {bp.total_jobs} | Completed: {bp.completed_jobs} | Overall: {pct}%"
        )

    def on_batch_finished(self, results: List[JobResult]):
        self.batch_start_btn.setEnabled(True)
        self.batch_stop_btn.setEnabled(False)
        self.batch_progress_bar.setValue(100)

        success_cnt = sum(1 for r in results if r.success)
        fail_cnt = sum(1 for r in results if not r.success)

        for idx, res in enumerate(results):
            if idx < self.batch_table.rowCount():
                it = self.batch_table.item(idx, 1)
                if it:
                    if res.success:
                        sz_mb = res.output_size_bytes / (1024 * 1024)
                        it.setText(f"✅ Done ({sz_mb:.1f} MB)")
                    else:
                        it.setText("❌ Failed")

        self.batch_status_lbl.setText(
            f"🎉 Batch Finished: {success_cnt} Succeeded, {fail_cnt} Failed across {len(results)} jobs."
        )

    def open_batch_output_folder(self):
        if not self.batch_jobs:
            return
        out_dir = self.batch_jobs[0].output_file.parent
        if out_dir.exists():
            import os
            os.startfile(str(out_dir))

    def on_theme_changed(self, theme_name: str):
        self.settings.setValue("theme", theme_name)
        self.apply_theme(theme_name)

    def apply_theme(self, theme_name: str = "☀️ Clean Light"):
        theme = THEMES.get(theme_name, THEMES["☀️ Clean Light"])

        self.header_label.setStyleSheet(f"color: {theme['header_color']}; margin: 0;")
        self.subhead_label.setStyleSheet(f"color: {theme['text_dim']}; margin-bottom: 2px;")
        self.status_label.setStyleSheet(f"color: {theme['header_color']};")

        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {theme['bg']}; }}
            QWidget {{ background-color: {theme['bg']}; color: {theme['text']}; }}
            QScrollArea {{ background-color: transparent; border: none; }}
            QScrollArea QWidget {{ background-color: transparent; }}
            QGroupBox {{
                background-color: {theme['card_bg']};
                color: {theme['header_color']};
                font-weight: bold;
                border: 1px solid {theme['border']};
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                background-color: {theme['card_bg']};
            }}
            QLabel {{ color: {theme['text']}; background-color: transparent; }}
            QPushButton {{
                background-color: {theme['input_bg']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {theme['border']};
            }}
            QLineEdit {{
                background-color: {theme['input_bg']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QComboBox {{
                background-color: {theme['input_bg']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                border-radius: 4px;
                padding: 5px 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme['input_bg']};
                color: {theme['text']};
                selection-background-color: {theme['border']};
            }}
            QCheckBox {{ color: {theme['text']}; background-color: transparent; }}
            QProgressBar {{
                border: 1px solid {theme['border']};
                border-radius: 5px;
                text-align: center;
                color: {theme['text']};
                background-color: {theme['input_bg']};
            }}
            QProgressBar::chunk {{
                background-color: {theme['accent']};
                border-radius: 4px;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid {theme['border']};
                height: 6px;
                background: {theme['input_bg']};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {theme['accent']};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {theme['accent']};
                border: 1px solid {theme['border']};
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }}
            QSplitter::handle {{
                background-color: {theme['border']};
                width: 2px;
            }}
            QTabWidget::pane {{
                border: 1px solid {theme['border']};
                background-color: {theme['bg']};
                border-radius: 6px;
                padding: 4px;
            }}
            QTabBar::tab {{
                background-color: {theme['card_bg']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                padding: 8px 18px;
                font-weight: bold;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: {theme['input_bg']};
                color: {theme['header_color']};
                border-bottom: 2px solid {theme['accent']};
            }}
            QTableWidget {{
                background-color: {theme['card_bg']};
                color: {theme['text']};
                gridline-color: {theme['border']};
                border: 1px solid {theme['border']};
                border-radius: 6px;
                selection-background-color: {theme['border']};
            }}
            QHeaderView::section {{
                background-color: {theme['input_bg']};
                color: {theme['header_color']};
                font-weight: bold;
                padding: 6px;
                border: 1px solid {theme['border']};
            }}
        """)

        # Start Button distinct accent styling
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme['accent']};
                color: {theme['btn_text']};
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme['accent_hover']};
            }}
            QPushButton:disabled {{
                background-color: {theme['border']};
                color: {theme['text_dim']};
            }}
        """)

        # Batch Action Buttons styling
        self.batch_start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme['accent']};
                color: {theme['btn_text']};
                border: none;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme['accent_hover']};
            }}
            QPushButton:disabled {{
                background-color: {theme['border']};
                color: {theme['text_dim']};
            }}
        """)

        self.batch_stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme['input_bg']};
                color: #EF4444;
                border: 1px solid #EF4444;
                border-radius: 6px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(239, 68, 68, 0.15);
            }}
            QPushButton:disabled {{
                background-color: {theme['border']};
                color: {theme['text_dim']};
                border: 1px solid {theme['border']};
            }}
        """)

        # Console text edit specific theme
        self.console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {theme['console_bg']};
                color: {theme['console_text']};
                border: 1px solid {theme['border']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)

    def copy_log(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.console.toPlainText())
        self.status_label.setText("Status: Log copied to clipboard!")

    def clear_log(self):
        self.console.clear()

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Left Eye / 3D Video File",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.mts *.m2ts)"
        )
        if path:
            self.input_file = Path(path)
            self.file_label.setText(f"Left: {self.input_file.name}")
            self.log(f"Ingested Left: {self.input_file}")

            # Auto-suggest output path
            fmt_idx = self.output_format_combo.currentIndex()
            ext = ".mkv" if fmt_idx == 0 else (".iso" if fmt_idx == 1 else "_BDMV")
            suggested = self.input_file.with_name(f"{self.input_file.stem}_3D{ext}")
            self.output_path_edit.setText(str(suggested))

            # Auto-populate title with clean filename stem
            clean_title = self.input_file.stem.replace("_", " ").replace(".", " ")
            self.title_edit.setText(clean_title)

            # Check for auto-paired right eye file
            paired_right = find_matching_eye_file(self.input_file)
            if paired_right:
                self.right_file = paired_right
                self.right_file_label.setText(f"Right Eye (Auto-paired): {self.right_file.name}")
                self.layout_combo.setCurrentIndex(3)
                self.log(f"🎉 Auto-paired matching Right Eye: {self.right_file.name}")
            else:
                self.right_file = None
                self.right_file_label.setText("Right Eye: (None / Packed in main file)")
                try:
                    profile = IngestionEngine().probe(self.input_file)
                    if profile.stereo_format in (StereoFormat.FULL_SBS, StereoFormat.HALF_SBS):
                        self.layout_combo.setCurrentIndex(1)
                        self.log(f"Detected 3D Format: Side-by-Side ({profile.width}x{profile.height})")
                    elif profile.stereo_format in (StereoFormat.FULL_TAB, StereoFormat.HALF_TAB):
                        self.layout_combo.setCurrentIndex(2)
                        self.log(f"Detected 3D Format: Top-and-Bottom ({profile.width}x{profile.height})")
                    else:
                        self.layout_combo.setCurrentIndex(0)

                    if profile.fps and not (23.97 <= profile.fps <= 24.01):
                        self.log(f"ℹ️ Framerate Note: Input is {profile.fps:.2f} fps. For physical 3D Blu-ray video discs on standalone players, 1080p @ 23.976 fps is strictly required. For VLC4MVC, Android, and network streaming, {profile.fps:.2f} fps will play normally.")
                except Exception:
                    pass

    def browse_right_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Right Eye Video File",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.mts *.m2ts)"
        )
        if path:
            self.right_file = Path(path)
            self.right_file_label.setText(f"Right: {self.right_file.name}")
            self.layout_combo.setCurrentIndex(3)
            self.log(f"Selected Right Eye video: {self.right_file}")

    def open_anaglyph_preview(self):
        if not self.input_file or not self.input_file.exists():
            self.log("⚠️ Please select an input 3D video file first.")
            return

        layout_idx = self.layout_combo.currentIndex()
        fmt = StereoFormat.HALF_SBS
        if layout_idx == 1:
            fmt = StereoFormat.HALF_SBS
        elif layout_idx == 2:
            fmt = StereoFormat.HALF_TAB
        elif layout_idx == 3:
            fmt = StereoFormat.DUAL_FILES
        else:
            try:
                profile = IngestionEngine().probe(self.input_file)
                fmt = profile.stereo_format
            except Exception:
                fmt = StereoFormat.HALF_SBS

        try:
            profile = IngestionEngine().probe(self.input_file)
            duration = profile.duration
        except Exception:
            duration = 60.0

        dialog = AnaglyphPreviewDialog(
            parent=self,
            input_file=self.input_file,
            right_file=self.right_file,
            format_type=fmt,
            swap_eyes=self.swap_eyes_cb.isChecked(),
            duration=duration
        )

        if dialog.exec():
            # Sync swap eyes checkbox if user changed orientation in preview
            self.swap_eyes_cb.setChecked(dialog.swap_eyes)
            if dialog.swap_eyes:
                self.log("🔄 Eye orientation set to: SWAPPED (Left/Right Inverted)")
            else:
                self.log("👁️ Eye orientation set to: STANDARD (Normal Left/Right)")

    def on_output_format_changed(self, index: int):
        if index == 0:
            self.format_note_lbl.setText("💡 Matroska (.mkv): Universal dual-track/MVC for Quest, Vision Pro, 4XVR, VLC. Supports arbitrary framerates (24, 30, 48, 60 fps).")
            self.format_note_lbl.setStyleSheet("font-size: 11px; color: #64748B; padding: 2px 4px;")
        else:
            self.format_note_lbl.setText("⚠️ Playable 3D Blu-ray Requirement: Burning a playable disc for standalone consumer players requires strictly 1080p @ 23.976/24 fps and max 40 Mbps. (Network & VLC4MVC file playback supports arbitrary framerates).")
            self.format_note_lbl.setStyleSheet("font-size: 11px; color: #D97706; font-weight: 500; padding: 2px 4px;")

        cur_text = self.output_path_edit.text().strip()
        if not cur_text:
            return
        p = Path(cur_text)
        parent = p.parent
        stem = p.stem.removesuffix("_3D")
        if index == 0:
            self.output_path_edit.setText(str(parent / f"{stem}_3D.mkv"))
        elif index == 1:
            self.output_path_edit.setText(str(parent / f"{stem}_3D.iso"))
        else:
            self.output_path_edit.setText(str(parent / f"{stem}_3D_BDMV"))

    def browse_output_file(self):
        cur_text = self.output_path_edit.text().strip()
        initial_dir = str(Path(cur_text).parent) if cur_text else ""
        fmt_idx = self.output_format_combo.currentIndex()
        if fmt_idx == 0:
            path, _ = QFileDialog.getSaveFileName(self, "Save 3D Matroska Video", cur_text or initial_dir, "3D Matroska (*.mkv)")
        elif fmt_idx == 1:
            path, _ = QFileDialog.getSaveFileName(self, "Save 3D Blu-ray ISO", cur_text or initial_dir, "3D Blu-ray ISO (*.iso)")
        else:
            path = QFileDialog.getExistingDirectory(self, "Select Output BDMV Directory", initial_dir)
        if path:
            self.output_path_edit.setText(path)

    def on_preset_changed(self, index: int):
        if index == 0:  # VR
            self.bitrate_slider.setValue(20)
            self.bluray_cap_cb.setChecked(False)
        elif index == 1:  # BD-50
            self.bitrate_slider.setValue(40)
            self.bluray_cap_cb.setChecked(True)
        elif index == 2:  # BD-25
            self.bitrate_slider.setValue(23)
            self.bluray_cap_cb.setChecked(True)

    def on_bitrate_changed(self, val: int):
        left = val * 0.70
        right = val * 0.30
        self.bitrate_label.setText(f"Target Bitrate: {val} Mbps (Left: {left:.1f} Mbps | Right: {right:.1f} Mbps)")

    def log(self, text: str):
        self.console.append(text)

    def start_encode(self):
        if not self.input_file:
            self.log("⚠️ Please select an input 3D video file first.")
            return

        out_path_str = self.output_path_edit.text().strip()
        if not out_path_str:
            self.log("⚠️ Please specify an output save destination first.")
            return

        out_path = Path(out_path_str)

        layout_idx = self.layout_combo.currentIndex()
        layout_override = None
        right_input = None
        if layout_idx == 1:
            layout_override = StereoFormat.HALF_SBS
        elif layout_idx == 2:
            layout_override = StereoFormat.HALF_TAB
        elif layout_idx == 3:
            layout_override = StereoFormat.DUAL_FILES
            right_input = self.right_file

        custom_title = self.title_edit.text().strip() or None

        selected_engine = "gpu_turbo" if self.engine_mode_combo.currentIndex() == 1 else "native_mvc"

        job = EncodeJob(
            input_file=self.input_file,
            right_file=right_input,
            output_file=Path(out_path),
            target_bitrate_mbps=self.bitrate_slider.value(),
            strict_bluray=self.bluray_cap_cb.isChecked(),
            swap_eyes=self.swap_eyes_cb.isChecked(),
            title=custom_title,
            layout_override=layout_override,
            auto_detect_inverted_eyes=self.auto_fix_inverted_cb.isChecked(),
            engine_mode=selected_engine
        )

        self.start_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Starting pipeline...")
        self.log("Starting StereoForge pipeline execution...")

        self.worker = WorkerThread(job)
        self.worker.progress_signal.connect(self.on_worker_progress)
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_progress(self, msg: str, pct: float):
        self.progress_bar.setValue(int(pct * 100))
        self.status_label.setText(f"Status: {msg}")
        self.log(msg)

    def on_worker_finished(self, success: bool, out_file: str):
        self.start_btn.setEnabled(True)
        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("Status: 🎉 Encode Completed Successfully!")
            self.log(f"🎉 Encode completed successfully! File: {out_file}")
        else:
            self.status_label.setText("Status: ❌ Encode Failed")
            self.log("❌ Encode failed. Check logs above for details.")


def main():
    if not HAS_PYSIDE6:
        print("[StereoForge] Error: PySide6 is not installed. Run 'pip install PySide6' to launch the GUI.")
        return 1

    app = QApplication(sys.argv)
    window = StereoForgeWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
