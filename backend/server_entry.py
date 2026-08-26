"""打包版后端服务入口"""
import os
import sys

home = os.environ.get("NEBULACODE_HOME") or os.getcwd()
os.chdir(home)

# --noconsole 打包下 stdout/stderr 是 None, uvicorn 日志初始化会崩溃.
# 重定向到日志文件(顺便保留引擎运行日志方便排查)
if sys.stdout is None or sys.stderr is None:
    _logf = open(os.path.join(home, "nebulacode-engine.log"),
                 "a", buffering=1, encoding="utf-8", errors="replace")
    if sys.stdout is None:
        sys.stdout = _logf
    if sys.stderr is None:
        sys.stderr = _logf

import uvicorn  # noqa: E402

if __name__ == "__main__":
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8790,
                    log_level="warning")
    except Exception:
        import traceback
        with open(os.path.join(home, "server-error.txt"), "w",
                  encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
