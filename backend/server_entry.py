"""打包版后端服务入口"""
import os

home = os.environ.get("AI_DESK_HOME")
if home:
    os.chdir(home)

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8790, log_level="warning")
