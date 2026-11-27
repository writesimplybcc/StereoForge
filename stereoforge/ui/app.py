"""StereoForge Modern Desktop GUI (Qt 6 / PySide6).

Imagined by writesimply.bcc • Coded by Gemini
"""

import sys
from pathlib import Path
from typing import Optional

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFileDialog, QSlider, QComboBox, QCheckBox,
        QProgressBar, QTextEdit, QGroupBox, QSplitter, QLineEdit
    )
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtGui import QIcon, QFont, QColor
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False

from stereoforge import __version__
from stereoforge.pipeline.orchestrator import StereoForgePipeline, EncodeJob
from stereoforge.pipeline.ingest import IngestionEngine, StereoFormat, find_matching_eye_file


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

        self.setWindowTitle(f"StereoForge v{__version__} - Stereoscopic 3D MVC Suite")
        self.resize(1000, 750)
        self.input_file: Optional[Path] = None
        self.right_file: Optional[Path] = None
        self.worker: Optional[WorkerThread] = None

        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header with Credits
        header = QLabel("StereoForge")
        header.setFont(QFont("Segoe UI", 24, QFont.Bold))
        header.setStyleSheet("color: #00F5FF; margin: 0;")
        layout.addWidget(header)

        subhead = QLabel("Imagined by writesimply.bcc • Coded by Gemini")
        subhead.setFont(QFont("Segoe UI", 10))
        subhead.setStyleSheet("color: #8D99AE; margin-bottom: 8px;")
        layout.addWidget(subhead)

        # File Drop Zone / Selector
        drop_box = QGroupBox("📁 Input 3D Media")
        drop_layout = QVBoxLayout(drop_box)

        file_row = QHBoxLayout()
        self.file_label = QLabel("Left Eye / 3D File: No file selected (Click Browse)")
        self.file_label.setStyleSheet("color: #E2E8F0; font-size: 13px;")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        file_row.addWidget(self.file_label, stretch=1)
        file_row.addWidget(browse_btn)
        drop_layout.addLayout(file_row)

        right_row = QHBoxLayout()
        self.right_file_label = QLabel("Right Eye: (Auto-detected or packed in main file)")
        self.right_file_label.setStyleSheet("color: #8D99AE; font-size: 12px;")
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

        layout.addWidget(drop_box)

        # Quality & Bitrate Settings
        settings_box = QGroupBox("⚙️ Encoding Profile & Bitrate")
        set_layout = QVBoxLayout(settings_box)

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

        # Uncapped Bitrate Meter
        slider_row = QHBoxLayout()
        self.bitrate_label = QLabel("Target Bitrate: 35 Mbps (Left: 24.5 Mbps | Right: 10.5 Mbps)")
        slider_row.addWidget(self.bitrate_label)
        set_layout.addLayout(slider_row)

        self.bitrate_slider = QSlider(Qt.Horizontal)
        self.bitrate_slider.setRange(5, 120)
        self.bitrate_slider.setValue(35)
        self.bitrate_slider.valueChanged.connect(self.on_bitrate_changed)
        set_layout.addWidget(self.bitrate_slider)

        # Options Row
        opts_row = QHBoxLayout()
        self.swap_eyes_cb = QCheckBox("Swap Left/Right Eyes")
        self.bluray_cap_cb = QCheckBox("Strict Blu-ray VBV Cap (Max 40 Mbps for Discs)")
        self.bluray_cap_cb.setChecked(False)
        opts_row.addWidget(self.swap_eyes_cb)
        opts_row.addWidget(self.bluray_cap_cb)
        opts_row.addStretch()
        set_layout.addLayout(opts_row)

        layout.addWidget(settings_box)

        # Output Destination & Packaging Format
        output_box = QGroupBox("💾 Output Settings & Destination")
        out_layout = QVBoxLayout(output_box)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Output Container:"))
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems([
            "3D MVC Matroska (.mkv) — Meta Quest, Vision Pro, 4XVR, VLC (mkvmerge)",
            "3D Blu-ray ISO (.iso) — Physical 3D Disc & Projectors (tsMuxeR)",
            "3D Blu-ray Folder (BDMV) — Directory Structure (tsMuxeR)"
        ])
        self.output_format_combo.currentIndexChanged.connect(self.on_output_format_changed)
        fmt_row.addWidget(self.output_format_combo, stretch=1)
        out_layout.addLayout(fmt_row)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Save To:"))
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Select an input file or click Browse to choose destination...")
        browse_out_btn = QPushButton("Browse...")
        browse_out_btn.clicked.connect(self.browse_output_file)
        dest_row.addWidget(self.output_path_edit, stretch=1)
        dest_row.addWidget(browse_out_btn)
        out_layout.addLayout(dest_row)

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("Title (Optional):"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Leave blank to display filename in players, or enter custom title...")
        title_row.addWidget(self.title_edit, stretch=1)
        out_layout.addLayout(title_row)

        layout.addWidget(output_box)

        # Encode Action
        action_row = QHBoxLayout()
        self.start_btn = QPushButton("🚀 Start 3D Encode")
        self.start_btn.setFixedHeight(45)
        self.start_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.start_btn.setStyleSheet("background-color: #00F5FF; color: #0B132B; border-radius: 6px;")
        self.start_btn.clicked.connect(self.start_encode)
        action_row.addWidget(self.start_btn)
        layout.addLayout(action_row)

        # Progress & Console
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFixedHeight(140)
        self.console.setFont(QFont("Consolas", 10))
        self.console.setStyleSheet("background-color: #0B132B; color: #00F5FF; border: 1px solid #1C2541;")
        layout.addWidget(self.console)

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0B132B; }
            QGroupBox { color: #00F5FF; font-weight: bold; border: 1px solid #1C2541; border-radius: 8px; margin-top: 12px; padding: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QLabel { color: #E2E8F0; }
            QPushButton { background-color: #1C2541; color: #FFFFFF; border: 1px solid #3A506B; border-radius: 4px; padding: 6px 14px; }
            QPushButton:hover { background-color: #3A506B; }
            QLineEdit { background-color: #1C2541; color: #FFFFFF; border: 1px solid #3A506B; border-radius: 4px; padding: 6px 10px; font-size: 13px; }
            QComboBox { background-color: #1C2541; color: #FFFFFF; border: 1px solid #3A506B; border-radius: 4px; padding: 4px; }
            QCheckBox { color: #E2E8F0; }
            QProgressBar { border: 1px solid #1C2541; border-radius: 4px; text-align: center; color: white; background-color: #1C2541; }
            QProgressBar::chunk { background-color: #00F5FF; border-radius: 3px; }
        """)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Left Eye / 3D Video File", "", "Video Files (*.mp4 *.mkv *.mov *.avi *.mts *.m2ts)")
        if path:
            self.input_file = Path(path)
            self.file_label.setText(f"Left: {self.input_file.name}")
            self.log(f"Ingested Left: {self.input_file}")

            # Auto-suggest output path
            fmt_idx = self.output_format_combo.currentIndex()
            ext = ".mkv" if fmt_idx == 0 else (".iso" if fmt_idx == 1 else "_BDMV")
            suggested = self.input_file.with_name(f"{self.input_file.stem}_3D{ext}")
            self.output_path_edit.setText(str(suggested))

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
        path, _ = QFileDialog.getOpenFileName(self, "Select Right Eye Video File", "", "Video Files (*.mp4 *.mkv *.mov *.avi *.mts *.m2ts)")
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
        self.log("Starting StereoForge pipeline execution...")

        self.worker = WorkerThread(job)
        self.worker.progress_signal.connect(self.on_worker_progress)
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_progress(self, msg: str, pct: float):
        self.progress_bar.setValue(int(pct * 100))
        self.log(msg)

    def on_worker_finished(self, success: bool, out_file: str):
        self.start_btn.setEnabled(True)
        if success:
            self.progress_bar.setValue(100)
            self.log(f"🎉 Encode completed successfully! File: {out_file}")
        else:
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
