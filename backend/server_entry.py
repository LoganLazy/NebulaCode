"""打包版后端服务入口"""
import os

home = os.environ.get("NEBULACODE_HOME")
if home:
    os.chdir(home)

import uvicorn  # noqa: E402

if __name__ == "__main__":
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8790,
                    log_level="warning")
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        with open(os.path.join(home, "server-error.txt"), "w",
                  encoding="utf-8") as f:
            f.write(err)
        raise
