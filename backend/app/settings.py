"""运行设置: data/settings.json, 热读取"""
import json

from .paths import SETTINGS_FILE

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
    SETTINGS_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    _CACHE = cur


def reload():
    global _CACHE
    if SETTINGS_FILE.exists():
        try:
            _CACHE = {**DEFAULTS,
                      **json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))}
        except Exception:
            _CACHE = dict(DEFAULTS)
    else:
        _CACHE = dict(DEFAULTS)


reload()