/* The checks a test suite cannot make, because they are about a browser.
   Run against a built page: `node web/browsercheck.js <path-to-index.html>`.
   Prints one JSON line per check. Kept out of the unittest run's way - it
   needs Playwright, and the package itself has no dependencies. */
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE
  || '/opt/node22/lib/node_modules/playwright');
const PAGE = 'file://' + path.resolve(process.argv[2]
  || path.join(__dirname, '..', 'docs', 'index.html'));
const BROWSER = process.env.CHROMIUM || '/opt/pw-browsers/chromium';

(async () => {
  /* The server already holds a real run, several days in. It is built by the
     port itself rather than typed out here, so it cannot go stale when the
     save format moves. */
  const seed = await (async () => {
    const b = await chromium.launch({ executablePath: BROWSER });
    const pg = await b.newPage();
    await pg.goto(PAGE);
    await pg.waitForTimeout(500);
    const run = await pg.evaluate(() => {
      const g = new Game(7, 1, null, {}, "normal");
      for (let i = 0; i < 8; i++) { try { g.travel((i * 3 + 1) % STATIONS.length); } catch (e) {} g.pending = null; }
      return saveToDict(g);
    });
    await b.close();
    return run;
  })();
  const server = seed;
  server.day = 9; server.saved_at = Date.now() / 1000;

  const browser = await chromium.launch({ executablePath: BROWSER });
  const page = await browser.newPage({ viewport: { width: 390, height: 664 } });
  const errs = []; page.on('pageerror', e => errs.push(String(e).split('\n')[0]));

  await page.addInitScript(({ run, SLOW }) => {
    // Safari in a frame: storage throws, so the page has no local copy at all
    const blow = () => { throw new Error("storage is blocked"); };
    Object.defineProperty(window, 'localStorage', {
      value: { getItem: blow, setItem: blow, removeItem: blow, clear: blow },
    });
    // a cloud that is SLOWER to read than the 1200ms push timer
    const store = { "progress": { updated_at: Date.now()/1000, profile: null, scores: [], run } };
    window.__writes = [];
    window.claude = {
      use: async (name) => {
        if (name === "user") return { id: async () => "u_test" };
        if (name === "db") return {
          doc: (path) => ({
            get: async () => { await new Promise(r => setTimeout(r, SLOW));
              const k = path.split("/").pop();
              return { exists: !!store[k], data: () => store[k] }; },
            set: async (body) => { window.__writes.push(body.run ? body.run.day : null);
              store[path.split("/").pop()] = body; },
          }),
          collection: () => ({ where: () => ({ orderBy: () => ({ limit: () => ({
            get: async () => ({ docs: [] }), onSnapshot: () => {} }) }) }),
            orderBy: () => ({ limit: () => ({ get: async () => ({ docs: [] }), onSnapshot: () => {} }) }),
            doc: () => ({ get: async () => ({ exists: false }), set: async () => {} }) }),
        };
        return null;
      },
    };
  }, { run: server, SLOW: 2600 });

  await page.goto(PAGE);
  await page.waitForTimeout(6000);
  const out = await page.evaluate(() => ({ day: game.day, writes: window.__writes }));
  await browser.close();
  /* The bug this pins: with storage blocked the page starts a fresh day-one
     run, saves it, and that save used to beat the restore down the wire and
     land on top of a real run. From the platform it looks like the days have
     stopped moving. */
  const ok = out.day === 9 && out.writes.every(d => d === 9) && errs.length === 0;
  console.log(JSON.stringify({ check: "boot never overwrites a newer cloud run",
                               ok, day: out.day, writes: out.writes, errors: errs.slice(0, 3) }));
  process.exit(ok ? 0 : 1);
})();
