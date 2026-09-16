/* Print the JS port's game data as JSON so tests can diff it against the
   Python package. Structural drift - a coin retuned in coins.py but not in
   game.js, a station bias changed on one side only - is silent otherwise, and
   would quietly make the phone version a different game from the terminal one. */
const G = require("./game.js");

const out = {
  constants: {
    DAYS: G.DAYS,
    SUBWAY_FARE: G.SUBWAY_FARE,
    START_CASH: new G.Game(1).player.cash,
    START_DEBT: new G.Game(1).player.debt,
    START_CAPACITY: new G.Game(1).player.capacity,
  },
  coins: G.COINS.map(c => ({
    symbol: c.symbol, name: c.name, low: c.low, high: c.high, meme: c.meme, note: c.note,
  })),
  progress: {
    version: G.PROGRESS_VERSION,
    runs_per_day: G.RUNS_PER_DAY,
    grades: G.GRADES.map(([threshold, letter, blurb]) => ({ threshold, letter, blurb })),
    tier_mults: G.TIERS.map(t => t.mult),
    tiers: G.TIERS.map(t => ({ level: t.level, name: t.name, debt: t.debt,
                               capacity: t.capacity, heat: t.heat, days: t.days })),
    /* a fixed instant, so both sides derive the same slate from the same date */
    daily_seeds: G.dailySeeds(1_700_000_000_000),
    achievements: G.ACHIEVEMENTS.map(a => a.key),
    perks: G.PERKS.map(x => ({ key: x.key, by: x.by })),
  },
  stations: G.STATIONS.map(s => ({
    name: s.name, heat: s.heat, bias: s.bias,
    shark: !!s.shark, vault: !!s.vault, shop: !!s.shop,
  })),
};
/* A representative save, so the Python side can check both implementations
   still agree on the format. Two front ends that disagree about what a save
   looks like is the same silent-drift problem as disagreeing about a coin. */
if (process.argv.includes("--save")) {
  const g = new G.Game(21);
  const q = g.maxBuyable("DOGE") * 0.3;
  if (q > 0) g.buy("DOGE", q);
  try { g.travel(0); } catch (e) { /* fare */ }
  process.stdout.write(JSON.stringify({ save_version: G.SAVE_VERSION, save: G.saveToDict(g) }, null, 2));
} else {
  process.stdout.write(JSON.stringify(out, null, 2));
}
