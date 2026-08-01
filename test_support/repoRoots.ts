import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const testingRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const products = {
  app: {
    environment: "MP_OPT_APP_ROOT",
    markers: [
      "backend/app/main.py",
      "compute/pyproject.toml",
      "desktop/integrity.js",
    ],
  },
  server: {
    environment: "MP_OPT_SERVER_ROOT",
    markers: [
      "backend/app/main.py",
      "deploy/deploy.sh",
      "infra/docker-compose.prod.yml",
    ],
  },
} as const;

function isProductRoot(candidate: string, markers: readonly string[]): boolean {
  return markers.every((marker) => fs.statSync(path.join(candidate, marker), { throwIfNoEntry: false })?.isFile());
}

function childDirectories(root: string): string[] {
  try {
    return fs.readdirSync(root, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => path.join(root, entry.name));
  } catch {
    return [];
  }
}

function discoveryCandidates(): string[] {
  const bases: string[] = [];
  let base = testingRoot;
  for (let index = 0; index < 3; index += 1) {
    base = path.dirname(base);
    bases.push(base);
  }
  return bases.flatMap((candidate) => {
    const children = childDirectories(candidate);
    return [candidate, ...children, ...children.flatMap(childDirectories)];
  });
}

function resolveProductRoot(product: keyof typeof products): string {
  const specification = products[product];
  const configured = process.env[specification.environment];
  if (configured) {
    const root = path.resolve(configured);
    if (!isProductRoot(root, specification.markers)) {
      throw new Error(
        `${specification.environment} does not identify a ${product} repository: ${root}. `
        + `Expected markers: ${specification.markers.join(", ")}`,
      );
    }
    return root;
  }

  const matches = Array.from(new Set(discoveryCandidates().map((candidate) => path.resolve(candidate))))
    .filter((candidate) => isProductRoot(candidate, specification.markers));
  if (matches.length === 1) return matches[0];
  if (matches.length === 0) {
    throw new Error(
      `Could not discover the ${product} repository. `
      + `Set ${specification.environment} to its exact root.`,
    );
  }
  throw new Error(
    `Multiple ${product} repositories were discovered (${matches.join(", ")}). `
    + `Set ${specification.environment} to the exact checkout under test.`,
  );
}

export function resolveAppRoot(): string {
  return resolveProductRoot("app");
}

export function resolveServerRoot(): string {
  return resolveProductRoot("server");
}
