"""StereoForge Anaglyph 3D Preview Module.

Enables instant Red/Cyan stereoscopic preview and real-time Left/Right
eye orientation verification to prevent inverted (pseudoscopic) 3D output.
Includes bidirectional timeline scrubbing and direct seek capabilities.
"""

from pathlib import Path
from typing import Optional, Tuple
import subprocess
import shutil

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QSlider, QComboBox, QGroupBox, QFrame, QSizePolicy
    )
    from PySide6.QtCore import Qt, QThread, Signal, QTimer
    from PySide6.QtGui import QPixmap, QFont
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
    """Generates the appropriate FFmpeg stereo3d filter string."""
    if is_dual:
        if swap_eyes:
            filter_str = f"[1:v]scale=960:1080[l];[0:v]scale=960:1080[r];[l][r]hstack,stereo3d=sbs2l:{mode},scale=960:540"
        else:
            filter_str = f"[0:v]scale=960:1080[l];[1:v]scale=960:1080[r];[l][r]hstack,stereo3d=sbs2l:{mode},scale=960:540"
        return filter_str, True

    if format_type in (StereoFormat.FULL_SBS, StereoFormat.HALF_SBS):
        in_code = "sbs2r" if swap_eyes else "sbs2l"
    elif format_type in (StereoFormat.FULL_TAB, StereoFormat.HALF_TAB):
        in_code = "ab2r" if swap_eyes else "ab2l"
    else:
        in_code = "sbs2r" if swap_eyes else "sbs2l"

    filter_str = f"stereo3d={in_code}:{mode},scale=960:540"
    return filter_str, False


class ClickableSlider(QSlider if HAS_PYSIDE6 else object):
    """Enhanced QSlider that jumps immediately to any clicked position."""

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.orientation() == Qt.Horizontal:
                val = self.minimum() + ((self.maximum() - self.minimum()) * event.position().x()) / max(1, self.width())
            else:
                val = self.minimum() + ((self.maximum() - self.minimum()) * (self.height() - event.position().y())) / max(1, self.height())
            clamped = max(self.minimum(), min(self.maximum(), int(round(val))))
            self.setValue(clamped)
            event.accept()
        super().mousePressEvent(event)


