const BASE = ""

async function jfetch(url, opts = {}) {
  const r = await fetch(BASE + url, opts)
  if (!r.ok) {
    let msg = `HTTP ${r.status}`
    try { msg = (await r.json()).detail || msg } catch (e) {}
    throw new Error(msg)
  }
  return r.json()
}

export const api = {
  fsList: (path) => jfetch("/api/fs/list", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path })
  }),
  readFile: (path, project) =>
    jfetch(`/api/file?path=${encodeURIComponent(path)}&project=${encodeURIComponent(project)}`),
  sysPoll: () => jfetch("/api/sys/poll"),
  approve: (request_id, allow) => jfetch("/api/agent/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id, allow })
  })
}

export async function agentStream(payload, handlers) {
  const r = await fetch(BASE + "/api/agent/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
  if (!r.ok || !r.body) throw new Error("HTTP " + r.status)
  const reader = r.body.getReader()
  const dec = new TextDecoder()
  let buf = ""
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    let i
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const line = buf.slice(0, i).trim()
      buf = buf.slice(i + 2)
      if (!line.startsWith("data:")) continue
      let ev
      try { ev = JSON.parse(line.slice(5)) } catch (e) { continue }
      handlers(ev)
    }
  }
}
