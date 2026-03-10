import type { Plugin } from "@opencode-ai/plugin"
import { appendFileSync } from "fs"

const BUSY_THRESHOLD = 3_000
const DEBUG = !!process.env.OPENCODE_NOTIFY_DEBUG
const LOG = "/tmp/opencode-notify.log"

const log = DEBUG
  ? (msg: string) => appendFileSync(LOG, `${new Date().toISOString()} ${msg}\n`)
  : () => {}

export const NotificationPlugin: Plugin = async () => {
  log("plugin loaded")
  const busy = new Map<string, number>()
  return {
    async event({ event }) {
      log(`event: ${event.type}`)

      if (event.type === "session.status" && event.properties.status.type === "busy") {
        if (!busy.has(event.properties.sessionID))
          busy.set(event.properties.sessionID, Date.now())
        return
      }

      if (event.type === "session.idle") {
        const start = busy.get(event.properties.sessionID)
        busy.delete(event.properties.sessionID)
        log(`idle: start=${start} elapsed=${start ? Date.now() - start : "n/a"}`)
        if (!start || Date.now() - start < BUSY_THRESHOLD) return
      }

      switch (event.type) {
        case "session.idle":
        case "session.error":
        case "permission.asked":
        case "question.asked":
          log(`notify: ${event.type}`)
          process.stdout.write("\x07")
      }
    },
  }
}
