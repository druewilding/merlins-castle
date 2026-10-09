// Lists every image prompt in art/prompts and whether its original exists in
// art/originals. Run with: npm run art:status

import { existsSync, readdirSync } from "node:fs";

const kinds = ["scenes", "rooms", "items", "moments"];
let done = 0;
let total = 0;

for (const kind of kinds) {
  const ids = readdirSync(`art/prompts/${kind}`)
    .filter((file) => file.endsWith(".md"))
    .map((file) => file.replace(/\.md$/, ""))
    .sort();
  const made = ids.filter((id) => existsSync(`art/originals/${kind}/${id}.png`));
  done += made.length;
  total += ids.length;
  console.log(`\n${kind} (${made.length}/${ids.length})`);
  for (const id of ids) console.log(`  ${made.includes(id) ? "✓" : "·"} ${id}`);
}

console.log(`\n${done} of ${total} images made`);
