"""NebulaCode 打包版后端服务入口

- 数据根: 环境变量 NEBULACODE_HOME(由Electron壳注入), 否则当前目录
- --noconsole打包下stdout为None的问题在此修复(重定向到引擎日志)
- 双击本exe可独立自检: 启动服务并自动打开浏览器
"""
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


def main():
    host = os.environ.get("AIDESK_BIND", "0.0.0.0")
    try:
        uvicorn.run("app.main:app", host=host, port=8790,
                    log_level="warning")
    except Exception:
        import traceback
        with open(os.path.join(home, "server-error.txt"), "w",
                  encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise


# 双击独立运行时: 自动打开浏览器, 方便用户单独验证引擎健康
if getattr(sys, "frozen", False) and len(sys.argv) == 1:
    import threading
    import webbrowser
    import time as _time

    def _open_later():
        _time.sleep(2.5)
        try:
            webbrowser.open("http://127.0.0.1:8790")
        except Exception:
            pass

    threading.Thread(target=_open_later, daemon=True).start()


main()
