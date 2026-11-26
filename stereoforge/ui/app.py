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
        QProgressBar, QTextEdit, QGroupBox, QSplitter
    )
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtGui import QIcon, QFont, QColor
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False

from stereoforge import __version__
from stereoforge.pipeline.orchestrator import StereoForgePipeline, EncodeJob


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

        success = pipeline.run(self.job, progress_cb=on_progress)
        if HAS_PYSIDE6:
            self.finished_signal.emit(success, str(self.job.output_file))


class StereoForgeWindow(QMainWindow if HAS_PYSIDE6 else object):
    """Main Application Window for StereoForge."""

    def __init__(self):
        if not HAS_PYSIDE6:
            raise RuntimeError("PySide6 is required to run the graphical interface.")
        super().__init__()

        self.setWindowTitle(f"StereoForge v{__version__} - Stereoscopic 3D MVC Suite")
        self.resize(1000, 750)
        self.input_file: Optional[Path] = None
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
        drop_layout = QHBoxLayout(drop_box)
        self.file_label = QLabel("No 3D video file selected (Drag & drop or click Browse)")
        self.file_label.setStyleSheet("color: #E2E8F0; font-size: 13px;")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        drop_layout.addWidget(self.file_label, stretch=1)
        drop_layout.addWidget(browse_btn)
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
            QComboBox { background-color: #1C2541; color: #FFFFFF; border: 1px solid #3A506B; border-radius: 4px; padding: 4px; }
            QCheckBox { color: #E2E8F0; }
            QProgressBar { border: 1px solid #1C2541; border-radius: 4px; text-align: center; color: white; background-color: #1C2541; }
            QProgressBar::chunk { background-color: #00F5FF; border-radius: 3px; }
        """)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select 3D Video File", "", "Video Files (*.mp4 *.mkv *.mov *.avi *.mts *.m2ts)")
        if path:
            self.input_file = Path(path)
            self.file_label.setText(f"Loaded: {self.input_file.name}")
            self.log(f"Ingested: {self.input_file}")

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

        out_path, _ = QFileDialog.getSaveFileName(self, "Save 3D Video", str(self.input_file.with_name(f"{self.input_file.stem}_3D.mkv")), "3D Matroska (*.mkv);;3D Blu-ray ISO (*.iso)")
        if not out_path:
            return

        job = EncodeJob(
            input_file=self.input_file,
            output_file=Path(out_path),
            target_bitrate_mbps=self.bitrate_slider.value(),
            strict_bluray=self.bluray_cap_cb.isChecked(),
            swap_eyes=self.swap_eyes_cb.isChecked()
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
