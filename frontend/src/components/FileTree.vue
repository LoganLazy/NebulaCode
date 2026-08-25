<template>
  <div class="ftree">
    <div class="ft-head">
      <span class="ft-title">📁 {{ rootName }}</span>
      <button class="ft-refresh" title="刷新" @click="$emit('reload')">⟳</button>
    </div>
    <div class="ft-body">
      <div v-if="!items.length" class="ft-empty">目录为空</div>
      <div v-for="(it, i) in items" :key="i" class="ft-item"
           :style="{ paddingLeft: 8 + depth * 16 + 'px' }">
        <template v-if="it.dir">
          <button class="ft-row dir" @click="toggle(it)">
            <span class="arrow">{{ it.open ? "▾" : "▸" }}</span> 📁 {{ it.name }}
          </button>
          <FileTree v-if="it.open" :root="root" :start-path="childPath(it.name)"
                    :depth="depth + 1" @preview="$emit('preview', $event)" />
        </template>
        <template v-else>
          <button class="ft-row file" :class="{ sel: selected === childPath(it.name) }"
                  @click="openPreview(childPath(it.name), it.name)">
            📄 {{ it.name }}
            <span v-if="it.size > 1024" class="size">{{ Math.round(it.size / 1024) }}k</span>
          </button>
        </template>
      </div>
    </div>

    <!-- 文件预览浮层 -->
    <div v-if="previewPath" class="preview">
      <div class="pv-head">
        <span>{{ previewName }}</span>
        <button class="pv-close" @click="previewPath = ''">✕</button>
      </div>
      <pre class="pv-body">{{ previewContent }}</pre>
    </div>
  </div>
</template>

<script>
import { api } from "../api"

export default {
  name: "FileTree",
  props: {
    root: String,
    startPath: { type: String, default: "." },
    depth: { type: Number, default: 0 }
  },
  emits: ["preview"],
  data() {
    return {
      items: [],
      previewPath: "",
      previewName: "",
      previewContent: "",
      selected: ""
    }
  },
  computed: {
    rootName() {
      return this.depth === 0
        ? (this.root.split("/").filter(Boolean).pop() || this.root)
        : this.startPath.split("/").pop()
    }
  },
  watch: {
    startPath() { this.load() },
    root() { this.load() }
  },
  mounted() { this.load() },
  methods: {
    childPath(name) {
      return this.startPath === "." ? name : `${this.startPath}/${name}`
    },
    async load() {
      try {
        const r = await api.fsList(this.startPath)
        this.items = r.items.map(x => ({ ...x, open: false }))
      } catch (e) {
        this.items = []
      }
    },
    async toggle(it) {
      it.open = !it.open
    },
    async openPreview(path, name) {
      try {
        const r = await api.readFile(path, this.root)
        this.previewPath = path
        this.previewName = name || path
        this.previewContent = r.content
      } catch (e) {
        this.previewPath = path
        this.previewName = name || path
        this.previewContent = "⚠️ " + e.message
      }
    }
  }
}
</script>
