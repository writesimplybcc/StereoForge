"""StereoForge Portable Release Packager.

Constructs a standalone, zero-setup portable distribution for Windows x64.
"""

import sys
import shutil
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "dist"
PACKAGE_NAME = "StereoForge_Portable_Win64"
TARGET_DIR = DIST_DIR / PACKAGE_NAME


def build_package():
    print(f"📦 Packaging StereoForge Portable Distribution: {PACKAGE_NAME}...")

    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR, ignore_errors=True)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy Python Package
    print("   -> Copying stereoforge python package...")
    shutil.copytree(REPO_ROOT / "stereoforge", TARGET_DIR / "stereoforge", dirs_exist_ok=True)

    # 2. Copy Native Core
    print("   -> Copying stereoforge_core and native C/C++ DLLs...")
    shutil.copytree(
        REPO_ROOT / "stereoforge_core",
        TARGET_DIR / "stereoforge_core",
        ignore=shutil.ignore_patterns("*.obj", "*.iobj", "*.ipdb", "*.tlog"),
        dirs_exist_ok=True
    )

    # 3. Ensure and Copy Tools (tsMuxeR and Subwoofa)
    print("   -> Setting up bundled tools (tsMuxeR and Subwoofa)...")
    target_tools = TARGET_DIR / "tools"
    target_tools.mkdir(exist_ok=True)
    tools_src = REPO_ROOT / "tools"

    if not (tools_src / "tsMuxeR.exe").exists() or not (tools_src / "subwoofa-cli.exe").exists():
        print("   -> Missing tools detected. Running download_tools...")
        import subprocess
        subprocess.run([sys.executable, str(tools_src / "download_tools.py")], check=True)

    shutil.copy(tools_src / "download_tools.py", target_tools / "download_tools.py")
    if (tools_src / "tsMuxeR.exe").exists():
        shutil.copy(tools_src / "tsMuxeR.exe", target_tools / "tsMuxeR.exe")
    if (tools_src / "subwoofa-cli.exe").exists():
        shutil.copy(tools_src / "subwoofa-cli.exe", target_tools / "subwoofa-cli.exe")

    # 4. Copy Launchers and Metadata
    print("   -> Copying launchers, requirements, and documentation...")
    shutil.copy(REPO_ROOT / "run_stereoforge.bat", TARGET_DIR / "run_stereoforge.bat")
    shutil.copy(REPO_ROOT / "run_stereoforge.ps1", TARGET_DIR / "run_stereoforge.ps1")
    shutil.copy(REPO_ROOT / "requirements.txt", TARGET_DIR / "requirements.txt")
    shutil.copy(REPO_ROOT / "pyproject.toml", TARGET_DIR / "pyproject.toml")
    shutil.copy(REPO_ROOT / "README.md", TARGET_DIR / "README.md")
    if (REPO_ROOT / "LICENSE").exists():
        shutil.copy(REPO_ROOT / "LICENSE", TARGET_DIR / "LICENSE")

    # Write Portable Quick Start Guide
    quick_start = TARGET_DIR / "README_PORTABLE.txt"
    quick_start.write_text(
        "StereoForge Portable Edition\n"
        "============================\n\n"
        "Conception & Vision: writesimply.bcc\n"
        "Architecture & Code: Gemini\n"
        "DTS-HD Master Audio Engine: Subwoofa by Callum (callumcomplains/subwoofa)\n\n"
        "Quick Start:\n"
        "1. Double-click 'run_stereoforge.bat' to launch the GUI.\n"
        "   (All bundled tools, tsMuxeR and Subwoofa, are included in tools/).\n"
        "2. To verify or re-download tools at any time, run: python tools/download_tools.py\n\n"
        "Documentation & Source: https://github.com/writesimplybcc/StereoForge\n"
    )

    # 5. Create Zip Archive
    zip_path = DIST_DIR / f"{PACKAGE_NAME}.zip"
    print(f"   -> Creating compressed zip archive: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in TARGET_DIR.rglob("*"):
            rel = p.relative_to(DIST_DIR)
            zf.write(p, rel)

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"🎉 Portable package created successfully! Size: {zip_size_mb:.2f} MB")
    print(f"   Destination: {zip_path}")
    return zip_path


if __name__ == "__main__":
    build_package()
