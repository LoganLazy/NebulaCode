<template>
  <div class="app">
    <!-- 顶栏 -->
    <header class="topbar">
      <span class="brand">🛠 AI Desk</span>
      <input v-model="project" class="proj-input"
             placeholder="输入项目目录绝对路径，如 /home/xxx/myproject"
             @keydown.enter="openProject" />
      <button class="open-btn" :class="{ active: projectOpen }" @click="openProject">
        {{ projectOpen ? "✓ 已打开" : "打开项目" }}
      </button>
      <button class="cfg-btn" @click="showCfg = true">⚙ 模型</button>
      <label class="git-toggle" title="AI每次改文件后自动git提交检查点">
        <input type="checkbox" v-model="autoGit" /> Git检查点
      </label>
      <span class="limit-ctl" title="并发任务上限">
        🔀并发上限
        <input type="number" min="1" max="6" v-model.number="runLimit" class="limit-input" />
      </span>
    </header>

    <!-- 任务标签栏 -->
    <div class="task-tabs" v-if="projectOpen">
      <button v-for="t in tasks" :key="t.id"
              :class="['tab', { active: t.id === activeId, running: runningMap[t.id] }]"
              @click="activeId = t.id">
        <span class="t-dot" v-if="runningMap[t.id]">●</span>
        {{ t.label }}
        <span class="t-close" @click.stop="closeTask(t.id)">✕</span>
      </button>
      <button class="tab add" @click="addTask">＋ 新任务</button>
      <span v-if="runningCount >= runLimit" class="limit-warn">
        ⚠ 已达并发上限({{ runLimit }}), 请等任务完成或调高上限
      </span>
    </div>

    <!-- 多实例面板(v-show保持状态) -->
    <main class="main">
      <section class="pane left">
        <FileTree v-if="projectOpen" :root="project" />
        <div v-else class="placeholder">
          <p>① 填写项目路径并打开</p>
          <p>② 在右侧对话下达任务</p>
          <p>③ 观察步骤卡片与资源占用</p>
        </div>
      </section>

      <template v-for="t in tasks" :key="t.id">
        <section v-show="t.id === activeId" class="pane mid">
          <ChatPanel :project="projectOpen ? project : ''" :model="activeModel"
                     :session-id="t.id" :can-run="runningCount < runLimit"
                     @changed="reloadStats" @running="setRunning(t.id, $event)" />
        </section>
      </template>

      <section class="pane right" v-if="tasks.length">
        <ResPanel :running="runningCount" :limit="runLimit"
                  @update:limit="runLimit = $event" />
      </section>
    </main>

    <!-- 模型方案管理弹窗 -->
    <div v-if="showCfg" class="cfg-mask" @click.self="showCfg = false">
      <div class="cfg-win card">
        <div class="cw-head">
          <h3>⚙ 模型方案管理</h3>
          <button class="x" @click="showCfg = false">✕</button>
        </div>

        <!-- 编辑表单 -->
        <div v-if="editing" class="edit-form">
          <label>方案名称</label>
          <input v-model="editing.name" placeholder="如：DeepSeek官方" />
          <label>接口地址（OpenAI兼容）</label>
          <input v-model="editing.base" placeholder="https://api.deepseek.com" />
          <div class="two-col">
            <div>
              <label>模型名</label>
              <input v-model="editing.model" placeholder="deepseek-chat" />
            </div>
            <div>
              <label>API Key{{ editing.id ? "（留空保留）" : "" }}</label>
              <input v-model="editing.key" type="password" placeholder="sk-…" />
            </div>
          </div>
          <div class="presets">
            <span>快捷填入：</span>
            <button @click="preset('https://api.deepseek.com', 'deepseek-chat')">DeepSeek</button>
            <button @click="preset('https://ai.121628.xyz/v1', 'deepseek-v4-flash-free')">中转站</button>
            <button @click="preset('http://127.0.0.1:11434/v1', 'qwen2.5-coder:7b')">Ollama</button>
          </div>
          <div class="edit-btns">
            <button class="t-btn" :disabled="testing" @click="testEditing">
              {{ testing ? "测试中…" : "🔌 测试连通" }}
            </button>
            <span :class="['t-msg', testOk ? 'ok' : 'bad']">{{ testMsg }}</span>
            <span style="flex:1"></span>
            <button class="t-btn cancel" @click="editing = null">取消</button>
            <button class="save-p" @click="saveProfile">保存方案</button>
          </div>
        </div>

        <!-- 方案列表 -->
        <template v-else>
          <div v-for="p in mcfg.profiles" :key="p.id"
               class="profile-card" :class="{ active: p.id === mcfg.active }">
            <div class="pc-main" @click="activate(p.id)">
              <div class="pc-line1">
                <b>{{ p.name }}</b>
                <span v-if="p.id === mcfg.active" class="in-use">✓ 使用中</span>
              </div>
              <div class="pc-sub">{{ p.model }} · {{ p.base }}</div>
            </div>
            <div class="pc-ops">
              <button title="测试" @click.stop="testOne(p)">🔌</button>
              <button title="编辑" @click.stop="startEdit(p)">✏️</button>
              <button title="删除" @click.stop="delProfile(p.id)">🗑</button>
            </div>
          </div>
          <div v-if="!mcfg.profiles.length" class="empty-hint">
            还没有模型方案，点下面按钮添加第一个
          </div>
          <button class="add-profile" @click="startNew">＋ 新增方案</button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue"
