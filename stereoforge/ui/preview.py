"""StereoForge Anaglyph 3D Preview Module.

Enables instant Red/Cyan stereoscopic preview and real-time Left/Right
eye orientation verification to prevent inverted (pseudoscopic) 3D output.
"""

from pathlib import Path
from typing import Optional, Tuple
import subprocess
import shutil
import tempfile

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QSlider, QComboBox, QGroupBox, QFrame, QSizePolicy
    )
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtGui import QPixmap, QImage, QFont
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False

from stereoforge.pipeline.ingest import StereoFormat


def get_anaglyph_filter_config(
    format_type: StereoFormat,
    swap_eyes: bool,
    mode: str = "arcd",
    is_dual: bool = False
) -> Tuple[str, bool]:
    """Generates the appropriate FFmpeg stereo3d filter string.

    Modes:
      arcd: Red/Cyan Dubois (color anaglyph)
      agmd: Green/Magenta Dubois
      ml: Mono Left eye
      mr: Mono Right eye

    Returns:
      (filter_str, is_complex)
    """
    if is_dual:
        # Dual separate Left/Right files
        if swap_eyes:
            filter_str = f"[1:v]scale=960:1080[l];[0:v]scale=960:1080[r];[l][r]hstack,stereo3d=sbs2l:{mode},scale=960:540"
        else:
            filter_str = f"[0:v]scale=960:1080[l];[1:v]scale=960:1080[r];[l][r]hstack,stereo3d=sbs2l:{mode},scale=960:540"
        return filter_str, True

    # Single-file layouts (SBS, TAB)
    if format_type in (StereoFormat.FULL_SBS, StereoFormat.HALF_SBS):
        in_code = "sbs2r" if swap_eyes else "sbs2l"
    elif format_type in (StereoFormat.FULL_TAB, StereoFormat.HALF_TAB):
        in_code = "ab2r" if swap_eyes else "ab2l"
    else:
        # Default fallback to Half-SBS
        in_code = "sbs2r" if swap_eyes else "sbs2l"

    filter_str = f"stereo3d={in_code}:{mode},scale=960:540"
    return filter_str, False


class FrameExtractorWorker(QThread if HAS_PYSIDE6 else object):
    """Background thread to extract anaglyph preview frames smoothly without GUI lag."""
    if HAS_PYSIDE6:
        frame_ready = Signal(str)
        error_signal = Signal(str)

    def __init__(
        self,
        input_file: Path,
        right_file: Optional[Path],
        format_type: StereoFormat,
        timestamp: float,
        swap_eyes: bool,
        mode: str,
        output_temp_jpg: Path
    ):
        if HAS_PYSIDE6:
            super().__init__()
        self.input_file = input_file
        self.right_file = right_file
        self.format_type = format_type
        self.timestamp = timestamp
        self.swap_eyes = swap_eyes
        self.mode = mode
        self.output_temp_jpg = output_temp_jpg

    def run(self):
        is_dual = bool(self.right_file and self.right_file.exists())
        filter_str, is_complex = get_anaglyph_filter_config(
            self.format_type,
            self.swap_eyes,
            self.mode,
            is_dual=is_dual
        )

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(round(self.timestamp, 2)),
            "-i", str(self.input_file)
        ]

        if is_dual:
            cmd.extend([
                "-ss", str(round(self.timestamp, 2)),
                "-i", str(self.right_file),
                "-filter_complex", filter_str
            ])
        else:
            cmd.extend(["-vf", filter_str])

        cmd.extend([
            "-vframes", "1",
            str(self.output_temp_jpg)
        ])

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            if self.output_temp_jpg.exists():
                self.frame_ready.emit(str(self.output_temp_jpg))
            else:
                self.error_signal.emit("Frame extraction produced no image.")
        except Exception as e:
            self.error_signal.emit(str(e))


