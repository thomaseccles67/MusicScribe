"use strict";

const { spawn } = require("child_process");
const http = require("http");
const net = require("net");
const path = require("path");
const {
  isDev,
  repoRoot,
  resourcesRoot,
  frontendDir,
  userDataDir,
  modelCacheDir,
  sidecarBinary,
  venvPython,
} = require("./paths");

const DEFAULT_PORT = 8765;

function findFreePort(preferred = DEFAULT_PORT) {
  return new Promise((resolve, reject) => {
    const tryListen = (port, fallback) => {
      const server = net.createServer();
      server.unref();
      server.on("error", (err) => {
        if (!fallback || port === 0) {
          reject(err);
          return;
        }
        // Preferred busy — let the OS pick.
        tryListen(0, false);
      });
      server.listen(port, "127.0.0.1", () => {
        const addr = server.address();
        const chosen = typeof addr === "object" && addr ? addr.port : port;
        server.close(() => resolve(chosen));
      });
    };
    tryListen(preferred, true);
  });
}

function helperEnv() {
  const env = {
    ...process.env,
    BANDSCRIBE_ROOT: resourcesRoot(),
    BANDSCRIBE_FRONTEND: frontendDir(),
    MUSICSCRIBE_USER_DATA: userDataDir(),
    MUSICSCRIBE_MODEL_CACHE: modelCacheDir(),
    // Jobs stay ephemeral unless the user opts in.
    PYTHONUNBUFFERED: "1",
  };
  if (isDev()) {
    env.PYTHONPATH = path.join(repoRoot(), "backend");
  }
  return env;
}

function buildSpawn() {
  const bin = !isDev() ? sidecarBinary() : null;
  if (bin) {
    return { command: bin, args: [], cwd: path.dirname(bin) };
  }
  if (!isDev()) {
    throw new Error(
      "Packaged Music Scribe is missing the local helper binary. Reinstall from GitHub Releases."
    );
  }
  const py = venvPython();
  if (!py) {
    throw new Error(
      "Dev mode needs a project virtualenv. Run ./setup.sh (macOS/Linux) or .\\setup.ps1 (Windows), then retry."
    );
  }
  return {
    command: py,
    args: ["-m", "bandscribe"],
    cwd: repoRoot(),
  };
}

class HelperProcess {
  constructor() {
    this.child = null;
    this.port = null;
    this.ready = false;
    this.logs = [];
    this.exitCode = null;
    this._listeners = new Set();
  }

  /** True only after /api/health has returned 200 for this child. */
  isReady() {
    return Boolean(this.child && this.port && this.ready);
  }

  onLog(fn) {
    this._listeners.add(fn);
    return () => this._listeners.delete(fn);
  }

  _emit(line) {
    const text = String(line).trimEnd();
    if (!text) return;
    this.logs.push(text);
    if (this.logs.length > 400) this.logs.shift();
    for (const fn of this._listeners) fn(text);
  }

  async start() {
    if (this.child && this.ready) return this.port;
    this.ready = false;
    this.port = await findFreePort(DEFAULT_PORT);
    const { command, args, cwd } = buildSpawn();
    const fullArgs = [...args, "--host", "127.0.0.1", "--port", String(this.port)];
    this._emit(`Starting helper: ${command} ${fullArgs.join(" ")}`);
    this.child = spawn(command, fullArgs, {
      cwd,
      env: helperEnv(),
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });
    this.child.stdout.on("data", (buf) => this._emit(buf.toString()));
    this.child.stderr.on("data", (buf) => this._emit(buf.toString()));
    this.child.on("exit", (code, signal) => {
      this.exitCode = code;
      this.ready = false;
      this._emit(`Helper exited (code=${code}, signal=${signal || "none"})`);
      this.child = null;
    });
    this.child.on("error", (err) => {
      this._emit(`Helper spawn error: ${err.message}`);
    });
    await this.waitUntilReady(90000);
    this.ready = true;
    return this.port;
  }

  waitUntilReady(timeoutMs = 60000) {
    const started = Date.now();
    const port = this.port;
    return new Promise((resolve, reject) => {
      const tick = () => {
        if (!this.child) {
          reject(
            new Error(
              `Local helper exited before becoming ready.\n\n${this.logs.slice(-20).join("\n")}`
            )
          );
          return;
        }
        if (Date.now() - started > timeoutMs) {
          reject(
            new Error(
              `Timed out waiting for the local helper on 127.0.0.1:${port}.\n\n${this.logs
                .slice(-30)
                .join("\n")}`
            )
          );
          return;
        }
        const req = http.get(
          { host: "127.0.0.1", port, path: "/api/health", timeout: 1500 },
          (res) => {
            res.resume();
            if (res.statusCode === 200) {
              resolve();
              return;
            }
            setTimeout(tick, 400);
          }
        );
        req.on("error", () => setTimeout(tick, 400));
        req.on("timeout", () => {
          req.destroy();
          setTimeout(tick, 400);
        });
      };
      tick();
    });
  }

  baseUrl() {
    if (!this.port) throw new Error("Helper is not running");
    return `http://127.0.0.1:${this.port}`;
  }

  async stop() {
    const child = this.child;
    if (!child) return;
    this.child = null;
    await new Promise((resolve) => {
      const timer = setTimeout(() => {
        try {
          child.kill("SIGKILL");
        } catch {
          /* already gone */
        }
        resolve();
      }, 4000);
      child.once("exit", () => {
        clearTimeout(timer);
        resolve();
      });
      try {
        if (process.platform === "win32") {
          spawn("taskkill", ["/pid", String(child.pid), "/f", "/t"]);
        } else {
          child.kill("SIGTERM");
        }
      } catch {
        resolve();
      }
    });
  }
}

module.exports = { HelperProcess, findFreePort, DEFAULT_PORT };
