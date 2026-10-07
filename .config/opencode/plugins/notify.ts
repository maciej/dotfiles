// Type-only import: erased at runtime. These plugins are symlinked from the
// dotfiles repo, so Bun resolves runtime imports from the repo path, where no
// node_modules exists. A value import of "@opencode/plugin" would fail to load.
import type { Plugin } from "@opencode/plugin";
import { appendFileSync } from "node:fs";

const BUSY_THRESHOLD = 3_000;
const DEBUG = !!process.env.OPENCODE_NOTIFY_DEBUG;
const LOG = "/tmp/opencode-notify.log";

const log = DEBUG
  ? (msg: string) => appendFileSync(LOG, `${new Date().toISOString()} ${msg}\n`)
  : () => {};

const plugin: Plugin.Plugin = {
  id: "notify",
  async setup(ctx: Plugin.Context) {
    log("plugin loaded");
    const busy = new Map<string, number>();
    const controller = new AbortController();

    const bell = (why: string) => {
      log(`notify: ${why}`);
      process.stdout.write("\x07");
    };

    void (async () => {
      try {
        for await (const event of ctx.event.subscribe({
          signal: controller.signal,
        })) {
          log(`event: ${event.type}`);

          switch (event.type) {
            case "session.status": {
              const { sessionID, status } = event.data;

              if (status.type === "busy") {
                if (!busy.has(sessionID)) busy.set(sessionID, Date.now());
                break;
              }

              if (status.type !== "idle") break;

              const start = busy.get(sessionID);
              busy.delete(sessionID);
              log(
                `idle: start=${start} elapsed=${start ? Date.now() - start : "n/a"}`,
              );
              if (!start || Date.now() - start < BUSY_THRESHOLD) break;

              bell("session.status:idle");
              break;
            }
            case "session.execution.failed":
              bell("session.execution.failed");
              break;
            case "permission.asked":
              bell("permission.asked");
              break;
            case "form.created":
              bell("form.created");
              break;
          }
        }
      } catch (err) {
        if (!controller.signal.aborted) log(`subscribe error=${err}`);
      }
    })();

    return () => controller.abort();
  },
};

export default plugin;
