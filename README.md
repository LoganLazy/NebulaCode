# AI Desk — 智能图形化 AI 编码助手（开发中）

图形化、看得见资源的 AI 写代码桌面工具：
不用终端、换模型一点就切、同时跑多个也卡不死。

## 当前进度

- ✅ Agent 内核 v1：工具循环（列目录/读文件/写文件/跑命令）
- ✅ 安全三级：项目内自动 / 越界敏感需批准 / 系统危害永久拒绝
- ✅ 审批流：SSE 先推送审批请求 → 用户允许/拒绝 → 继续
- ✅ 写文件自动备份旧版本 + diff
- ⏳ 前端界面（三栏布局）
- 📋 二期：模型方案管理、多任务标签页、一键回滚

## 后端启动（开发模式）

```bash
cd backend
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python start_daemon.py     # 8790端口, 日志 last-run.log
./stop_daemon.sh                     # 停止
```

## API 一览

```
POST /api/agent/chat/stream   SSE: 对话+步骤+diff+审批请求
POST /api/agent/approve       批准/拒绝 {request_id, allow}
POST /api/fs/list             项目文件树 {path}
GET  /api/file?path=&project= 读预览文件
GET  /api/sys/poll            CPU/内存/磁盘/网络实时
```
