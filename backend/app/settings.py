"""运行设置: data/settings.json, 热读取"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)
FILE = DATA_DIR / "settings.json"

DEFAULTS = {"AUTO_GIT_COMMIT": False}
_CACHE: dict | None = None


def get(key: str):
    global _CACHE
    if _CACHE is None:
        reload()
    return _CACHE.get(key, DEFAULTS.get(key))


def set_many(patch: dict):
    global _CACHE
    cur = dict(_CACHE or {})
    cur.update(patch)
    FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    _CACHE = cur


def reload():
    global _CACHE
    if FILE.exists():
        try:
            _CACHE = {**DEFAULTS, **json.loads(FILE.read_text(encoding="utf-8"))}
        except Exception:
            _CACHE = dict(DEFAULTS)
    else:
        _CACHE = dict(DEFAULTS)


reload()