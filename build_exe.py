#!/usr/bin/env python3
"""
Build script for TFT Video Tool Windows executable.
Uses PyInstaller to create a standalone .exe with bundled FFmpeg.

Usage:
    python build_exe.py

Requirements:
    pip install pyinstaller
"""

import os
import sys
import shutil
import subprocess

# Project paths
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, 'dist')
BUILD_DIR = os.path.join(PROJECT_DIR, 'build')
BIN_DIR = os.path.join(PROJECT_DIR, 'bin')
SOURCE_DIR = os.path.join(PROJECT_DIR, 'source')

def clean():
    """Clean previous build artifacts"""
    print("Cleaning previous build...")
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)

def check_dependencies():
    """Check if PyInstaller is installed"""
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])

def create_spec_file():
    """Create PyInstaller spec file"""
    ffmpeg_source = os.path.join(BIN_DIR, 'ffmpeg.exe')
    ffmpeg_dest = os.path.join(DIST_DIR, 'TFT-Video-Tool', 'bin', 'ffmpeg.exe')
    
    # Create destination directories
    os.makedirs(os.path.dirname(ffmpeg_dest), exist_ok=True)
    
    # Copy ffmpeg if it exists
    if os.path.exists(ffmpeg_source):
        shutil.copy(ffmpeg_source, ffmpeg_dest)
        print(f"Copied ffmpeg.exe to {ffmpeg_dest}")
    else:
        print(f"Warning: ffmpeg.exe not found at {ffmpeg_source}")
    
    # Create spec content
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['{PROJECT_DIR}'],
    binaries=[
        ('{BIN_DIR}\\ffmpeg.exe', 'bin'),
    ],
    datas=[
        ('{SOURCE_DIR}', 'source'),
    ],
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'qtawesome',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TFT-Video-Tool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='source\\demo.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TFT-Video-Tool',
)
'''
    
    spec_path = os.path.join(PROJECT_DIR, 'TFT-Video-Tool.spec')
    with open(spec_path, 'w') as f:
        f.write(spec_content)
    
    print(f"Created spec file: {spec_path}")
    return spec_path

def build():
    """Run PyInstaller build"""
    print("Building executable...")
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=TFT-Video-Tool',
        '--onefile',
        '--windowed',
        f'--distpath={DIST_DIR}',
        f'--workpath={BUILD_DIR}',
        '--noconfirm',
        '--add-binary=bin/ffmpeg.exe:bin',
        f'--add-data={SOURCE_DIR}:source',
        '--hidden-import=PySide6',
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui',
        '--hidden-import=PySide6.QtWidgets',
        '--hidden-import=PySide6.QtMultimedia',
        '--hidden-import=PySide6.QtMultimediaWidgets',
        '--hidden-import=qtawesome',
        '--collect-all=qtawesome',
        'main.py'
    ]
    
    result = subprocess.run(cmd, cwd=PROJECT_DIR)
    
    if result.returncode == 0:
        print("\nBuild successful!")
        
        # Verify exe exists
        exe_path = os.path.join(DIST_DIR, 'TFT-Video-Tool.exe')
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"Output: {exe_path}")
            print(f"Size: {size_mb:.1f} MB")
        else:
            print(f"Warning: Expected exe not found at {exe_path}")
    else:
        print(f"\nBuild failed with return code: {result.returncode}")
        sys.exit(1)

def main():
    """Main build function"""
    print("=" * 50)
    print("TFT Video Tool - Windows Build Script")
    print("=" * 50)
    
    if not sys.platform.startswith('win'):
        print("Warning: This script is designed for Windows.")
        print("Building anyway may not produce a working .exe")
    
    clean()
    check_dependencies()
    build()
    
    print("\n" + "=" * 50)
    print("Build complete!")
    print("=" * 50)
    print(f"\nOutput: {os.path.join(DIST_DIR, 'TFT-Video-Tool.exe')}")
    print("\nNote: Include bin/ffmpeg.exe in the same folder as the .exe for full functionality.")

if __name__ == '__main__':
    main()