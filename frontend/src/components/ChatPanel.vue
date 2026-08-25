<template>
  <div class="chat">
    <div class="msgs" ref="box">
      <div v-if="!timeline.length" class="empty">
        <div class="e-ico">🛠</div>
        <h3>AI Desk 就绪</h3>
        <p>选择项目目录后，用自然语言下达任务<br>我会自己读文件、改代码、跑命令，每一步都看得见</p>
      </div>

      <template v-for="(item, i) in timeline" :key="i">
        <!-- 用户消息 -->
        <div v-if="item.kind === 'user'" class="msg user">
          <div class="bubble">{{ item.text }}</div>
        </div>

        <!-- AI文字 -->
        <div v-else-if="item.kind === 'ai'" class="msg ai">
          <div class="avatar">AI</div>
          <div class="bubble ai-b">{{ item.text }}<span v-if="item.cursor" class="cursor">▍</span></div>
        </div>

        <!-- 步骤卡片 -->
        <div v-else-if="item.kind === 'step'" class="step-card" :class="{ running: !item.done }">
          <span class="s-icon">{{ toolIcon(item.tool) }}</span>
          <div class="s-body">
            <div class="s-title">
              {{ toolName(item.tool) }}
              <span v-if="!item.done" class="spin">⟳</span>
              <span v-else-if="item.ok" class="ok">✓</span>
              <span v-else class="bad">✗</span>
            </div>
            <code class="s-args">{{ argsText(item) }}</code>
            <details v-if="item.summary"><summary>输出</summary><pre>{{ item.summary }}</pre></details>
          </div>
        </div>

        <!-- diff 卡片 -->
        <div v-else-if="item.kind === 'diff'" class="diff-card">
          <div class="d-head">
            {{ item.created ? "🆕 新建文件" : "✏️ 修改文件" }} · {{ item.path }}
            <button v-if="!item.created && item.backup && !item.rolled"
                    class="rb-btn" @click="rollbackDiff(item)">↩ 回滚此改动</button>
            <span v-if="item.rolled" class="rb-done">↩ 已回滚</span>
          </div>
          <details open>
            <summary>查看改动 ({{ diffLines(item.diff) }})</summary>
            <pre class="diff-body"><span v-for="(ln, li) in diffArr(item.diff)" :key="li"
              :class="{ add: ln.startsWith('+') && !ln.startsWith('+++'), del: ln.startsWith('-') && !ln.startsWith('---') }">{{ ln }}
