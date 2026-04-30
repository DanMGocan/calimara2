#!/usr/bin/env node
import crypto from "node:crypto";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const BASE_URL = process.env.CALIMARA_SMOKE_BASE_URL || "http://lvh.me:8000";
const CONNECT_URL = process.env.CALIMARA_SMOKE_CONNECT_URL || (() => {
  const url = new URL(BASE_URL);
  url.hostname = "127.0.0.1";
  return url.toString().replace(/\/$/, "");
})();
const USER_ID = process.env.CALIMARA_SMOKE_USER_ID || "5";
const ROUTES = (process.env.CALIMARA_SMOKE_ROUTES || [
  "/panou",
  "/scrie",
  "/mesaje",
  "/magazin",
  "/inventar",
  "/premium",
].join(",")).split(",").map((route) => route.trim()).filter(Boolean);

function chromeCandidates() {
  const candidates = [
    process.env.CHROME_BIN,
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ];
  if (process.env.CALIMARA_ALLOW_WINDOWS_CHROME === "1") {
    candidates.push("/mnt/c/Program Files/Google/Chrome/Application/chrome.exe");
  }
  return candidates.filter(Boolean);
}

function findChrome() {
  for (const candidate of chromeCandidates()) {
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error(
    "Chrome was not found. Set CHROME_BIN to a Linux Chrome/Chromium binary. " +
    "Set CALIMARA_ALLOW_WINDOWS_CHROME=1 only if launching Windows Chrome from WSL is safe in your terminal."
  );
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function signSessionCookie() {
  const python = process.env.CALIMARA_PYTHON || path.join(ROOT, ".venv/bin/python");
  const code = [
    "import base64, json, os",
    "from pathlib import Path",
    "from dotenv import load_dotenv",
    "import itsdangerous",
    `os.chdir(${JSON.stringify(ROOT)})`,
    "load_dotenv()",
    `user_id = int(${JSON.stringify(USER_ID)})`,
    "epoch_file = Path('.db_epoch')",
    "epoch = epoch_file.read_text().strip() if epoch_file.exists() else ''",
    "payload = {'user_id': user_id, 'db_epoch': epoch}",
    "data = base64.b64encode(json.dumps(payload).encode('utf-8'))",
    "print(itsdangerous.TimestampSigner(os.environ['SESSION_SECRET_KEY']).sign(data).decode('utf-8'))",
  ].join("; ");
  const result = spawnSync(python, ["-c", code], {
    cwd: ROOT,
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error(`Could not create session cookie:\n${result.stderr || result.stdout}`);
  }
  return result.stdout.trim();
}

async function waitForJson(url, timeoutMs = 5000) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
      lastError = new Error(`${response.status} ${response.statusText}`);
    } catch (error) {
      lastError = new Error(`${error.message}${error.cause ? ` (${error.cause.message})` : ""}`);
    }
    await sleep(100);
  }
  throw lastError || new Error(`Timed out waiting for ${url}`);
}

function encodeFrame(text) {
  const payload = Buffer.from(text);
  let headerLength = 2;
  if (payload.length >= 126 && payload.length <= 0xffff) headerLength = 4;
  if (payload.length > 0xffff) headerLength = 10;
  const frame = Buffer.alloc(headerLength + 4 + payload.length);
  frame[0] = 0x81;
  if (payload.length < 126) {
    frame[1] = 0x80 | payload.length;
  } else if (payload.length <= 0xffff) {
    frame[1] = 0x80 | 126;
    frame.writeUInt16BE(payload.length, 2);
  } else {
    frame[1] = 0x80 | 127;
    frame.writeBigUInt64BE(BigInt(payload.length), 2);
  }
  const maskOffset = headerLength;
  const payloadOffset = maskOffset + 4;
  const mask = crypto.randomBytes(4);
  mask.copy(frame, maskOffset);
  for (let i = 0; i < payload.length; i += 1) {
    frame[payloadOffset + i] = payload[i] ^ mask[i % 4];
  }
  return frame;
}

function decodeFrames(buffer) {
  const messages = [];
  let offset = 0;
  while (buffer.length - offset >= 2) {
    const first = buffer[offset];
    const second = buffer[offset + 1];
    const opcode = first & 0x0f;
    let length = second & 0x7f;
    let headerLength = 2;
    if (length === 126) {
      if (buffer.length - offset < 4) break;
      length = buffer.readUInt16BE(offset + 2);
      headerLength = 4;
    } else if (length === 127) {
      if (buffer.length - offset < 10) break;
      length = Number(buffer.readBigUInt64BE(offset + 2));
      headerLength = 10;
    }
    const masked = Boolean(second & 0x80);
    const maskLength = masked ? 4 : 0;
    const frameLength = headerLength + maskLength + length;
    if (buffer.length - offset < frameLength) break;
    let payload = buffer.subarray(offset + headerLength + maskLength, offset + frameLength);
    if (masked) {
      const mask = buffer.subarray(offset + headerLength, offset + headerLength + 4);
      payload = Buffer.from(payload.map((byte, index) => byte ^ mask[index % 4]));
    }
    if (opcode === 1) messages.push(payload.toString("utf8"));
    offset += frameLength;
  }
  return { messages, remaining: buffer.subarray(offset) };
}