import { api } from "./api"
import FileTree from "./components/FileTree.vue"
import ChatPanel from "./components/ChatPanel.vue"
import ResPanel from "./components/ResPanel.vue"

const project = ref(localStorage.getItem("aidesk.project") || "")
const projectOpen = ref(false)
const showCfg = ref(false)

const mcfg = ref({ profiles: [], active: "" })
const autoGit = ref(false)

watch(autoGit, async (v) => {
  try {
    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ AUTO_GIT_COMMIT: v })
    })
  } catch (e) {}
})
const tasks = ref([])
const activeId = ref("")
const runningMap = ref({})
const runLimit = ref(parseInt(localStorage.getItem("aidesk.limit") || "2"))

const runningCount = computed(() =>
  Object.values(runningMap.value).filter(Boolean).length)

function addTask() {
  const id = "task_" + Date.now().toString(36)
  tasks.value.push({ id, label: `任务${tasks.value.length + 1}` })
  activeId.value = id
}
function closeTask(id) {
  const t = tasks.value.find(x => x.id === id)
  if (runningMap.value[id]) return alert("该任务正在执行，请等待完成或刷新页面强制中断")
  if (!confirm(`关闭「${t.label}」？(聊天记录将清除)`)) return
  tasks.value = tasks.value.filter(x => x.id !== id)
  if (activeId.value === id && tasks.value.length) activeId.value = tasks.value[0].id
}
function setRunning(id, state) { runningMap.value[id] = state }
watch(runLimit, (v) => localStorage.setItem("aidesk.limit", String(v)))
const editing = ref(null)
const testing = ref(false)
const testMsg = ref("")
const testOk = ref(false)

const activeModel = computed(() => {
  const act = mcfg.value.profiles.find(p => p.id === mcfg.value.active)
  if (act) return { base: act.base, key: act.key, model: act.model }
  return { base: "", key: "", model: "" }
})

async function loadModels() {
  try {
    const r = await fetch("/api/models")
    mcfg.value = await r.json()
  } catch (e) {}
}

async function openProject() {
  const p = project.value.trim()
  if (!p.startsWith("/")) return alert("请输入绝对路径")
  try {
    await api.fsList(p)
    projectOpen.value = true
    localStorage.setItem("aidesk.project", p)
  } catch (e) {
    alert("打开失败: " + e.message)
  }
}