class FrameExtractorWorker(QThread if HAS_PYSIDE6 else object):
    """Background thread that extracts anaglyph preview frames directly into memory."""
    if HAS_PYSIDE6:
        frame_ready = Signal(int, bytes)
        error_signal = Signal(int, str)

    def __init__(
        self,
        request_id: int,
        input_file: Path,
        right_file: Optional[Path],
        format_type: StereoFormat,
        timestamp: float,
        swap_eyes: bool,
        mode: str
    ):
        if HAS_PYSIDE6:
            super().__init__()
        self.request_id = request_id
        self.input_file = input_file
        self.right_file = right_file
        self.format_type = format_type
        self.timestamp = timestamp
        self.swap_eyes = swap_eyes
        self.mode = mode
        self.process: Optional[subprocess.Popen] = None
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True
        if self.process:
            try:
                self.process.kill()
            except Exception:
                pass

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
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "-"
        ])

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            out, err = self.process.communicate()
            if self._is_cancelled:
                return

            if self.process.returncode == 0 and len(out) > 1000:
                self.frame_ready.emit(self.request_id, out)
            else:
                err_text = err.decode("utf-8", errors="ignore")
                self.error_signal.emit(self.request_id, f"Extraction error: {err_text[:200]}")
        except Exception as e:
            if not self._is_cancelled:
                self.error_signal.emit(self.request_id, str(e))


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

        self.request_id = 0
        self._active_workers = []
        self.current_pixmap: Optional[QPixmap] = None

        # Debounce timer to avoid spamming ffmpeg during rapid scrubbing
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(120)
        self.debounce_timer.timeout.connect(self.request_frame)

        self.setWindowTitle("StereoForge 3D Anaglyph Preview & Orientation Checker")
        self.resize(1020, 780)
        self.setMinimumSize(880, 620)

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

        # Timeline Scrub Bar (Bidirectional & Clickable)
        scrub_group = QGroupBox("⏱️ Timeline Scrub & Seek (Bidirectional)")
        scrub_layout = QVBoxLayout(scrub_group)
        scrub_layout.setSpacing(8)

        slider_row = QHBoxLayout()
        self.time_label = QLabel(f"{self.format_time(self.current_time)} / {self.format_time(self.duration)}")
        self.time_label.setFont(QFont("Consolas", 10, QFont.Bold))
        self.time_label.setFixedWidth(130)

        # Use ClickableSlider for instant click-to-position jumps anywhere on the bar
        self.time_slider = ClickableSlider(Qt.Horizontal)
        self.time_slider.setRange(0, 1000)
        init_pct = int((self.current_time / self.duration) * 1000)
        self.time_slider.setValue(init_pct)
        # Handle all slider changes (drag, click forward, click backward, arrow keys)
        self.time_slider.valueChanged.connect(self.on_slider_value_changed)
        self.time_slider.sliderReleased.connect(self.on_slider_released)

        slider_row.addWidget(self.time_label)
        slider_row.addWidget(self.time_slider, stretch=1)
        scrub_layout.addLayout(slider_row)

        # Step Navigation & Quick Jump Row
        nav_row = QHBoxLayout()
        nav_row.addWidget(QLabel("Step / Seek:"))

        step_b5 = QPushButton("⏪ -5s")
        step_b5.setFixedHeight(28)
        step_b5.clicked.connect(lambda: self.step_seconds(-5.0))
        nav_row.addWidget(step_b5)

        step_b1 = QPushButton("◀ -1s")
        step_b1.setFixedHeight(28)
        step_b1.clicked.connect(lambda: self.step_seconds(-1.0))
        nav_row.addWidget(step_b1)

        step_f1 = QPushButton("+1s ▶")
        step_f1.setFixedHeight(28)
        step_f1.clicked.connect(lambda: self.step_seconds(1.0))
        nav_row.addWidget(step_f1)

        step_f5 = QPushButton("+5s ⏩")
        step_f5.setFixedHeight(28)
        step_f5.clicked.connect(lambda: self.step_seconds(5.0))
        nav_row.addWidget(step_f5)

        nav_row.addSpacing(15)
        nav_row.addWidget(QLabel("Quick Jump:"))
        for pct, lbl in [(0.10, "10%"), (0.25, "25%"), (0.50, "50%"), (0.75, "75%"), (0.90, "90%")]:
            btn = QPushButton(lbl)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked=False, p=pct: self.jump_to_pct(p))
            nav_row.addWidget(btn)

        nav_row.addStretch()
        scrub_layout.addLayout(nav_row)
        layout.addWidget(scrub_group)

        # Control Panel: Modes & Eye Orientation
        ctrl_box = QGroupBox("⚙️ Viewing Modes & Eye Orientation")
        ctrl_layout = QHBoxLayout(ctrl_box)
        ctrl_layout.setSpacing(12)

        ctrl_layout.addWidget(QLabel("Preview Mode:"))
        self.mode_combo = QComboBox()
        self.preview_modes = [
            ("🔴🔵 Red / Cyan (Dubois Color - Recommended)", "arcd"),
            ("🔴🔵 Red / Cyan (Standard Full Color)", "arcc"),
            ("🔴🔵 Red / Cyan (Half Color)", "arch"),
            ("🟢🟣 Green / Magenta (Trioscopic 3D)", "agmd"),
            ("🟡🔵 Amber / Blue (ColorCode 3D)", "aybd"),
            ("👁️ Left Eye Only (2D Base)", "ml"),
            ("👁️ Right Eye Only (2D Dependent)", "mr")
        ]
        for label, _ in self.preview_modes:
            self.mode_combo.addItem(label)
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
            "<b>How to verify 3D Orientation:</b> Put on your matching 3D glasses (e.g. Red on Left Eye for Red/Cyan modes). "
            "Foreground elements should naturally pop out with depth. "
            "If objects feel inverted or sink inward (pseudoscopic), click <b>'🔄 Swap Left/Right Eyes'</b>.<br/>"
            "<i>Note on Glasses:</i> Red/Cyan modes require Red/Cyan glasses; Green/Magenta requires Trioscopic glasses; Amber/Blue requires ColorCode 3D glasses."
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

    def on_slider_value_changed(self, val: int):
        """Called immediately whenever the slider position changes (drag, click, or step)."""
        self.current_time = max(0.0, min(self.duration, (val / 1000.0) * self.duration))
        self.time_label.setText(f"{self.format_time(self.current_time)} / {self.format_time(self.duration)}")
        # Restart debounce timer (120ms) so rapid dragging doesn't spam ffmpeg
        self.debounce_timer.start(120)

    def on_slider_released(self):
        """Immediately triggers frame extraction when the user finishes dragging."""
        self.debounce_timer.stop()
        self.request_frame()

    def step_seconds(self, delta: float):
        """Steps forward or backward by delta seconds."""
        new_time = max(0.0, min(self.duration, self.current_time + delta))
        pct = new_time / self.duration
        self.time_slider.blockSignals(True)
        self.time_slider.setValue(int(pct * 1000))
        self.time_slider.blockSignals(False)
        self.current_time = new_time
        self.time_label.setText(f"{self.format_time(self.current_time)} / {self.format_time(self.duration)}")
        self.request_frame()

    def jump_to_pct(self, pct: float):
        """Jumps directly to a percentage position."""
        self.time_slider.blockSignals(True)
        self.time_slider.setValue(int(pct * 1000))
        self.time_slider.blockSignals(False)
        self.current_time = pct * self.duration
        self.time_label.setText(f"{self.format_time(self.current_time)} / {self.format_time(self.duration)}")
        self.request_frame()

    def on_mode_changed(self, idx: int):
        if 0 <= idx < len(self.preview_modes):
            self.current_mode = self.preview_modes[idx][1]
        else:
            self.current_mode = "arcd"
        self.request_frame()

    def toggle_swap_eyes(self):
        self.swap_eyes = not self.swap_eyes
        self.update_badge()
        self.request_frame()

    def request_frame(self):
        if not self.input_file or not self.input_file.exists():
            return

        self.request_id += 1
        req_id = self.request_id

        # Cancel any previous in-flight workers safely without dropping references
        for w in list(self._active_workers):
            w.cancel()

        worker = FrameExtractorWorker(
            request_id=req_id,
            input_file=self.input_file,
            right_file=self.right_file,
            format_type=self.format_type,
            timestamp=self.current_time,
            swap_eyes=self.swap_eyes,
            mode=self.current_mode
        )
        self._active_workers.append(worker)

        def cleanup(w=worker):
            if w in self._active_workers:
                self._active_workers.remove(w)

        worker.finished.connect(cleanup)
        worker.frame_ready.connect(self.on_frame_ready)
        worker.error_signal.connect(self.on_frame_error)
        worker.start()

    def on_frame_ready(self, req_id: int, img_bytes: bytes):
        # Ignore outdated responses from earlier seek requests
        if req_id != self.request_id:
            return

        pixmap = QPixmap()
        if pixmap.loadFromData(img_bytes):
            self.current_pixmap = pixmap
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText("Failed to decode frame from memory.")

    def on_frame_error(self, req_id: int, err_msg: str):
        if req_id == self.request_id:
            self.image_label.setText(f"Preview extraction error:\n{err_msg}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_pixmap and not self.current_pixmap.isNull():
            scaled = self.current_pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)

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
        self.debounce_timer.stop()
        for w in list(self._active_workers):
            w.cancel()
            w.wait(200)
        self._active_workers.clear()
        super().closeEvent(event)
