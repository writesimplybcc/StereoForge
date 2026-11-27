"""Python ctypes binding for stereoforge-core native C/C++ engine."""

import ctypes
import os
import sys
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass

# Locate compiled shared library
_lib_names = [
    "stereoforge_mvc.dll",
    "libstereoforge_mvc.so",
    "libstereoforge_mvc.dylib",
]

_search_dirs = [
    Path(__file__).resolve().parent.parent / "build" / "Release",
    Path(__file__).resolve().parent.parent / "build",
    Path(__file__).resolve().parent.parent / "build" / "Debug",
    Path(__file__).resolve().parent.parent / "bin",
    Path(__file__).resolve().parents[2] / "build",
]

_native_lib = None
for d in _search_dirs:
    for name in _lib_names:
        candidate = d / name
        if candidate.exists():
            try:
                _native_lib = ctypes.CDLL(str(candidate))
                break
            except Exception:
                pass
    if _native_lib:
        break


class _ConfigStruct(ctypes.Structure):
    _fields_ = [
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("fps_num", ctypes.c_int),
        ("fps_den", ctypes.c_int),
        ("bitrate_kbps", ctypes.c_int),
        ("gop_size", ctypes.c_int),
        ("strict_bluray", ctypes.c_int),
        ("view_id_base", ctypes.c_int),
        ("view_id_dep", ctypes.c_int),
    ]


class _FrameStruct(ctypes.Structure):
    _fields_ = [
        ("y_plane", ctypes.c_char_p),
        ("u_plane", ctypes.c_char_p),
        ("v_plane", ctypes.c_char_p),
        ("stride_y", ctypes.c_int),
        ("stride_uv", ctypes.c_int),
        ("pts", ctypes.c_int64),
        ("dts", ctypes.c_int64),
        ("is_keyframe", ctypes.c_int),
    ]


class _PacketStruct(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.c_char_p),
        ("size", ctypes.c_size_t),
        ("capacity", ctypes.c_size_t),
        ("pts", ctypes.c_int64),
        ("dts", ctypes.c_int64),
        ("is_keyframe", ctypes.c_int),
    ]


if _native_lib:
    # Explicit 64-bit restypes and argtypes to prevent pointer truncation
    _native_lib.stereoforge_mvc_init.restype = ctypes.c_void_p
    _native_lib.stereoforge_mvc_init.argtypes = [ctypes.POINTER(_ConfigStruct)]

    _native_lib.stereoforge_mvc_get_subset_sps.restype = ctypes.c_int
    _native_lib.stereoforge_mvc_get_subset_sps.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]

    _native_lib.stereoforge_mvc_encode_frame.restype = ctypes.c_int
    _native_lib.stereoforge_mvc_encode_frame.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_FrameStruct),
        ctypes.POINTER(_FrameStruct),
        ctypes.POINTER(_PacketStruct),
    ]

    _native_lib.stereoforge_mvc_close.restype = None
    _native_lib.stereoforge_mvc_close.argtypes = [ctypes.c_void_p]

    _native_lib.stereoforge_mvc_version.restype = ctypes.c_char_p
    _native_lib.stereoforge_mvc_version.argtypes = []


class NativeMVCEngine:
    """High-level Python wrapper around the native stereoforge-core C library."""

    @classmethod
    def is_available(cls) -> bool:
        """Returns True if the compiled native library is available on host."""
        return _native_lib is not None

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        bitrate_kbps: int = 15000,
        fps_num: int = 24000,
        fps_den: int = 1001,
        strict_bluray: bool = True
    ):
        if not self.is_available():
            raise RuntimeError(
                "stereoforge-core native shared library (stereoforge_mvc.dll / .so) not found. "
                "Build stereoforge_core using CMake to enable native C acceleration."
            )

        self.cfg = _ConfigStruct(
            width=width,
            height=height,
            fps_num=fps_num,
            fps_den=fps_den,
            bitrate_kbps=bitrate_kbps,
            gop_size=24,
            strict_bluray=1 if strict_bluray else 0,
            view_id_base=0,
            view_id_dep=1
        )
        self._ctx = _native_lib.stereoforge_mvc_init(ctypes.byref(self.cfg))

    def get_subset_sps(self) -> bytes:
        """Retrieves the Annex H Subset SPS (NAL Unit Type 15)."""
        buf = ctypes.create_string_buffer(512)
        length = _native_lib.stereoforge_mvc_get_subset_sps(self._ctx, buf, len(buf))
        if length > 0:
            return buf.raw[:length]
        raise RuntimeError("Failed to generate Subset SPS from native core")

    def close(self):
        if self._ctx:
            _native_lib.stereoforge_mvc_close(self._ctx)
            self._ctx = None

    def __del__(self):
        self.close()
