/**
 * Tests for desktop user-data preservation during app updates.
 */
import { describe, expect, it, vi } from "vitest";
import { createRequire } from "node:module";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const require = createRequire(import.meta.url);
const userDataPaths = require(
  path.resolve(
    process.cwd(),
    "..",
    "..",
    "MasterplanOptimiserV3 - App",
    "masterplanOptimiserV3 - App",
    "desktop",
    "user-data-paths.js",
  ),
);

const {
  buildDesktopBackendEnv,
  buildSqliteDatabaseUrl,
  prepareDesktopUserData,
  resolveDesktopDataPaths,
} = userDataPaths;

function makeTempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mp-update-data-"));
}

function makeLogger() {
  return { log: vi.fn() };
}

describe("desktop user-data paths", () => {
  it("stores persistent data under the stable user-data directory", () => {
    const userDataDir = path.join(makeTempRoot(), "Masterplan Optimiser");

    const paths = resolveDesktopDataPaths(userDataDir);

    expect(paths.dataDir).toBe(path.join(userDataDir, "data"));
    expect(paths.databasePath).toBe(path.join(userDataDir, "data", "masterplan.db"));
    expect(paths.encryptionKeyPath).toBe(path.join(userDataDir, "data", "encryption.key"));
    expect(paths.databaseUrl).toBe(buildSqliteDatabaseUrl(paths.databasePath));
    expect(paths.databaseUrl).not.toContain("\\");
  });

  it("creates only the data directory before backend startup", () => {
    const userDataDir = path.join(makeTempRoot(), "user-data");
    const logger = makeLogger();

    const paths = prepareDesktopUserData({ userDataDir, logger });

    expect(fs.existsSync(paths.dataDir)).toBe(true);
    expect(fs.existsSync(paths.databasePath)).toBe(false);
    expect(fs.existsSync(paths.encryptionKeyPath)).toBe(false);
    expect(paths.databaseExists).toBe(false);
    expect(paths.encryptionKeyExists).toBe(false);
  });

  it("reuses existing database and key paths without overwriting files", () => {
    const userDataDir = path.join(makeTempRoot(), "user-data");
    const paths = resolveDesktopDataPaths(userDataDir);
    fs.mkdirSync(paths.dataDir, { recursive: true });
    fs.writeFileSync(paths.databasePath, "existing database", "utf-8");
    fs.writeFileSync(paths.encryptionKeyPath, "existing key", "utf-8");

    const prepared = prepareDesktopUserData({ userDataDir, logger: makeLogger() });

    expect(prepared.databaseExists).toBe(true);
    expect(prepared.encryptionKeyExists).toBe(true);
    expect(fs.readFileSync(prepared.databasePath, "utf-8")).toBe("existing database");
    expect(fs.readFileSync(prepared.encryptionKeyPath, "utf-8")).toBe("existing key");
  });

  it("passes absolute persistent paths to the backend environment", () => {
    const userDataDir = path.join(makeTempRoot(), "user-data");
    const paths = resolveDesktopDataPaths(userDataDir);

    const env = buildDesktopBackendEnv({ EXISTING: "1" }, paths, "token");

    expect(env.EXISTING).toBe("1");
    expect(env.ENVIRONMENT).toBe("desktop");
    expect(env.DESKTOP_AUTH_TOKEN).toBe("token");
    expect(env.DATABASE_URL).toBe(paths.databaseUrl);
    expect(env.ENCRYPTION_KEY_PATH).toBe(paths.encryptionKeyPath);
    expect(env.MASTERPLAN_USER_DATA_DIR).toBe(paths.userDataDir);
    expect(env.MASTERPLAN_DATA_DIR).toBe(paths.dataDir);
  });

  it("does not log encryption key contents", () => {
    const userDataDir = path.join(makeTempRoot(), "user-data");
    const logger = makeLogger();

    prepareDesktopUserData({ userDataDir, logger });

    const loggedText = logger.log.mock.calls.flat().join("\n");
    expect(loggedText).toContain("Active desktop data directory");
    expect(loggedText).toContain("Active desktop database path");
    expect(loggedText).not.toContain("existing key");
    expect(loggedText).not.toContain("ENCRYPTION_KEY");
    expect(loggedText).not.toContain("encryption.key");
  });
});
