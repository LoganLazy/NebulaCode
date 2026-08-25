# AI Desk — 智能图形化 AI 编码助手

不用终端、换模型一点就切、同时跑多个也卡不死。

## Windows 版使用

1. 解压 `AIDesk-Windows-x64.zip` 到任意位置
2. 双击 `AIDesk.exe`（首次弹 SmartScreen 警告 → 更多信息 → 仍要运行）
3. 顶栏输入你的项目目录绝对路径 → 打开项目
4. ⚙ 模型 → 添加/选择模型方案并填入 API Key
5. 对话区下达任务，观察步骤卡片与资源仪表盘

- 所有数据保存在 exe 同级的 `data/` 目录，整个文件夹拷走即迁移
- `projects/` 为建议的代码项目存放处
- AI 改文件自动备份旧版本到项目内 `.aideck/backups/`，diff 卡片可一键回滚
- 越界/敏感操作会弹出审批卡片，需你手动允许

## 开发模式（本仓库源码）

```bash
# 后端
cd backend && python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python start_daemon.py        # 8790端口

# 前端
cd frontend && npm install && npm run build

# 浏览器访问 http://127.0.0.1:8790 或 Electron壳:
cd ../electron && npm install && npx electron .
```

## 架构

```
Electron(Vue3) ←SSE→ FastAPI 后端
                    ├── Agent循环: list_dir/read_file/write_file/
                    │              replace_in_file/search_code/repo_map/run_command
                    ├── 安全三级: 项目内自动 / 越界批准 / 危险拒绝
                    ├── 写文件自动备份+diff+可选git检查点
                    └── psutil资源采集(1s推送)
```

## License

MIT
