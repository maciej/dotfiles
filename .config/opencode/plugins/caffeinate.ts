// Type-only import: erased at runtime. These plugins are symlinked from the
// dotfiles repo, so Bun resolves runtime imports from the repo path, where no
// node_modules exists. A value import of "@opencode/plugin" would fail to load.
import type { Plugin } from "@opencode/plugin";
import { appendFileSync } from "node:fs";

const LOG = "/tmp/opencode-caffeinate.log";

function trace() {
  const raw = process.env.OPENCODE_CAFFEINATE_TRACE;
  if (!raw) return;

  const val = raw.toLowerCase();
  if (val === "0" || val === "false") return;
  if (val === "1" || val === "true") return LOG;
  return raw;
}

const plugin: Plugin.Plugin = {
  id: "caffeinate",
  async setup(ctx: Plugin.Context) {
    const file = trace();
    const log = file
      ? (msg: string) =>
          appendFileSync(
            file,
            `${new Date().toISOString()} pid=${process.pid} ${msg}\n`,
          )
      : () => {};

    log("load");

    if (process.platform !== "darwin") {
      log(`disable platform=${process.platform}`);
      return;
    }

    const bin = Bun.which("caffeinate");
    if (!bin) {
      log("disable missing=caffeinate");
      return;
    }

    const ids = new Set<string>();
    let proc: Bun.Subprocess | undefined;

    const stop = (why: string) => {
      const child = proc;
      if (!child) return;

      proc = undefined;
      log(`stop why=${why} active=${ids.size}`);
      child.kill();
    };

    const start = (why: string) => {
      if (proc) return;

      log(`start why=${why} active=${ids.size}`);

      // Tie caffeinate to this process so it cannot outlive opencode on crashes.
      const child = Bun.spawn([bin, "-i", "-w", `${process.pid}`], {
        stdin: "ignore",
        stdout: "ignore",
        stderr: "ignore",
      });

      child.exited.then((code) => {
        log(`exit code=${code}`);
        if (proc !== child) return;

        proc = undefined;
        if (ids.size) start(`exit:${code}`);
      });

      proc = child;
    };

    const sync = (why: string) => {
      if (ids.size) {
        start(why);
        return;
      }

      stop(why);
    };

    const clear = (why: string) => {
      ids.clear();
      stop(why);
    };

    const controller = new AbortController();

    void (async () => {
      try {
        for await (const event of ctx.event.subscribe({
          signal: controller.signal,
        })) {
          log(`event type=${event.type}`);

          if (event.type === "global.disposed") {
            clear("global.disposed");
            return;
          }

          if (event.type !== "session.status") continue;

          const { sessionID, status } = event.data;
          if (status.type === "idle") ids.delete(sessionID);
          else ids.add(sessionID);

          sync(`status:${status.type}:${sessionID}`);
        }
      } catch (err) {
        if (!controller.signal.aborted) log(`subscribe error=${err}`);
      }
    })();

    return () => {
      controller.abort();
      clear("unload");
    };
  },
};

export default plugin;
