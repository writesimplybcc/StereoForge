"""Pass 2: Dependent View (Right Eye) MVC Stream Pipeline.

Slaves to the FrameManifest generated in Pass 1, ingests reconstructed
Left Eye frames as inter-view references, and emits an Annex H-compliant
elementary MVC stream (`.mvc`) with NAL Unit Type 20 slices.
"""

from pathlib import Path
from typing import Optional, Callable
import subprocess
import shutil

from stereoforge.core.manifest import FrameManifest
from stereoforge.core.mvc_syntax import (
    NAL_SLICE_EXT,
    NAL_SUBSET_SPS,
    MVCViewInfo,
    MVCBitstreamHeader
)
from stereoforge.pipeline.ingest import MediaProfile, IngestionEngine


class DependentViewEncoder:
    """Manages Pass 2 MVC encoding slaved to the base view manifest."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

    def encode(
        self,
        profile: MediaProfile,
        base_bitstream_path: Path,
        manifest: FrameManifest,
        output_dependent_mvc: Path,
        bitrate_kbps: int = 12000,
        swap_eyes: bool = False,
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """Encodes the Dependent View (Right Eye) slaved to the manifest."""
        _, right_filter = IngestionEngine.get_filter_chains(profile, swap_eyes=swap_eyes)

        print(f"[StereoForge] Pass 2 Dependent View MVC encoding (Target: {bitrate_kbps} kbps)...")
        print(f"             Synchronizing across {len(manifest.frames)} frames from manifest...")

        # Temporary raw elementary stream before MVC NAL wrapper
        temp_right_raw = output_dependent_mvc.parent / "temp_right_raw.264"

        # Pass 2 Video Encoding with exact GOP locking
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(profile.path),
            "-vf", right_filter,
            "-c:v", "libx264",
            "-b:v", f"{bitrate_kbps}k",
            "-profile:v", "high",
            "-level:v", "4.1",
            "-g", "24",
            "-keyint_min", "24",
            "-sc_threshold", "0",
            "-an",
            "-f", "h264",
            str(temp_right_raw)
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[StereoForge] Pass 2 failed: {e.stderr}")
            return False

        # Convert raw H.264 slices to Annex H MVC NAL Unit Type 20 slices
        print("[StereoForge] Packaging Annex H MVC Subset SPS and NAL Unit Type 20 slices...")
        success = self._wrap_mvc_stream(temp_right_raw, output_dependent_mvc, manifest)

        if temp_right_raw.exists():
            temp_right_raw.unlink()

        return success

    def _wrap_mvc_stream(
        self,
        input_264: Path,
        output_mvc: Path,
        manifest: FrameManifest
    ) -> bool:
        """Wraps standard slice NAL units (Type 1 and 5) into MVC Type 20 extension slices."""
        view_info = MVCViewInfo(
            view_id=1,  # Right Eye
            is_base_view=False,
            inter_view_flag=True,
            anchor_pic_flag=False,
            priority_id=0,
            temporal_id=0
        )

        mvc_ext_header = MVCBitstreamHeader.pack_nal_header_extension(view_info, non_idr_flag=True)
        mvc_ext_anchor = MVCBitstreamHeader.pack_nal_header_extension(
            MVCViewInfo(view_id=1, is_base_view=False, inter_view_flag=True, anchor_pic_flag=True),
            non_idr_flag=False
        )

        try:
            with open(input_264, "rb") as fin, open(output_mvc, "wb") as fout:
                data = fin.read()

                # Find NAL units by Annex B start codes (0x00 00 01 or 0x00 00 00 01)
                i = 0
                n = len(data)

                while i < n:
                    # Look for start code
                    if i + 3 < n and data[i:i+3] == b"\x00\x00\x01":
                        start_code_len = 3
                    elif i + 4 < n and data[i:i+4] == b"\x00\x00\x00\x01":
                        start_code_len = 4
                    else:
                        fout.write(bytes([data[i]]))
                        i += 1
                        continue

                    fout.write(data[i:i+start_code_len])
                    i += start_code_len

                    if i >= n:
                        break

                    nal_header_byte = data[i]
                    nal_ref_idc = (nal_header_byte >> 5) & 0x03
                    nal_unit_type = nal_header_byte & 0x1F

                    if nal_unit_type in (1, 5):
                        # Convert Slice (Type 1) or IDR (Type 5) into Coded Slice Extension (Type 20)
                        is_anchor = (nal_unit_type == 5)
                        new_nal_byte = (nal_ref_idc << 5) | NAL_SLICE_EXT
                        fout.write(bytes([new_nal_byte]))
                        # Append 3-byte MVC header extension
                        fout.write(mvc_ext_anchor if is_anchor else mvc_ext_header)
                        i += 1
                    else:
                        # Write non-slice NAL unmodified (SPS, PPS, SEI, etc.)
                        fout.write(bytes([nal_header_byte]))
                        i += 1

            return True
        except Exception as e:
            print(f"[StereoForge] MVC packaging error: {e}")
            return False
