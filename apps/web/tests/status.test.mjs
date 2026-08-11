import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("status shell explicitly excludes business behavior", async () => {
  const page = await readFile(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(page, /Business capabilities,\s+AI,/);
  assert.match(page, /external effects are intentionally unavailable/);
});
