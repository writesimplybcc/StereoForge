"""StereoForge: Optical disc drive detection, media sizing advisor, and direct ISO burning engine.
Supports Windows Native (isoburn.exe), ImgBurn (pro BD-50/layer-break control), growisofs (Linux), and hdiutil (macOS).
"""

from __future__ import annotations
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# Exact usable capacities on standard Blu-ray media
BD25_MAX_BYTES = 25_025_314_816  # 23.31 GiB (Single Layer BD-R / BD-RE)
BD50_MAX_BYTES = 50_050_629_632  # 46.61 GiB (Dual Layer BD-R DL)
BD100_MAX_BYTES = 100_103_356_416 # 93.23 GiB (Triple Layer BDXL)


@dataclass
class OpticalDrive:
    """Represents an optical BD/DVD writer drive."""
    drive_letter: str
    name: str
    media_loaded: bool = False
    is_bd_capable: bool = True

    def __str__(self) -> str:
        return f"[{self.drive_letter}] {self.name}"


class DiscMediaAdvisor:
    """Calculates whether a 3D Blu-ray ISO fits on a BD-25, BD-50, or BDXL disc."""

    @staticmethod
    def analyze(size_bytes: int) -> Dict[str, Any]:
        size_gb = size_bytes / (1024 ** 3)
        fits_bd25 = size_bytes <= BD25_MAX_BYTES
        fits_bd50 = size_bytes <= BD50_MAX_BYTES
        fits_bd100 = size_bytes <= BD100_MAX_BYTES

        if fits_bd25:
            rec = "BD-25 (Single Layer)"
            note = f"ISO is {size_gb:.2f} GB. Fits comfortably on a standard 25 GB BD-R disc."
        elif fits_bd50:
            rec = "BD-50 (Dual Layer)"
            note = f"ISO is {size_gb:.2f} GB. Exceeds BD-25; requires a 50 GB Dual-Layer BD-R DL disc."
        elif fits_bd100:
            rec = "BD-100 (BDXL Triple Layer)"
            note = f"ISO is {size_gb:.2f} GB. Requires an ultra-high capacity BDXL disc."
        else:
            rec = "Over-sized (Hard Drive / NAS Only)"
            note = f"ISO is {size_gb:.2f} GB. Exceeds standard physical Blu-ray disc capacities."

        return {
            "size_bytes": size_bytes,
            "size_gb": size_gb,
            "recommended_media": rec,
            "fits_bd25": fits_bd25,
            "fits_bd50": fits_bd50,
            "fits_bd100": fits_bd100,
            "note": note
        }


