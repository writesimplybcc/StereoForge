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
from stereoforge.pipeline.ingest import MediaProfile, IngestionEngine, StereoFormat
from stereoforge.pipeline.pass1_base import detect_best_h264_encoder, get_h264_encoder_options


class DependentViewEncoder:
    """Manages Pass 2 MVC encoding slaved to the base view manifest."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg", encoder: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin
        self.encoder = encoder or detect_best_h264_encoder(ffmpeg_bin)

    def encode(
        self,
        profile: MediaProfile,
        base_bitstream_path: Path,
        manifest: FrameManifest,
        output_dependent_264: Path,
        output_dependent_mvc: Optional[Path] = None,
        bitrate_kbps: int = 12000,
        strict_bluray: bool = True,
        swap_eyes: bool = False,
        right_file: Optional[Path] = None,
        progress_cb: Optional[Callable[[int, int], None]] = None,
        use_native_mvc: bool = False
    ) -> bool:
        """Encodes the Dependent View (Right Eye) slaved to the manifest."""
        if use_native_mvc and output_dependent_mvc:
            print("[StereoForge] Running Native C stereoforge-core (True MVC Inter-View Reference Injection)...")
            ok = self._encode_native_mvc(
                profile=profile,
                base_bitstream_path=base_bitstream_path,
                manifest=manifest,
                output_dependent_mvc=output_dependent_mvc,
                bitrate_kbps=bitrate_kbps,
                strict_bluray=strict_bluray,
                swap_eyes=swap_eyes,
                right_file=right_file,
                progress_cb=progress_cb
            )
            if ok:
                return True
            print("[StereoForge] Falling back to GPU turbo encoding...")

        input_media = right_file if (right_file and right_file.exists()) else profile.path
        _, right_filter = IngestionEngine.get_filter_chains(profile, swap_eyes=swap_eyes)

        print(f"[StereoForge] Pass 2 Dependent View encoding with {self.encoder} (Target: {bitrate_kbps} kbps)...")
        print(f"             Input: {input_media.name}")
        print(f"             Synchronizing across {len(manifest.frames)} frames from manifest...")

        # Pass 2 Video Encoding with exact GOP locking
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(input_media),
        ]
        if profile.stereo_format == StereoFormat.MULTI_STREAM_AVI:
            cmd.extend(["-map", "0:v:0" if swap_eyes else "0:v:1"])
        cmd.extend([
            "-vf", right_filter,
            "-pix_fmt", "yuv420p",
        ])
        cmd.extend(get_h264_encoder_options(self.encoder, bitrate_kbps, strict_bluray=strict_bluray))
        cmd.extend([
            "-an",
            "-f", "h264",
            str(output_dependent_264)
        ])

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[StereoForge] Pass 2 failed: {e.stderr}")
            return False

        if output_dependent_mvc:
            # Convert raw H.264 slices to Annex H MVC NAL Unit Type 20 slices for tsMuxeR / Blu-ray
            print("[StereoForge] Packaging Annex H MVC Subset SPS and NAL Unit Type 20 slices for 3D Blu-ray...")
            return self._wrap_mvc_stream(output_dependent_264, output_dependent_mvc, manifest)

        return True

    def _encode_native_mvc(
        self,
        profile: MediaProfile,
        base_bitstream_path: Path,
        manifest: FrameManifest,
        output_dependent_mvc: Path,
        bitrate_kbps: int,
        strict_bluray: bool = True,
        swap_eyes: bool = False,
        right_file: Optional[Path] = None,
        progress_cb: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """Encodes Dependent View directly via native C stereoforge-core engine."""
        try:
            from stereoforge_core.python.native_bridge import NativeMVCEngine
            if not NativeMVCEngine.is_available():
                return False
        except Exception:
            return False

        w, h = 1920, 1080
        fps_num = int(profile.fps * 1000)
        fps_den = 1000
        native = NativeMVCEngine(width=w, height=h, bitrate_kbps=bitrate_kbps, fps_num=fps_num, fps_den=fps_den, strict_bluray=strict_bluray)
        sps = native.get_subset_sps()

        input_media = right_file if (right_file and right_file.exists()) else profile.path
        _, right_filter = IngestionEngine.get_filter_chains(profile, target_w=w, target_h=h, swap_eyes=swap_eyes)

        # Pipe 1: Reconstructed Left Eye decoded from base_bitstream_path
        cmd_l = [
            self.ffmpeg_bin, "-y",
            "-i", str(base_bitstream_path),
            "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"
        ]
        # Pipe 2: Right Eye raw video
        cmd_r = [
            self.ffmpeg_bin, "-y",
            "-i", str(input_media),
        ]
        if profile.stereo_format == StereoFormat.MULTI_STREAM_AVI:
            cmd_r.extend(["-map", "0:v:0" if swap_eyes else "0:v:1"])
        cmd_r.extend([
            "-vf", right_filter,
            "-pix_fmt", "yuv420p", "-f", "rawvideo", "-"
        ])

        proc_l = subprocess.Popen(cmd_l, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        proc_r = subprocess.Popen(cmd_r, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        frame_sz = w * h * 3 // 2
        luma_sz = w * h
        total_frames = len(manifest.frames)

        try:
            with open(output_dependent_mvc, "wb") as fout:
                fout.write(sps)
                f_idx = 0
                while True:
                    raw_l = proc_l.stdout.read(frame_sz)
                    raw_r = proc_r.stdout.read(frame_sz)
                    if len(raw_l) < frame_sz or len(raw_r) < frame_sz:
                        break

                    is_key = (f_idx % 24 == 0)
                    if f_idx < total_frames:
                        is_key = manifest.frames[f_idx].is_keyframe

                    if is_key and f_idx > 0:
                        fout.write(sps)

                    nal20 = native.encode_dependent_frame(
                        right_y=raw_r[:luma_sz],
                        left_y=raw_l[:luma_sz],
                        is_keyframe=is_key,
                        pts=f_idx * 1001,
                        dts=f_idx * 1001
                    )
                    fout.write(nal20)
                    f_idx += 1
                    if progress_cb and total_frames > 0 and (f_idx % 10 == 0 or f_idx == total_frames):
                        progress_cb(f_idx, total_frames)

            return True
        except Exception as e:
            print(f"[StereoForge] Native MVC encode error: {e}")
            return False
        finally:
            proc_l.kill()
            proc_r.kill()
            native.close()

    def _wrap_mvc_stream(
        self,
        input_264: Path,
        output_mvc: Path,
        manifest: Optional[FrameManifest] = None,
        chunk_size: int = 1024 * 1024
    ) -> bool:
        """Wraps standard slice NAL units (Type 1 and 5) into MVC Type 20 extension slices.
        
        Uses chunked streaming buffers (1MB default) to process multi-gigabyte bitstreams
        without loading the entire file into memory.
        """
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

                    # Process all complete NAL units except the last (which may be incomplete across chunks)
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
                                    fout.write(buf[sc_pos:nal_hdr_idx])
                                    fout.write(bytes([(nal_ref << 5) | NAL_SLICE_EXT]))
                                    fout.write(mvc_ext_anchor if nal_type == 5 else mvc_ext_header)
                                    fout.write(buf[nal_hdr_idx + 1:next_sc_pos])
                                else:
                                    fout.write(buf[sc_pos:next_sc_pos])
                            else:
                                fout.write(buf[sc_pos:next_sc_pos])

                        buf = buf[sc_list[-1][0]:]

                # Process final remaining NAL units in buffer at EOF
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
                                    fout.write(buf[sc_pos:nal_hdr_idx])
                                    fout.write(bytes([(nal_ref << 5) | NAL_SLICE_EXT]))
                                    fout.write(mvc_ext_anchor if nal_type == 5 else mvc_ext_header)
                                    fout.write(buf[nal_hdr_idx + 1:next_sc_pos])
                                else:
                                    fout.write(buf[sc_pos:next_sc_pos])
                            else:
                                fout.write(buf[sc_pos:next_sc_pos])
                    else:
                        fout.write(buf)

            return True
        except Exception as e:
            print(f"[StereoForge] MVC packaging error: {e}")
            return False