class WebSocketClient {
  constructor(wsUrl) {
    this.url = new URL(wsUrl);
    this.buffer = Buffer.alloc(0);
    this.messages = [];
    this.waiters = [];
  }

  async connect() {
    const key = crypto.randomBytes(16).toString("base64");
    this.socket = net.createConnection({
      host: this.url.hostname,
      port: Number(this.url.port || 80),
    });
    await new Promise((resolve, reject) => {
      this.socket.once("connect", resolve);
      this.socket.once("error", reject);
    });
    this.socket.write([
      `GET ${this.url.pathname}${this.url.search} HTTP/1.1`,
      `Host: ${this.url.host}`,
      "Upgrade: websocket",
      "Connection: Upgrade",
      `Sec-WebSocket-Key: ${key}`,
      "Sec-WebSocket-Version: 13",
      "\r\n",
    ].join("\r\n"));

    let handshake = Buffer.alloc(0);
    while (!handshake.includes(Buffer.from("\r\n\r\n"))) {
      const chunk = await new Promise((resolve, reject) => {
        this.socket.once("data", resolve);
        this.socket.once("error", reject);
      });
      handshake = Buffer.concat([handshake, chunk]);
    }
    const headerEnd = handshake.indexOf("\r\n\r\n");
    const headers = handshake.subarray(0, headerEnd).toString("utf8");
    if (!headers.startsWith("HTTP/1.1 101")) {
      throw new Error(`WebSocket handshake failed:\n${headers}`);
    }
    const leftover = handshake.subarray(headerEnd + 4);
    this.socket.on("data", (chunk) => this.handleData(chunk));
    if (leftover.length) this.handleData(leftover);
  }

  handleData(chunk) {
    const decoded = decodeFrames(Buffer.concat([this.buffer, chunk]));
    this.buffer = decoded.remaining;
    for (const message of decoded.messages) {
      const waiter = this.waiters.shift();
      if (waiter) waiter(message);
      else this.messages.push(message);
    }
  }

  send(data) {
    this.socket.write(encodeFrame(JSON.stringify(data)));
  }

  nextMessage(timeoutMs = 5000) {
    if (this.messages.length) return Promise.resolve(this.messages.shift());
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        const index = this.waiters.indexOf(done);
        if (index >= 0) this.waiters.splice(index, 1);
        reject(new Error("Timed out waiting for WebSocket message"));
      }, timeoutMs);
      const done = (message) => {
        clearTimeout(timer);
        resolve(message);
      };
      this.waiters.push(done);
    });
  }

  close() {
    this.socket?.end();
  }
}

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.nextId = 1;
    this.pending = new Map();
    this.events = [];
    this.closed = false;
  }

  async start() {
    this.loop();
  }

  async loop() {
    while (!this.closed) {
      try {
        const raw = await this.ws.nextMessage(30000);
        const message = JSON.parse(raw);
        if (message.id && this.pending.has(message.id)) {
          const { resolve, reject } = this.pending.get(message.id);
          this.pending.delete(message.id);
          if (message.error) reject(new Error(`${message.error.message}: ${message.error.data || ""}`));
          else resolve(message.result || {});
        } else {
          this.events.push(message);
        }
      } catch {
        if (!this.closed) this.closed = true;
      }
    }
  }

  send(method, params = {}, sessionId = undefined) {
    const id = this.nextId++;
    const message = { id, method, params };
    if (sessionId) message.sessionId = sessionId;
    this.ws.send(message);
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`CDP command timed out: ${method}`));
        }
      }, 10000);
    });
  }

  async waitForEvent(method, sessionId, timeoutMs = 10000) {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      const index = this.events.findIndex((event) => (
        event.method === method && (!sessionId || event.sessionId === sessionId)
      ));
      if (index >= 0) return this.events.splice(index, 1)[0];
      await sleep(50);
    }
    throw new Error(`Timed out waiting for ${method}`);
  }

  drainPageIssues(sessionId) {
    const issues = { consoleErrors: [], exceptions: [], api500s: [] };
    for (const event of this.events.splice(0)) {
      if (sessionId && event.sessionId !== sessionId) continue;
      if (event.method === "Runtime.consoleAPICalled" && event.params?.type === "error") {
        issues.consoleErrors.push((event.params.args || []).map((arg) => arg.value || arg.description || "").join(" "));
      }
      if (event.method === "Runtime.exceptionThrown") {
        issues.exceptions.push(event.params?.exceptionDetails?.text || "Runtime exception");
      }
      if (event.method === "Network.responseReceived") {
        const response = event.params?.response;
        if (response?.url?.includes("/api/") && response.status >= 500) {
          issues.api500s.push(`${response.status} ${response.url}`);
        }
      }
    }
    return issues;
  }
}

