import { webkit } from "playwright";
const S = "/private/tmp/claude-501/-Volumes-Ester-code-druewilding/ee26de0c-e50d-432e-a073-3dd0cb73bf3c/scratchpad";
const browser = await webkit.launch();
const page = await browser.newPage({ viewport: { width: 900, height: 600 } });
page.on("pageerror", (e) => console.log("ERR", e.message));
for (let i = 0; ; i++) { try { await page.goto("http://localhost:5179/3d?debug&at=-90,-104,0"); await page.waitForFunction(() => window.world?.scene, null, { timeout: 30000 }); break; } catch (e) { if (i > 3) throw e; } }
await page.waitForTimeout(2000);
await page.evaluate(() => document.querySelectorAll(".overlay").forEach((o) => (o.hidden = true)));
const said = () => page.evaluate(() => { const t = [...document.querySelectorAll("*")].filter((e) => e.children.length === 0 && /slange|balkon|stige|snake|balcony|ladder/i.test(e.textContent)).map((e) => e.textContent); return t.join(" | "); });
const pos = () => page.evaluate(() => { const p = window.world.player; return `${p.position.x.toFixed(1)}, ${p.position.z.toFixed(1)} ${p.under ? "(in the doorway/tower)" : ""} ${document.querySelector(".here").textContent}`; });
const walkTo = async (tx, tz, ms) => {
  await page.evaluate(([tx, tz]) => { const p = window.world.player; p.yaw = Math.atan2(-(tx - p.position.x), -(tz - p.position.z)); p.pitch = 0; }, [tx, tz]);
  await page.keyboard.down("KeyW");
  for (let t = 0; t < ms; t += 100) {
    await page.waitForTimeout(100);
    await page.evaluate(([tx, tz]) => { const p = window.world.player; p.yaw = Math.atan2(-(tx - p.position.x), -(tz - p.position.z)); }, [tx, tz]);
  }
  await page.keyboard.up("KeyW");
};
// 1. The ladder, propped.
await page.evaluate(() => window.world.player.place(-88, -108, 0));
await page.waitForTimeout(500);
await page.evaluate(() => { const { items } = window.world; const state = structuredClone(items.state); state.itemLocations.ladder = "carried"; items.restart({ state, three: { slots: ["ladder", null, null, null, null], lying: {} } }); });
await page.waitForTimeout(300);
await page.evaluate(() => { const p = window.world.player; p.yaw = 0.6; p.pitch = 0.6; });
await page.keyboard.press("KeyE");
await page.waitForTimeout(500);
const foot = await page.evaluate(() => { let m; window.world.scene.traverse((o) => { if (o.name === "ladder" && o.parent?.type === "Scene") m = o; }); return { x: m.position.x, z: m.position.z, tilt: (90 - Math.abs(m.rotation.x) * 180 / Math.PI).toFixed(0) }; });
console.log("1. ladder up:", (await said()), `${foot.tilt}° from upright`);
// 2. From the steps, walk to the ladder.
await page.evaluate(() => { const p = window.world.player; p.place(-88, -110, 0); });
await page.waitForTimeout(800);
await walkTo(foot.x - 0.6, foot.z + 1.2, 3000);
console.log("2. at the ladder:", await pos(), "|", await said());
await page.evaluate(() => { const p = window.world.player; p.pitch = 0.35; });
await page.waitForTimeout(300);
await page.screenshot({ path: `${S}/zones-ladder.png` });
await browser.close();