</span></pre>
          </details>
        </div>

        <!-- 审批 -->
        <div v-else-if="item.kind === 'approval'" class="approval">
          <div class="ap-head">🛡 需要你的批准</div>
          <code class="ap-cmd">{{ item.command }}</code>
          <div class="ap-reason">{{ item.reason }}</div>
          <div class="ap-btns" v-if="!item.resolved">
            <button class="allow" @click="decide(item, true)">✓ 允许执行</button>
            <button class="deny" @click="decide(item, false)">✕ 拒绝</button>
          </div>
          <div v-else class="resolved">{{ item.resolved }}</div>
        </div>
      </template>
    </div>

    <div class="inputbar">
      <textarea v-model="draft" rows="2"
                :placeholder="project ? '描述任务，Enter 发送（Shift+Enter 换行）…' : '请先在上方填写项目路径'"
                @keydown.enter.exact.prevent="send"></textarea>
      <button :disabled="busy || !draft.trim() || !project" @click="send">
        {{ busy ? "执行中…" : "发送 ▶" }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from "vue"
import { api, agentStream } from "../api"

const props = defineProps({ project: String, model: Object,
  sessionId: { type: String, default: "main" },
  canRun: { type: Boolean, default: true } })
const emit = defineEmits(["changed", "running"])

const draft = ref("")
const busy = ref(false)
const box = ref(null)
const timeline = ref([])
let approvalResolve = null

function scroll() {
  nextTick(() => box.value && (box.value.scrollTop = box.value.scrollHeight))
}

function toolIcon(t) {
  return { list_dir: "📂", read_file: "📖", write_file: "✏️", run_command: "⚡" }[t] || "🔧"
}
function toolName(t) {
  return { list_dir: "浏览目录", read_file: "读取文件", write_file: "写入文件", run_command: "执行命令" }[t] || t
}
function argsText(item) {
  const a = item.args || {}
  if (item.tool === "run_command") return a.command || ""
  return a.path || ""
}
function diffArr(d) { return d.split("\n") }

async function rollbackDiff(item) {
  if (!confirm(`把 ${item.path} 回滚到本次修改前的版本？`)) return
  try {
    const r = await api.rollback(props.project, item.path, item.backup)
    if (r.code === 0) {
      item.rolled = true
      timeline.value.push({ kind: "ai", text: `↩ 已回滚 ${item.path}（当前版本也已备份，可再次操作找回）` })
      emit("changed")
      scroll()
    }
  } catch (e) {
    alert("回滚失败: " + e.message)
  }
}
function diffLines(d) { return d.split("\n").filter(l => l.startsWith("+") || l.startsWith("-")).length }

async function send() {
  const q = draft.value.trim()
  if (!q || busy.value || !props.project) return
  if (!props.canRun) {
    alert("已达并发任务上限，请等待其他任务完成或在右侧调高上限")
    return
  }
  draft.value = ""
  busy.value = true
  emit("running", true)
  timeline.value.push({ kind: "user", text: q })
  scroll()

  let cur = null
  try {
    await agentStream({
      project: props.project,
      message: q,
      session_id: props.sessionId || "main",
      base: props.model.base,
      key: props.model.key,
      model: props.model.model
    }, (ev) => {
      if (ev.type === "token") {
        if (!cur || cur.kind !== "ai") {
          cur = { kind: "ai", text: "", cursor: true }
          timeline.value.push(cur)
        }
        cur.text += ev.text
        scroll()
      } else if (ev.type === "step") {
        cur = null
        timeline.value.push({ kind: "step", tool: ev.tool, args: ev.args, done: false })
        scroll()
      } else if (ev.type === "step_result") {
        for (let i = timeline.value.length - 1; i >= 0; i--) {
          const it = timeline.value[i]
          if (it.kind === "step" && !it.done) { it.done = true; it.ok = ev.ok; it.summary = ev.summary; break }
        }
      } else if (ev.type === "diff") {
        timeline.value.push({ kind: "diff", path: ev.path, diff: ev.diff, created: ev.created })
        emit("changed")
        scroll()
      } else if (ev.type === "approval_required") {
        cur = null
        timeline.value.push({
          kind: "approval", request_id: ev.request_id,
          command: ev.command, reason: ev.reason
        })
        scroll()
      } else if (ev.type === "error") {
        timeline.value.push({ kind: "ai", text: "⚠️ " + ev.msg })
      }
    })
    if (cur) cur.cursor = false
  } catch (e) {
    timeline.value.push({ kind: "ai", text: "⚠️ " + e.message })
  }
  busy.value = false
  emit("running", false)
  scroll()
}

function decide(item, allow) {
  api.approve(item.request_id, allow)
  item.resolved = allow ? "✓ 已批准，正在执行…" : "✕ 已拒绝"
  approvalResolve = null
}
</script>

<style scoped>
.chat { display: flex; flex-direction: column; height: 100%; }
.msgs { flex: 1; overflow-y: auto; padding: 18px 22px; }

.empty { text-align: center; margin-top: 12vh; color: var(--muted); }
.e-ico { font-size: 46px; }
.empty h3 { color: var(--text); margin: 10px 0 6px; }
.empty p { line-height: 1.7; font-size: 13px; }

.msg.user { display: flex; justify-content: flex-end; margin-bottom: 14px; }
.bubble {
  max-width: 78%;
  background: #23406b;
  border-radius: 11px;
  padding: 10px 14px;
  line-height: 1.65;
  white-space: pre-wrap;
}
.msg.ai { display: flex; gap: 10px; margin-bottom: 14px; align-items: flex-start; }
.avatar {
  width: 30px; height: 30px; border-radius: 8px; flex-shrink: 0;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 12px; font-weight: bold;
}
.ai-b { background: var(--panel2); }

.cursor { animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0; } }