async function verifySignedCookie(cookie) {
  const base = new URL(BASE_URL);
  let response;
  try {
    response = await fetch(`${CONNECT_URL}/api/utilizator/eu`, {
      headers: {
        cookie: `calimara_sess=${cookie}`,
        host: base.host,
      },
    });
  } catch (error) {
    throw new Error(`/api/utilizator/eu smoke check failed: ${error.message}${error.cause ? ` (${error.cause.message})` : ""}`);
  }
  const data = await response.json();
  if (!response.ok || !data.authenticated) {
    throw new Error(`/api/utilizator/eu did not authenticate smoke user ${USER_ID}: ${response.status} ${JSON.stringify(data)}`);
  }
  return data.user;
}

async function main() {
  const cookie = signSessionCookie();
  const user = await verifySignedCookie(cookie);
  const chrome = findChrome();
  const port = await freePort();
  const userDataDir = path.join(os.tmpdir(), `calimara-chrome-smoke-${process.pid}-${Date.now()}`);
  const chromeProcess = spawn(chrome, [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-dev-shm-usage",
    "--host-resolver-rules=MAP lvh.me 127.0.0.1,MAP *.lvh.me 127.0.0.1",
    `--user-data-dir=${userDataDir}`,
    `--remote-debugging-port=${port}`,
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  let stderr = "";
  chromeProcess.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });

  try {
    let version;
    try {
      version = await waitForJson(`http://127.0.0.1:${port}/json/version`, 10000);
    } catch (error) {
      throw new Error(`Chrome DevTools did not become reachable on 127.0.0.1:${port}: ${error.message}\n${stderr}`);
    }
    const ws = new WebSocketClient(version.webSocketDebuggerUrl);
    await ws.connect();
    const cdp = new Cdp(ws);
    await cdp.start();
    const target = await cdp.send("Target.createTarget", { url: "about:blank" });
    const attached = await cdp.send("Target.attachToTarget", {
      targetId: target.targetId,
      flatten: true,
    });
    const sessionId = attached.sessionId;

    await cdp.send("Runtime.enable", {}, sessionId);
    await cdp.send("Log.enable", {}, sessionId);
    await cdp.send("Page.enable", {}, sessionId);
    await cdp.send("Network.enable", {}, sessionId);
    const cookieResult = await cdp.send("Network.setCookie", {
      name: "calimara_sess",
      value: cookie,
      domain: ".lvh.me",
      path: "/",
      httpOnly: true,
      secure: false,
      sameSite: "Lax",
      url: BASE_URL,
    }, sessionId);
    if (!cookieResult.success) throw new Error("Chrome rejected the session cookie");

    const failures = [];
    for (const route of ROUTES) {
      const url = new URL(route, BASE_URL).toString();
      const load = cdp.waitForEvent("Page.loadEventFired", sessionId, 15000);
      await cdp.send("Page.navigate", { url }, sessionId);
      await load;
      await sleep(1200);
      const evaluation = await cdp.send("Runtime.evaluate", {
        returnByValue: true,
        expression: `(() => {
          const root = document.getElementById("root");
          const text = (root && root.innerText || "").trim();
          return {
            href: location.href,
            title: document.title,
            rootTextLength: text.length,
            textSample: text.slice(0, 300)
          };
        })()`,
      }, sessionId);
      const value = evaluation.result?.value || {};
      const issues = cdp.drainPageIssues(sessionId);
      if (!value.rootTextLength) failures.push(`${route}: root rendered no text at ${value.href}`);
      if (value.textSample?.includes("Pagina nu a putut fi afisata")) {
        failures.push(`${route}: React error boundary rendered`);
      }
      for (const issue of issues.consoleErrors) failures.push(`${route}: console error: ${issue}`);
      for (const issue of issues.exceptions) failures.push(`${route}: exception: ${issue}`);
      for (const issue of issues.api500s) failures.push(`${route}: API 500: ${issue}`);
      console.log(`ok ${route} -> ${value.href} (${value.rootTextLength} chars)`);
    }

    if (failures.length) {
      throw new Error(`Browser smoke failed for ${user.username}:\n${failures.join("\n")}`);
    }
    ws.close();
  } finally {
    chromeProcess.kill();
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }

  if (stderr.includes("DevTools listening")) {
    console.error(stderr.split("\n").filter((line) => line.includes("ERROR")).join("\n"));
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
