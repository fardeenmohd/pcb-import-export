# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect CustomTkinter themes, fonts, and assets
ctk_datas = collect_data_files('customtkinter')

# Collect Playwright driver files
playwright_datas = collect_data_files('playwright')

# Application data files
datas = [
    ('.env', '.'),
    ('app_icon.ico', '.'),
    ('vision_context.md', '.'),
    ('vision_context_v2.md', '.'),
    ('vision_context_suppliers.md', '.'),
] + ctk_datas + playwright_datas

hiddenimports = [
    'customtkinter',
    'darkdetect',
    'PIL',
    'PIL._tkinter_finder',
    'pydantic',
    'pydantic_core',
    'google',
    'google.genai',
    'google.genai.types',
    'playwright',
    'playwright.sync_api',
    'playwright_stealth',
    'openpyxl',
    'pandas',
    'ddgs',
    'bs4',
    'resource_util',
] + collect_submodules('playwright')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SinoMaganTrade',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico',
)
