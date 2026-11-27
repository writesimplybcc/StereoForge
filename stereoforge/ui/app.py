"""StereoForge Modern Desktop GUI (Qt 6 / PySide6).

Imagined by writesimply.bcc • Coded by Gemini
"""

import sys
from pathlib import Path
from typing import Optional, Dict

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFileDialog, QSlider, QComboBox, QCheckBox,
        QProgressBar, QTextEdit, QGroupBox, QSplitter, QLineEdit,
        QScrollArea, QFrame, QSizePolicy
    )
    from PySide6.QtCore import Qt, QThread, Signal, QSettings
    from PySide6.QtGui import QIcon, QFont, QColor, QClipboard
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False

from stereoforge import __version__
from stereoforge.pipeline.orchestrator import StereoForgePipeline, EncodeJob
from stereoforge.pipeline.ingest import IngestionEngine, StereoFormat, find_matching_eye_file


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

        opts_row = QHBoxLayout()
        self.swap_eyes_cb = QCheckBox("Swap Left/Right Eyes")
        self.bluray_cap_cb = QCheckBox("Strict Blu-ray VBV Cap (Max 40 Mbps)")
        self.bluray_cap_cb.setChecked(False)
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
        root_layout.addWidget(splitter, stretch=1)

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
            QScrollArea > QWidget > QWidget {{ background-color: transparent; }}
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
            QPushButton#{self.start_btn.objectName()} {{
                background-color: {theme['accent']};
                color: {theme['btn_text']};
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

    def on_output_format_changed(self, index: int):
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

        job = EncodeJob(
            input_file=self.input_file,
            right_file=right_input,
            output_file=Path(out_path),
            target_bitrate_mbps=self.bitrate_slider.value(),
            strict_bluray=self.bluray_cap_cb.isChecked(),
            swap_eyes=self.swap_eyes_cb.isChecked(),
            title=custom_title,
            layout_override=layout_override
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
