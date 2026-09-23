/* The balance table from scripts/balance.py, run against the JS port.

   The medians cannot match Python exactly - mulberry32 and the Mersenne
   Twister produce different streams - so what is compared is the shape:
   doing nothing must lose, random play must lose badly, and better judgement
   must raise both the survival rate and the ceiling. */
const { Game, STATIONS, COINS, bestChoice } = require("./game.js");

const RUNS = Number(process.argv[2] || 200);
const median = a => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };

function liquidate(g) {
  for (const [sym, h] of Object.entries(g.player.wallet)) if (h.qty > 0) g.sell(sym, h.qty);
}
function cheapest(g) {
  let best = null;
  for (const c of COINS) {
    if (c.symbol === "USDC") continue;
    const pos = (g.market.prices[c.symbol] - c.low) / (c.high - c.low);
    if (!best || pos < best[1]) best = [c.symbol, pos];
  }
  return best[0];
}

const STRATEGIES = [
  ["do nothing", () => {}],
  ["buy at random", g => {
    liquidate(g);
    const c = g.rng.choice(COINS);
    const q = g.maxBuyable(c.symbol);
    if (q > 0) g.buy(c.symbol, q * 0.9);
  }],
  ["buy the cheapest", g => {
    liquidate(g);
    const s = cheapest(g);
    const q = g.maxBuyable(s);
    if (q > 0) g.buy(s, q * 0.95);
  }],
  ["+ clear the debt", g => {
    liquidate(g);
    if (g.station.shark && g.player.debt > 0 && g.player.debt < g.player.cash * 0.55) {
      try { g.repay(g.player.debt); } catch (e) { /* not affordable */ }
    }
    if (g.station.shop && g.player.debt === 0 && g.player.cash > 80000) {
      try { g.buyCapacity(); } catch (e) { /* not affordable */ }
    }
    const s = cheapest(g);
    const q = g.maxBuyable(s);
    if (q > 0) g.buy(s, q * 0.95);
  }],
];

function play(seed, strategy) {
  const g = new Game(seed);
  for (let d = 0; d < 30; d++) {
    if (g.finished) break;
    try { strategy(g); } catch (e) { /* an unaffordable move is a no-op */ }
    const options = STATIONS.map((s, i) => i).filter(i => STATIONS[i].name !== g.station.name);
    try { g.travel(g.rng.choice(options)); } catch (e) { break; }
    // A standoff blocks every other action until it is answered. A bot that
    // ignored one would not merely skip an event - it would stop playing, and
    // quietly report the rest of the game as unwinnable.
    if (g.pending) { try { g.resolve(bestChoice(g)); } catch (e) { break; } }
  }
  return g.finalScore();
}

const results = {};
for (const [name, fn] of STRATEGIES) {
  const scores = [];
  for (let i = 0; i < RUNS; i++) scores.push(play(i, fn));
  scores.sort((a, b) => a - b);
  results[name] = {
    median: median(scores),
    p90: scores[Math.floor(scores.length * 0.9)],
    best: scores[scores.length - 1],
    solvent: scores.filter(s => s > 0).length / scores.length,
  };
}

if (process.argv.includes("--json")) {
  process.stdout.write(JSON.stringify(results));
} else {
  console.log(`\n  JS port, ${RUNS} runs per strategy\n`);
  console.log("  " + "strategy".padEnd(20) + "median".padStart(12) + "p90".padStart(12)
              + "best".padStart(13) + "solvent".padStart(10));
  console.log("  " + "-".repeat(67));
  for (const [name, r] of Object.entries(results)) {
    console.log("  " + name.padEnd(20)
      + Math.round(r.median).toLocaleString().padStart(12)
      + Math.round(r.p90).toLocaleString().padStart(12)
      + Math.round(r.best).toLocaleString().padStart(13)
      + (Math.round(r.solvent * 100) + "%").padStart(10));
  }
  console.log();
}
