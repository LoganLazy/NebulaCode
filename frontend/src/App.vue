<template>
  <div class="app">
    <!-- 顶栏: 项目路径 + 模型设置 -->
    <header class="topbar">
      <span class="brand">🛠 AI Desk</span>
      <input v-model="project" class="proj-input"
             placeholder="输入项目目录绝对路径，如 /home/xxx/myproject"
             @keydown.enter="openProject" />
      <button class="open-btn" :class="{ active: projectOpen }" @click="openProject">
        {{ projectOpen ? "✓ 已打开" : "打开项目" }}
      </button>
      <button class="cfg-btn" @click="showCfg = !showCfg">⚙ 模型</button>
    </header>

    <!-- 模型配置浮层 -->
    <div v-if="showCfg" class="cfg-mask" @click.self="showCfg = false">
      <div class="cfg card">
        <h4>模型接入（OpenAI 兼容）</h4>
        <label>接口地址</label>
        <input v-model="model.base" placeholder="https://api.deepseek.com" />
        <label>模型名</label>
        <input v-model="model.model" placeholder="deepseek-chat" />
        <label>API Key</label>
        <input v-model="model.key" type="password" placeholder="sk-…" />
        <div class="presets">
          <button @click="preset('https://api.deepseek.com', 'deepseek-chat')">DeepSeek</button>
          <button @click="preset('https://ai.121628.xyz/v1', 'deepseek-v4-flash-free')">中转站</button>
          <button @click="preset('http://127.0.0.1:11434/v1', 'qwen2.5-coder:7b')">Ollama本地</button>
        </div>
        <button class="save" @click="saveModel">保存</button>
      </div>
    </div>

    <!-- 三栏主体 -->
    <main class="main">
      <section class="pane left">
        <FileTree v-if="projectOpen" :root="project" />
        <div v-else class="placeholder">
          <p>① 填写项目路径并打开</p>
          <p>② 在右侧对话下达任务</p>
          <p>③ 观察步骤卡片与资源占用</p>
        </div>
      </section>

      <section class="pane mid">
        <ChatPanel :project="projectOpen ? project : ''" :model="savedModel"
                   @changed="fileTreeKey++" />
      </section>

      <section class="pane right">
        <ResPanel />
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue"
import { api } from "./api"

const project = ref(localStorage.getItem("aidesk.project") || "")
const projectOpen = ref(false)
const showCfg = ref(false)
const fileTreeKey = ref(0)

const savedModel = ref(JSON.parse(localStorage.getItem("aidesk.model") || "null") || {
  base: "https://api.deepseek.com",
  key: "",
  model: "deepseek-chat"
})

const model = ref({ ...savedModel.value })

function preset(base, m) {
  model.value.base = base
  model.value.model = m
}
function saveModel() {
  if (!model.value.key.trim()) {
    alert("请填写 API Key")
    return
  }
  savedModel.value = { ...model.value }
  localStorage.setItem("aidesk.model", JSON.stringify(savedModel.value))
  showCfg.value = false
}

function openProject() {
  const p = project.value.trim()
  if (!p.startsWith("/")) {
    alert("请输入绝对路径")
    return
  }
  api.fsList(p).then(() => {
    projectOpen.value = true
    localStorage.setItem("aidesk.project", p)
  }).catch(e => alert("打开失败: " + e.message))
}

onMounted(() => {
  if (project.value) openProject()
})
</script>

<style scoped>
.app { display: flex; flex-direction: column; height: 100vh; }

.topbar {
  display: flex; gap: 10px; align-items: center;
  padding: 10px 16px;
  background: var(--panel);
  border-bottom: 1px solid var(--border);
}
.brand { font-weight: 800; font-size: 15.5px; margin-right: 6px; }
.proj-input {
  flex: 1;
  background: var(--panel2);
  border: 1px solid var(--border);
  border-radius: 9px;
  padding: 9px 13px;
  color: var(--text);
  outline: none;
  font-size: 13.5px;
}
.proj-input:focus { border-color: var(--accent); }
.open-btn, .cfg-btn {
  background: var(--panel2); color: var(--text);
  border: 1px solid var(--border); border-radius: 9px;
  padding: 9px 15px; cursor: pointer; font-size: 13.5px;
}
.open-btn.active { border-color: var(--ok); color: var(--ok); }
.cfg-btn:hover, .open-btn:hover { border-color: var(--accent); }

.cfg-mask {
  position: fixed; inset: 0; z-index: 40;
  background: rgba(0,0,0,.55);
  display: flex; align-items: center; justify-content: center;
}
.cfg {
  width: 420px;
  display: flex; flex-direction: column; gap: 8px;
  background: var(--panel);
  border-radius: 14px;
  padding: 20px;
}
.cfg h4 { margin: 0 0 4px; }
.cfg label { color: var(--muted); font-size: 12.5px; }
.cfg input {
  background: var(--bg); color: var(--text);
  border: 1px solid var(--border); border-radius: 9px;
  padding: 10px 12px; outline: none; font-size: 13.5px;
}
.cfg input:focus { border-color: var(--accent); }
.presets { display: flex; gap: 8px; }
.presets button {
  flex: 1; background: var(--panel2); color: var(--text);
  border: 1px solid var(--border); border-radius: 8px;
  padding: 7px; cursor: pointer; font-size: 12px;
}
.presets button:hover { border-color: var(--accent2); }
.save {
  margin-top: 6px;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  color: #fff; border: none; border-radius: 10px;
  padding: 11px; font-weight: 600; cursor: pointer;
}

.main { flex: 1; display: flex; overflow: hidden; }
.pane { overflow: hidden; display: flex; flex-direction: column; }
.left {
  width: 260px; flex-shrink: 0;
  background: var(--panel);
  border-right: 1px solid var(--border);
}
.mid { flex: 1; min-width: 0; border-right: 1px solid var(--border); }
.right { width: 270px; flex-shrink: 0; background: var(--panel); }

.placeholder {
  margin: auto; text-align: center;
  color: var(--muted); line-height: 2.4; font-size: 13.5px;
}
</style>