.step-card, .diff-card, .approval {
  display: flex; gap: 10px;
  max-width: 86%;
  margin: 0 auto 12px;
  border-radius: 11px;
  padding: 11px 14px;
  background: var(--panel2);
  border-left: 3px solid var(--accent);
  margin-left: 40px;
}
.step-card.running { border-left-color: var(--warn); }
.s-icon { font-size: 17px; }
.s-body { flex: 1; min-width: 0; }
.s-title { font-weight: 600; font-size: 13px; }
.spin { display: inline-block; animation: rot 1s linear infinite; }
@keyframes rot { to { transform: rotate(360deg); } }
.ok { color: var(--ok); }
.bad { color: var(--bad); }
.s-args {
  display: block;
  color: var(--muted);
  font-size: 12.5px;
  margin-top: 4px;
  word-break: break-all;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
details summary { cursor: pointer; color: var(--muted); font-size: 12.5px; margin-top: 5px; }
details pre { margin: 6px 0 0; font-size: 12px; line-height: 1.55;
              white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; }

.diff-card { border-left-color: var(--accent2); display: block; margin-left: 40px; }
.d-head { font-weight: 600; font-size: 13px; margin-bottom: 4px;
          display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.rb-btn {
  background: var(--panel); color: var(--warn);
  border: 1px solid var(--warn); border-radius: 7px;
  padding: 3px 9px; cursor: pointer; font-size: 12px; font-weight: normal;
}
.rb-btn:hover { background: rgba(255,180,84,.12); }
.rb-done { color: var(--muted); font-size: 12px; font-weight: normal; }
.diff-body {
  background: #0a0d13;
  padding: 10px 12px;
  font-size: 12.3px;
  line-height: 1.55;
  overflow: auto;
  max-height: 260px;
}
.add { color: #7ee787; background: rgba(46,160,67,.15); display: block; }
.del { color: #ffa198; background: rgba(248,81,73,.12); display: block; }

.approval { border-left-color: var(--warn); margin-left: 40px; }
.ap-head { font-weight: 700; color: var(--warn); font-size: 13.5px; margin-bottom: 6px; }
.ap-cmd { display: block; background: #0a0d13; padding: 8px 11px;
          border-radius: 8px; font-size: 12.5px; word-break: break-all; }
.ap-reason { color: var(--muted); font-size: 12.5px; margin-top: 6px; }
.ap-btns { display: flex; gap: 10px; margin-top: 10px; }
.allow, .deny { border-radius: 8px; border: none; padding: 8px 16px; font-size: 13.5px; }
.allow { background: var(--ok); color: #fff; }
.deny { background: #4a3038; color: #ffb4b4; }
.resolved { color: var(--muted); font-size: 13px; }

.inputbar {
  display: flex; gap: 10px;
  padding: 14px 18px;
  border-top: 1px solid var(--border);
}
.inputbar textarea {
  flex: 1;
  resize: none;
  background: var(--panel2);
  border: 1px solid var(--border);
  border-radius: 11px;
  padding: 11px 13px;
  color: var(--text);
  outline: none;
  font-size: 14px;
  line-height: 1.5;
}
.inputbar textarea:focus { border-color: var(--accent); }
.inputbar button {
  width: 96px;
  background: linear-gradient(90deg, var(--accent), var(--accent2));
  color: #fff; border: none; border-radius: 11px; font-size: 14.5px;
}
.inputbar button:disabled { opacity: .45; cursor: default; }
</style>
