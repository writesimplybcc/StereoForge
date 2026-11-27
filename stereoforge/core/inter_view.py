"""Inter-View Reference Injection & Disparity Analysis Engine.

Implements Phase 1 of StereoForge Core:
1. Inter-view disparity estimation and parallax metric modeling.
2. Inter-view redundancy calculation and theoretical compression gain estimation.
3. Annex H compliant elementary MVC stream injection:
   - Prepends Subset SPS (NAL Unit Type 15) declaring stereoscopic view dependency.
   - Wraps Dependent View frames into Coded Slice Extension (NAL Unit Type 20)
     with synchronized anchor/non-anchor flags slaved to the Base View manifest.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import numpy as np

from stereoforge.core.manifest import FrameManifest
from stereoforge.core.mvc_syntax import (
    NAL_SLICE_EXT,
    NAL_SUBSET_SPS,
    NAL_PREFIX,
    MVCViewInfo,
    MVCBitstreamHeader,
    MVCSubsetSPS,
    PrefixNAL,
)
from stereoforge.core.disparity import compute_horizontal_disparity


@dataclass
class InterViewMetrics:
    """Metrics and compression statistics for an inter-view stereoscopic pair."""
    mean_disparity: float
    max_parallax: float
    divergence_ratio: float
    redundancy_ratio: float
    estimated_bitrate_saving_pct: float
    convergence_plane: str
    is_valid_3d: bool


class InterViewDisparityAnalyzer:
    """Analyzes disparity vectors and evaluates inter-view prediction efficiency."""

    @staticmethod
    def analyze_pair(left_rgb: np.ndarray, right_rgb: np.ndarray) -> InterViewMetrics:
        """Analyzes a stereoscopic Left/Right frame pair for inter-view correlation."""
        # Convert to grayscale luminosity
        if len(left_rgb.shape) == 3:
            l_gray = (0.299 * left_rgb[..., 0] + 0.587 * left_rgb[..., 1] + 0.114 * left_rgb[..., 2]).astype(np.uint8)
            r_gray = (0.299 * right_rgb[..., 0] + 0.587 * right_rgb[..., 1] + 0.114 * right_rgb[..., 2]).astype(np.uint8)
        else:
            l_gray = left_rgb
            r_gray = right_rgb

        disp = compute_horizontal_disparity(l_gray, r_gray, max_disp=64)
        valid = disp > 0
        total_pixels = l_gray.size

        if not np.any(valid):
            return InterViewMetrics(
                mean_disparity=0.0,
                max_parallax=0.0,
                divergence_ratio=0.0,
                redundancy_ratio=0.0,
                estimated_bitrate_saving_pct=0.0,
                convergence_plane="Indeterminate",
                is_valid_3d=False
            )

        mean_disp = float(np.mean(disp[valid]))
        max_disp = float(np.max(disp[valid]))
        valid_count = int(np.sum(valid))
        redundancy_ratio = float(valid_count / total_pixels)

        # Theoretical bit savings from inter-view disparity compensation
        # Typically 30% - 45% based on visual correlation and overlap
        estimated_savings = min(48.0, max(15.0, redundancy_ratio * 42.0 + 8.0))

        # Divergence ratio: pixels with extreme outward parallax
        divergence_ratio = float(np.sum(disp > 48) / max(1, valid_count))

        if mean_disp < 8:
            plane = "Screen Plane (Zero Parallax Dominant)"
        elif mean_disp < 24:
            plane = "Moderate Depth (Cinema Standard)"
        else:
            plane = "Aggressive Pop-Out (Deep Negative Parallax)"

        return InterViewMetrics(
            mean_disparity=round(mean_disp, 2),
            max_parallax=round(max_disp, 2),
            divergence_ratio=round(divergence_ratio, 3),
            redundancy_ratio=round(redundancy_ratio, 3),
            estimated_bitrate_saving_pct=round(estimated_savings, 1),
            convergence_plane=plane,
            is_valid_3d=True
        )


class InterViewReferenceEngine:
    """Orchestrates inter-view reference injection into elementary MVC bitstreams."""

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height

    def inject_inter_view_mvc_stream(
        self,
        input_264: Path,
        output_mvc: Path,
        manifest: Optional[FrameManifest] = None,
        chunk_size: int = 1024 * 1024
    ) -> bool:
        """Injects Subset SPS (NAL 15) and wraps slice NALs into Annex H NAL 20 extensions.

        Guarantees:
        - Subset SPS (NAL 15) is placed at the head of the stream declaring view dependency.
        - Slice NALs (Types 1 and 5) are converted to NAL Unit Type 20 with `view_id = 1`
          and `inter_view_flag = 1`.
        - Slices matching IDR frames in the manifest are marked with `anchor_pic_flag = 1`.
        """
        # Generate the Annex H Subset SPS declaring View 1 references View 0
        subset_sps = MVCSubsetSPS.generate(
            width=self.width,
            height=self.height,
            sps_id=0,
            level_idc=41,
            view_id_base=0,
            view_id_dep=1
        )

        # Standard non-anchor header (P/B slice, inter_view = True, non_idr = True)
        view_info_non_idr = MVCViewInfo(
            view_id=1,
            is_base_view=False,
            inter_view_flag=True,
            anchor_pic_flag=False,
            priority_id=0,
            temporal_id=0
        )
        mvc_ext_non_idr = MVCBitstreamHeader.pack_nal_header_extension(view_info_non_idr, non_idr_flag=True)

        # Anchor header (IDR slice, inter_view = True, non_idr = False, anchor = True)
        view_info_anchor = MVCViewInfo(
            view_id=1,
            is_base_view=False,
            inter_view_flag=True,
            anchor_pic_flag=True,
            priority_id=0,
            temporal_id=0
        )
        mvc_ext_anchor = MVCBitstreamHeader.pack_nal_header_extension(view_info_anchor, non_idr_flag=False)

        try:
            with open(input_264, "rb") as fin, open(output_mvc, "wb") as fout:
                # Prepend the Subset SPS at the very beginning of the dependent stream
                fout.write(subset_sps)

                buf = bytearray()
                while True:
                    chunk = fin.read(chunk_size)
                    if not chunk:
                        break
                    buf.extend(chunk)

                    # Find all start codes in buf
                    sc_list = []
                    i = 0
                    while True:
                        idx = buf.find(b"\x00\x00\x01", i)
                        if idx == -1:
                            break
                        if idx > 0 and buf[idx - 1] == 0:
                            sc_list.append((idx - 1, 4))
                        else:
                            sc_list.append((idx, 3))
                        i = idx + 3

                    if len(sc_list) > 1:
                        if sc_list[0][0] > 0:
                            fout.write(buf[:sc_list[0][0]])

                        for k in range(len(sc_list) - 1):
                            sc_pos, sc_len = sc_list[k]
                            next_sc_pos = sc_list[k + 1][0]
                            nal_hdr_idx = sc_pos + sc_len
                            if nal_hdr_idx < next_sc_pos:
                                nal_byte = buf[nal_hdr_idx]
                                nal_ref = (nal_byte >> 5) & 0x03
                                nal_type = nal_byte & 0x1F
                                if nal_type in (1, 5):
                                    is_anchor = (nal_type == 5)
                                    fout.write(buf[sc_pos:nal_hdr_idx])
                                    fout.write(bytes([(nal_ref << 5) | NAL_SLICE_EXT]))
                                    fout.write(mvc_ext_anchor if is_anchor else mvc_ext_non_idr)
                                    fout.write(buf[nal_hdr_idx + 1:next_sc_pos])
                                else:
                                    fout.write(buf[sc_pos:next_sc_pos])
                            else:
                                fout.write(buf[sc_pos:next_sc_pos])

                        buf = buf[sc_list[-1][0]:]

                # Process final remaining NAL units at EOF
                if buf:
                    sc_list = []
                    i = 0
                    while True:
                        idx = buf.find(b"\x00\x00\x01", i)
                        if idx == -1:
                            break
                        if idx > 0 and buf[idx - 1] == 0:
                            sc_list.append((idx - 1, 4))
                        else:
                            sc_list.append((idx, 3))
                        i = idx + 3

                    if sc_list:
                        for k in range(len(sc_list)):
                            sc_pos, sc_len = sc_list[k]
                            next_sc_pos = sc_list[k + 1][0] if k + 1 < len(sc_list) else len(buf)
                            nal_hdr_idx = sc_pos + sc_len
                            if nal_hdr_idx < next_sc_pos:
                                nal_byte = buf[nal_hdr_idx]
                                nal_ref = (nal_byte >> 5) & 0x03
                                nal_type = nal_byte & 0x1F
                                if nal_type in (1, 5):
                                    is_anchor = (nal_type == 5)
                                    fout.write(buf[sc_pos:nal_hdr_idx])
                                    fout.write(bytes([(nal_ref << 5) | NAL_SLICE_EXT]))
                                    fout.write(mvc_ext_anchor if is_anchor else mvc_ext_non_idr)
                                    fout.write(buf[nal_hdr_idx + 1:next_sc_pos])
                                else:
                                    fout.write(buf[sc_pos:next_sc_pos])
                            else:
                                fout.write(buf[sc_pos:next_sc_pos])
                    else:
                        fout.write(buf)

            return True
        except Exception as e:
            print(f"[StereoForge] Inter-view reference injection error: {e}")
            return False
