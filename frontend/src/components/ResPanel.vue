<template>
  <div class="rpanel">
    <div class="rp-head">📊 资源监控</div>

    <div class="gauges">
      <div class="gauge">
        <svg viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="32" class="g-bg" />
          <circle cx="40" cy="40" r="32" class="g-fg" :style="{ stroke: cpuColor, strokeDashoffset: circ - circ * cpu / 100 }" />
          <text x="40" y="46" text-anchor="middle" class="g-text">{{ Math.round(cpu) }}%</text>
        </svg>
        <span>CPU</span>
      </div>
      <div class="gauge">
        <svg viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="32" class="g-bg" />
          <circle cx="40" cy="40" r="32" class="g-fg" style="stroke:#8b5cf6"
                  :style="{ stroke: '#8b5cf6', strokeDashoffset: circ - circ * mem / 100 }" />
          <text x="40" y="46" text-anchor="middle" class="g-text">{{ Math.round(mem) }}%</text>
        </svg>
        <span>内存</span>
      </div>
    </div>

    <canvas ref="spark" width="240" height="70" class="spark"></canvas>

    <div class="rows">
      <div class="row"><span>内存用量</span><b>{{ memUsed }}G / {{ memTotal }}G</b></div>
      <div class="row"><span>磁盘</span><b>{{ disk }}%</b></div>
      <div class="row"><span>网速 ↓/↑</span><b>{{ down }} / {{ up }} KB/s</b></div>
      <div class="row hl"><span>本进程</span><b>CPU {{ procCpu }}% · {{ procMem }}MB</b></div>
    </div>

    <div v-if="warnMsg" class="warn">{{ warnMsg }}</div>
  </div>
</template>

<script>
import { api } from "../api"

export default {
  data() {
    return { cpu: 0, mem: 0, memUsed: 0, memTotal: 0, disk: 0,
             up: 0, down: 0, procCpu: 0, procMem: 0,
             history: [], timer: null }
  },
  computed: {
    circ() { return 2 * Math.PI * 32 },
    cpuColor() { return this.cpu > 85 ? "#ff6b6b" : this.cpu > 60 ? "#ffb454" : "#34c777" },
    warnMsg() {
      if (this.cpu > 90) return "⚠️ CPU 过载，建议暂停部分任务"
      if (this.mem > 92) return "⚠️ 内存吃紧，系统可能开始杀进程"
      return ""
    }
  },
  mounted() {
    this.tick()
    this.timer = setInterval(() => this.tick(), 1000)
  },
  unmounted() { clearInterval(this.timer) },
  methods: {
    async tick() {
      try {
        const d = await api.sysPoll()
        this.cpu = d.cpu; this.mem = d.mem_percent
        this.memUsed = d.mem_used_gb; this.memTotal = d.mem_total_gb
        this.disk = d.disk_percent
        this.up = d.net_up_kbs; this.down = d.net_down_kbs
        this.procCpu = d.proc_cpu; this.procMem = d.proc_mem_mb
        this.history.push(d.cpu)
        if (this.history.length > 60) this.history.shift()
        this.draw()
      } catch (e) {}
    },
    draw() {
      const c = this.$refs.spark
      if (!c) return
      const ctx = c.getContext("2d")
      ctx.clearRect(0, 0, c.width, c.height)
      ctx.strokeStyle = "#1c212d"
      ctx.beginPath(); ctx.moveTo(0, 35); ctx.lineTo(c.width, 35); ctx.stroke()
      const h = this.history
      ctx.beginPath()
      h.forEach((v, i) => {
        const x = (i / 59) * c.width
        const y = c.height - (v / 100) * c.height
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      })
      ctx.strokeStyle = "#4da3ff"
      ctx.lineWidth = 1.6
      ctx.stroke()
      ctx.lineTo((h.length - 1) / 59 * c.width || 0, c.height)
      ctx.lineTo(0, c.height)
      ctx.closePath()
      ctx.fillStyle = "rgba(77,163,255,.12)"
      ctx.fill()
    }
  }
}
</script>

<style scoped>
.rpanel { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.rp-head { font-weight: 700; color: var(--muted); font-size: 13px; letter-spacing: 1px; }

.gauges { display: flex; gap: 18px; justify-content: center; }
.gauge { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.gauge svg { width: 84px; height: 84px; transform: rotate(-90deg); }
.g-bg { fill: none; stroke: var(--panel2); stroke-width: 8; }
.g-fg { fill: none; stroke-width: 8; stroke-linecap: round;
        transition: stroke-dashoffset .5s ease; }
.g-text { fill: var(--text); font-size: 17px; font-weight: bold; }
.gauge span { color: var(--muted); font-size: 12px; }

.spark { background: var(--panel2); border-radius: 10px; width: 100%; height: 70px; }

.rows { display: flex; flex-direction: column; gap: 7px; }
.row { display: flex; justify-content: space-between; font-size: 13px; color: var(--muted); }
.row b { color: var(--text); font-weight: normal; }
.row.hl b { color: var(--accent); }

.warn {
  background: #3a2622; border: 1px solid #6e3a30;
  color: #ffb4a0; border-radius: 9px; padding: 9px 12px; font-size: 13px;
}
</style>
