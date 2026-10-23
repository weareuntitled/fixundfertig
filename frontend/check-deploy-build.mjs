import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const html = await readFile(new URL("./dist/index.html", import.meta.url), "utf8");
const revision = html.match(/<meta name="app-revision" content="([^"]+)"\s*\/>/)?.[1];
const expectedRevision = process.env.APP_REVISION;

assert.ok(revision, "Built frontend must expose its app-revision metadata");
assert.match(html, /(?:src|href)="\/static\/frontend\/assets\//, "Built assets must use the production mount path");
if (expectedRevision) assert.equal(revision, expectedRevision, "Built frontend revision must match APP_REVISION");

console.log(`Frontend build verified: revision=${revision}, base=/static/frontend/`);
