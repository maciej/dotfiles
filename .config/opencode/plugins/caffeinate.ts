import type { Plugin } from "@opencode-ai/plugin";
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

export const CaffeinatePlugin: Plugin = async () => {
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
    return {};
  }

  const bin = Bun.which("caffeinate");
  if (!bin) {
    log("disable missing=caffeinate");
    return {};
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

  process.once("beforeExit", () => clear("beforeExit"));
  process.once("exit", () => clear("exit"));
  process.once("SIGINT", () => clear("SIGINT"));
  process.once("SIGTERM", () => clear("SIGTERM"));
  process.once("SIGHUP", () => clear("SIGHUP"));

  return {
    event: async ({ event }) => {
      log(`event type=${event.type}`);

      if (event.type === "server.instance.disposed") {
        clear("instance.disposed");
        return;
      }

      if (event.type === "session.idle") {
        ids.delete(event.properties.sessionID);
        sync(`idle:${event.properties.sessionID}`);
        return;
      }

      if (event.type !== "session.status") return;

      if (event.properties.status.type === "idle")
        ids.delete(event.properties.sessionID);
      else ids.add(event.properties.sessionID);

      sync(
        `status:${event.properties.status.type}:${event.properties.sessionID}`,
      );
    },
  };
};
