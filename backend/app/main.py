"""AI Desk 后端入口"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import psutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import agent
from .agent import resolve_approval

app = FastAPI(title="AI Desk")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ---------------- 资源监控 ----------------

_net_last = {"t": time.time(), "sent": 0, "recv": 0}


@app.get("/api/sys/poll")
def sys_poll():
    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(os.getcwd())
    net = psutil.net_io_counters()
    now = time.time()
    dt = max(now - _net_last["t"], 0.001)
    up_kb = (net.bytes_sent - _net_last["sent"]) / dt / 1024
    down_kb = (net.bytes_recv - _net_last["recv"]) / dt / 1024
    _net_last.update(t=now, sent=net.bytes_sent, recv=net.bytes_recv)
    proc = psutil.Process()
    return {
        "v": "build-2",
        "cpu": cpu,
        "mem_percent": mem.percent,
        "mem_used_gb": round(mem.used / 1073741824, 2),
        "mem_total_gb": round(mem.total / 1073741824, 2),
        "disk_percent": disk.percent,
        "net_up_kbs": round(max(up_kb, 0), 1),
        "net_down_kbs": round(max(down_kb, 0), 1),
        "proc_cpu": proc.cpu_percent(),
        "proc_mem_mb": round(proc.memory_info().rss / 1048576, 1),
        "time": now,
    }


# ---------------- 文件浏览 ----------------

class ListReq(BaseModel):
    path: str


@app.post("/api/fs/list")
def fs_list(req: ListReq):
    root = req.path
    if not os.path.isdir(root):
        raise HTTPException(400, "目录不存在")
    items = []
    try:
        for child in sorted(Path(root).iterdir(),
                            key=lambda x: (x.is_file(), x.name.lower())):
            if child.name.startswith(".") and child.name not in (".env",):
                continue
            items.append({
                "name": child.name,
                "dir": child.is_dir(),
                "size": child.stat().st_size if child.is_file() else 0,
            })
            if len(items) >= 500:
                break
    except PermissionError:
        raise HTTPException(403, "无权限读取该目录")
    return {"items": items}


@app.get("/api/file")
def read_file(path: str, project: str):
    from .safety import safe_path
    full, err = safe_path(project, path)
    if err:
        raise HTTPException(400, err)
    fp = Path(full)
    if not fp.exists() or fp.is_dir():
        raise HTTPException(404, "文件不存在")
    if fp.stat().st_size > 500_000:
        raise HTTPException(400, "文件过大，暂不支持预览")
    return {"content": fp.read_text(encoding="utf-8", errors="ignore")}


# ---------------- Agent ----------------

class AgentReq(BaseModel):
    project: str
    message: str
    session_id: str
    base: str = "https://api.deepseek.com"
    key: str = ""
    model: str = "deepseek-chat"

    class Config:
        extra = "ignore"


_sessions: dict[str, list[dict]] = {}


def _session_history(key: str) -> list[dict]:
    return _sessions.setdefault(key, [])


@app.post("/api/agent/chat/stream")
def agent_chat(req: AgentReq):
    if not os.path.isdir(req.project):
        raise HTTPException(400, f"项目目录不存在: {req.project}")
    if not req.key:
        raise HTTPException(400, "请先在设置中配置 API Key")

    model_cfg = {"base": req.base, "key": req.key, "model": req.model}
    skey = f"{req.project}::{req.session_id}"
    history = _session_history(skey)
    user_msg = {"role": "user", "content": req.message}

    async def gen():
        yield 'data: {"type": "start"}\n\n'
        pieces = []
        try:
            async for ev in agent.run_agent_stream(
                    req.project, req.message, history + [user_msg],
                    model_cfg, skey):
                if ev["type"] == "token":
                    pieces.append(ev["text"])
                elif ev["type"] == "approval_required":
                    # 审批事件立即透传
                    pass
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            answer = "".join(pieces).strip()
            history.append(user_msg)
            if answer:
                history.append({"role": "assistant", "content": answer})
            if len(history) > 60:
                del history[:20]
            yield 'data: {"type": "done"}\n\n'
        except Exception as e:
            yield json.dumps({"type": "error", "msg": str(e)}) and \
                f'data: {json.dumps({"type": "error", "msg": str(e)}, ensure_ascii=False)}\n\n'
            yield 'data: {"type": "done"}\n\n'

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


class ApproveIn(BaseModel):
    request_id: str
    allow: bool


@app.post("/api/agent/approve")
def approve(a: ApproveIn):
    ok = resolve_approval(a.request_id, a.allow)
    print(f"[审批接口] request={a.request_id} allow={a.allow} found={ok}", flush=True)
    return {"code": 0 if ok else 1}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8790)
