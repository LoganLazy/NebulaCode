"""Agent 内核: 工具调用循环 + 安全审批 + 步骤事件流"""
import asyncio
import difflib
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

from .safety import classify_command, safe_path

MAX_ITER = 30
CMD_TIMEOUT = 180
APPROVAL_TIMEOUT = 600

# request_id -> {"event": asyncio.Event, "allow": bool|None}
PENDING_APPROVALS: dict[str, dict] = {}


def resolve_approval(request_id: str, allow: bool) -> bool:
    """线程安全: 从任意线程调用都会正确唤醒等待中的事件循环"""
    item = PENDING_APPROVALS.get(request_id)
    if not item:
        return False
    item["allow"] = allow
    try:
        item["loop"].call_soon_threadsafe(item["event"].set)
    except RuntimeError:
        item["event"].set()
    return True


def get_tools() -> list[dict]:
    return [
        {"type": "function", "function": {
            "name": "list_dir",
            "description": "列出项目里某个目录的内容(文件与子目录)",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "相对项目根的路径, 默认为根目录"}}}},
        },
        {"type": "function", "function": {
            "name": "read_file",
            "description": "读取项目内某个文本文件的内容",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string", "description": "相对项目根的文件路径"}},
                "required": ["path"]}},
        },
        {"type": "function", "function": {
            "name": "write_file",
            "description": "创建或覆盖项目内的文本文件。系统会自动备份旧版本并生成diff。",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"},
                "content": {"type": "string", "description": "完整的文件新内容"}},
                "required": ["path", "content"]}},
        },
        {"type": "function", "function": {
            "name": "run_command",
            "description": "在项目根目录执行一条shell命令(有超时限制)。涉及系统级或项目外的危险操作会被拦截等待用户批准。",
            "parameters": {"type": "object", "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "description": "秒, 默认120"}},
                "required": ["command"]}},
        },
    ]


SYSTEM_PROMPT = """你是 SecondBrain 团队打造的图形化编码助手 AI Desk, 运行在用户的本机上。

工作规则:
1. 你只能在指定的项目目录内活动, 所有文件路径都相对项目根
2. 改代码前先读相关文件了解现状; 改完可以跑命令验证
3. 用户说中文你就用中文思考和汇报
4. 每次写文件只写必要修改, 不要重排无关内容
5. 全部任务完成后, 用简短总结回复用户: 做了什么、改了哪些文件、如何验证

当前项目根目录: {root}
操作系统: {os}"""


async def _chat(model_cfg: dict, messages: list[dict], tools: list[dict]):
    """流式调用模型, 返回 (content, tool_calls_list)"""
    content_parts: list[str] = []
    pending: dict[int, dict] = {}
    finish = ""

    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream(
            "POST",
            model_cfg["base"].rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {model_cfg['key']}"},
            json={
                "model": model_cfg["model"],
                "messages": messages,
                "tools": tools,
                "temperature": 0.3,
                "max_tokens": 4000,
                "stream": True,
            },
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    j = json.loads(payload)
                except Exception:
                    continue
                choices = j.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta") or {}
                piece = delta.get("content")
                if piece:
                    content_parts.append(piece)
                for tc in delta.get("tool_calls") or []:
                    try:
                        idx = tc.get("index") or 0
                        fn = tc.get("function") or {}
                        slot = pending.setdefault(
                            idx, {"id": "", "name": "", "args": ""})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        if fn.get("name"):
                            slot["name"] = fn["name"]
                        arg = fn.get("arguments")
                        if isinstance(arg, str):
                            slot["args"] += arg
                    except Exception as te:
                        print(f"[agent] tool_call分片异常: {te} raw={tc}",
                              flush=True)
                if choice.get("finish_reason"):
                    finish = choice["finish_reason"]

    content = "".join(content_parts)
    calls = []
    for idx in sorted(pending):
        c = pending[idx]
        try:
            args = json.loads(c["args"]) if c["args"] else {}
        except Exception:
            args = {"_raw": c["args"]}
        calls.append({"id": c["id"] or f"call_{idx}",
                      "name": c["name"], "args": args})
    return content, calls, finish


# ---------------- 工具实现 ----------------

def _tool_list_dir(root: str, args: dict):
    path, err = safe_path(root, args.get("path", "."))
    if err:
        return err, False
    p = Path(path)
    items = []
    for child in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name)):
        tag = "📁" if child.is_dir() else "📄"
        size = f" {child.stat().st_size}B" if child.is_file() else ""
        items.append(f"{tag} {child.name}{size}")
    if not items:
        return "(空目录)", True
    return "\n".join(items[:200]), True


def _tool_read_file(root: str, args: dict):
    path, err = safe_path(root, args.get("path", ""))
    if err:
        return err, False
    fp = Path(path)
    if not fp.exists():
        return f"文件不存在: {args.get('path')}", False
    text = fp.read_text(encoding="utf-8", errors="ignore")
    if len(text) > 30000:
        text = text[:30000] + "\n...(过长截断)"
    return text, True


