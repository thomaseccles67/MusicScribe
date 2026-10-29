"use strict";

const path = require("path");
const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const { HelperProcess } = require("./helper");
const { ensureDirs, isDev, userDataDir, modelCacheDir } = require("./paths");

/** @type {BrowserWindow | null} */
let mainWindow = null;
/** @type {HelperProcess | null} */
let helper = null;
/** Shared in-flight start so splash get-state waits instead of racing. */
let startPromise = null;
let lastError = null;
let modelsReady = false;

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

function preloadPath() {
  return path.join(__dirname, "preload.js");
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 900,
    minHeight: 600,
    show: false,
    title: "Music Scribe",
    backgroundColor: "#12161c",
    webPreferences: {
      preload: preloadPath(),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow && mainWindow.show());
  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  mainWindow.loadFile(path.join(__dirname, "splash.html"));
  return mainWindow;
}

function attachHelperLogs(proc) {
  proc.onLog((line) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("helper:log", line);
    }
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Start (or await) the local helper. Concurrent callers share one promise so the
 * splash cannot probe /api/models before waitUntilReady finishes — that race
 * surfaced as undici's opaque "fetch failed" + Try again on every cold open.
 */
function startHelper({ force = false } = {}) {
  if (startPromise && !force) return startPromise;

  const prior = force ? startPromise : null;
  startPromise = (async () => {
    if (prior) {
      try {
        await prior;
      } catch {
        /* previous attempt failed — continue into a fresh start */
      }
    }
    lastError = null;
    try {
      ensureDirs();
      if (helper) {
        await helper.stop();
        helper = null;
      }
      helper = new HelperProcess();
      attachHelperLogs(helper);
      await helper.start();
      modelsReady = await probeModelsReady();
      return helper;
    } catch (err) {
      lastError = err.message || String(err);
      // Allow a later retry to create a fresh startPromise.
      startPromise = null;
      throw err;
    }
  })();

  return startPromise;
}

async function ensureHelperReady() {
  if (helper && helper.isReady()) return helper;
  // After a crash, startPromise may still be a resolved success from earlier —
  // force a new start rather than returning that stale settlement.
  if (startPromise && (!helper || !helper.isReady())) {
    try {
      await startPromise;
      if (helper && helper.isReady()) return helper;
    } catch {
      /* fall through to restart */
    }
    return startHelper({ force: true });
  }
  return startHelper();
}

/**
 * Probe model cache readiness. Retries briefly so a one-shot undici failure
 * right after health OK does not strand the splash on "fetch failed".
 */
async function probeModelsReady({ retries = 12, delayMs = 250 } = {}) {
  if (!helper || !helper.port) return false;
  let lastErr = null;
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const url = `${helper.baseUrl()}/api/models`;
      const res = await fetch(url);
      if (!res.ok) {
        lastErr = new Error(`Models probe HTTP ${res.status}`);
        await sleep(delayMs);
        continue;
      }
      const body = await res.json();
      return Boolean(body.ready);
    } catch (err) {
      lastErr = err;
      await sleep(delayMs);
    }
  }
  if (lastErr) throw lastErr;
  return false;
}

async function fetchJson(pathname, options) {
  if (!helper) throw new Error("Helper is not running");
  const res = await fetch(`${helper.baseUrl()}${pathname}`, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

async function showModelsOrApp() {
  if (!helper || !mainWindow) return;
  modelsReady = await probeModelsReady();
  if (!modelsReady) {
    await mainWindow.loadFile(path.join(__dirname, "models.html"));
    return;
  }
  await mainWindow.loadURL(helper.baseUrl());
}

ipcMain.handle("desktop:get-state", async () => {
  try {
    await ensureHelperReady();
    modelsReady = await probeModelsReady();
    return {
      port: helper.port,
      baseUrl: helper.baseUrl(),
      modelsReady,
      userDataDir: userDataDir(),
      modelCacheDir: modelCacheDir(),
      dev: isDev(),
      error: null,
    };
  } catch (err) {
    return {
      port: null,
      baseUrl: null,
      modelsReady: false,
      userDataDir: userDataDir(),
      modelCacheDir: modelCacheDir(),
      dev: isDev(),
      error: err.message || String(err),
    };
  }
});

ipcMain.handle("desktop:retry-helper", async () => {
  await startHelper({ force: true });
  return { ok: true, port: helper.port };
});

ipcMain.handle("desktop:open-app", async () => {
  await ensureHelperReady();
  await showModelsOrApp();
  return { ok: true, modelsReady };
});

ipcMain.handle("desktop:start-models", async () => {
  return fetchJson("/api/models/download", { method: "POST" });
});

ipcMain.handle("desktop:model-status", async () => {
  return fetchJson("/api/models/download");
});

app.whenReady().then(async () => {
  createWindow();
  try {
    await startHelper();
  } catch (err) {
    // Splash UI shows the error via get-state / logs.
    console.error(err);
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", async (event) => {
  if (!helper) return;
  event.preventDefault();
  const proc = helper;
  helper = null;
  startPromise = null;
  try {
    await proc.stop();
  } catch (err) {
    console.error("helper stop failed", err);
  }
  app.exit(0);
});

process.on("uncaughtException", (err) => {
  console.error(err);
  if (app.isReady()) {
    dialog.showErrorBox("Music Scribe", err.message || String(err));
  }
});
