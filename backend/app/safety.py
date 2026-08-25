"""安全层: 命令风险分级 + 路径围栏"""
import os
import re
from pathlib import Path

# 永远拒绝(直接危害系统/不可逆)
HARD_BLOCK_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b.*\s+/",
    r"\bsudo\b",
    r"\bshutdown\b", r"\breboot\b", r"\bpoweroff\b", r"\bhalt\b",
    r"\bmkfs\b", r"\bdd\s+if=",
    r">\s*/dev/[sh]d[a-z]", r"\bformat\b\s+[cC]:",
    r"\bdel\s+/[sf]", r"[Rr]emove-Item\s+.*-Recurse.*\s+C:\\\\?$",
    r"\breg\s+(add|delete)", r"\bregedit\b",
    r":\(\)\{.*\};:",            # fork炸弹
    r"\bchmod\s+-R\s+777\s+/",
    r"\bcurl\b.*\|\s*(ba)?sh", r"\bwget\b.*\|\s*(ba)?sh",
    r"\bkill(all)?\s+-9\s+1\b",
    r"/etc/(passwd|shadow|sudoers)",
]

# 需要人工批准(越界或潜在高危)
APPROVAL_PATTERNS = [
    r"\.\./",                          # 试图跳出项目目录
    r"(?<![\w.])/(etc|usr|var|root|home)/",   # 写绝对系统路径
    r"\bgit\s+push\b",
    r"\bnpm\s+publish\b",
    r"\bcurl\b", r"\bwget\b",          # 网络下载需知情
    r"\brm\s+-rf?\b",
    r"\bmv\b\s+\S*\s+/",               # 移动到根
]


def classify_command(cmd: str, project_root: str) -> tuple[str, str]:
    """返回 (verdict, reason)
    verdict: auto=自动执行 | approve=需人工批准 | block=永远拒绝
    """
    cmd_l = " ".join(cmd.split())

    for pat in HARD_BLOCK_PATTERNS:
        if re.search(pat, cmd_l):
            return "block", f"命中危险命令规则: {pat}"

    for pat in APPROVAL_PATTERNS:
        if re.search(pat, cmd_l):
            return "approve", f"包含敏感操作: {pat}"

    # 引用了项目目录外的路径 => 批准制
    root = os.path.abspath(project_root)
    abs_paths = re.findall(r"(?<![\w.~])(/[A-Za-z0-9_./-]+)", cmd_l)
    for p in abs_paths:
        real = os.path.abspath(p)
        if not (real == root or real.startswith(root + os.sep)):
            return "approve", f"涉及项目目录外路径: {p}"

    return "auto", ""


def safe_path(project_root: str, rel_or_abs: str) -> tuple[str | None, str]:
    """把工具传入的路径限制在项目目录内.
    返回 (绝对路径, 错误信息)"""
    root = Path(project_root).resolve()
    p = Path(rel_or_abs)
    if p.is_absolute():
        full = p.resolve()
    else:
        full = (root / p).resolve()
    try:
        full.relative_to(root)
    except ValueError:
        return None, f"路径越界: {rel_or_abs} 不在项目目录内"
    return str(full), ""