def detect_optical_drives() -> List[OpticalDrive]:
    """Scans the system for connected CD/DVD/BD optical burner drives."""
    drives: List[OpticalDrive] = []
    current_os = platform.system()

    if current_os == "Windows":
        try:
            # Query WMI / CIM through PowerShell
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_CDROMDrive | Select-Object -Property Drive, Caption, MediaLoaded | ConvertTo-Json"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            import json
            raw = res.stdout.strip()
            if raw:
                try:
                    data = json.loads(raw)
                    items = data if isinstance(data, list) else [data]
                    for it in items:
                        d_letter = str(it.get("Drive") or "").strip()
                        caption = str(it.get("Caption") or "Optical Drive").strip()
                        loaded = bool(it.get("MediaLoaded", False))
                        if d_letter:
                            drives.append(OpticalDrive(drive_letter=d_letter, name=caption, media_loaded=loaded))
                except Exception:
                    pass
        except Exception:
            pass

        # Fallback: Check drive letters using Get-PSDrive
        if not drives:
            try:
                cmd = [
                    "powershell", "-NoProfile", "-Command",
                    "[System.IO.DriveInfo]::GetDrives() | Where-Object { $_.DriveType -eq 'CDRom' } | Select-Object -ExpandProperty Name"
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                for line in res.stdout.splitlines():
                    d = line.strip().rstrip("\\")
                    if d:
                        drives.append(OpticalDrive(drive_letter=d, name=f"Optical Drive ({d})"))
            except Exception:
                pass

    elif current_os == "Linux":
        try:
            res = subprocess.run(
                ["lsblk", "-d", "-o", "NAME,TYPE,MODEL", "-J"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=4
            )
            import json
            data = json.loads(res.stdout)
            for dev in data.get("blockdevices", []):
                if dev.get("type") == "rom":
                    dev_name = f"/dev/{dev.get('NAME')}"
                    model = dev.get("MODEL", "Optical Drive").strip()
                    drives.append(OpticalDrive(drive_letter=dev_name, name=model))
        except Exception:
            pass

    elif current_os == "Darwin":
        try:
            res = subprocess.run(
                ["drutil", "list"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=4
            )
            for line in res.stdout.splitlines():
                if "/dev/" in line:
                    parts = line.strip().split()
                    drives.append(OpticalDrive(drive_letter=parts[0], name="Apple Optical Drive"))
        except Exception:
            pass

    return drives


class BurnerEngine:
    """Manages execution of disc burning jobs with speed control and verification."""

    def __init__(self, custom_imgburn_path: Optional[str] = None):
        self.custom_imgburn_path = custom_imgburn_path

    def find_imgburn(self) -> Optional[str]:
        """Locates ImgBurn on Windows (tools/, standard Program Files, or PATH)."""
        candidates = [
            self.custom_imgburn_path,
            shutil.which("ImgBurn"),
            shutil.which("ImgBurn.exe"),
            r"tools\ImgBurn\ImgBurn.exe",
            r"C:\Program Files (x86)\ImgBurn\ImgBurn.exe",
            r"C:\Program Files\ImgBurn\ImgBurn.exe",
        ]
        for c in candidates:
            if c and (shutil.which(c) or Path(c).is_file()):
                return str(c)
        return None

    def find_windows_isoburn(self) -> Optional[str]:
        """Locates native Windows isoburn.exe utility."""
        isoburn = os.path.expandvars(r"%SystemRoot%\System32\isoburn.exe")
        if Path(isoburn).is_file():
            return isoburn
        if shutil.which("isoburn.exe"):
            return "isoburn.exe"
        return None

    def get_preferred_burner(self) -> Dict[str, Any]:
        """Returns the best available burning tool and its capabilities."""
        imgburn = self.find_imgburn()
        if imgburn:
            return {
                "engine": "imgburn",
                "path": imgburn,
                "label": "ImgBurn (Pro BD-50 & Layer Break Control)",
                "supports_speed": True,
                "supports_verify": True
            }

        if platform.system() == "Windows":
            isoburn = self.find_windows_isoburn()
            if isoburn:
                return {
                    "engine": "isoburn",
                    "path": isoburn,
                    "label": "Windows Native Disc Image Burner (isoburn.exe)",
                    "supports_speed": False,
                    "supports_verify": False
                }

        if platform.system() == "Linux" and shutil.which("growisofs"):
            return {
                "engine": "growisofs",
                "path": shutil.which("growisofs"),
                "label": "growisofs (Linux DVD+RW / BD-R Tools)",
                "supports_speed": True,
                "supports_verify": True
            }

        return {
            "engine": "none",
            "path": None,
            "label": "No burning utility detected",
            "supports_speed": False,
            "supports_verify": False
        }

    def burn(
        self,
        iso_path: Path,
        drive_target: str,
        write_speed: str = "4x",
        verify: bool = True,
        log_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Executes the ISO burn operation using the best available burner."""
        def log(msg: str):
            if log_callback:
                log_callback(msg)
            print(f"[Burner] {msg}")

        if not iso_path.exists():
            log(f"Error: Target ISO does not exist: {iso_path}")
            return False

        burner = self.get_preferred_burner()
        engine = burner.get("engine")
        b_path = burner.get("path")

        if engine == "none" or not b_path:
            log("Error: No optical disc burning tool found.")
            return False

        log(f"Starting burn of '{iso_path.name}' to drive {drive_target} via {burner['label']}...")

        # 1. ImgBurn Execution (Windows Pro)
        if engine == "imgburn":
            speed_val = write_speed.lower().replace("x", "")
            verify_flag = "YES" if verify else "NO"
            # Format drive: Ensure format is e.g. "D:"
            drive_clean = drive_target.rstrip("\\")
            cmd = [
                b_path,
                "/MODE", "WRITE",
                "/SRC", str(iso_path),
                "/DEST", drive_clean,
                "/SPEED", f"{speed_val}x",
                "/START",
                "/CLOSESUCCESS",
                "/VERIFY", verify_flag
            ]
            log(f"Executing: {' '.join(cmd)}")
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                proc.wait()
                if proc.returncode == 0:
                    log("Burn completed successfully!")
                    return True
                else:
                    log(f"ImgBurn exited with code {proc.returncode}")
                    return False
            except Exception as e:
                log(f"Execution error: {e}")
                return False

        # 2. Windows Native isoburn.exe
        elif engine == "isoburn":
            # Usage: isoburn.exe /Q [Drive:] [PathToISO]
            # /Q launches the UI and automatically selects the drive and image
            drive_clean = drive_target.rstrip("\\")
            if not drive_clean.endswith(":"):
                drive_clean += ":"
            cmd = [b_path, "/Q", drive_clean, str(iso_path)]
            log(f"Launching Windows Native Disc Image Burner: {' '.join(cmd)}")
            try:
                proc = subprocess.Popen(cmd)
                proc.wait()
                log("Windows isoburn process completed.")
                return True
            except Exception as e:
                log(f"Execution error: {e}")
                return False

        # 3. Linux growisofs
        elif engine == "growisofs":
            cmd = [b_path, "-dvd-compat", "-Z", f"{drive_target}={iso_path}"]
            if write_speed:
                cmd.extend(["-speed", write_speed.replace("x", "")])
            log(f"Executing growisofs: {' '.join(cmd)}")
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode == 0:
                    log("growisofs completed successfully!")
                    return True
                else:
                    log(f"growisofs error: {res.stderr}")
                    return False
            except Exception as e:
                log(f"Execution error: {e}")
                return False

        log(f"Unsupported burner engine: {engine}")
        return False
