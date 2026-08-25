"""轻量仓库地图: 目录树 + 各代码文件的关键定义(函数/类), 供Agent开图知全局"""
import os
import time
from pathlib import Path

from .safety import safe_path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "dist", "build", ".aideck", ".next", ".cache",
             "__pycache__", "target", "vendor"}

# 各语言的定义提取正则: (扩展名, [模式])
SIG_PATTERNS = {
    ".py": [r"^\s*(?:async\s+)?def\s+(\w+)", r"^\s*class\s+(\w+)"],
    ".js": [r"(?:function|class)\s+(\w+)", r"(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?(?:function|\()"],
    ".ts": [r"(?:function|class|interface)\s+(\w+)"],
    ".jsx": [r"(?:function|class)\s+(\w+)"],
    ".tsx": [r"(?:function|class|interface)\s+(\w+)"],
    ".go": [r"^func\s+(?:\([^)]+\)\s+)?(\w+)"],
    ".java": [r"(?:public|private|protected)?\s*(?:static\s+)?(?:class|\w+\s+\w+)\s+(\w+)\s*[({]"],
    ".vue": [],
    ".html": [],
    ".css": [],
    ".md": [],
}
CODE_EXTS = set(SIG_PATTERNS.keys())
MAX_FILE_SCAN = 200_000
MAX_MAP_CHARS = 3600
CACHE_TTL = 60

_cache: dict[str, tuple[float, str]] = {}


def _extract_sigs(fp: Path, ext: str) -> list[str]:
    pats = SIG_PATTERNS.get(ext)
    if not pats:
        return []
    import re as _re
    try:
        text = fp.read_text(encoding="utf-8", errors="ignore")[:MAX_FILE_SCAN]
    except Exception:
        return []
    out = []
    seen = set()
    for line in text.splitlines()[:1500]:
        for pat in pats:
            m = _re.match(pat, line) or _re.search(pat, line)
            if m:
                name = m.group(1)
                if name not in seen and not name.startswith("_"):
                    seen.add(name)
                    out.append(name)
                break
    return out[:10]


def build_map(root: str, max_chars: int = MAX_MAP_CHARS) -> str:
    rootp = Path(root)
    lines: list[str] = []

    def add(line: str):
        if sum(len(x) + 1 for x in lines) >= max_chars:
            raise StopIteration
        lines.append(line)

    try:
        for cur, dirs, files in os.walk(rootp):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS
                             and not d.startswith("."))
            rel_cur = os.path.relpath(cur, rootp)
            depth = 0 if rel_cur == "." else rel_cur.count(os.sep) + 1
            if depth > 3:
                dirs[:] = []
                continue
            prefix = "│  " * (depth - 1) + ("├─ " if depth else "")
            if depth:
                add(f"{prefix}{os.path.basename(cur)}/")

            for f in sorted(files):
                if f.startswith("."):
                    continue
                fp = Path(cur) / f
                ext = fp.suffix.lower()
                rel = str(fp.relative_to(rootp))
                try:
                    size = fp.stat().st_size
                except OSError:
                    continue
                sigs = _extract_sigs(fp, ext) if ext in CODE_EXTS and size < MAX_FILE_SCAN else []
                info = f"{f} ({size // 1024}K)" if size > 1024 else f
                if sigs:
                    info += "  ▸ " + ", ".join(sigs)
                try:
                    add(f"{prefix}│  {info}")
                except StopIteration:
                    raise
    except StopIteration:
        lines.append("...(地图截断)")

    return "\n".join(lines)


def cached_map(root: str) -> str | None:
    """带TTL缓存的入口"""
    key = os.path.abspath(root)
    ts, m = _cache.get(key, (0, ""))
    if time.time() - ts < CACHE_TTL:
        return m or None
    try:
        m = build_map(key)
        _cache[key] = (time.time(), m)
        return m or None
    except Exception:
        return None


def tool_repo_map(root: str, args: dict) -> tuple[str, bool]:
    full, err = safe_path(root, args.get("path") or ".")
    if err:
        return err, False
    m = build_map(full)
    return (m or "(空项目)"), True