class AnaglyphPreviewDialog(QDialog if HAS_PYSIDE6 else object):
    """Interactive Anaglyph 3D Preview and Eye Orientation Verification Dialog."""

    def __init__(
        self,
        parent=None,
        input_file: Optional[Path] = None,
        right_file: Optional[Path] = None,
        format_type: StereoFormat = StereoFormat.HALF_SBS,
        swap_eyes: bool = False,
        duration: float = 60.0
    ):
        if not HAS_PYSIDE6:
            raise RuntimeError("PySide6 is required.")
        super().__init__(parent)

        self.input_file = input_file
        self.right_file = right_file
        self.format_type = format_type
        self.swap_eyes = swap_eyes
        self.duration = max(1.0, duration)
        self.current_time = min(5.0, self.duration * 0.15)
        self.current_mode = "arcd"
        self.worker: Optional[FrameExtractorWorker] = None

        self.temp_dir = Path(tempfile.mkdtemp(prefix="stereoforge_preview_"))
        self.temp_frame_path = self.temp_dir / "preview_frame.jpg"

        self.setWindowTitle("StereoForge 3D Anaglyph Preview & Orientation Checker")
        self.resize(1000, 760)
        self.setMinimumSize(850, 600)

        self.init_ui()
        self.request_frame()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 16)

        # Header Info Row
        head_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("👓 3D Anaglyph Preview & Eye Alignment")
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_box.addWidget(title_lbl)

        file_desc = self.input_file.name if self.input_file else "No File"
        sub_lbl = QLabel(f"Source: {file_desc} • Format: {self.format_type.value}")
        sub_lbl.setStyleSheet("color: #8D99AE; font-size: 11px;")
        title_box.addWidget(sub_lbl)
        head_row.addLayout(title_box, stretch=1)

        # Orientation Indicator Badge
        self.badge_lbl = QLabel()
        self.badge_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.badge_lbl.setStyleSheet("padding: 6px 14px; border-radius: 4px;")
        self.update_badge()
        head_row.addWidget(self.badge_lbl)
        layout.addLayout(head_row)

        # Image Viewport
        self.image_label = QLabel("Extracting preview frame...")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumHeight(420)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #080C16;
                border: 2px solid #2A3654;
                border-radius: 8px;
                color: #8D99AE;
            }
        """)
        layout.addWidget(self.image_label, stretch=1)

        # Timeline Scrub Bar
        scrub_group = QGroupBox("⏱️ Timeline Position")
        scrub_layout = QVBoxLayout(scrub_group)
        scrub_layout.setSpacing(6)

        slider_row = QHBoxLayout()
        self.time_label = QLabel(f"00:05 / {self.format_time(self.duration)}")
        self.time_label.setFont(QFont("Consolas", 10, QFont.Bold))
        self.time_label.setFixedWidth(120)

        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setRange(0, 1000)
        init_pct = int((self.current_time / self.duration) * 1000)
        self.time_slider.setValue(init_pct)
        self.time_slider.sliderMoved.connect(self.on_slider_moved)
        self.time_slider.sliderReleased.connect(self.on_slider_released)

        slider_row.addWidget(self.time_label)
        slider_row.addWidget(self.time_slider, stretch=1)
        scrub_layout.addLayout(slider_row)

        # Quick Jump Buttons
        jumps_row = QHBoxLayout()
        jumps_row.addWidget(QLabel("Quick Jump:"))
        for pct, lbl in [(0.10, "10%"), (0.25, "25%"), (0.50, "50%"), (0.75, "75%"), (0.90, "90%")]:
            btn = QPushButton(lbl)
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda checked=False, p=pct: self.jump_to_pct(p))
            jumps_row.addWidget(btn)
        jumps_row.addStretch()
        scrub_layout.addLayout(jumps_row)
        layout.addWidget(scrub_group)

        # Control Panel: Modes & Eye Orientation
        ctrl_box = QGroupBox("⚙️ Viewing Modes & Eye Orientation")
        ctrl_layout = QHBoxLayout(ctrl_box)
        ctrl_layout.setSpacing(12)

        ctrl_layout.addWidget(QLabel("Preview Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "🔴🔵 Red / Cyan (Dubois Color Anaglyph)",
            "🟢🟣 Green / Magenta (Trioscopic)",
            "👁️ Left Eye Only (2D Base)",
            "👁️ Right Eye Only (2D Dependent)"
        ])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        ctrl_layout.addWidget(self.mode_combo, stretch=1)

        # Prominent Swap Eyes Button
        self.swap_btn = QPushButton("🔄 Swap Left/Right Eyes")
        self.swap_btn.setFixedHeight(34)
        self.swap_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.swap_btn.clicked.connect(self.toggle_swap_eyes)
        ctrl_layout.addWidget(self.swap_btn)

        # Live Player Launcher
        self.play_btn = QPushButton("▶️ Live Playback (ffplay)")
        self.play_btn.setFixedHeight(34)
        self.play_btn.clicked.connect(self.launch_ffplay)
        ctrl_layout.addWidget(self.play_btn)

        layout.addWidget(ctrl_box)

        # Stereo Guide Banner
        guide_banner = QFrame()
        guide_banner.setStyleSheet("background-color: #121A2F; border: 1px solid #2B3A5E; border-radius: 6px; padding: 6px 12px;")
        g_layout = QHBoxLayout(guide_banner)
        g_layout.setContentsMargins(8, 4, 8, 4)
        g_icon = QLabel("💡")
        g_icon.setFont(QFont("Segoe UI", 14))
        g_text = QLabel(
            "<b>How to verify 3D Orientation:</b> Put on standard Red/Cyan glasses (Red on Left Eye). "
            "Foreground objects should appear naturally closer with pop-out depth. "
            "If objects feel inverted, sink inward, or cause eye strain, click <b>'🔄 Swap Left/Right Eyes'</b>."
        )
        g_text.setWordWrap(True)
        g_text.setStyleSheet("font-size: 11px; color: #CBD5E1;")
        g_layout.addWidget(g_icon)
        g_layout.addWidget(g_text, stretch=1)
        layout.addWidget(guide_banner)

        # Bottom Actions: Apply / Cancel
        action_row = QHBoxLayout()
        action_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(110)
        cancel_btn.clicked.connect(self.reject)

        self.apply_btn = QPushButton("✓ Apply & Keep Orientation")
        self.apply_btn.setFixedHeight(38)
        self.apply_btn.setFixedWidth(220)
        self.apply_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.apply_btn.setStyleSheet("background-color: #0284C7; color: white; border-radius: 4px;")
        self.apply_btn.clicked.connect(self.accept)

        action_row.addWidget(cancel_btn)
        action_row.addWidget(self.apply_btn)
        layout.addLayout(action_row)

    def update_badge(self):
        if self.swap_eyes:
            self.badge_lbl.setText("⚠️ EYES SWAPPED (INVERTED)")
            self.badge_lbl.setStyleSheet("background-color: #D97706; color: white; border-radius: 4px; padding: 6px 12px;")
        else:
            self.badge_lbl.setText("👁️ STANDARD L/R ORIENTATION")
            self.badge_lbl.setStyleSheet("background-color: #059669; color: white; border-radius: 4px; padding: 6px 12px;")

    def format_time(self, seconds: float) -> str:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    def on_slider_moved(self, val: int):
        self.current_time = (val / 1000.0) * self.duration
        self.time_label.setText(f"{self.format_time(self.current_time)} / {self.format_time(self.duration)}")

    def on_slider_released(self):
        self.request_frame()

    def jump_to_pct(self, pct: float):
        self.current_time = pct * self.duration
        self.time_slider.setValue(int(pct * 1000))
        self.time_label.setText(f"{self.format_time(self.current_time)} / {self.format_time(self.duration)}")
        self.request_frame()

    def on_mode_changed(self, idx: int):
        modes = ["arcd", "agmd", "ml", "mr"]
        self.current_mode = modes[idx] if idx < len(modes) else "arcd"
        self.request_frame()

    def toggle_swap_eyes(self):
        self.swap_eyes = not self.swap_eyes
        self.update_badge()
        self.request_frame()

    def request_frame(self):
        if not self.input_file or not self.input_file.exists():
            return

        self.image_label.setText("Rendering 3D preview frame...")

        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()

        self.worker = FrameExtractorWorker(
            input_file=self.input_file,
            right_file=self.right_file,
            format_type=self.format_type,
            timestamp=self.current_time,
            swap_eyes=self.swap_eyes,
            mode=self.current_mode,
            output_temp_jpg=self.temp_frame_path
        )
        self.worker.frame_ready.connect(self.on_frame_ready)
        self.worker.error_signal.connect(self.on_frame_error)
        self.worker.start()

    def on_frame_ready(self, frame_path_str: str):
        pixmap = QPixmap(frame_path_str)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText("Failed to load extracted frame.")

    def on_frame_error(self, err_msg: str):
        self.image_label.setText(f"Preview extraction error:\n{err_msg}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.temp_frame_path.exists():
            self.on_frame_ready(str(self.temp_frame_path))

    def launch_ffplay(self):
        """Launches native ffplay window playing the active anaglyph video stream."""
        if not shutil.which("ffplay"):
            self.image_label.setText("ffplay is not installed or not in PATH.")
            return

        is_dual = bool(self.right_file and self.right_file.exists())
        filter_str, is_complex = get_anaglyph_filter_config(
            self.format_type,
            self.swap_eyes,
            self.current_mode,
            is_dual=is_dual
        )

        title = f"StereoForge 3D Anaglyph: {self.input_file.name} (Swap={self.swap_eyes})"
        cmd = [
            "ffplay",
            "-window_title", title,
            "-ss", str(round(self.current_time, 2))
        ]

        if is_dual:
            # Complex pipeline piped into ffplay
            cmd_pipe = [
                "ffmpeg", "-ss", str(round(self.current_time, 2)),
                "-i", str(self.input_file),
                "-ss", str(round(self.current_time, 2)),
                "-i", str(self.right_file),
                "-filter_complex", filter_str,
                "-f", "nut", "-"
            ]
            p_ffmpeg = subprocess.Popen(cmd_pipe, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            subprocess.Popen(["ffplay", "-window_title", title, "-"], stdin=p_ffmpeg.stdout)
        else:
            cmd.extend([
                "-vf", filter_str,
                str(self.input_file)
            ])
            subprocess.Popen(cmd)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().closeEvent(event)
