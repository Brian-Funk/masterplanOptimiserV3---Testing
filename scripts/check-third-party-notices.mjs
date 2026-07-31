import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const expectedLicence = "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0";
const normalised = fs.readFileSync(path.join(root, "LICENSE"), "utf8").replaceAll("\r\n", "\n");
if (crypto.createHash("sha256").update(normalised).digest("hex") !== expectedLicence) {
  throw new Error("LICENSE does not match the approved GNU AGPLv3 text");
}
const project = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const lock = JSON.parse(fs.readFileSync(path.join(root, "package-lock.json"), "utf8"));
if (project.license !== "AGPL-3.0-only" || lock.packages?.[""].license !== "AGPL-3.0-only") {
  throw new Error("Root npm SPDX metadata must be AGPL-3.0-only");
}
const notices = fs.readFileSync(path.join(root, "THIRD-PARTY-NOTICES.md"), "utf8");
for (const [packagePath, metadata] of Object.entries(lock.packages || {})) {
  if (!packagePath || metadata.link) continue;
  const name = packagePath.split("node_modules/").at(-1);
  const row = `| ${name} | ${metadata.version} | ${String(metadata.license).replaceAll("|", "\\|")} |`;
  if (!notices.includes(row)) throw new Error(`Missing notice row for ${name}@${metadata.version}`);
}
for (const required of ["BRANDING.md", "CONTRIBUTING.md", "COPYRIGHT-AND-CONTRIBUTION-PROVENANCE.md"]) {
  if (!fs.existsSync(path.join(root, required))) throw new Error(`Missing ${required}`);
}
console.log("Licence metadata and generated third-party notices verified.");
