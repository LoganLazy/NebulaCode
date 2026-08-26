"""AI Desk 运行时路径与数据根目录.

规则(按优先级):
1. 环境变量 NEBULACODE_HOME (Electron壳注入的便携数据根, exe同级)
2. PyInstaller冻结模式: exe所在目录
3. 开发模式: 本文件所在目录(app/)
"""
import os
import sys
from pathlib import Path


def _base() -> Path:
    env = os.environ.get("NEBULACODE_HOME")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = _base()
DATA_DIR = BASE_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
MODELS_FILE = DATA_DIR / "models.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

for _d in (DATA_DIR, SESSIONS_DIR):
    try:
        _d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
