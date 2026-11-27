"""Automated Downloader for StereoForge Portable Tools.

Downloads and sets up:
1. tsMuxeR (v2.7.0 Win64) - Required for 3D Blu-ray ISO authoring
2. subwoofa (Win64) - Open-source lossless DTS-HD Master Audio encoder
"""

import sys
import os
import io
import urllib.request
import zipfile
import subprocess
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent

TSMUXER_URL = "https://github.com/justdan96/tsMuxer/releases/download/v2.7.0/tsMuxer-2.7.0-win64.zip"
SUBWOOFA_URL = "https://github.com/callumcomplains/subwoofa/releases/download/b0.1.0-2026-10-11-18-28-28/Subwoofa-b0.1.0-2026-10-11-18-28-28-windows-portable.zip"


def download_tsmuxer() -> bool:
    target_exe = TOOLS_DIR / "tsMuxeR.exe"
    if target_exe.exists():
        print(f"✅ tsMuxeR already present: {target_exe}")
        return True

    print("📥 Downloading tsMuxeR v2.7.0 for Windows x64...")
    try:
        req = urllib.request.Request(TSMUXER_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for member in zf.namelist():
                if member.lower().endswith("tsmuxer.exe"):
                    with zf.open(member) as src, open(target_exe, "wb") as dst:
                        dst.write(src.read())
                    print(f"✅ Extracted tsMuxeR.exe to: {target_exe}")
                    return True
        print("❌ Could not locate tsMuxeR.exe inside downloaded archive.")
        return False
    except Exception as e:
        print(f"❌ Failed to download tsMuxeR: {e}")
        return False


def download_subwoofa() -> bool:
    target_cli = TOOLS_DIR / "subwoofa-cli.exe"
    target_gui = TOOLS_DIR / "Subwoofa.exe"
    if target_cli.exists():
        print(f"✅ subwoofa already present: {target_cli}")
        return True

    print("📥 Downloading subwoofa (DTS-HD Master Audio Suite)...")
    try:
        req = urllib.request.Request(SUBWOOFA_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(TOOLS_DIR)
        if target_cli.exists():
            print(f"✅ Extracted subwoofa-cli.exe to: {target_cli}")
            return True
        elif target_gui.exists():
            print(f"✅ Extracted Subwoofa.exe to: {target_gui}")
            return True
        print("❌ Could not locate subwoofa executables inside archive.")
        return False
    except Exception as e:
        print(f"❌ Failed to download subwoofa: {e}")
        return False


def verify_tools():
    print("\n🔍 Verifying tool installations...")
    ts = TOOLS_DIR / "tsMuxeR.exe"
    if ts.exists():
        try:
            res = subprocess.run([str(ts)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            first_line = (res.stdout or res.stderr).splitlines()[0] if (res.stdout or res.stderr) else "OK"
            print(f"   💿 tsMuxeR: {first_line}")
        except Exception as e:
            print(f"   💿 tsMuxeR verification error: {e}")
    else:
        print("   💿 tsMuxeR: Not installed")

    sw = TOOLS_DIR / "subwoofa-cli.exe"
    if not sw.exists():
        sw = TOOLS_DIR / "Subwoofa.exe"
    if sw.exists():
        try:
            res = subprocess.run([str(sw), "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            first_line = (res.stdout or res.stderr).strip()
            print(f"   🔊 subwoofa: {first_line}")
        except Exception as e:
            print(f"   🔊 subwoofa verification error: {e}")
    else:
        print("   🔊 subwoofa: Not installed")


def main():
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("  StereoForge Portable Tools Setup")
    print("=" * 60)
    download_tsmuxer()
    download_subwoofa()
    verify_tools()
    print("=" * 60)
    print("Setup completed successfully.")


if __name__ == "__main__":
    main()
