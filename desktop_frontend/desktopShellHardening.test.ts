import { createRequire } from "node:module";
import { EventEmitter } from "node:events";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";

const require = createRequire(import.meta.url);
const desktopRoot = path.resolve(
  process.cwd(),
  "..",
  "..",
  "MasterplanOptimiserV3 - App",
  "masterplanOptimiserV3 - App",
  "desktop",
);
const {
  createOwnedProcessRegistry,
  terminateProcessTree,
} = require(path.join(desktopRoot, "process-ownership.js"));
const {
  MANIFEST_FORMAT,
  PROTECTED_ROOTS,
  buildManifestFileMap,
  verifySignedManifest,
} = require(path.join(desktopRoot, "integrity.js"));
const { resolveDesktopRuntimeConfig } = require(
  path.join(desktopRoot, "runtime-config.js"),
);

const temporaryRoots: string[] = [];

afterEach(() => {
  for (const root of temporaryRoots.splice(0)) {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

function fakeProcess(pid: number | string) {
  const proc = new EventEmitter() as EventEmitter & {
    pid: number | string;
    exitCode: number | null;
    killed: boolean;
    kill: (signal?: string) => void;
  };
  proc.pid = pid;
  proc.exitCode = null;
  proc.killed = false;
  proc.kill = () => undefined;
  return proc;
}

function integrityFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "mp-opt-external-integrity-"));
  temporaryRoots.push(root);
  fs.mkdirSync(path.join(root, "backend"));
  fs.mkdirSync(path.join(root, "frontend"));
  fs.writeFileSync(path.join(root, "app.asar"), "application");
  fs.writeFileSync(path.join(root, "backend", "backend.exe"), "backend");
  fs.writeFileSync(path.join(root, "frontend", "server.js"), "frontend");

  const keys = crypto.generateKeyPairSync("ed25519");
  const publicKeyPath = path.join(root, "public.pem");
  const manifestPath = path.join(root, "manifest.signed.json");
  fs.writeFileSync(
    publicKeyPath,
    keys.publicKey.export({ type: "spki", format: "pem" }),
  );
  return { root, keys, publicKeyPath, manifestPath };
}

function writeManifest(fixture: ReturnType<typeof integrityFixture>) {
  const manifest = JSON.stringify({
    format: MANIFEST_FORMAT,
    version: "external-test",
    timestamp: new Date(0).toISOString(),
    protectedRoots: PROTECTED_ROOTS,
    files: buildManifestFileMap(fixture.root),
  }, null, 2);
  fs.writeFileSync(fixture.manifestPath, JSON.stringify({
    signed: true,
    manifest,
    signature: crypto
      .sign(null, Buffer.from(manifest), fixture.keys.privateKey)
      .toString("base64"),
  }));
}

describe("desktop shell hardening", () => {
  it("terminates only validated process IDs registered as owned", () => {
    const calls: unknown[][] = [];
    const registry = createOwnedProcessRegistry({
      platform: "win32",
      execFileSync: (...args: unknown[]) => calls.push(args),
    });
    registry.register("backend", fakeProcess(4312));

    expect(registry.terminateAll()).toEqual([
      { label: "backend", terminated: true },
    ]);
    expect(calls[0]?.[0]).toBe("taskkill.exe");
    expect(calls[0]?.[1]).toEqual(["/F", "/PID", "4312", "/T"]);
    expect(JSON.stringify(calls)).not.toContain("/IM");
  });

  it("rejects hostile process identifiers before executing a command", () => {
    let called = false;
    expect(() => terminateProcessTree(
      fakeProcess("7 & taskkill /IM electron.exe"),
      {
        platform: "win32",
        execFileSync: () => { called = true; },
      },
    )).toThrow(/Invalid owned process identifier/);
    expect(called).toBe(false);
  });

  it("accepts distinct loopback ports and rejects remote origins", () => {
    const config = resolveDesktopRuntimeConfig({
      API_URL: "http://localhost:18123",
      FRONTEND_URL: "http://127.0.0.1:18124",
    });

    expect(config.backendUrl).toBe("http://127.0.0.1:18123");
    expect(config.frontendUrl).toBe("http://127.0.0.1:18124");
    expect(() => resolveDesktopRuntimeConfig({
      API_URL: "http://192.0.2.1:8000",
    })).toThrow(/loopback origin/);
  });

  it("rejects unsigned, modified, and unexpected packaged resources", () => {
    const fixture = integrityFixture();
    fs.writeFileSync(fixture.manifestPath, JSON.stringify({ signed: false }));
    expect(verifySignedManifest({
      resourcesDir: fixture.root,
      publicKeyPath: fixture.publicKeyPath,
      manifestPath: fixture.manifestPath,
    }).valid).toBe(false);

    writeManifest(fixture);
    fs.writeFileSync(path.join(fixture.root, "backend", "backend.exe"), "modified");
    fs.writeFileSync(path.join(fixture.root, "frontend", "injected.js"), "unexpected");
    const result = verifySignedManifest({
      resourcesDir: fixture.root,
      publicKeyPath: fixture.publicKeyPath,
      manifestPath: fixture.manifestPath,
    });

    expect(result.valid).toBe(false);
    expect(result.files.find((entry: { path: string }) => (
      entry.path === "backend/backend.exe"
    ))?.status).toBe("modified");
    expect(result.files.find((entry: { path: string }) => (
      entry.path === "frontend/injected.js"
    ))?.status).toBe("unexpected");
  });
});
