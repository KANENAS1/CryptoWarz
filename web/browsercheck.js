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
            set: async (body) => {
              // only the progress document is what this check is about; the
              // page also writes a mark to the platform, which is not a save
              if (/(^|\/)progress$/.test(path)) window.__writes.push(body.run ? body.run.day : null);
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
  /* CHECK 2: the database hands documents back FROZEN. The restore used to
     adopt one by reference, so `stats.stations.push` raised inside travel,
     between the line that moves the station and the line that moves the day.
     New stop, same day, same prices - and the wheel spinnable forever, because
     the run could not record that it had been spun. */
  const page2 = await browser.newPage({ viewport: { width: 390, height: 664 } });
  const errs2 = []; page2.on('pageerror', e => errs2.push(String(e).split('\n')[0]));
  await page2.goto(PAGE);
  await page2.waitForTimeout(600);
  const frozen = await page2.evaluate(run => {
    const deepFreeze = o => { if (o && typeof o === 'object') { Object.values(o).forEach(deepFreeze); Object.freeze(o); } return o; };
    game = saveFromDict(deepFreeze(JSON.parse(JSON.stringify(run))));
    const day = game.day, prices = Object.assign({}, game.market.prices);
    let threw = null, to = null;
    for (let i = 0; i < STATIONS.length; i++) {
      if (STATIONS[i].name === game.station.name) continue;
      to = STATIONS[i].name;
      try { game.travel(i); } catch (e) { threw = e.message; }
      break;
    }
    return { threw, arrived: game.station.name === to, dayMoved: game.day > day,
             pricesMoved: JSON.stringify(game.market.prices) !== JSON.stringify(prices),
             recorded: (game.stats.stations || []).includes(to) };
  }, seed);
  await page2.close();

  /* CHECK 3: robbing another player, end to end, across two real clients.
     The one that matters is the books: a published page cannot write into
     anybody else's save, so a lift is a document the mark settles and the
     thief later reads. If the two clients disagree about what it says, money
     is created or destroyed between two real people. */
  const db = { marks: {}, lifts: {} };
  const client = async (uid, name) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 664 } });
    const pg = await ctx.newPage();
    const errs = [];
    pg.on('pageerror', e => errs.push(uid + ': ' + String(e).split('\n')[0]));
    await pg.addInitScript(([uid, name, seed]) => {
      window.__db = JSON.parse(JSON.stringify(seed));
      const q = (n, f) => ({
        where: (k, op, v) => q(n, f.concat([[k, v]])),
        limit: () => q(n, f),
        get: async () => ({ docs: Object.entries(window.__db[n] || {})
          .filter(([id, d]) => f.every(([k, v]) => d[k] === v))
          .map(([id, d]) => ({ id, data: () => d })) }),
      });
      window.claude = { use: async t => {
        if (t === "user") return { id: async () => uid };
        if (t === "db") return {
          doc: p => ({
            get: async () => { const [c, i] = p.split("/");
              const d = (window.__db[c] || {})[i]; return { exists: !!d, data: () => d }; },
            set: async b => { const [c, i] = p.split("/");
              (window.__db[c] = window.__db[c] || {})[i] = JSON.parse(JSON.stringify(b)); },
          }),
          collection: n => q(n, []),
        };
        return null; } };
      try { localStorage.setItem("cryptowarz.player.v1", JSON.stringify({ id: uid, name })); } catch (e) {}
    }, [uid, name, db]);
    await pg.goto(PAGE);
    await pg.waitForTimeout(800);
    return { ctx, pg, errs };
  };
  const pull = c => c.pg.evaluate(() => window.__db);
  const push = (c, d) => c.pg.evaluate(x => { window.__db = x; }, d);

  const thief = await client("u_thief", "Thief");
  const markC = await client("u_mark", "Mark");
  const stand = (c, cash) => c.pg.evaluate(v => {
    game.day = 10; game.player.cash = v; game.pending = null; game.finished = false;
    game.station = STATIONS.find(s => s.name === "Wall Street");
    render(); persist();
  }, cash);
  await stand(thief, 45000);
  await stand(markC, 60000);
  await markC.pg.evaluate(() => pushMark());
  await markC.pg.waitForTimeout(200);
  await push(thief, await pull(markC));

  const cashOf = c => c.pg.evaluate(() => game.player.cash);
  const t0 = await cashOf(thief), m0 = await cashOf(markC);
  await thief.pg.evaluate(() => openPlatform());
  await thief.pg.waitForTimeout(400);
  const listed = await thief.pg.evaluate(() => document.querySelectorAll('[data-lift]').length);
  await thief.pg.evaluate(() => { const b = document.querySelector('[data-lift]'); if (b) b.click(); });
  await thief.pg.waitForTimeout(500);
  const staked = t0 - await cashOf(thief);

  // the mark opens the game and is met by it; it must survive a RELOAD unanswered
  await push(markC, await pull(thief));
  await markC.pg.evaluate(() => platformBoot());
  await markC.pg.waitForTimeout(400);
  const metFirst = await markC.pg.evaluate(() => !!pendingLift);
  const carried = await pull(markC);
  await markC.pg.reload();
  await markC.pg.waitForTimeout(400);
  await push(markC, carried);
  await markC.pg.evaluate(() => { game.day = 10; game.player.cash = 60000; platformBoot(); });
  await markC.pg.waitForTimeout(600);
  const survived = await markC.pg.evaluate(() => ({
    still: !!pendingLift,
    modal: pendingLift ? getComputedStyle($('lift')).display !== 'none' : false,
    answers: document.querySelectorAll('[data-lanswer]').length }));

  await markC.pg.evaluate(() => answerLift("brace"));
  await markC.pg.waitForTimeout(500);
  const m1 = await cashOf(markC), cleared = await markC.pg.evaluate(() => !pendingLift);

  await push(thief, await pull(markC));
  await thief.pg.evaluate(() => collectLifts());
  await thief.pg.waitForTimeout(500);
  const t1 = await cashOf(thief);
  await thief.pg.evaluate(() => collectLifts());       // twice must pay nothing
  await thief.pg.waitForTimeout(400);
  const t2 = await cashOf(thief);

  const pvpErrs = thief.errs.concat(markC.errs);
  await thief.ctx.close();
  await markC.ctx.close();
  const books = Math.abs((t1 - t0) + (m1 - m0));
  const pvp = { listed, staked: Math.round(staked), metFirst,
                survivedReload: survived.still && survived.modal && survived.answers === 3,
                cleared, booksOut: +books.toFixed(2),
                doubleCollected: +(t2 - t1).toFixed(2), errors: pvpErrs.slice(0, 3) };

  await browser.close();
  /* The bug this pins: with storage blocked the page starts a fresh day-one
     run, saves it, and that save used to beat the restore down the wire and
     land on top of a real run. From the platform it looks like the days have
     stopped moving. */
  const ok = out.day === 9 && out.writes.every(d => d === 9) && errs.length === 0;
  console.log(JSON.stringify({ check: "boot never overwrites a newer cloud run",
                               ok, day: out.day, writes: out.writes, errors: errs.slice(0, 3) }));
  const ok2 = !frozen.threw && frozen.arrived && frozen.dayMoved
              && frozen.pricesMoved && frozen.recorded && errs2.length === 0;
  console.log(JSON.stringify({ check: "a run restored from a frozen document can still ride",
                               ok: ok2, ...frozen, errors: errs2.slice(0, 3) }));
  const ok3 = pvp.listed > 0 && pvp.staked > 0 && pvp.metFirst && pvp.survivedReload
              && pvp.cleared && pvp.booksOut < 0.02 && pvp.doubleCollected === 0
              && !pvp.errors.length;
  console.log(JSON.stringify({ check: "a lift moves money between two runs and invents none",
                               ok: ok3, ...pvp }));
  process.exit(ok && ok2 && ok3 ? 0 : 1);
})();