def _tool_write_file(root: str, args: dict, emit):
    path, err = safe_path(root, args.get("path", ""))
    if err:
        return err, False
    fp = Path(path)
    new_content = args.get("content", "")
    old_content = fp.read_text(encoding="utf-8", errors="ignore") if fp.exists() else ""

    # 自动备份旧版本
    backup_name = None
    if fp.exists():
        backup_dir = Path(root) / ".aideck" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = fp.name.replace("/", "_")
        backup_name = f"{stamp}_{safe_name}"
        (backup_dir / backup_name).write_text(old_content, encoding="utf-8")

    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(new_content, encoding="utf-8")

    diff = "\n".join(difflib.unified_diff(
        old_content.splitlines(), new_content.splitlines(),
        fromfile=f"a/{args.get('path')}", tofile=f"b/{args.get('path')}",
        lineterm=""))
    if len(diff) > 6000:
        diff = diff[:6000] + "\n...(diff截断)"
    emit({"type": "diff", "path": args.get("path"),
          "diff": diff, "created": not bool(old_content),
          "backup": backup_name})
    return (f"已写入 {len(new_content)} 字符"
            + (" (新建文件)" if not old_content else " (已备份旧版本)")), True


def _exec_command(root: str, cmd: str, timeout: int) -> tuple[str, bool]:
    import subprocess

    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=root, capture_output=True, text=True,
            timeout=timeout,
            env={**os.environ, "TERM": "dumb"})
    except subprocess.TimeoutExpired:
        return f"命令超时({timeout}s)被终止", False

    out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
    out = out.strip()
    if len(out) > 5000:
        out = out[:2500] + "\n...(中间截断)...\n" + out[-2000:]
    summary = f"退出码 {proc.returncode}" + ("\n" + out if out else " (无输出)")
    return summary, proc.returncode == 0


# ---------------- 主循环 ----------------

async def run_agent_stream(project: str, message: str, history: list[dict],
                           model_cfg: dict, session_key: str):
    """异步生成器: 逐步产出事件"""
    root = os.path.abspath(project)
    emit_events: list[dict] = []

    def emit(ev: dict):
        emit_events.append(ev)

    system = SYSTEM_PROMPT.format(root=root, os=sys.platform)
    messages = [{"role": "system", "content": system}]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    tools = get_tools()

    for iteration in range(MAX_ITER):
        try:
            content, calls, _ = await _chat(model_cfg, messages, tools)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()[-600:]
            yield {"type": "error", "msg": f"模型调用失败: {e}\n{tb}"}
            yield {"type": "done"}
            return

        if content:
            yield {"type": "token", "text": content}

        if not calls:
            break  # 模型给出最终答复

        # 执行工具
        messages.append({"role": "assistant", "content": content or None,
                         "tool_calls": [
                             {"id": c["id"], "type": "function",
                              "function": {"name": c["name"],
                                           "arguments": json.dumps(c["args"], ensure_ascii=False)}}
                             for c in calls]})
        for c in calls:
            name, args = c["name"], c["args"]
            yield {"type": "step", "tool": name,
                   "args": {k: (str(v)[:120]) for k, v in args.items()}}

            for ev in emit_events:
                yield ev
            emit_events.clear()

            if name == "list_dir":
                result, ok = _tool_list_dir(root, args)
            elif name == "read_file":
                result, ok = _tool_read_file(root, args)
            elif name == "write_file":
                result, ok = _tool_write_file(root, args, emit)
            elif name == "run_command":
                import subprocess as _sp
                cmd = args.get("command", "")
                timeout = min(int(args.get("timeout", CMD_TIMEOUT)), 600)
                verdict, reason = classify_command(cmd, root)

                if verdict == "block":
                    result = f"该命令被安全策略永久拒绝: {reason}\n请不要尝试此类操作。"
                    ok = False
                else:
                    if verdict == "approve":
                        req_id = uuid.uuid4().hex[:12]
                        ev = asyncio.Event()
                        loop = asyncio.get_running_loop()
                        PENDING_APPROVALS[req_id] = {
                            "event": ev, "allow": None,
                            "cmd": cmd, "loop": loop}
                        # 关键: 先把审批请求推给前端, 再进入等待
                        yield {"type": "approval_required",
                               "request_id": req_id,
                               "command": cmd, "reason": reason}
                        print(f"[审批] 等待批准 id={req_id} cmd={cmd}", flush=True)
                        try:
                            await asyncio.wait_for(ev.wait(),
                                                   timeout=APPROVAL_TIMEOUT)
                            allowed = PENDING_APPROVALS[req_id]["allow"]
                        except asyncio.TimeoutError:
                            allowed = False
                        PENDING_APPROVALS.pop(req_id, None)
                        print(f"[审批] 结果 id={req_id} allow={allowed}",
                              flush=True)
                        if not allowed:
                            result = "用户未批准或未及时批准该操作。请改用项目目录内的安全方案。"
                            ok = False
                        else:
                            result, ok = _exec_command(root, cmd, timeout)
                    else:
                        result, ok = _exec_command(root, cmd, timeout)
            else:
                result, ok = f"未知工具 {name}", False

            for ev in emit_events:
                yield ev
            emit_events.clear()

            yield {"type": "step_result", "tool": name, "ok": ok,
                   "summary": result[:160]}
            messages.append({"role": "tool", "tool_call_id": c["id"],
                             "content": result})
    else:
        yield {"type": "token",
               "text": "\n\n(达到单轮步数上限, 如需继续请再说一声)"}

    for ev in emit_events:
        yield ev
    yield {"type": "done"}
