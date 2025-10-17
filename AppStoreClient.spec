# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# ******************************************************************************
# !!! 路径已修正为您的环境路径 !!!
# ******************************************************************************
TTKBOOTSTRAP_THEMES_PATH = 'd:\\app_store_backend\\.venv\\Lib\\site-packages\\ttkbootstrap\\themes'


a = Analysis(
    ['desktop_client.py'],
    pathex=['.'], 
    binaries=[],
    
    datas=[
        # 显式包含 ttkbootstrap 的主题数据 (使用修正后的路径)
        (TTKBOOTSTRAP_THEMES_PATH, 'ttkbootstrap/themes'),
        # 确保 icon.ico 被打包到运行时目录
        ('icon.ico', '.') 
    ],
    hiddenimports=[
        'ttkbootstrap.style',
        'ttkbootstrap.themes',
        'PIL.ImageTk', 
        'PIL.Image'
    ],
    
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimizations=[],
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='AppStoreClient',
    debug=False,
    strip=False,
    upx=True,
    # 隐藏控制台窗口
    console=False, 
    # 设置应用程序图标
    icon='icon.ico'
)