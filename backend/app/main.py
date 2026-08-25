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

_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
from .agent import resolve_approval

app = FastAPI(title="AI Desk")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ---------------- 回滚 ----------------

class RollbackIn(BaseModel):
    project: str
    path: str
    backup: str


class ListBkIn(BaseModel):
    project: str
    path: str


@app.post("/api/backups/list")
def backups_list(b: ListBkIn):
    from .safety import safe_path
    full, err = safe_path(b.project, b.path)
    if err:
        raise HTTPException(400, err)
    bk_dir = Path(full).parent / ".aideck" / "backups"
    name = Path(full).name
    out = []
    if bk_dir.exists():
        for f in sorted(bk_dir.glob(f"*_{name}"), reverse=True):
            out.append({"name": f.name,
                        "time": time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.strptime(f.name.split("_")[0], "%Y%m%d_%H%M%S"))})
    return {"backups": out[:20]}


@app.post("/api/rollback")
def rollback(b: RollbackIn):
    from .safety import safe_path
    full, err = safe_path(b.project, b.path)
    if err:
        raise HTTPException(400, err)
    fp = Path(full)
    bk_name = os.path.basename(b.backup)
    bk = fp.parent / ".aideck" / "backups" / bk_name
    if not bk.exists():
        raise HTTPException(404, "备份不存在")
    # 回滚前先备份当前版本(回滚本身可撤销)
    if fp.exists():
        cur_bk = fp.parent / ".aideck" / "backups" / (
            "pre_rollback_" + time.strftime("%Y%m%d_%H%M%S") + "_" + fp.name)
        cur_bk.write_text(fp.read_text(encoding="utf-8", errors="ignore"),
                          encoding="utf-8")
    fp.write_text(bk.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    return {"code": 0, "msg": f"已回滚到 {bk_name}"}


# ---------------- 模型方案管理 ----------------

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)
MODELS_FILE = DATA_DIR / "models.json"


def _load_models() -> dict:
    if MODELS_FILE.exists():
        try:
            return json.loads(MODELS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"profiles": [], "active": ""}


def _save_models(cfg: dict):
    MODELS_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                           encoding="utf-8")


class ProfileIn(BaseModel):
    id: str | None = None
    name: str
    base: str
    key: str = ""
    model: str


@app.get("/api/models")
def get_models():
    return _load_models()


class IdIn(BaseModel):
    id: str


@app.post("/api/models/profile")
def save_profile(p: ProfileIn):
    cfg = _load_models()
    plist = cfg.setdefault("profiles", [])
    if p.id:
        for i, x in enumerate(plist):
            if x["id"] == p.id:
                newp = p.dict()
                if not newp["key"]:  # 留空保留旧key
                    newp["key"] = x["key"]
                plist[i] = newp
                break
        else:
            raise HTTPException(404, "方案不存在")
    else:
        import random
        pid = "mp_" + "".join(random.choices("0123456789abcdef", k=6))
        newp = p.dict()
        newp["id"] = pid
        plist.append(newp)
    _save_models(cfg)
    return {"code": 0, "id": (plist[-1]["id"] if not p.id else p.id)}


@app.post("/api/models/delete")
def delete_profile(b: IdIn):
    cfg = _load_models()
    cfg["profiles"] = [x for x in cfg.get("profiles", []) if x["id"] != b.id]
    if cfg.get("active") == b.id:
        cfg["active"] = ""
    _save_models(cfg)
    return {"code": 0}


@app.post("/api/models/active")
def set_active(b: IdIn):
    cfg = _load_models()
    if not any(x["id"] == b.id for x in cfg.get("profiles", [])):
        raise HTTPException(404, "方案不存在")
    cfg["active"] = b.id
    _save_models(cfg)
    return {"code": 0}


class TestIn(BaseModel):
    base: str
    key: str = ""
    model: str


@app.post("/api/models/test")
def test_profile(t: TestIn):
    import httpx
    try:
        r = httpx.post(
            t.base.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {t.key}"},
            json={"model": t.model,
                  "messages": [{"role": "user", "content": "hi"}],
                  "max_tokens": 5},
            timeout=30)
        r.raise_for_status()
        return {"code": 0, "msg": f"连通 ✓ ({t.model})"}
    except Exception as e:
        msg = str(e)
        if "401" in msg: msg = "Key无效或未授权(401)"
        elif "404" in msg: msg = "地址或模型不存在(404)"
        elif "timed out" in msg.lower(): msg = "连接超时"
        return {"code": 1, "msg": msg}


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
    session_id: str = "main"
    base: str | None = None
    key: str | None = None
    model: str | None = None

    class Config:
        extra = "ignore"


def resolve_model(req: AgentReq) -> dict:
    """前端显式传入优先; 否则用激活的方案"""
    if req.base and req.key and req.model:
        return {"base": req.base, "key": req.key, "model": req.model}
    cfg = _load_models()
    act = next((x for x in cfg.get("profiles", [])
                if x["id"] == cfg.get("active")), None)
    if act:
        return {"base": act["base"], "key": act["key"], "model": act["model"]}
    raise HTTPException(400, "没有已激活的模型方案，请先在设置里添加并启用一个")


_sessions: dict[str, list[dict]] = {}


def _session_history(key: str) -> list[dict]:
    return _sessions.setdefault(key, [])


@app.post("/api/agent/chat/stream")
def agent_chat(req: AgentReq):
    if not os.path.isdir(req.project):
        raise HTTPException(400, f"项目目录不存在: {req.project}")
    model_cfg = resolve_model(req)
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


if _dist.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="fe")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8790)