function startNew() {
  editing.value = { id: null, name: "", base: "https://api.deepseek.com",
                    key: "", model: "deepseek-chat" }
}
function startEdit(p) {
  editing.value = { ...p }
}
function preset(base, m) {
  if (!editing.value) return
  editing.value.base = base
  editing.value.model = m
}
async function saveProfile() {
  const e = editing.value
  if (!e?.name.trim() || !e.base.trim() || !e.model.trim())
    return alert("名称/地址/模型名都要填")
  const r = await fetch("/api/models/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(e)
  })
  const d = await r.json()
  if (d.code === 0) {
    if (!mcfg.value.active) await activate(d.id)
    editing.value = null
    loadModels()
  } else alert("保存失败")
}
async function activate(id) {
  await fetch("/api/models/active", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id })
  })
  await loadModels()
}
async function delProfile(id) {
  if (!confirm("删除该方案？")) return
  await fetch("/api/models/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id })
  })
  loadModels()
}
async function testOne(p) {
  testing.value = true
  try {
    const r = await fetch("/api/models/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ base: p.base, key: p.key, model: p.model })
    })
    const d = await r.json()
    alert((d.code === 0 ? "✓ " : "✗ ") + d.msg)
  } catch (e) { alert("测试出错") }
  testing.value = false
}
async function testEditing() {
  testing.value = "edit"
  testMsg.value = ""
  try {
    const e = editing.value
    const r = await fetch("/api/models/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ base: e.base, key: e.key, model: e.model })
    })
    const d = await r.json()
    testMsg.value = d.msg
    testOk.value = d.code === 0
  } catch (e2) {
    testMsg.value = "出错"
    testOk.value = false
  }
  testing.value = false
}
function reloadStats() {}

onMounted(loadModels)
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

/* ---- 模型方案弹窗 ---- */
.cfg-mask {
  position: fixed; inset: 0; z-index: 50;
  background: rgba(0,0,0,.55);
  display: flex; align-items: center; justify-content: center;
}
.cfg-win {
  width: 520px; max-height: 84vh; overflow-y: auto;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 20px;
}
.cw-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.cw-head h3 { margin: 0; }
.x { background: none; border: none; color: var(--muted); font-size: 16px; cursor: pointer; }

.profile-card {
  display: flex; align-items: center; gap: 12px;
  background: var(--panel2);
  border: 1px solid var(--border);
  border-radius: 11px;
  padding: 12px 15px;
  margin-bottom: 10px;
  cursor: pointer;
}
.profile-card:hover { border-color: var(--accent); }
.profile-card.active { border-color: var(--ok); }
.pc-main { flex: 1; min-width: 0; }
.pc-line1 { display: flex; align-items: center; gap: 8px; font-size: 14.5px; }
.in-use { color: var(--ok); font-size: 12px; }
.pc-sub { color: var(--muted); font-size: 12px; margin-top: 3px;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pc-ops { display: flex; gap: 6px; }
.pc-ops button {
  background: var(--bg); color: var(--text);
  border: 1px solid var(--border); border-radius: 7px;
  width: 30px; height: 28px; cursor: pointer; font-size: 13px;
}
.pc-ops button:hover { border-color: var(--accent); }

.add-profile {
  width: 100%;
  background: var(--panel2); color: var(--text);
  border: 1px dashed var(--border); border-radius: 11px;
  padding: 13px; cursor: pointer; font-size: 14px;
}
.add-profile:hover { border-color: var(--accent); color: var(--accent); }
.empty-hint { text-align: center; color: var(--muted); padding: 20px; font-size: 13.5px; }

.edit-form { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.edit-form label { color: var(--muted); font-size: 12.5px; }
.edit-form input {
  background: var(--bg); color: var(--text);
  border: 1px solid var(--border); border-radius: 9px;
  padding: 10px 12px; outline: none; font-size: 13.5px;
}
.edit-form input:focus { border-color: var(--accent); }
.two-col { display: flex; gap: 10px; }
.two-col > div { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.presets { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 12.5px; }
.presets button {
  background: var(--panel2); color: var(--text);
  border: 1px solid var(--border); border-radius: 7px;
  padding: 5px 10px; cursor: pointer; font-size: 12px;
}
.presets button:hover { border-color: var(--accent2); }
.edit-btns { display: flex; align-items: center; gap: 10px; margin-top: 4px; }
.t-btn {
  background: var(--panel2); color: var(--text);
  border: 1px solid var(--border); border-radius: 8px;
  padding: 8px 14px; cursor: pointer; font-size: 13px;
}
.t-btn.cancel { background: #3a3f4a; }
.t-msg.ok { color: var(--ok); font-size: 13px; }
.t-msg.bad { color: #ff9b9b; font-size: 13px; }
.save-p {
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  color: #fff; border: none; border-radius: 8px;
  padding: 9px 18px; font-weight: 600; cursor: pointer;
}
</style>
