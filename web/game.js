/* CryptoWarz game logic - a faithful port of the Python package.
   Kept deliberately separate from the UI so it can be diffed against
   cryptowarz/*.py and balance-tested with the same strategy bots. */

/* ---- seeded RNG: mulberry32 + Box-Muller, mirroring random.Random's API ---- */
function RNG(seed) {
  // the counter is a property rather than a closure variable so the whole
  // generator state can be serialised - a save that could not restore the
  // dice would let a reload reroll a bad day
  this._a = (seed >>> 0) || 1;
  this._spare = null;
}
RNG.prototype._next = function () {
  this._a = (this._a + 0x6D2B79F5) | 0;
  let t = Math.imul(this._a ^ (this._a >>> 15), 1 | this._a);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
RNG.prototype.getState = function () { return { a: this._a, spare: this._spare }; };
RNG.prototype.setState = function (s) { this._a = s.a | 0; this._spare = s.spare === undefined ? null : s.spare; };
RNG.prototype.random = function () { return this._next(); };
RNG.prototype.uniform = function (a, b) { return a + (b - a) * this._next(); };
RNG.prototype.gauss = function (mu, sigma) {
  if (this._spare !== null) { const s = this._spare; this._spare = null; return mu + sigma * s; }
  let u = 0, v = 0, s = 0;
  do { u = this._next() * 2 - 1; v = this._next() * 2 - 1; s = u * u + v * v; } while (s >= 1 || s === 0);
  const f = Math.sqrt(-2 * Math.log(s) / s);
  this._spare = v * f;
  return mu + sigma * u * f;
};
RNG.prototype.choice = function (arr) { return arr[Math.floor(this._next() * arr.length)]; };
RNG.prototype.choices = function (arr, weights) {
  const total = weights.reduce((x, y) => x + y, 0);
  let r = this._next() * total;
  for (let i = 0; i < arr.length; i++) { r -= weights[i]; if (r <= 0) return arr[i]; }
  return arr[arr.length - 1];
};

/* ------------------------------ coins.py ------------------------------ */
/* A spread of SPEEDS, not just of prices: `vol` is how fast the real market
   moves under every station, `meme` is how silly the local price gets from stop
   to stop. A coin can be a serious asset and still rip. */
const COINS = [
  { symbol: "SHIB", name: "Shiba Inu", low: 8e-06, high: 7.5e-05,
    meme: true, vol: 0.3, pull: 0.18,
    note: "fractions of a cent, whole lot of hope" },
  { symbol: "PEPE", name: "Pepe", low: 2e-06, high: 3.1e-05,
    meme: true, vol: 0.3, pull: 0.18,
    note: "pure vibes, no roadmap" },
  { symbol: "BONK", name: "Bonk", low: 9e-06, high: 0.000105,
    meme: true, vol: 0.42, pull: 0.11,
    note: "moves like a firework - lit at one stop, gone by the next" },
  { symbol: "DOGE", name: "Dogecoin", low: 0.06, high: 0.71,
    meme: true, vol: 0.3, pull: 0.18,
    note: "started as a joke, still is" },
  { symbol: "WIF", name: "Dogwifhat", low: 0.22, high: 4.8,
    meme: true, vol: 0.45, pull: 0.1,
    note: "the fastest thing on the board, in both directions" },
  { symbol: "XRP", name: "Ripple", low: 0.38, high: 3.4,
    meme: false, vol: 0.13, pull: 0.18,
    note: "perpetually in court" },
  { symbol: "SUI", name: "Sui", low: 0.45, high: 6.2,
    meme: false, vol: 0.24, pull: 0.12,
    note: "a real chain that trades like a rumour" },
  { symbol: "USDC", name: "USD Coin", low: 0.97, high: 1.03,
    meme: false, vol: 0.01, pull: 0.18,
    note: "a dollar, mostly - park cash here when it gets hot" },
  { symbol: "SOL", name: "Solana", low: 18.0, high: 260.0,
    meme: false, vol: 0.13, pull: 0.18,
    note: "fast chain, frequent outages" },
  { symbol: "AVAX", name: "Avalanche", low: 9.0, high: 78.0,
    meme: false, vol: 0.2, pull: 0.14,
    note: "serious money that still can't sit still" },
  { symbol: "ETH", name: "Ethereum", low: 1100.0, high: 4900.0,
    meme: false, vol: 0.13, pull: 0.18,
    note: "gas fees will eat you alive" },
  { symbol: "BTC", name: "Bitcoin", low: 21000.0, high: 109000.0,
    meme: false, vol: 0.11, pull: 0.18,
    note: "the original, and the heaviest to carry" },
];
COINS.forEach(c => { c.mid = (c.low + c.high) / 2; });
const COIN = Object.fromEntries(COINS.map(c => [c.symbol, c]));

/* ---------------------------- stations.py ----------------------------- */
const STATIONS = [
  { name: "Wall Street", lines: ["4", "5"], borough: "Manhattan",
    flavor: "Suits everywhere. Someone is explaining an ETF to a tourist.",
    bias: { BTC: 1.3, ETH: 1.22, AVAX: 1.16, USDC: 1.02, SUI: 1.06, DOGE: 0.62, SHIB: 0.55, PEPE: 0.5, BONK: 0.48, WIF: 0.44 },
    heat: 0.85, shark: false, vault: true, shop: false, wheel: false },
  { name: "Jefferson St", lines: ["L"], borough: "Brooklyn",
    flavor: "Bushwick. Three people in this car are launching a token this week.",
    bias: { WIF: 1.88, PEPE: 1.75, BONK: 1.7, SHIB: 1.62, DOGE: 1.45, SOL: 1.14, SUI: 1.12, BTC: 0.8 },
    heat: 0.55, shark: false, vault: false, shop: true, wheel: false },
  { name: "Times Sq-42 St", lines: ["N", "Q", "R", "W", "1", "2", "3", "7", "S"], borough: "Manhattan",
    flavor: "Tourist money. Everything here costs more and everyone knows it.",
    bias: { BTC: 1.18, ETH: 1.15, SOL: 1.2, DOGE: 1.25, XRP: 1.15, WIF: 1.32, BONK: 1.24, SUI: 1.18, AVAX: 1.12 },
    heat: 0.8, shark: false, vault: false, shop: false, wheel: false },
  { name: "Coney Island-Stillwell Av", lines: ["D", "F", "N", "Q"], borough: "Brooklyn",
    flavor: "End of the line. Salt air, dead arcade, suspiciously cheap everything.",
    bias: { SHIB: 0.45, PEPE: 0.42, BONK: 0.4, WIF: 0.38, DOGE: 0.58, XRP: 0.7, SOL: 0.82, SUI: 0.72, AVAX: 0.8 },
    heat: 0.3, shark: false, vault: false, shop: false, wheel: false },
  { name: "125 St", lines: ["4", "5", "6"], borough: "Manhattan",
    flavor: "Harlem. A man with a folding table will sell you anything.",
    bias: { DOGE: 1.3, XRP: 1.34, SHIB: 1.2, WIF: 1.36, BONK: 1.28, SUI: 1.12, ETH: 0.88 },
    heat: 0.6, shark: true, vault: false, shop: false, wheel: false },
  { name: "Grand Central-42 St", lines: ["4", "5", "6", "7", "S"], borough: "Manhattan",
    flavor: "Commuters moving with purpose. Liquidity, but no bargains.",
    bias: { BTC: 1.08, ETH: 1.1, USDC: 1.01, SOL: 1.05, AVAX: 1.07, SUI: 1.04 },
    heat: 0.7, shark: false, vault: true, shop: false, wheel: false },
  { name: "Flushing-Main St", lines: ["7"], borough: "Queens",
    flavor: "The busiest station outside Manhattan. Cash moves fast here.",
    bias: { XRP: 0.62, USDC: 0.98, SOL: 0.86, ETH: 0.92, SUI: 0.66, AVAX: 0.88, WIF: 0.78 },
    heat: 0.45, shark: false, vault: false, shop: false, wheel: false },
  { name: "161 St-Yankee Stadium", lines: ["4", "B", "D"], borough: "Bronx",
    flavor: "Game day. Everyone is up, everyone is buying, nobody is reading.",
    bias: { DOGE: 1.52, SHIB: 1.4, PEPE: 1.38, WIF: 1.6, BONK: 1.48, SUI: 1.22, BTC: 0.92 },
    heat: 0.65, shark: true, vault: false, shop: false, wheel: false },
  { name: "St George", lines: ["SIR"], borough: "Staten Island",
    flavor: "Off the ferry. Quiet, cheap, and a long way from anywhere.",
    bias: { BTC: 0.78, ETH: 0.8, SOL: 0.74, USDC: 0.99, AVAX: 0.76, SUI: 0.7, WIF: 0.72, BONK: 0.74 },
    heat: 0.2, shark: false, vault: false, shop: true, wheel: false },
  { name: "14 St-Union Sq", lines: ["4", "5", "6", "L", "N", "Q", "R", "W"], borough: "Manhattan",
    flavor: "Everything connects here. Fair prices, which is its own kind of trap.",
    bias: {  },
    heat: 0.5, shark: false, vault: true, shop: true, wheel: false },
  { name: "Bedford Av", lines: ["L"], borough: "Brooklyn",
    flavor: "Williamsburg. Every third person here has a podcast about this.",
    bias: { WIF: 1.72, BONK: 1.58, PEPE: 1.5, SOL: 1.18, SUI: 1.16, BTC: 0.86, ETH: 0.9 },
    heat: 0.58, shark: false, vault: false, shop: false, wheel: true },
  { name: "Atlantic Av-Barclays Ctr", lines: ["2", "3", "4", "5", "B", "D", "N", "Q", "R"], borough: "Brooklyn",
    flavor: "Nine lines and a arena. Everybody is going somewhere else.",
    bias: { BTC: 1.12, ETH: 1.09, AVAX: 1.1, DOGE: 1.18, SUI: 1.08, USDC: 1.01 },
    heat: 0.72, shark: true, vault: false, shop: false, wheel: true },
  { name: "Roosevelt Av-Jackson Hts", lines: ["7", "E", "F", "M", "R"], borough: "Queens",
    flavor: "Five lines, forty languages, and a remittance shop on every corner.",
    bias: { XRP: 1.3, USDC: 1.02, SOL: 1.08, AVAX: 1.04, SHIB: 1.12, BTC: 0.9 },
    heat: 0.62, shark: false, vault: true, shop: false, wheel: true },
  { name: "Canal St", lines: ["6", "J", "N", "Q", "R", "W", "Z"], borough: "Manhattan",
    flavor: "Chinatown. Cash only, and everything is a slightly better price.",
    bias: { USDC: 0.99, BTC: 0.84, ETH: 0.86, SOL: 0.8, XRP: 0.76, SUI: 0.78, AVAX: 0.82 },
    heat: 0.68, shark: false, vault: false, shop: true, wheel: true },
  { name: "Woodlawn", lines: ["4"], borough: "Bronx",
    flavor: "The top of the 4. A cemetery, a golf course, and nobody watching.",
    bias: { SHIB: 0.52, PEPE: 0.5, BONK: 0.48, WIF: 0.46, DOGE: 0.66, ETH: 0.88 },
    heat: 0.18, shark: false, vault: false, shop: false, wheel: true },
  { name: "Far Rockaway-Mott Av", lines: ["A"], borough: "Queens",
    flavor: "Ninety minutes from Midtown. The board here has not been updated in a while.",
    bias: { WIF: 0.44, BONK: 0.46, SUI: 0.68, AVAX: 0.74, SOL: 0.78, XRP: 1.28, USDC: 1.02 },
    heat: 0.22, shark: true, vault: false, shop: false, wheel: true },
];
const bias = (st, sym) => (st.bias[sym] !== undefined ? st.bias[sym] : 1.0);
/* How much of a stop's raw opinion reaches the price. Compressed toward 1.0 so
   no single stop is a money printer. */
const BIAS_COMPRESSION = 0.62;
/* What THIS stop adds to, or takes off, the market price. 1.0 is fair.
   The single biggest thing that happens to a player's money, and it used to be
   invisible: buying WIF where it is loved and selling anywhere else loses 60%
   with the market completely still. A player who cannot see that experiences
   their own overpaying as the coin turning on them. */
function stationMarkup(st, sym) { return 1 + (bias(st, sym) - 1) * BIAS_COMPRESSION; }

/* ----------------------------- market.py ------------------------------ */
const CRASHES = [
  ["{name} rugged - devs deleted the repo", 0.34],
  ["Exchange delists {name} without warning", 0.46],
  ["{name} bridge drained overnight", 0.38],
  ["Influencer who shilled {name} deletes the account", 0.55],
];
const PUMPS = [
  ["{name} trending #1 - the normies are buying", 2.10],
  ["Major fund announces a {name} allocation", 1.75],
  ["{name} listed everywhere at once", 1.95],
  ["Somebody's grandma asks about {name} on TV", 1.60],
];
const MEME_PUMPS = [
  ["A billionaire tweets a dog picture - {name} goes vertical", 3.10],
  ["{name} adopted by an entire subreddit", 2.45],
];

/* How often a coin's run re-rolls, and how hard it pushes as a multiple of the
   coin's daily volatility. A pure random walk wanders; it does not pump and it
   does not dump. This is the term that gives a chart SHAPES - a climb that
   builds over four days and then rolls over is something a player can see
   coming, be wrong about, and act on. Noise alone is none of those. */
const TREND_FLIP = 0.22, TREND_STRENGTH = 0.55;
/* How many days of level history to keep per coin, and how many a sparkline
   draws. The game has always moved like this and never let anyone SEE it - a
   market game showing one number per coin is a trading screen with the chart
   switched off, and a rumour that a coin is running is unusable if you cannot
   check whether it has been. */
const HISTORY_KEPT = 20, SPARK_DAYS = 14;

function MarketState(rng) {
  this.levels = {};
  /* the current run for each coin: a daily push that persists a few days */
  this.trends = {};
  for (const c of COINS) this.trends[c.symbol] = 0;
  for (const c of COINS) {
    // clamped to the coin's own range - an unclamped USDC opened as low as
    // $0.78, which made the safe asset the best trade on the board
    this.levels[c.symbol] = Math.max(c.low, Math.min(c.mid * rng.uniform(0.8, 1.2), c.high));
  }
  /* seeded AFTER the opening levels exist */
  this.history = {};
  for (const c of COINS) this.history[c.symbol] = [this.levels[c.symbol]];
}
MarketState.prototype.remember = function () {
  for (const c of COINS) {
    const past = (this.history[c.symbol] = this.history[c.symbol] || []);
    past.push(this.levels[c.symbol]);
    if (past.length > HISTORY_KEPT) past.splice(0, past.length - HISTORY_KEPT);
  }
};
MarketState.prototype.running = function (sym) { return this.trends[sym] || 0; };
MarketState.prototype.drift = function (rng) {
  for (const c of COINS) {
    let level = this.levels[c.symbol];
    if (c.symbol === "USDC") {
      this.levels.USDC = Math.max(0.97, Math.min(1.03, level * rng.uniform(0.997, 1.003)));
      continue;
    }
    // the run re-rolls now and then; the rest of the time it carries on, which
    // is what turns a walk into a pump and then a dump
    if (rng.random() < TREND_FLIP) this.trends[c.symbol] = rng.gauss(0, c.vol * TREND_STRENGTH);
    const step = this.trends[c.symbol] + rng.gauss(0, c.vol);
    const pull = level > 0 ? c.pull * Math.log(c.mid / level) : 0;
    level *= Math.exp(step + pull);
    this.levels[c.symbol] = Math.max(c.low * 0.4, Math.min(level, c.high * 1.6));
  }
  this.remember();
};
MarketState.prototype.apply = function (symbol, factor, coin) {
  /* A shock moves the real level, so it persists beyond one station - and it
     CORRECTS today's history point rather than adding one. The shock lands
     after drift has already recorded the day, so without this the chart kept
     the pre-shock number: a coin could double on a headline and the sparkline
     would show the day it did not move. */
  const level = this.levels[symbol] * factor;
  this.levels[symbol] = Math.max(coin.low * 0.15, Math.min(level, coin.high * 2.2));
  const past = this.history[symbol];
  if (past && past.length) past[past.length - 1] = this.levels[symbol];
};

function stationPrice(c, level, st, rng) {
  const b = stationMarkup(st, c.symbol);
  const noise = c.meme ? rng.uniform(0.94, 1.06) : rng.uniform(0.975, 1.025);
  const price = level * b * noise;
  if (c.symbol === "USDC") return Math.max(c.low, Math.min(price, c.high));
  return Math.max(c.low * 0.1, price);
}

/* `luck` maps a symbol to how far the crash/pump coin-flip tilts toward a pump
   for it. It moves the threshold on a draw that already happens rather than
   adding one; the flip is the same flip, weighted differently. */
function generate(st, rng, state, shockChance, luck) {
  if (shockChance === undefined) shockChance = 0.24;
  let shock = null;
  if (rng.random() < shockChance) {
    const pool = COINS.filter(c => c.symbol !== "USDC");
    const target = rng.choice(pool);
    const crashOdds = 0.5 - ((luck || {})[target.symbol] || 0);
    let entry;
    if (rng.random() < crashOdds) entry = rng.choice(CRASHES);
    else entry = rng.choice(target.meme ? MEME_PUMPS.concat(PUMPS) : PUMPS);
    shock = { symbol: target.symbol, headline: entry[0].replace("{name}", target.name),
              factor: entry[1], crash: entry[1] < 1.0 };
    state.apply(target.symbol, entry[1], target);
  }
  const prices = {};
  for (const c of COINS) prices[c.symbol] = stationPrice(c, state.levels[c.symbol], st, rng);
  return { station: st, prices, shock, headline: shock ? shock.headline : null };
}

/* ------------------------------ game.py ------------------------------- */
const DAYS = 30, START_CASH = 2000, START_DEBT = 5500, START_CAPACITY = 25000;
const SHARK_RATE = 0.10, VAULT_RATE = 0.04, SUBWAY_FARE = 2.90;
// reserving the fare exactly is not enough: rounding leaves $2.8999999999 and
// a player who cannot afford the fare the reserve was protecting
const FARE_BUFFER = 0.01;

/* -------------------------------- a word ------------------------------
   How often the man on the dice has heard something, and how often he is right
   ABOUT THE RUN. Measured against what the price really does over the next
   three days, tips land about 59% - a run pushes at roughly half a coin's daily
   noise, so three days of noise can bury it. A real edge, wrong often enough
   that believing one stays a decision. */
const TIP_CHANCE = 0.6, TIP_ACCURACY = 0.85;
const TIP_MIN_RUN = 0.5, TIP_FRESH_FOR = 3;

/* ------------------------------ the wheel -----------------------------
   Somebody has a prize wheel on the mezzanine at some stops. ONE SPIN PER STOP
   PER RUN, which is the whole design: it pays for going somewhere you have not
   been, not for bouncing between two stations. Without that it is a lever you
   pull instead of a map you explore, and a bigger map earns nothing.

   [label, weight, cash, gives gear] */
const WHEEL = [
  ["BUST", 24.0, 0.0, false],
  ["SMALL", 30.0, 300.0, false],
  ["MIDDLE", 22.0, 750.0, false],
  ["BIG", 13.0, 1600.0, false],
  ["JACKPOT", 7.0, 3400.0, false],
  ["GEAR", 4.0, 0.0, true]
];
const WHEEL_LINES = {
  BUST: "It lands between two wedges. The man shrugs.",
  SMALL: "A small one. He counts it out slowly, to make it last.",
  MIDDLE: "A decent wedge. He looks mildly disappointed for you.",
  BIG: "The crowd makes a noise. He stops smiling.",
  JACKPOT: "JACKPOT. He looks at the wheel, then at you, then at the wheel.",
  GEAR: "The wheel stops on the wedge nobody ever hits."
};

/* ------------------------------- the dice ------------------------------
   Somebody runs dice on the platform every few rides. There is no stake: the
   worst outcome is nothing, so this is a flourish rather than a decision, and
   deliberately not a way to gamble out of a bad run. */
const DICE_EVERY = 4, DICE_SIDES = 6, DICE_TOP_PRIZE = 1450.0;
/* How close you got, and what share of the top prize that is worth. Binary
   hit-or-miss made nine calls in ten pay nothing, which is a slot machine
   rather than a call. Graded by distance, most calls pay something and the
   number you say out loud starts to matter.

   Tuned so the worst call is worth roughly what the old version averaged and
   the best about 40% more. A quiet consequence worth leaving in: middle numbers
   beat 1 and 10, because a call at the edge has nowhere to be close on one
   side - $541 an offer against $381. Exact arithmetic, and small enough that it
   is a detail to notice rather than a headline. */
const DICE_LADDER = [
  [0, "DEAD ON", 1.0],
  [1, "ONE OFF", 0.4],
  [2, "CLOSE", 0.18],
  [3, "WARM", 0.06],
];
function diceTier(distance) {
  const hit = DICE_LADDER.find(([reach]) => distance <= reach);
  return hit ? { label: hit[1], share: hit[2] } : { label: "", share: 0 };
}
/* Opening calls that put a player on a streak, and what a streak pays. Not
   every ride and not the same amount: a fixed payment on a metronome stopped
   being a windfall by the third station and started being a salary. */
const HOT_HAND = [4, 2];
const HOT_HAND_CHANCE = 0.75, HOT_HAND_MIN = 250, HOT_HAND_MAX = 10000;


function Game(seed, tier, perk, gear, difficulty) {
  // kept so a save records which run this was - the RNG state is what restores
  // the dice, but the seed is what lets you tell someone else to try it
  this.seed = (seed === undefined || seed === null) ? (Math.random() * 1e9) | 0 : seed;
  this.tier = tier || 1;
  this.perk = perk || null;
  this.gear = gear || {};                  // {coin class: level}; see gear.py
  const t = TIER_BY_LEVEL[this.tier] || TIER_BY_LEVEL[1];
  const hard = difficultyOf(difficulty);
  this.difficulty = hard.key;              // normalised; an unknown key is Express
  this.days = t.days;
  this.heatMult = t.heat * hard.heatMult;  // the two axes multiply
  this.rng = new RNG(this.seed);
  this.day = 1;
  this.finished = false;
  this.station = STATIONS[9];              // 14 St-Union Sq
  this.player = { cash: START_CASH + hard.cash, debt: t.debt * hard.debtMult, vault: 0,
                  capacity: t.capacity, vpn: 0, wallet: {} };
  if (this.perk === "seed_round") this.player.cash += 2000;
  if (this.perk === "cold_storage") this.player.capacity += 15000;
  this.stats = { stations: [this.station.name], raids: 0, peak_worth: 0,
                 best_multiple: 0, worth_by_day: [],
                 dice_picks: [], dice_days: [], hot_hand: false };
  this.hotHand = false;
  this.wheelAward = null;                  // a gear class for the caller to bank
  this.gearAward = null;                   // the same, bought from a dealer
  /* somebody standing in front of you, waiting for an answer. While this is
     set the run is stopped, and it rides the save, so a reload is not a way
     to walk away from a man with a knife. */
  this.pending = null;
  this.weapon = null;                      // what you are carrying; one at a time
  this.log = [];
  this.state = new MarketState(this.rng);
  this.market = generate(this.station, this.rng, this.state, undefined, this.luckBySymbol());
  this.markStats();
  this.say(`Day 1. You're at ${this.station.name} with $${Math.round(this.player.cash).toLocaleString()} and a $${Math.round(this.player.debt).toLocaleString()} problem.`);
  if (this.market.headline) this.say(this.market.headline);
}
/* Refuse anything that is not an answer while somebody is waiting. Without
   this a player could buy, sell and ride away from a man holding a knife,
   which would make the encounter a message rather than a decision. */
Game.prototype.notNow = function () {
  if (this.pending) throw new Error("there is somebody in front of you. Answer him first");
};
Game.prototype.choices = function () { return encounterChoices(this); };
Game.prototype.resolve = function (choice) { return resolveStandoff(this, choice); };
/* Buy something to carry. One at a time, and only where they sell it. */
Game.prototype.buyWeapon = function (key) {
  this.notNow();
  if (!this.station.shop) throw new Error("nobody here sells that. Try a stop with a shop");
  if (!FOR_SALE.includes(key)) throw new Error(`no such thing; they stock ${FOR_SALE.join(", ")}`);
  const want = WEAPON_BY_KEY[key];
  if (this.player.cash < want.price) {
    throw new Error(`the ${want.name} is $${want.price.toLocaleString()} and you have `
                    + `$${this.player.cash.toFixed(2)}`);
  }
  const had = weaponOf(this.weapon);
  this.player.cash -= want.price;
  this.weapon = want.key;
  let message = `You buy the ${want.name}. $${want.price.toLocaleString()}, no receipt.`;
  if (had) message += ` The ${had.name.toLowerCase()} goes in a bin on the way out.`;
  this.say(message);
  return [message];
};
/* A day gone that you did not spend travelling: a stopped train or a beating.
   Both used to move the clock alone, which froze the market for a day - wrong
   fiction, a small free lunch, and a break in the one-price-per-day invariant
   the sparklines are drawn from. */
Game.prototype.loseADay = function () {
  this.day += 1;
  this.player.debt *= (1 + this.sharkRate);
  this.player.vault *= (1 + VAULT_RATE);
  this.state.drift(this.rng);
  this.market = generate(this.station, this.rng, this.state, undefined, this.luckBySymbol());
  this.markStats();
  this.endIfOver();
};
/* Close the run the moment the clock passes the last day.

   This check used to live only in travel(), which was true while the only way
   to spend a day was to ride somewhere. A stopped train and a beating also
   take one - and a beating arrives inside a standoff, whose resolution had no
   check at all. So a run could walk past day thirty and keep going: the header
   clamps the day to the last one, so it reads as a game that has stopped
   moving, the end screen never comes, and the score is never banked. */
Game.prototype.endIfOver = function () {
  if (!this.finished && this.day > this.days) this.finished = true;
};
Game.prototype.markStats = function () {
  const worth = this.netWorth();
  this.stats.peak_worth = Math.max(this.stats.peak_worth, worth);
  this.stats.worth_by_day.push(Math.round(worth * 100) / 100);
};
Object.defineProperty(Game.prototype, "fare", {
  get() { return this.perk === "metrocard" ? 0 : SUBWAY_FARE; } });
/* The difficulty's rate, less the Fixer's discount. The discount is a ratio so
   it is worth the same everywhere; at Express it still lands on exactly 8.5%. */
Object.defineProperty(Game.prototype, "sharkRate", {
  get() {
    const rate = difficultyOf(this.difficulty).shark;
    return this.perk === "fixer" ? rate * 0.85 : rate;
  } });
/* The best SINGLE bonus you have right now, 0 to 0.15: gear you are holding
   for, or the nerve of whatever is in your coat - whichever is larger, never
   the two added. "Never a sum" is the rule the luck system rests on, and a
   weapon is not an exception; what carrying something buys is a floor, which
   matters most early, when you have no gear at all. */
Object.defineProperty(Game.prototype, "luck", {
  get() { return Math.max(bestLuck(this.gear, this.player.wallet), nerveOf(this)); } });
Game.prototype.luckBySymbol = function () { return luckBySymbol(this.gear, this.player.wallet); };

/* ------------------------------- dead end ---------------------------- */
/* The game can genuinely corner you: a raid takes the bags, a gas spike takes
   the cash, and you are standing on a platform with no Shark and no vault and
   $1.40 in your pocket. Every other loss here is a decision that went wrong.
   This one is a wall, and a wall the player cannot see is just a frozen screen
   with a working button bar. */
Object.defineProperty(Game.prototype, "stranded", {
  get() {
    if (this.finished || this.player.cash + 1e-9 >= this.fare) return false;
    if (Object.values(this.player.wallet).some(h => h.qty > 0)) return false;
    if (this.station.vault && this.player.vault > 0) return false;
    if (this.station.shark && this.borrowable() > 0) return false;
    return true;
  } });
/* Deliberately not a way to erase the run: it finishes, so it is graded,
   recorded, and if it was ranked it spends the slot. Walking away from a bad
   position is allowed. Pretending it never happened is not. */
Game.prototype.giveUp = function () {
  if (this.finished) return [];
  this.finished = true;
  const message = `You give up the run at ${this.station.name} on day ${this.day}. That's it.`;
  this.say(message);
  return [message];
};

/* -------------------------------- a word ----------------------------- */
Object.defineProperty(Game.prototype, "tip", {
  get() {
    const rumour = this.stats.tip;
    if (!rumour) return null;
    return (this.day - (rumour.day || 0)) > TIP_FRESH_FOR ? null : rumour;
  } });
/* The man on the dice passes on what he heard. Sometimes it is true. */
Game.prototype.hearSomething = function () {
  if (this.rng.random() > TIP_CHANCE) return [];
  const running = COINS
    .filter(c => c.symbol !== "USDC"
                 && Math.abs(this.state.running(c.symbol)) >= c.vol * TIP_MIN_RUN)
    .map(c => [c.symbol, this.state.running(c.symbol)]);
  if (!running.length) return [];
  const [symbol, trend] = running.reduce((a, b) => Math.abs(b[1]) > Math.abs(a[1]) ? b : a);
  const truthful = this.rng.random() < TIP_ACCURACY;
  const goingUp = truthful ? trend > 0 : trend <= 0;
  this.stats.tip = { symbol: symbol, up: goingUp, day: this.day };
  const word = goingUp ? "about to run" : "about to fall over";
  return [`"Word is ${COIN[symbol].name} is ${word}." He might be wrong. He usually isn't.`];
};

/* -------------------------------- broker ----------------------------- */
Game.prototype.buyGear = function () {
  this.notNow();
  const cls = brokerOffer(this);
  if (cls === null) {
    if (this.stats.gear_bought) throw new Error("he only has the one, and you bought it");
    if (!this.station.shop) throw new Error("nobody's dealing here. Try a stop with a shop");
    throw new Error(`he wants ${BROKER_PRICE.toLocaleString()} in cash, and not a dollar less`);
  }
  this.player.cash -= BROKER_PRICE;
  this.stats.gear_bought = true;
  this.gearAward = cls;
  const message = `A million dollars, in a station. He hands over the `
    + `${GEAR_BY_KEY[cls].name} and is gone before you turn around.`;
  this.say(message);
  return [message];
};

/* ------------------------------ the wheel ---------------------------- */
Object.defineProperty(Game.prototype, "wheelReady", {
  get() {
    return !!this.station.wheel && !(this.stats.wheels || []).includes(this.station.name);
  } });
/* Sets wheelAward to a gear class on the rare wedge; the caller banks it,
   because the Game does not own the profile. */
Game.prototype.spinWheel = function () {
  this.notNow();
  if (!this.wheelReady) throw new Error("no wheel here, or you've already had your spin");
  this.wheelAward = null;
  (this.stats.wheels = this.stats.wheels || []).push(this.station.name);
  const label = this.rng.choices(WHEEL.map(w => w[0]), WHEEL.map(w => w[1]));
  const wedge = WHEEL.find(w => w[0] === label);
  const cash = wedge[2], givesGear = wedge[3];
  const messages = [`You spin. ${WHEEL_LINES[label]}`];
  if (cash > 0) messages.push(...this.gift(cash * (1 + this.luck), `Wheel - ${label}`));
  if (givesGear) {
    if (!countsForProgress(this)) {
      messages.push("It would have been a piece of gear. This run keeps nothing.");
    } else {
      // the class you are actually carrying, so the wheel reinforces a style
      const cls = winningClass(this) || this.rng.choice(GEAR.map(g => g.key));
      this.wheelAward = cls;
      messages.push(`${GEAR_BY_KEY[cls].name}. That is a win banked toward it, `
                    + `and they are not given away.`);
    }
  } else if (!cash) {
    messages.push("Nothing. It cost you nothing either.");
  }
  messages.forEach(m => this.say(m));
  return messages;
};

/* ------------------------------- the dice ---------------------------- */
/* Measured from the last roll rather than off the calendar: a signal delay
   costs two days instead of one, and a plain `day % 4` offer silently skipped
   every time one landed on the wrong day. Counting from the last roll also
   means an offer you ignore keeps standing. */
Object.defineProperty(Game.prototype, "diceReady", {
  get() {
    const days = this.stats.dice_days || [];
    return this.day - (days.length ? days[days.length - 1] : 0) >= DICE_EVERY;
  } });
/* Fair value rather than zero cost on purpose: a bag with no cost basis would
   take up no wallet room and make every sale an infinite multiple. Free means
   you did not pay cash for it, not that it weighs nothing. */
Game.prototype.gift = function (value, why) {
  const target = this.rng.choice(COINS.filter(c => c.symbol !== "USDC"));
  const price = this.market.prices[target.symbol];
  if (price <= 0) return [];
  const room = this.freeCapacity();
  if (room < 1) return [`${why} - and your wallet is full. It goes to somebody else.`];
  value = Math.min(value, room);
  const h = this.holding(target.symbol);
  h.qty += value / price;
  h.cost += value;
  return [`${why}: ${fmtQty(value / price)} ${target.symbol} (~$${value.toFixed(2)}).`];
};
/* Sometimes, and never the same amount twice. The draw is squared, which pulls
   most payouts down toward the floor and leaves the ceiling rare - a flat draw
   made five figures ordinary, and a windfall you can count on is not one. */
Game.prototype.streakGift = function () {
  if (this.rng.random() > HOT_HAND_CHANCE) return [];
  const draw = this.rng.random() ** 2;
  return this.gift(HOT_HAND_MIN + (HOT_HAND_MAX - HOT_HAND_MIN) * draw,
                   "The turnstile blesses you");
};
Game.prototype.rollDice = function (pick) {
  this.notNow();
  if (!this.diceReady) throw new Error("nobody's running dice right now");
  pick = parseInt(pick, 10);
  if (!(pick >= 1 && pick <= DICE_SIDES)) throw new Error(`call a number from 1 to ${DICE_SIDES}`);
  (this.stats.dice_days = this.stats.dice_days || []).push(this.day);
  const picks = (this.stats.dice_picks = this.stats.dice_picks || []);
  picks.push(pick);
  const rolled = 1 + Math.floor(this.rng.random() * DICE_SIDES);
  const distance = Math.abs(rolled - pick);
  const tier = diceTier(distance);
  const messages = [`You call ${pick}. The dice come up ${rolled}.`];
  if (tier.share > 0) {
    // gear pays out here too: a bag you are geared for is what makes the
    // platform friendlier, and the dice are on the platform
    const value = DICE_TOP_PRIZE * tier.share * (1 + this.luck);
    const bonus = this.luck > 0 ? ` (+${Math.round(this.luck * 100)}% on your gear)` : "";
    messages.push(...this.gift(value,
      `${tier.label} - ${Math.round(tier.share * 100)}% of the pot${bonus}`));
  } else {
    messages.push(`Off by ${distance}. Nothing, and it was free to play.`);
  }
  messages.push(...this.checkStreak(picks));
  messages.forEach(m => this.say(m));
  return messages;
};
Game.prototype.checkStreak = function (picks) {
  if (this.hotHand || picks.length < HOT_HAND.length) return [];
  if (!HOT_HAND.every((n, i) => picks[i] === n)) return [];
  this.hotHand = true;
  this.stats.hot_hand = true;
  return ["The dice stop mid-air.",
          "GOD MODE. The turnstile swings open for you from now on - free crypto every ride.",
          "This run is a sandbox now: it posts nothing and unlocks nothing."];
};
Game.prototype.finalise = function () {
  const held = Object.entries(this.player.wallet).filter(([, h]) => h.qty > 0).map(([s]) => s);
  this.stats.meme_only_finish = held.length > 0 && held.every(s => COIN[s].meme);
  this.markStats();
};
Game.prototype.say = function (m) { this.log.push(m); if (this.log.length > 200) this.log.shift(); };
Game.prototype.holding = function (sym) {
  if (!this.player.wallet[sym]) this.player.wallet[sym] = { qty: 0, cost: 0 };
  return this.player.wallet[sym];
};
Game.prototype.dropEmpty = function () {
  // an empty bag is not a holding - keeps saved and live wallets identical
  for (const [sym, h] of Object.entries(this.player.wallet)) {
    if (h.qty <= 1e-12 && h.cost <= 1e-12) delete this.player.wallet[sym];
  }
};
Game.prototype.usedCapacity = function () {
  return Object.values(this.player.wallet).reduce((s, h) => s + h.cost, 0);
};
Game.prototype.freeCapacity = function () {
  return Math.max(0, this.player.capacity - this.usedCapacity());
};
Game.prototype.portfolioValue = function () {
  let v = 0;
  for (const [sym, h] of Object.entries(this.player.wallet)) if (h.qty > 0) v += h.qty * this.market.prices[sym];
  return v;
};
Game.prototype.netWorth = function () {
  return this.player.cash + this.player.vault + this.portfolioValue() - this.player.debt;
};
Game.prototype.maxBuyable = function (sym) {
  const p = this.market.prices[sym];
  if (!(p > 0)) return 0;
  const spendable = Math.max(0, this.player.cash - this.fare - FARE_BUFFER);
  return Math.max(0, Math.min(spendable / p, this.freeCapacity() / p));
};
Game.prototype.buy = function (sym, qty) {
  this.notNow();
  if (!COIN[sym]) throw new Error(`nobody here trades ${sym}`);
  if (!(qty > 0)) throw new Error("buy how much?");
  const price = this.market.prices[sym], cost = price * qty;
  if (cost > this.player.cash + 1e-9) throw new Error(`that costs $${cost.toFixed(2)} and you have $${this.player.cash.toFixed(2)}`);
  if (cost > this.freeCapacity() + 1e-9) throw new Error(`your wallet only has $${this.freeCapacity().toFixed(2)} of room left`);
  const h = this.holding(sym);
  h.qty += qty; h.cost += cost; this.player.cash -= cost;
  return { text: `Bought ${fmtQty(qty)} ${sym} for $${cost.toFixed(2)}`, good: true };
};
Game.prototype.sell = function (sym, qty) {
  this.notNow();
  const h = this.holding(sym);
  if (!(qty > 0)) throw new Error("sell how much?");
  if (qty > h.qty + 1e-12) throw new Error(`you only hold ${fmtQty(h.qty)} ${sym}`);
  const price = this.market.prices[sym], proceeds = price * qty;
  const released = h.qty > 0 ? h.cost * (qty / h.qty) : 0;
  if (released > 0) this.stats.best_multiple = Math.max(this.stats.best_multiple, proceeds / released);
  const profit = proceeds - released;
  h.qty -= qty; h.cost -= released;
  if (h.qty <= 1e-12) { h.qty = 0; h.cost = 0; }
  this.dropEmpty();
  this.player.cash += proceeds;
  return { text: `Sold ${fmtQty(qty)} ${sym} for $${proceeds.toFixed(2)} (${profit >= 0 ? "made" : "lost"} $${Math.abs(profit).toFixed(2)})`,
           good: profit >= 0, profit };
};
// measured against what The Shark could seize, not net worth - net worth
// already subtracts the debt, so the ceiling sat below the opening loan and
// borrowing was refused every time a player first tried it
Game.prototype.borrowLimit = function () {
  // twice the opening loan: any lower and the Shark is dead UI, since a $6,000
  // ceiling already sits below day two's $6,050 of debt
  return Math.max(START_DEBT * 2, (this.player.cash + this.player.vault + this.portfolioValue()) * 2);
};
Game.prototype.borrowable = function () {
  return Math.max(0, this.borrowLimit() - this.player.debt);
};
Game.prototype.borrow = function (amount) {
  this.notNow();
  if (!this.station.shark) throw new Error("The Shark doesn't work this station");
  if (!(amount > 0)) throw new Error("borrow how much?");
  if (this.player.debt + amount > this.borrowLimit())
    throw new Error(`The Shark looks you up and down. Not a chance over $${this.borrowable().toFixed(0)}`);
  this.player.debt += amount; this.player.cash += amount;
  return { text: `Borrowed $${amount.toFixed(2)}. The Shark smiles. That's never good.`, good: false };
};
Game.prototype.repay = function (amount) {
  this.notNow();
  if (!this.station.shark) throw new Error("The Shark doesn't work this station");
  amount = Math.min(amount, this.player.debt, this.player.cash);
  if (!(amount > 0)) throw new Error("nothing to repay, or nothing to repay it with");
  this.player.debt -= amount; this.player.cash -= amount;
  return { text: `Repaid $${amount.toFixed(2)}.${this.player.debt <= 0 ? " Debt cleared. You can breathe." : ""}`, good: true };
};
Game.prototype.deposit = function (amount) {
  this.notNow();
  if (!this.station.vault) throw new Error("no vault at this station");
  amount = Math.min(amount, this.player.cash);
  if (!(amount > 0)) throw new Error("deposit how much?");
  this.player.cash -= amount; this.player.vault += amount;
  return { text: `Deposited $${amount.toFixed(2)}. It earns 4% a day in there.`, good: true };
};
Game.prototype.withdraw = function (amount) {
  this.notNow();
  if (!this.station.vault) throw new Error("no vault at this station");
  amount = Math.min(amount, this.player.vault);
  if (!(amount > 0)) throw new Error("withdraw how much?");
  this.player.vault -= amount; this.player.cash += amount;
  return { text: `Withdrew $${amount.toFixed(2)}.`, good: true };
};
Game.prototype.upgradeCost = function () {
  const steps = Math.round((this.player.capacity - START_CAPACITY) / 25000);
  return 3500 * Math.pow(1.7, steps);
};
Game.prototype.vpnCost = function () { return 2200 * Math.pow(2, this.player.vpn); };
Game.prototype.buyCapacity = function () {
  this.notNow();
  if (!this.station.shop) throw new Error("nowhere to buy hardware here");
  const price = this.upgradeCost();
  if (this.player.cash < price) throw new Error(`a bigger cold wallet costs $${price.toFixed(2)}`);
  this.player.cash -= price; this.player.capacity += 25000;
  return { text: `New cold wallet. Capacity now $${this.player.capacity.toLocaleString()}.`, good: true };
};
Game.prototype.buyVpn = function () {
  this.notNow();
  if (!this.station.shop) throw new Error("nowhere to buy hardware here");
  if (this.player.vpn >= 3) throw new Error("you are already as invisible as this gets");
  const price = this.vpnCost();
  if (this.player.cash < price) throw new Error(`that VPN costs $${price.toFixed(2)}`);
  this.player.cash -= price; this.player.vpn += 1;
  return { text: `VPN level ${this.player.vpn}. You draw less attention now.`, good: true };
};
Game.prototype.travel = function (index) {
  this.notNow();
  const wasReady = this.diceReady;         // so the offer is announced once
  const target = STATIONS[index];
  if (target.name === this.station.name) throw new Error("you're already here");
  if (this.player.cash + 1e-9 < this.fare) throw new Error(`you can't even make the $${this.fare.toFixed(2)} fare`);
  this.player.cash -= this.fare;
  this.station = target;
  if (!this.stats.stations.includes(target.name)) this.stats.stations.push(target.name);
  this.day += 1;
  this.player.debt *= (1 + this.sharkRate);
  this.player.vault *= (1 + VAULT_RATE);
  this.state.drift(this.rng);
  this.market = generate(this.station, this.rng, this.state, undefined, this.luckBySymbol());
  const messages = [`Day ${this.day}. ${target.name}.`, target.flavor];
  if (this.market.headline) messages.push(this.market.headline);
  if (this.hotHand) for (const m of this.streakGift()) messages.push(m);
  for (const m of rollEvent(this)) messages.push(m);
  if (this.wheelReady) messages.push("There's a prize wheel set up on the mezzanine here. "
    + "One spin, and only at stops you haven't worked yet.");
  if (this.diceReady && !wasReady) {
    messages.push(`Somebody's running dice on the platform. Call a number, 1 to ${DICE_SIDES}.`);
    for (const m of this.hearSomething()) messages.push(m);
  }
  this.markStats();
  messages.forEach(m => this.say(m));
  if (this.day > this.days) { this.finished = true; messages.push("That's the run."); }
  return messages;
};
Game.prototype.finalScore = function () { return this.netWorth(); };
Game.prototype.verdict = function () {
  const s = this.finalScore();
  if (this.player.debt > this.player.cash + this.player.vault + this.portfolioValue())
    return "The Shark owns you. Try a smaller loan next time.";
  if (s < START_CASH) return "You went thirty days and finished poorer. The subway still got its fare.";
  if (s < 25000) return "A living. Barely.";
  if (s < 100000) return "Respectable. You could do this for real. Please don't.";
  if (s < 500000) return "You cleaned up. Somebody is going to ask questions.";
  return "Legendary. They'll name a station after you.";
};

/* --------------------------- encounter.py -----------------------------
   Somebody is standing in front of you, and the game stops to ask.

   Every other bad thing here happens TO you and you read about it afterwards.
   That is right for weather and wrong for a person: a person blocking the
   stairs is a decision. So a stickup does not resolve - it waits, it blocks
   every other action, and it rides the save, so a reload is not a way out.

   Every option is bad in a different way. Running is free and usually works,
   but a full wallet is a slow wallet - the run that most needs to walk away is
   the one least able to. Fighting is a coin flip that can cost a day. Paying
   is certain, expensive, and advertises you. A weapon makes the fight a
   favourite and makes the SEC look twice, which is the trade the armoury is
   built on. */
const WEAPONS = [
  { key: "brick",  name: "Half a Brick",
    blurb: "It was holding a door open. Now it is holding your nerve together.",
    edge: 0.12, heat: 0.02, breaks: 0.45, price: 0, nerve: 0.01 },
  { key: "pipe",   name: "Length of Pipe",
    blurb: "Scaffolding offcut. Heavier than it looks, which is the entire idea.",
    edge: 0.18, heat: 0.06, breaks: 0.20, price: 400, nerve: 0.02 },
  { key: "cutter", name: "Box Cutter",
    blurb: "Nobody wants to find out whether you would. That is usually enough.",
    edge: 0.26, heat: 0.14, breaks: 0.10, price: 1200, nerve: 0.03 },
  { key: "bat",    name: "Louisville Slugger",
    blurb: "You tell people you play softball. Nobody has ever believed you.",
    edge: 0.33, heat: 0.20, breaks: 0.06, price: 3200, nerve: 0.04 },
  { key: "taser",  name: "Stun Gun",
    blurb: "Legal in some states. This is not one of them, and it is the good kind.",
    edge: 0.42, heat: 0.28, breaks: 0.14, price: 9000, nerve: 0.05 },
];
const WEAPON_BY_KEY = Object.fromEntries(WEAPONS.map(w => [w.key, w]));
const FOR_SALE = WEAPONS.filter(w => w.price > 0).map(w => w.key);
function weaponOf(key) { return key ? (WEAPON_BY_KEY[key] || null) : null; }
function carryHeat(g) { const w = weaponOf(g.weapon); return w ? w.heat : 0; }
/* The luck a weapon is worth just by being in your coat. */
function nerveOf(g) { const w = weaponOf(g.weapon); return w ? w.nerve : 0; }

const REP_MAX = 3, REP_ENCOUNTER = 0.06, REP_ODDS = 0.05;
function repOf(g) { return Math.max(-REP_MAX, Math.min(REP_MAX, (g.stats.rep | 0))); }
function bumpRep(g, d) { g.stats.rep = Math.max(-REP_MAX, Math.min(REP_MAX, repOf(g) + d)); }

/* A full wallet is a slow wallet - the sharpest idea in the encounter. */
const MAX_LOAD_PENALTY = 0.28, RUN_BASE = 0.62, FIGHT_BASE = 0.34;
function loadPenalty(g) {
  const cap = Math.max(1, g.player.capacity);
  return MAX_LOAD_PENALTY * Math.min(1, g.usedCapacity() / cap);
}
function encounterOdds(g, choice) {
  const rep = repOf(g);
  let chance;
  if (choice === "relay") {
    /* the same coin every gamble here is flipped on: luck tilts it, which is
       the one place nerve pays off outside a fight */
    return Math.max(0.05, Math.min(0.95, RELAY_BASE + g.luck));
  }
  if (choice === "run") {
    chance = RUN_BASE - loadPenalty(g) + rep * REP_ODDS;
  } else if (choice === "fight" || choice === "weapon") {
    chance = FIGHT_BASE + rep * REP_ODDS;
    if (choice === "weapon") {
      const w = weaponOf(g.weapon);
      if (!w) return 0;
      chance += w.edge;
    }
    chance += g.luck * 0.5;
  } else { return 1; }
  return Math.max(0.05, Math.min(0.95, chance));
}

const KINDS = [
  { key: "stickup", title: "SOMEBODY BLOCKS THE STAIRS", severity: 1.0, armable: true,
    options: ["run", "fight", "weapon", "pay"],
    opening: [
      'A man steps out of the stairwell at {station} and does not move. "Phone. Wallet. Whatever\'s in the bag."',
      "Two of them, one either side of the turnstile at {station}. The one on the left is doing the talking and the one on the right is why.",
      "He has been on the platform at {station} since you got off, and now he is close enough that you can smell the cigarettes.",
    ] },
  { key: "followed", title: "YOU WERE FOLLOWED OFF THE TRAIN", severity: 0.85, armable: true,
    options: ["run", "fight", "weapon", "pay"],
    opening: [
      "Somebody got off at {station} when you did, and took the same stairs, and is now standing closer than anybody stands by accident.",
      "He rode three cars down and got off at {station} behind you. He is not looking at his phone. Nobody on this platform is not looking at their phone.",
      "The kid who was watching your screen on the ride gets off at {station} too, and he has friends.",
    ] },
  { key: "collector", title: "THE SHARK SENT SOMEBODY", severity: 1.0, armable: true,
    options: ["pay", "run", "fight", "weapon"],
    opening: [
      "The large man from the platform at {station} is not large by accident, and he knows your name, and he would like some of it back.",
      '"He says you\'ve been busy." The associate does not sit down. Nobody at {station} is looking at either of you, very deliberately.',
      "He is waiting at the bottom of the stairs at {station} with his hands where you can see them, which is somehow worse.",
    ] },
  /* No weapon against a badge, deliberately: a trap you can only learn by
     falling into it is a worse teacher than a door that was never there. */
  { key: "badge", title: "FEDERAL AGENTS AT THE TURNSTILE", severity: 1.0, armable: false,
    options: ["comply", "lawyer", "run"],
    opening: [
      "Two of them at the {station} turnstile, and they were waiting for you rather than for a train.",
      "The suit at {station} shows you something in a wallet and asks you to step to one side. He is not really asking.",
      "They come down both stairwells at {station} at once, which tells you how long they have known.",
    ] },
  { key: "drain", title: "A SIGNATURE REQUEST", severity: 1.0, armable: false,
    options: ["sign", "check", "walk"],
    opening: [
      "Your wallet lights up at {station}. A contract wants permission for something, and the name on it is one letter off a name you trust.",
      "The airdrop everybody has been posting about wants you to sign. It is either the one they mean or the one pretending to be it.",
      "A DM, a link, a connect prompt, and a countdown. Everything about it is designed to make you hurry.",
    ] },
  { key: "gas", title: "THE NETWORK IS ON FIRE", severity: 1.0, armable: false,
    options: ["paygas", "relay"],
    opening: [
      "Every block at {station} is a bidding war. Moving your own money is going to cost you today.",
      "Fees have gone vertical. Somebody minted something and the whole chain is paying for it.",
      "The mempool is a car park. You can pay to get out of it or you can find another way round.",
    ] },
];
const KIND_BY_KEY = Object.fromEntries(KINDS.map(k => [k.key, k]));

function openStandoff(g, kindKey) {
  const kind = KIND_BY_KEY[kindKey] || KINDS[0];
  const line = g.rng.choice(kind.opening).replace(/\{station\}/g, g.station.name);
  const pending = { kind: kind.key, day: g.day, station: g.station.name, line: line };
  /* decided now, not when you answer: paying to read the contract has to
     reveal something that already exists, or "check" would be a different roll
     rather than the same one seen clearly. It rides the save for the same
     reason. */
  if (kind.key === "drain") pending.real = g.rng.random() < DRAIN_REAL ? 1 : 0;
  if (kind.key === "gas") pending.fee = 120 + g.rng.random() * 700;
  g.pending = pending;
  g.stats.standoffs = (g.stats.standoffs | 0) + 1;
  return [line];
}

function payCost(g) {
  const kind = KIND_BY_KEY[(g.pending || {}).kind] || KINDS[0];
  return Math.max(150, g.player.cash * 0.22 * kind.severity);
}

/* What a lawyer costs and what he is worth: the only answer to a badge that is
   not a bet - you buy the seizure down instead. */
/* How often a signature request is the airdrop it claims to be. Under half on
   purpose: signing has to be a bad bet you sometimes take anyway, or "read the
   contract" would be a tax rather than a choice. */
const DRAIN_REAL = 0.25, DRAIN_PAYS = [350, 1800], DRAIN_TAKES = [0.08, 0.22];
const CHECK_SHARE = 0.04, CHECK_MIN = 220;
const RELAY_SHARE = 0.10, RELAY_BASE = 0.72, RELAY_TAKES = [0.06, 0.15];
function checkCost(g) { return Math.max(CHECK_MIN, g.player.cash * CHECK_SHARE); }
function gasFee(g) { return ((g.pending || {}).fee) || 400; }

const LAWYER_SHARE = 0.18, LAWYER_MIN = 800, LAWYER_SAVES = 0.55;
function lawyerCost(g) { return Math.max(LAWYER_MIN, g.player.cash * LAWYER_SHARE); }
/* What the Shark's man came for: a quarter of the debt, if you have it. */
function collectorDemand(g) {
  return Math.min(Math.max(0, g.player.cash - SUBWAY_FARE), g.player.debt * 0.25);
}

/* Every option a kind accepts, built in one place so the terminal, the phone
   and the tests read one list. A kind that does not accept an answer simply
   does not show it - no hidden options, none shown and then refused. */
function encounterChoices(g) {
  if (!g.pending) return [];
  const kind = KIND_BY_KEY[g.pending.kind] || KINDS[0];
  const w = weaponOf(g.weapon);
  const n = v => Math.round(v).toLocaleString();
  const built = {
    run: { key: "run", label: "RUN", odds: encounterOdds(g, "run"),
           note: "Down the platform and out. What you are carrying slows you down." },
    fight: { key: "fight", label: "SWING FIRST", odds: encounterOdds(g, "fight"),
             note: "Bare hands. It is a coin flip and the coin is not yours." },
    pay: { key: "pay", label: "HAND IT OVER", odds: 1,
           note: `Give up ${n(payCost(g))} and walk away whole. Word gets around that you do.` },
    comply: { key: "comply", label: "HANDS WHERE THEY CAN SEE THEM", odds: 1,
              note: "Let them take what they came for. Nothing else happens to you today." },
  };
  if (w && kind.armable) {
    built.weapon = { key: "weapon", label: `USE THE ${w.name.toUpperCase()}`,
                     odds: encounterOdds(g, "weapon"),
                     note: `${w.name}. It might not survive the night either.` };
  }
  if (kind.key === "collector") {
    built.pay = { key: "pay", label: "PAY HIM", odds: 1,
                  note: `${n(collectorDemand(g))} off the cash and the same off the debt. `
                        + `It is a payment, not a robbery.` };
    built.run = Object.assign({}, built.run, {
      note: "You keep the money. The Shark adds a fee for the inconvenience, and he does not forget." });
    for (const key of ["fight", "weapon"]) {
      if (built[key]) built[key] = Object.assign({}, built[key],
        { note: built[key].note + " The debt stands either way." });
    }
  }
  if (kind.key === "drain") {
    const real = (g.pending.real | 0), known = !!g.pending.known;
    built.sign = { key: "sign", label: "SIGN IT",
      odds: known ? (real ? 1 : 0) : DRAIN_REAL,
      note: known ? (real ? "It is the real one. Sign." : "It is a drainer. Do not.")
                  : `Roughly ${Math.round(DRAIN_REAL * 100)}% of these are the airdrop `
                    + `they say they are. The rest empty a share of your bag.` };
    built.check = { key: "check", label: "READ THE CONTRACT", odds: 1,
      note: known ? "Already read."
                  : `${n(checkCost(g))} to somebody who can read Solidity. You will `
                    + `know which it is, and then you decide.` };
    built.walk = { key: "walk", label: "IGNORE IT", odds: 1,
      note: "Costs nothing. You will never know what it was." };
    if (known) delete built.check;
  }
  if (kind.key === "gas") {
    built.paygas = { key: "paygas", label: "PAY THE FEE", odds: 1,
      note: `About ${n(gasFee(g))} to move your own money. Annoying, certain, over with.` };
    built.relay = { key: "relay", label: "USE A PRIVATE RELAY",
      odds: encounterOdds(g, "relay"),
      note: `A tenth of the fee, through somebody you found on a forum. Usually fine.` };
  }
  if (kind.key === "badge") {
    built.lawyer = { key: "lawyer", label: "CALL A LAWYER", odds: 1,
      note: `${n(lawyerCost(g))} on a retainer, and they leave with `
            + `${Math.round((1 - LAWYER_SAVES) * 100)}% of what they came for. Certain, and it hurts.` };
    built.run = Object.assign({}, built.run, {
      note: "From federal agents, in a subway station. If it works you keep everything. "
            + "They will remember you either way." });
  }
  return kind.options.map(k => built[k]).filter(Boolean);
}

/* The answer with the best odds, for bots and simulations - not for the game,
   where a standoff is the player's to answer. It exists so the balance bots
   face the same decisions a player does rather than being exempt from them. */
function bestChoice(g) {
  const options = encounterChoices(g);
  if (!options.length) return null;
  /* For the two encounters that replaced an event, a bot takes the answer that
     event used to take on its own, so balance numbers stay comparable. */
  const kind = (g.pending || {}).kind;
  if (kind === "badge") return "comply";
  if (kind === "collector") return "pay";
  if (kind === "gas") return "paygas";
  if (kind === "drain") return "sign";   // the naive answer the old event forced
  const keys = options.map(c => c.key);
  const fighting = options.filter(c => c.key !== "pay");
  const best = fighting.reduce((a, b) => (b.odds > a.odds ? b : a));
  if (best.odds >= 0.45) return best.key;
  return keys.includes("pay") ? "pay" : best.key;
}

const TAKE_CASH = [0.30, 0.60], TAKE_BAG = [0.10, 0.26], HOSPITAL_CHANCE = 0.35;
function rob(g, scale) {
  const cashShare = g.rng.uniform(TAKE_CASH[0], TAKE_CASH[1]) * scale;
  const bagShare = Math.min(0.9, g.rng.uniform(TAKE_BAG[0], TAKE_BAG[1]) * scale);
  const cash = takeCash(g, g.player.cash * cashShare);
  const bag = confiscate(g, bagShare);
  return [cash, bag];
}
function lossLine(cash, bag) {
  const m = v => "$" + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (cash > 0 && bag > 0) return `${m(cash)} and ${m(bag)} of the bag, at cost.`;
  if (cash > 0) return `${m(cash)}.`;
  if (bag > 0) return `${m(bag)} of the bag, at cost.`;
  return "nothing, because you had nothing. Small mercies.";
}
/* What refusing the Shark's man costs on the loan. He does not take it
   personally; he takes it out of the principal. */
const SHARK_FEE_RAN = 0.08, SHARK_FEE_FOUGHT = 0.13;
const money2 = v => "$" + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/* The Shark's associate: the one encounter where paying is the GOOD end. What
   he takes comes off the debt as well as the cash, so refusing is not saving
   money - it is declining to pay down a loan that compounds at ten per cent a
   day, and being charged for the privilege. */
function collectorStandoff(g, choice, w) {
  const out = [];
  const finish = () => { out.forEach(m => g.say(m)); return out; };
  const demand = collectorDemand(g);

  if (choice === "pay") {
    if (demand < 50) {
      out.push("You turn out your pockets. He counts what is there, which does not take long, and tells you he will find you again.");
      return finish();
    }
    const taken = takeCash(g, demand);
    g.player.debt = Math.max(0, g.player.debt - taken);
    out.push(`You pay him ${money2(taken)}. It comes straight off the loan, which is the only good thing anybody can say about it.`);
    return finish();
  }

  const won = g.rng.random() < encounterOdds(g, choice);

  if (choice === "run") {
    if (won) {
      g.player.debt *= (1 + SHARK_FEE_RAN);
      out.push("You lose him on the mezzanine. Nothing leaves your pocket today.");
      out.push(`By the evening the loan has grown ${Math.round(SHARK_FEE_RAN * 100)}%. He made a phone call before he lost you.`);
      return finish();
    }
    const taken = takeCash(g, demand * 1.2);
    g.player.debt = Math.max(0, g.player.debt - taken);
    out.push(`He is faster than he looks. ${money2(taken)}, off the cash and off the loan, and he keeps the difference for his trouble.`);
    return finish();
  }

  if (won) {
    bumpRep(g, 1);
    if (choice === "weapon" && w) {
      out.push(`The ${w.name.toLowerCase()} settles it. He goes back up the stairs with a message you did not write down.`);
      if (g.rng.random() < w.breaks) {
        g.weapon = null;
        out.push(`You leave the ${w.name.toLowerCase()} in a bin two blocks away. It was that or explain it.`);
      }
    } else {
      out.push("You put him on the floor of the mezzanine. People step around both of you without breaking stride.");
    }
    g.player.debt *= (1 + SHARK_FEE_FOUGHT);
    out.push(`The Shark hears about it within the hour and adds ${Math.round(SHARK_FEE_FOUGHT * 100)}% to what you owe. He can afford to be philosophical.`);
    return finish();
  }

  bumpRep(g, -1);
  if (choice === "weapon" && w) {
    g.weapon = null;
    out.push(`He takes the ${w.name.toLowerCase()} off you before you have finished deciding to use it.`);
  }
  const taken = takeCash(g, demand * 1.35);
  g.player.debt = Math.max(0, g.player.debt - taken);
  out.push(`It does not go your way. ${money2(taken)}, and he counts it twice.`);
  if (g.rng.random() < HOSPITAL_CHANCE) {
    g.loseADay();
    out.push("You lose a day to it, and the loan does not stop for that either.");
  }
  return finish();
}

/* Running from federal agents works or it does not, and if it does not they
   are considerably less interested in your side of it. */
const CAUGHT_MULTIPLIER = 1.4;

/* Agents at the turnstile. The seizure itself is unchanged, so every number
   the game was balanced against still holds for anybody who complies. */
function badgeStandoff(g, choice) {
  const out = [];
  const finish = () => { out.forEach(m => g.say(m)); return out; };
  const seize = scale => {
    const holding = Object.values(g.player.wallet).some(h => h.qty > 0);
    if (!holding) {
      const fine = takeCash(g, (400 + g.rng.random() * 900) * scale);
      return `Nothing to seize, so they write you a ${money2(fine)} fine instead and take your name twice.`;
    }
    const fraction = Math.min(0.95, g.rng.uniform(0.18, 0.42) * scale);
    const lost = confiscate(g, fraction);
    return `They seize ${Math.round(fraction * 100)}% of the wallet - ${money2(lost)} at cost. Your lawyer is not returning calls.`;
  };
  g.stats.raids = (g.stats.raids | 0) + 1;

  if (choice === "comply") {
    out.push("You put your hands where they can see them and let it happen.");
    out.push(seize(1));
    return finish();
  }
  if (choice === "lawyer") {
    const paid = takeCash(g, lawyerCost(g));
    out.push(`You make the call. ${money2(paid)} on a retainer, and somebody who knows the words arrives inside the hour.`);
    out.push(seize(1 - LAWYER_SAVES));
    return finish();
  }

  if (g.rng.random() < encounterOdds(g, "run")) {
    g.stats.fled_sec = (g.stats.fled_sec | 0) + 1;
    out.push(g.rng.choice([
      "You go over the turnstile and out through the service door before either of them is through the crowd. Nothing of yours leaves with them.",
      "Down the stairs, along the platform, up the far exit. You are on a bus before anybody has said your name into a radio.",
    ]));
    out.push("They have your face now, which is a bill that arrives later.");
    return finish();
  }

  out.push("They have you before the turnstile, and they are not gentle about the fact that you tried.");
  out.push(seize(CAUGHT_MULTIPLIER));
  const w = weaponOf(g.weapon);
  if (w) {
    g.weapon = null;
    out.push(`They find the ${w.name.toLowerCase()}. That goes in a bag with a label on it, and so does the rest of your afternoon.`);
    g.loseADay();
  }
  return finish();
}

/* A signature request that is either the airdrop or the thing wearing it. The
   decision is information, not odds: take the bet blind, pay to know and then
   take it with your eyes open, or walk and never find out. Ignoring it is
   always free, which is what stops "read it" being a tax. */
function drainStandoff(g, choice, was) {
  const out = [];
  const finish = () => { out.forEach(m => g.say(m)); return out; };
  const real = !!(was.real | 0);

  if (choice === "walk") {
    out.push("You close the tab. Whatever it was, it was not worth finding out at that speed.");
    return finish();
  }
  if (choice === "check") {
    const paid = takeCash(g, checkCost(g));
    g.pending = Object.assign({}, was, { known: true });
    g.pending.line = `${money2(paid)} later, somebody who reads Solidity for a living tells you `
      + (real ? "it is exactly what it says it is."
              : "the approval is unlimited and the recipient is not the project.");
    out.push(g.pending.line);
    return finish();
  }
  if (real) {
    const pool = COINS.filter(c => c.symbol !== "USDC");
    const target = g.rng.choice(pool);
    const value = g.rng.uniform(DRAIN_PAYS[0], DRAIN_PAYS[1]);
    const price = g.market.prices[target.symbol];
    if (g.freeCapacity() < value) {
      out.push(`It was real, and your wallet is full. The ${target.symbol} expires unclaimed, which is its own kind of answer.`);
      return finish();
    }
    const h = g.holding(target.symbol);
    h.qty += value / price; h.cost += value;
    out.push(`It was the real one. ${fmtQty(value / price)} ${target.symbol} (~${money2(value)}) lands while you are still reading the tweet.`);
    return finish();
  }
  const fraction = g.rng.uniform(DRAIN_TAKES[0], DRAIN_TAKES[1]);
  const lost = confiscate(g, fraction);
  if (lost <= 0) {
    out.push("You signed something you should not have. There was nothing in there to take, which is the first time that has been good news.");
    return finish();
  }
  out.push(`You signed it. The approval was unlimited and the wallet on the other end was not the project's. ${money2(lost)} of the bag, gone in one block.`);
  return finish();
}

/* Fees have gone vertical. Pay them, or go round and risk it. */
function gasStandoff(g, choice, was) {
  const out = [];
  const finish = () => { out.forEach(m => g.say(m)); return out; };
  const fee = was.fee || 400;
  if (choice === "paygas") {
    const paid = takeCash(g, fee);
    out.push(`You pay it. ${money2(paid)} to move your own money, and the block still takes four minutes.`);
    return finish();
  }
  const cheap = takeCash(g, fee * RELAY_SHARE);
  if (g.rng.random() < encounterOdds(g, "relay")) {
    out.push(`The relay works. ${money2(cheap)} instead of ${money2(fee)}, and nobody asks where the transaction came from.`);
    return finish();
  }
  const lost = confiscate(g, g.rng.uniform(RELAY_TAKES[0], RELAY_TAKES[1]));
  out.push(`The relay was somebody's honeypot. ${money2(cheap)} in fees and ${money2(lost)} of the bag with it. The forum post is gone too.`);
  return finish();
}

function spoils(g) {
  const roll = g.rng.random();
  if (roll < 0.30) {
    const found = 80 + g.rng.random() * 620;
    g.player.cash += found;
    return [`He leaves $${found.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} on the platform. You are not too proud.`];
  }
  if (roll < 0.44 && !g.weapon) {
    const dropped = g.rng.choice(WEAPONS.filter(w => w.price <= 3200));
    g.weapon = dropped.key;
    return [`He drops what he was holding. ${dropped.name}. It is yours now.`];
  }
  return [];
}

/* Answer the standoff. Clears it either way - there is no third option. */
function resolveStandoff(g, choice) {
  if (!g.pending) throw new Error("nobody is in front of you");
  const kind = KIND_BY_KEY[g.pending.kind] || KINDS[0];
  const valid = encounterChoices(g).map(c => c.key);
  if (!valid.includes(choice)) throw new Error(`you can't do that here; try ${valid.sort().join(", ")}`);
  const wasPending = Object.assign({}, g.pending);   // before it goes
  g.pending = null;
  const w = weaponOf(g.weapon);
  const out = [];
  const finish = () => { out.forEach(m => g.say(m)); return out; };
  const was = wasPending;
  if (kind.key === "collector") return collectorStandoff(g, choice, w);
  if (kind.key === "badge") return badgeStandoff(g, choice);
  if (kind.key === "drain") return drainStandoff(g, choice, was);
  if (kind.key === "gas") return gasStandoff(g, choice, was);

  if (choice === "pay") {
    const paid = takeCash(g, payCost(g));
    bumpRep(g, -1);
    out.push(`You hand it over. $${paid.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}, `
             + `and he counts it in front of you to make the point. Word gets around.`);
    return finish();
  }

  const won = g.rng.random() < encounterOdds(g, choice);

  if (choice === "run") {
    if (won) {
      out.push(g.rng.choice([
        "You go down the platform and through the crowd at the far stairs. Nobody follows you up. Your heart does not get the message for another ten minutes.",
        "You move before he finishes the sentence. Two flights, one turnstile, and a street you do not recognise. Everything you had, you still have.",
        "He is not as interested as he looked. You are three blocks away before you slow down.",
      ]));
      return finish();
    }
    const [cash, bag] = rob(g, kind.severity);
    out.push("You get four steps. The bag is the problem - it always is.");
    out.push(`They take ${lossLine(cash, bag)}`);
    return finish();
  }

  if (won) {
    bumpRep(g, 1);
    if (choice === "weapon" && w) {
      out.push(g.rng.choice([
        `You bring the ${w.name.toLowerCase()} out and the conversation ends. He decides, quickly, that this is not his night.`,
        `One swing. It does not connect and it does not have to - he is already going the other way.`,
      ]));
      if (g.rng.random() < w.breaks) {
        g.weapon = null;
        out.push(`The ${w.name.toLowerCase()} does not survive the night. You leave it where it lands.`);
      }
    } else {
      out.push(g.rng.choice([
        "You swing first, which is the only part of this you get to choose. He goes down the stairs the fast way and does not come back up.",
        "It is short, ugly and entirely unlike the movies. You are still standing at the end of it, and he is not.",
      ]));
    }
    for (const m of spoils(g)) out.push(m);
    return finish();
  }

  bumpRep(g, -1);
  if (choice === "weapon" && w) {
    g.weapon = null;
    out.push(`He takes the ${w.name.toLowerCase()} off you, which is worse than not having had one.`);
  }
  const [cash, bag] = rob(g, kind.severity * 1.25);
  out.push(`It goes badly. They take ${lossLine(cash, bag)}`);
  if (g.rng.random() < HOSPITAL_CHANCE) {
    g.loseADay();
    out.push("You come round on a bench with a day gone and the Shark's clock still running.");
  }
  return finish();
}

/* ----------------------------- events.py ------------------------------ */
function confiscate(game, fraction) {
  let removed = 0;
  for (const h of Object.values(game.player.wallet)) {
    if (h.qty <= 0) continue;
    h.qty -= h.qty * fraction; removed += h.cost * fraction; h.cost -= h.cost * fraction;
  }
  return removed;
}
const hasCoins = g => Object.values(g.player.wallet).some(h => h.qty > 0);
/* Take cash, but never the last fare: stripped to nothing with an empty
   wallet a player cannot buy, sell or travel - a dead end, not a hard spot. */
function takeCash(g, amount) {
  const spendable = Math.max(0, g.player.cash - SUBWAY_FARE);
  const taken = Math.min(amount, spendable);
  g.player.cash -= taken;
  return taken;
}

/* Agents at the turnstile - and now you get to answer them. The seizure is
   untouched, so the balance still holds for anybody who complies; what is new
   is that complying is a choice. */
function secRaid(g) {
  return openStandoff(g, "badge");
}
function secRaidOld(g) {
  if (!hasCoins(g)) {
    g.stats.raids += 1;
    const fine = takeCash(g, 400 + g.rng.random() * 900);
    return [`SEC agents stop you at the turnstile. Nothing to seize, so they write you a $${fine.toFixed(2)} fine instead.`];
  }
  g.stats.raids += 1;
  const f = g.rng.uniform(0.18, 0.42), lost = confiscate(g, f);
  return [`SEC raid on the platform. They seize ${Math.round(f * 100)}% of your wallet - $${lost.toFixed(2)} at cost.`];
}
/* A signature request, which you now get to look at before you sign it. */
function phishing(g) {
  if (!Object.values(g.player.wallet).some(h => h.qty > 0)) {
    return ["A DM offers you a free NFT. You ignore it. Small victories."];
  }
  return openStandoff(g, "drain");
}
function phishingOld(g) {
  if (!hasCoins(g)) return ["A DM offers you a free NFT. You ignore it. Small victories."];
  const lost = confiscate(g, g.rng.uniform(0.08, 0.22));
  return [`You signed something you shouldn't have. A drainer takes $${lost.toFixed(2)} of your bags.`];
}
/* Fees have gone vertical: pay them, or find a way round and risk it. */
function gasSpike(g) {
  return openStandoff(g, "gas");
}
function gasSpikeOld(g) {
  const fee = takeCash(g, 120 + g.rng.random() * 700);
  return [`Network congestion. Gas eats $${fee.toFixed(2)} just to move your own money.`];
}
function airdrop(g) {
  const target = g.rng.choice(COINS.filter(c => c.symbol !== "USDC"));
  const value = 300 + g.rng.random() * 2600;
  if (g.freeCapacity() < value)
    return [`An ${target.symbol} airdrop lands, but your wallet is full. It expires unclaimed.`];
  const qty = value / g.market.prices[target.symbol];
  const h = g.holding(target.symbol);
  h.qty += qty; h.cost += value;
  return [`Airdrop: ${fmtQty(qty)} ${target.symbol} (~$${value.toFixed(2)}) for a wallet you forgot you'd connected.`];
}
function foundWallet(g) {
  const found = 250 + g.rng.random() * 1800;
  g.player.cash += found;
  return [`A seed phrase on the back of a MetroCard. It still had $${found.toFixed(2)} on it.`];
}
/* The Shark's associate, also answerable now. Paying him is the good end -
   what he takes comes off the loan. */
function sharkVisit(g) {
  if (g.player.debt <= 0) {
    return ["A large man studies you on the platform, decides you're nobody, and goes back to his phone."];
  }
  return openStandoff(g, "collector");
}
function sharkVisitOld(g) {
  if (g.player.debt <= 0) return ["A large man studies you on the platform, decides you're nobody, and goes back to his phone."];
  const demand = Math.min(Math.max(0, g.player.cash - SUBWAY_FARE), g.player.debt * 0.25);
  if (demand < 50) return ["The Shark's associate finds you. You have nothing. He is patient. That's worse."];
  g.player.cash -= demand; g.player.debt -= demand;
  return [`The Shark's associate takes $${demand.toFixed(2)} off you on the platform.`];
}
function whaleOffer(g) {
  const held = Object.entries(g.player.wallet).filter(([, h]) => h.qty > 0);
  if (!held.length) return ["A whale wallet DMs you asking what you're holding. Nothing. Awkward."];
  const [sym, h] = g.rng.choice(held);
  const premium = g.rng.uniform(1.25, 1.85);
  const proceeds = h.qty * g.market.prices[sym] * premium;
  g.player.cash += proceeds; h.qty = 0; h.cost = 0; g.dropEmpty();
  return [`A whale takes your entire ${sym} bag at ${Math.round(premium * 100)}% of market - $${proceeds.toFixed(2)}.`];
}
function delayEvent(g) {
  if (g.perk === "metrocard") {
    return ["Signal problems at Chambers St. You know the workaround and reroute without losing the day."];
  }
  g.loseADay();
  return ["Signal problems at Chambers St. You lose a day on a stopped train while your debt keeps compounding."];
}
/* The only event that does not resolve itself: it sets a standoff, the
   standoff blocks everything else, and it rides the save. */
function stickup(g) {
  // a reputation for standing your ground makes the next one pick somebody
  // else; a reputation for paying up is an advertisement
  if (g.rng.random() < repOf(g) * 0.12) {
    return ["Somebody clocks you on the platform, thinks about it, and finds something else to look at."];
  }
  return openStandoff(g, g.rng.random() < 0.45 ? "followed" : "stickup");
}

const quiet = () => [];

const EVENTS = [
  [secRaid, 10, true], [stickup, 5.5, true], [phishing, 8, true], [gasSpike, 9, false], [sharkVisit, 7, false],
  [delayEvent, 5, false], [airdrop, 8, false], [foundWallet, 6, false], [whaleOffer, 6, false],
  [quiet, 34, false],
];

/* ---------------------------- enforcement ---------------------------- */
/* Days the SEC leaves you alone at the start of a run. Losing a third of your
   bags on day three is not a hard position, it is a coin flip that decides the
   run before you have made a decision worth judging. The pressure is not
   removed, it is moved: RAID_RAMP_TO puts it in the back half, where you
   actually have something worth taking. */
const RAID_GRACE = 15;
const RAID_RAMP_TO = 1.8;

function raidPressure(game, day) {
  const d = (day === undefined || day === null) ? game.day : day;
  if (d <= RAID_GRACE) return 0;
  const span = Math.max(1, (game.days || 30) - RAID_GRACE);
  return 1 + (RAID_RAMP_TO - 1) * Math.min(1, (d - RAID_GRACE) / span);
}

/* The weight of every event for an arrival, in EVENTS order. The threat meter
   reads THIS, so a forecast can never disagree with the roll. */
function eventWeights(game, station, day) {
  const stop = station || game.station;
  const heat = Math.min(1, stop.heat * (game.heatMult || 1));
  let shelter = 1.0 - Math.min(0.66, 0.22 * game.player.vpn);
  if (game.perk === "burner") shelter *= 0.66;
  // gear you are currently holding for; the best piece, never the sum
  shelter *= 1 - game.luck;
  const pressure = raidPressure(game, day);
  // what makes a mugger reconsider is exactly what makes an agent look twice
  const armed = 1 + carryHeat(game);
  return EVENTS.map(([fn, w, scales]) => {
    let out = scales ? w * (0.35 + 1.4 * heat) * shelter : w;
    if (fn === secRaid) out *= pressure * armed;
    // the grace period is the SEC's alone; the city never signed it
    if (fn === stickup) out *= Math.max(0.35, 1 - carryHeat(game) * 2);
    return out;
  });
}

/* The exact probability the SEC turns up on one arrival. Never a guess. */
function raidChance(game, station, day) {
  const weights = eventWeights(game, station, day);
  const total = weights.reduce((a, b) => a + b, 0);
  if (total <= 0) return 0;
  return weights[EVENTS.findIndex(e => e[0] === secRaid)] / total;
}

/* Five readings and how many bars each fills. Cut points read off the real
   chance: at Express with no VPN the map spans LOW to HIGH the day the grace
   ends and WATCH to SEVERE by day thirty, and two VPN levels pull it back to
   LOW and WATCH - which is the point of showing any of it. */
const THREAT = [[0.185, "SEVERE", 4], [0.130, "HIGH", 3], [0.085, "WATCH", 2], [0.0, "LOW", 1]];
const THREAT_BARS = 4;
const WIRE_LINES = {
  QUIET: ["Enforcement is still working last quarter's cases. Nobody downtown knows your name.",
          "The regulator's press office is talking about something else entirely.",
          "Nothing on the wire. It will not last, and everybody knows it."],
  LOW: ["A subcommittee asks for documents. Nothing moves fast in Washington.",
        "An enforcement notice goes out to somebody else. You read it twice anyway.",
        "Quiet, but the tone has changed. They are writing things down."],
  WATCH: ["Two agents were seen at {station} this week. They were not commuting.",
          "The {borough} field office has been busy. Ask anyone on the platform.",
          "Somebody at {station} got stopped on Tuesday. Nobody has seen him since."],
  HIGH: ["Word on the platform: the feds are working this line. A day or two, maybe less.",
         "They have a van on the street above {station}. It has not moved since Monday.",
         "Three seizures in {borough} this week. {station} is next, if you believe the wire."],
  SEVERE: ["They are at {station}. The only question left is who they stop.",
           "{station} is crawling. Turnstiles, mezzanine, both platforms.",
           "If you are carrying anything, {station} is the worst place in the city today."],
};

/* The stop's own reputation, in bars, for use while the grace holds: during
   the first fifteen days every stop reads QUIET, which is true and useless. */
function standingHeat(station) {
  return Math.max(0, Math.min(THREAT_BARS, Math.round(station.heat * THREAT_BARS)));
}

function threatLevel(chance) {
  if (chance <= 0) return ["QUIET", 0];
  for (const [floor, label, bars] of THREAT) if (chance >= floor) return [label, bars];
  return ["QUIET", 0];
}

/* The threat reading for a stop, as a news post the page can draw. The line is
   picked by day and station rather than by a die: a headline that re-rolls on
   every redraw reads as noise, and drawing here would move the run's stream. */
function wire(game, station, day) {
  const stop = station || game.station;
  const when = (day === undefined || day === null) ? game.day : day;
  const chance = raidChance(game, stop, day);
  const [label, bars] = threatLevel(chance);
  const lines = WIRE_LINES[label];
  const text = lines[(when + stop.name.length) % lines.length]
    .replace(/\{station\}/g, stop.name).replace(/\{borough\}/g, stop.borough);
  return { label: label, bars: bars, of: THREAT_BARS, chance: chance,
           two_stops: 1 - Math.pow(1 - chance, 2),
           grace_left: Math.max(0, RAID_GRACE - when), text: text };
}

function rollEvent(game) {
  const weights = eventWeights(game);
  return game.rng.choices(EVENTS.map(e => e[0]), weights)(game);
}

/* ------------------------------- gear.py ------------------------------ */
/* Perks are a choice you make before a run. Gear is the opposite: you earn it
   by WINNING while holding something, and it then quietly favours that same
   kind of holding forever after. It rewards having a style, not grinding - a
   win credits only the class you were actually holding at the end.

   Luck is deliberately small (15% at full level, only on coins in the wallet
   right now), never a sum (your best piece, not all of them), and it re-weights
   decisions that already exist rather than adding new rolls. Gear is written
   into the save, so a reloaded run carries the same luck and replays as it
   would have. */
const CLASSES = {
  meme:   ["SHIB", "PEPE", "BONK", "DOGE", "WIF"],
  alt:    ["XRP", "SUI", "SOL"],
  major:  ["AVAX", "ETH", "BTC"],
  stable: ["USDC"],
};
const CLASS_OF = {};
for (const [cls, syms] of Object.entries(CLASSES)) for (const s of syms) CLASS_OF[s] = cls;

const GEAR = [
  { key: "meme",   name: "Platform Rat Charm",
    blurb: "Found on the roadbed at Canal St. The jokes go your way.",
    covers: "SHIB · PEPE · DOGE" },
  { key: "alt",    name: "Brass Subway Token",
    blurb: "Minted before the turnstiles took cards. Older money, better odds.",
    covers: "XRP · SOL" },
  { key: "major",  name: "Cold-Storage Watch",
    blurb: "Heavy, unfashionable, and it has never lost a key.",
    covers: "ETH · BTC" },
  { key: "stable", name: "Laminated MetroCard",
    blurb: "Nothing much happens to somebody holding dollars.",
    covers: "USDC" },
];
const GEAR_BY_KEY = Object.fromEntries(GEAR.map(g => [g.key, g]));
const MAX_LEVEL = 3, WINS_FOR_LEVEL = [1, 3, 7], LUCK_PER_LEVEL = 0.05, WIN_AT = 2000;
/* What a private dealer wants for a piece, in cash, during a run. Absurd on
   purpose: a sink for a run that went enormous, and a REAL decision, because
   the million comes straight off your net worth and therefore off your score.
   You trade this run's place on the board for something you keep. */
const BROKER_PRICE = 1000000;
/* The class a dealer would sell you here, or null if there is no deal. */
function brokerOffer(g) {
  if (!countsForProgress(g)) return null;
  if (!g.station.shop || g.stats.gear_bought) return null;
  if (g.player.cash < BROKER_PRICE) return null;
  return winningClass(g) || "meme";
}

/* Moving a banked win costs two to give one: free respec would make four
   pieces one piece with a dropdown, and a punitive rate means nobody uses it. */
const RETUNE_COST = 2, MAX_NAME = 22;

function displayName(profile, piece) {
  const custom = (profile && profile.gear_names || {})[piece.key];
  return custom ? custom : piece.name;
}
function cleanName(name) { return String(name).split(/\s+/).filter(Boolean).join(" ").slice(0, MAX_NAME); }
function renameGear(profile, key, name) {
  if (!GEAR_BY_KEY[key]) throw new Error(`no such gear ${key}`);
  if (!profile.gear_names) profile.gear_names = {};
  if (levelFor((profile.gear_wins || {})[key] || 0) < 1) {
    throw new Error(`you haven't earned the ${GEAR_BY_KEY[key].name} yet`);
  }
  const cleaned = cleanName(name);
  if (!cleaned) { delete profile.gear_names[key]; return `Back to ${GEAR_BY_KEY[key].name}.`; }
  profile.gear_names[key] = cleaned;
  return `${GEAR_BY_KEY[key].name} is now ${cleaned}.`;
}
/* How gear gets customised rather than merely accumulated: a player whose style
   moved from memecoins to majors carries some of what they earned across. */
function retuneGear(profile, source, target) {
  for (const key of [source, target]) if (!GEAR_BY_KEY[key]) throw new Error(`no such gear ${key}`);
  if (source === target) throw new Error("that is where it already is");
  if (!profile.gear_wins) profile.gear_wins = {};
  if (!profile.gear_names) profile.gear_names = {};
  const have = profile.gear_wins[source] || 0;
  if (have < RETUNE_COST) {
    throw new Error(`${GEAR_BY_KEY[source].name} has ${have} win(s); moving one costs ${RETUNE_COST}`);
  }
  profile.gear_wins[source] = have - RETUNE_COST;
  profile.gear_wins[target] = (profile.gear_wins[target] || 0) + 1;
  if (profile.gear_wins[source] <= 0) {
    delete profile.gear_wins[source];
    delete profile.gear_names[source];        // an unearned piece keeps no name
  }
  return `Moved a win from ${GEAR_BY_KEY[source].name} to ${GEAR_BY_KEY[target].name}. `
       + `It cost ${RETUNE_COST}.`;
}

function levelFor(wins) { return WINS_FOR_LEVEL.filter(n => wins >= n).length; }
function levelsFromWins(wins) {
  const out = {};
  for (const key of Object.keys(CLASSES)) if (wins && wins[key]) out[key] = levelFor(wins[key]);
  return out;
}
function luckOf(levels, cls) {
  return LUCK_PER_LEVEL * Math.min(MAX_LEVEL, (levels && levels[cls]) || 0);
}
/* Gear you own but are not holding for does nothing: the bonus follows the bag. */
function luckBySymbol(levels, wallet) {
  const out = {};
  for (const [sym, h] of Object.entries(wallet || {})) {
    const cls = CLASS_OF[sym];
    if (h.qty > 0 && cls) { const l = luckOf(levels, cls); if (l > 0) out[sym] = l; }
  }
  return out;
}
function bestLuck(levels, wallet) {
  const vals = Object.values(luckBySymbol(levels, wallet));
  return vals.length ? Math.max(...vals) : 0;
}
/* None when they finished holding nothing - gear is earned by HOLDING through
   the finish, so cashing out entirely earns nothing. */
function winningClass(g) {
  const totals = {};
  for (const [sym, h] of Object.entries(g.player.wallet)) {
    if (h.qty <= 0 || !CLASS_OF[sym]) continue;
    totals[CLASS_OF[sym]] = (totals[CLASS_OF[sym]] || 0) + h.qty * g.market.prices[sym];
  }
  const best = Object.entries(totals).sort((a, b) => b[1] - a[1])[0];
  return best ? best[0] : null;
}
/* Returns [piece, levelBefore, levelAfter] or null. */
/* Same bank as a real win, deliberately: two parallel progress tracks for the
   same four pieces would be a UI problem pretending to be a feature. */
function creditWheel(profile, cls) {
  if (!GEAR_BY_KEY[cls]) return null;
  if (!profile.gear_wins) profile.gear_wins = {};
  const before = levelFor(profile.gear_wins[cls] || 0);
  profile.gear_wins[cls] = (profile.gear_wins[cls] || 0) + 1;
  return [GEAR_BY_KEY[cls], before, levelFor(profile.gear_wins[cls])];
}

function creditWin(profile, g) {
  if (!countsForProgress(g) || g.finalScore() <= WIN_AT) return null;
  const cls = winningClass(g);
  if (cls === null) return null;
  if (!profile.gear_wins) profile.gear_wins = {};
  const before = levelFor(profile.gear_wins[cls] || 0);
  profile.gear_wins[cls] = (profile.gear_wins[cls] || 0) + 1;
  return [GEAR_BY_KEY[cls], before, levelFor(profile.gear_wins[cls])];
}

/* ---------------------------- progress.py ----------------------------- */
/* Mirrors cryptowarz/progress.py. A lost run has to leave something behind,
   or the thirtieth loss looks exactly like the first. */
const ACHIEVEMENTS = [
  { key: "first_run",    name: "Off Peak",            blurb: "Finish a run, any run.",
    test: g => true },
  { key: "in_the_black", name: "In the Black",        blurb: "Finish worth more than you started.",
    test: g => g.finalScore() > 2000 },
  { key: "debt_free",    name: "Paid in Full",        blurb: "Clear the Shark completely.",
    test: g => g.player.debt <= 0 },
  { key: "whale",        name: "Whale Watching",      blurb: "Be worth $100,000 at any point.",
    test: g => (g.stats.peak_worth || 0) >= 100000 },
  { key: "tourist",      name: "The Whole Map",       blurb: "Visit every station in one run.",
    test: g => (g.stats.stations || []).length >= STATIONS.length },
  { key: "untouchable",  name: "Untouchable",         blurb: "Thirty days, no SEC raid.",
    test: g => (g.stats.raids || 0) === 0 && g.day > 25 },
  { key: "moonshot",     name: "Moonshot",            blurb: "Triple your money on one trade.",
    test: g => (g.stats.best_multiple || 0) >= 3.0 },
  { key: "degen",        name: "Nothing but Vibes",   blurb: "Finish in profit holding only memecoins.",
    test: g => g.finalScore() > 2000 && !!g.stats.meme_only_finish },
  { key: "six_figures",  name: "Six Figures",         blurb: "Finish above $100,000.",
    test: g => g.finalScore() >= 100000 },
  { key: "legend",       name: "They Named a Station", blurb: "Finish above $500,000.",
    test: g => g.finalScore() >= 500000 },
];

const PERKS = [
  { key: "metrocard",    name: "Unlimited MetroCard", blurb: "Rides are free, and signal delays never cost you a day.", by: "first_run" },
  { key: "seed_round",   name: "Seed Round",          blurb: "Start with $2,000 more.",                                  by: "in_the_black" },
  { key: "burner",       name: "Burner Phone",        blurb: "Trouble finds you a third less often.",                    by: "untouchable" },
  { key: "cold_storage", name: "Cold Storage",        blurb: "+$15,000 wallet capacity.",                                by: "whale" },
  { key: "fixer",        name: "The Fixer",           blurb: "The Shark charges 8.5% a day, not 10%.",                   by: "debt_free" },
  { key: "insider",      name: "Insider",             blurb: "The map shows which coin each station pays most for.",     by: "tourist" },
];

/* Tuned by simulation: starting debt compounds daily while profit scales with
   capacity, so leaning on debt made the top tier unwinnable. Capacity and heat
   carry the ladder instead. */
const TIERS = [
  { level: 1, name: "Off Peak",   blurb: "The standard thirty days.",           debt: 5500,  capacity: 25000, heat: 1.00, days: 30, mult: 1.00 },
  { level: 2, name: "Rush Hour",  blurb: "A bigger loan and more eyes on you.", debt: 6800,  capacity: 21000, heat: 1.25, days: 30, mult: 1.30 },
  { level: 3, name: "Track Work", blurb: "Deeper in, carrying less.",           debt: 7800,  capacity: 17000, heat: 1.50, days: 30, mult: 1.65 },
  { level: 4, name: "Last Train", blurb: "Four fewer days to do it in.",        debt: 7800,  capacity: 15000, heat: 1.60, days: 26, mult: 2.00 },
  { level: 5, name: "Blackout",   blurb: "Everything at once.",                 debt: 9000,  capacity: 13000, heat: 1.80, days: 26, mult: 2.40 },
];
const TIER_BY_LEVEL = Object.fromEntries(TIERS.map(t => [t.level, t]));
/* How hard the city is playing - a second axis, free to choose on any run.
   A tier is progression you unlock; a difficulty is a dial you can turn on
   day one. Both pay the board honestly: the multipliers multiply. */
const DIFFICULTIES = [
  { key: "easy",   name: "Local",      blurb: "Every stop, no hurry. The city is not paying attention.",
    cash: 1500, debtMult: 0.85, shark: 0.075, heatMult: 0.80, mult: 0.70 },
  { key: "normal", name: "Express",    blurb: "The game as it is meant to be played.",
    cash: 0,    debtMult: 1.00, shark: 0.100, heatMult: 1.00, mult: 1.00 },
  { key: "hard",   name: "Third Rail", blurb: "Bigger loan, worse rate, and everybody is looking.",
    cash: 0,    debtMult: 1.25, shark: 0.125, heatMult: 1.30, mult: 1.50 },
];
const DIFFICULTY_BY_KEY = Object.fromEntries(DIFFICULTIES.map(d => [d.key, d]));
const DEFAULT_DIFFICULTY = "normal";
/* Falls back rather than throwing: a save from an older build carries no
   difficulty at all, and a run that refuses to load is worse than Express. */
function difficultyOf(key) {
  return DIFFICULTY_BY_KEY[key || DEFAULT_DIFFICULTY] || DIFFICULTY_BY_KEY[DEFAULT_DIFFICULTY];
}
function difficultyMult(key) { return difficultyOf(key).mult; }
const PERK_BY_KEY = Object.fromEntries(PERKS.map(p => [p.key, p]));
const PROGRESS_KEY = "cryptowarz.progress.v1";
const PROGRESS_VERSION = 3;

/* ---------------------------- grading -------------------------------- */
/* Three ranked runs a day, each a full thirty-day market, each graded on what
   it was finally worth weighted by the tier it was played on. A leaderboard
   needs a fixed slate or it just ranks patience. */
const RUNS_PER_DAY = 3;
const GRADES = [
  [750000, "S+", "They'll name a station after you."],
  [300000, "S",  "Somebody is going to ask questions."],
  [100000, "A",  "Six figures. Quit while you're ahead."],
  [35000,  "B",  "A real score."],
  [10000,  "C",  "Out of the hole and then some."],
  [2000,   "D",  "You finished. Barely."],
  [0,      "F",  "The Shark got paid. You didn't."],
];
/* Shown instead of a letter for a run that is not eligible to be ranked. */
const UNRANKED_GRADE = "G";
/* A run handed money it did not earn may not touch the board, the goals or the
   ladder: posting it would end the leaderboard, and unlocking from it would
   hand somebody the whole progression for nothing. It costs nothing either -
   the ranked slot stays unspent. */
function countsForProgress(g) { return !(g && g.hotHand); }
function runGrade(g) { return countsForProgress(g) ? gradeFor(runPoints(g)) : UNRANKED_GRADE; }
function tierMult(tier) { return (TIER_BY_LEVEL[tier] || TIERS[0]).mult; }
/* Floored at zero: a board that can be dragged down is one where the safe play
   is not to play. */
function difficultyMultOf(g) { return difficultyMult(g.difficulty || DEFAULT_DIFFICULTY); }
function runPoints(g) {
  return Math.max(0, g.finalScore()) * tierMult(g.tier || 1) * difficultyMultOf(g);
}
function gradeFor(points) { return (GRADES.find(r => points >= r[0]) || GRADES[GRADES.length - 1])[1]; }
function gradeBlurb(points) { return (GRADES.find(r => points >= r[0]) || GRADES[GRADES.length - 1])[2]; }
/* Per slot, so run two is a new market rather than run one replayed with the
   answers; per date, so everyone plays the same three today. */
function dailySeeds(when) {
  const day = dailySeed(when);
  return [0, 1, 2].map(slot => day * 10 + slot);
}

function blankProfile() {
  return { version: PROGRESS_VERSION, runs: 0, achievements: [], best_net: 0,
           best_tier_cleared: 0, daily_day: null, daily_runs: [],
           best_daily: 0, best_daily_day: null, gear_wins: {}, gear_names: {},
           updated_at: 0 };
}
function readProfile() {
  try {
    const raw = JSON.parse(localStorage.getItem(PROGRESS_KEY) || "null");
    // a version 1 profile predates ranked runs; its achievements were still
    // earned, so it migrates rather than being thrown away
    if (!raw || ![1, 2, PROGRESS_VERSION].includes(raw.version)) return blankProfile();
    const known = new Set(ACHIEVEMENTS.map(a => a.key));
    raw.achievements = (raw.achievements || []).filter(k => known.has(k));
    if (!Array.isArray(raw.daily_runs)) raw.daily_runs = [];
    if (!raw.gear_wins || typeof raw.gear_wins !== "object") raw.gear_wins = {};
    if (!raw.gear_names || typeof raw.gear_names !== "object") raw.gear_names = {};
    delete raw.daily_seed; delete raw.daily_net;
    return Object.assign(blankProfile(), raw, { version: PROGRESS_VERSION });
  } catch (e) { return blankProfile(); }   // a profile is a reward, never a blocker
}
/* Point the profile at today's slate, clearing yesterday's. Nothing is lost by
   missing a day - the old slate simply is not today's any more. */
function rollDay(p, day) {
  day = day === undefined ? dailySeed() : day;
  if (p.daily_day !== day) { p.daily_day = day; p.daily_runs = []; }
  return day;
}
function runsToday(p, day) {
  day = day === undefined ? dailySeed() : day;
  return p.daily_day === day ? p.daily_runs.slice() : [];
}
function nextSlot(p, day) {
  const done = new Set(runsToday(p, day).map(r => r.slot));
  for (let i = 0; i < RUNS_PER_DAY; i++) if (!done.has(i)) return i;
  return null;
}
function dailyTotal(p, day) {
  return runsToday(p, day).reduce((a, r) => a + (r.points || 0), 0);
}
/* Re-recording a slot is ignored rather than overwriting: three ranked runs
   only means something if each market is played once. */
function recordDaily(p, g, slot, day) {
  day = rollDay(p, day);
  if (!countsForProgress(g)) {          // the slot is not spent either
    return { slot: slot, points: 0, net: Math.round(g.finalScore() * 100) / 100,
             grade: UNRANKED_GRADE, tier: g.tier || 1, at: Date.now() / 1000 };
  }
  const points = runPoints(g);
  const entry = { slot: slot, points: Math.round(points * 100) / 100,
                  net: Math.round(g.finalScore() * 100) / 100,
                  grade: gradeFor(points), tier: g.tier || 1, at: Date.now() / 1000 };
  if (p.daily_runs.some(r => r.slot === slot)) return entry;
  p.daily_runs.push(entry);
  p.daily_runs.sort((a, b) => a.slot - b.slot);
  const total = dailyTotal(p, day);
  if (total > p.best_daily) { p.best_daily = total; p.best_daily_day = day; }
  return entry;
}
function writeProfile(p) {
  p.updated_at = Date.now() / 1000;
  try { localStorage.setItem(PROGRESS_KEY, JSON.stringify(p)); } catch (e) {}
  return p;
}
function unlockedPerks(p) {
  const earned = new Set(p.achievements);
  return PERKS.filter(x => earned.has(x.by));
}
function maxTier(p) { return Math.max(1, Math.min(TIERS.length, (p.best_tier_cleared || 0) + 1)); }

/* Today's date as YYYYMMDD - the key the ranked slate hangs on. Not a streak:
   miss a day and nothing is taken away, there is simply a new slate waiting. */
function dailySeed(when) {
  const d = new Date(when === undefined ? Date.now() : when);
  return Number(`${d.getUTCFullYear()}${String(d.getUTCMonth() + 1).padStart(2, "0")}${String(d.getUTCDate()).padStart(2, "0")}`);
}

function award(profile, g) {
  if (!countsForProgress(g)) return [];
  const earned = [];
  for (const a of ACHIEVEMENTS) {
    if (profile.achievements.includes(a.key)) continue;
    let hit = false;
    try { hit = !!a.test(g); } catch (e) { hit = false; }
    if (hit) { profile.achievements.push(a.key); earned.push(a); }
  }
  profile.runs += 1;
  profile.best_net = Math.max(profile.best_net, g.finalScore());
  if (g.finalScore() > 2000 && g.tier > profile.best_tier_cleared) profile.best_tier_cleared = g.tier;
  return earned;
}

/* ------------------------------ save.js ------------------------------- */
/* Mirrors cryptowarz/save.py, including the decision that matters: the RNG
   state is saved, so reloading replays the same dice. A game of raids and rug
   pulls where a reload rerolls is a game where the risk is optional.

   localStorage is per-browser and can throw (private mode, blocked site data),
   so every read and write is guarded and the game plays fine without it. */
const SAVE_VERSION = 1;
/* -------------------------- taking it with you -----------------------
   The save and the profile live in whatever browser you happened to play in.
   That is fine until a new phone, a cleared cache or a page saved to disk -
   and the gear you spent twenty runs earning is simply gone. So the game hands
   you the bytes: one line of text that both front ends read and write, so a
   run started here can be finished in the terminal and the other way round.

   Text rather than a file, because a download is blocked or awkward in half
   the places this game runs. With a checksum, because a half-copied paste that
   silently loaded would overwrite a good profile with a broken one - the exact
   failure a backup exists to prevent. Not a cheat guard: it is base64, not a
   lock, and the leaderboard is protected where it always was. */
const BACKUP_VERSION = 1, BACKUP_PREFIX = "CW1";

/* Whether this browser will actually keep anything.
   Every write in this file is already wrapped in try/catch, which keeps a
   blocked store from ending the run - and means a player in iOS Private
   Browsing, where setItem throws, plays thirty days and loses all of it
   without ever being told. So it is asked once, out loud, and the page says
   so. A probe rather than a feature test, because Safari HAS localStorage in
   private mode; it just refuses to write to it. */
function storageWorks() {
  try {
    const probe = "cryptowarz.probe";
    localStorage.setItem(probe, "1");
    const back = localStorage.getItem(probe) === "1";
    localStorage.removeItem(probe);
    return back;
  } catch (e) { return false; }
}

/* 32-bit FNV-1a: four lines in every language, so the two ports cannot drift
   on it. It catches truncation and transcription, which is all it is for. */
function fnv1a(text) {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i) & 0xff;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}
function backupEncode(payload) {
  const raw = JSON.stringify(payload);
  const bytes = new TextEncoder().encode(raw);
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  const body = btoa(bin);
  return `${BACKUP_PREFIX}.${fnv1a(body).toString(16).padStart(8, "0")}.${body}`;
}
function backupDecode(text) {
  const parts = String(text).replace(/\s+/g, "").split(".");
  if (parts.length !== 3 || parts[0] !== BACKUP_PREFIX) {
    throw new Error("that doesn't look like a CryptoWarz backup line");
  }
  const [, checksum, body] = parts;
  if (fnv1a(body).toString(16).padStart(8, "0") !== checksum.toLowerCase()) {
    throw new Error("that backup is damaged or was only half copied - copy the whole "
                    + "line, including the CW1 at the front");
  }
  let payload;
  try {
    const bin = atob(body);
    const bytes = Uint8Array.from(bin, ch => ch.charCodeAt(0));
    payload = JSON.parse(new TextDecoder().decode(bytes));
  } catch (e) { throw new Error(`that backup could not be read (${e.message})`); }
  if (!payload || typeof payload !== "object") throw new Error("that backup is not a backup");
  return payload;
}
/* A backup line for a profile, optionally with a run in progress. */
function makeBackup(profile, save, scores) {
  const payload = { v: BACKUP_VERSION, profile: profile };
  if (save) payload.save = save;
  if (scores && scores.length) payload.scores = scores;
  return backupEncode(payload);
}
/* {profile, save, scores} from a line. The profile goes through the same
   reader a stored one does, so an older backup migrates identically. */
function readBackup(text) {
  const payload = backupDecode(text);
  const version = payload.v | 0;
  if (version > BACKUP_VERSION) {
    throw new Error(`that backup was written by a newer build (version ${version}; `
                    + `this one reads ${BACKUP_VERSION})`);
  }
  let profile = null;
  if (payload.profile) {
    const known = new Set(ACHIEVEMENTS.map(a => a.key));
    const raw = Object.assign({}, payload.profile);
    raw.achievements = (raw.achievements || []).filter(k => known.has(k));
    if (!Array.isArray(raw.daily_runs)) raw.daily_runs = [];
    if (!raw.gear_wins || typeof raw.gear_wins !== "object") raw.gear_wins = {};
    if (!raw.gear_names || typeof raw.gear_names !== "object") raw.gear_names = {};
    profile = Object.assign(blankProfile(), raw, { version: PROGRESS_VERSION });
  }
  return { profile: profile, save: payload.save || null, scores: payload.scores || null };
}

const SAVE_KEY = "cryptowarz.save.v1";
const SCORE_KEY = "cryptowarz.scores.v1";
const MAX_SCORES = 25;

function saveToDict(g) {
  const wallet = {};
  for (const [sym, h] of Object.entries(g.player.wallet)) {
    if (h.qty > 0 || h.cost > 0) wallet[sym] = { qty: h.qty, cost: h.cost };
  }
  return {
    save_version: SAVE_VERSION,
    saved_at: Date.now() / 1000,
    seed: g.seed,
    tier: g.tier,
    /* added after version 1 shipped and read with a default, so a save from an
       older build still loads - it simply resumes on Express */
    difficulty: g.difficulty || DEFAULT_DIFFICULTY,
    perk: g.perk,
    /* the gear the run started with, so a reload keeps the same luck */
    gear: Object.assign({}, g.gear || {}),
    /* which ranked run of today this is, or null for practice. Added after
       version 1 shipped and read with a default, so an in-progress save from
       the older build still loads - it simply resumes as practice. */
    daily_slot: g.dailySlot === undefined ? null : g.dailySlot,
    /* what you are carrying, and anybody waiting for an answer. The standoff
       rides the save on purpose: without it a reload walks away from a man
       with a knife. Both read with a default, so an older save still loads. */
    weapon: g.weapon || null,
    pending: g.pending || null,
    stats: g.stats,
    day: g.day,
    finished: g.finished,
    station: g.station.name,
    player: { cash: g.player.cash, debt: g.player.debt, vault: g.player.vault,
              capacity: g.player.capacity, vpn: g.player.vpn, wallet },
    levels: Object.assign({}, g.state.levels),
    /* the run each coin is on. Without it a reloaded game keeps the prices and
       forgets which way everything was going - a different market wearing the
       same numbers. */
    trends: Object.assign({}, g.state.trends || {}),
    /* the chart the player has been reading. Dropping it on reload would blank
       every sparkline mid-run, which looks exactly like a bug. */
    history: Object.fromEntries(Object.entries(g.state.history || {})
      .map(([sym, vals]) => [sym, vals.slice()])),
    market: {
      prices: Object.assign({}, g.market.prices),
      shock: g.market.shock ? { symbol: g.market.shock.symbol,
                                headline: g.market.shock.headline,
                                factor: g.market.shock.factor } : null,
    },
    rng: g.rng.getState(),
    log: g.log.slice(-40),
  };
}

function saveFromDict(data) {
  if (!data || data.save_version !== SAVE_VERSION) {
    throw new Error("that save is from a different version of the game");
  }
  const g = new Game(data.seed === undefined ? 0 : data.seed, data.tier || 1,
                     data.perk || null, data.gear || {},
                     data.difficulty || DEFAULT_DIFFICULTY);
  g.rng.setState(data.rng);
  g.dailySlot = (data.daily_slot === undefined || data.daily_slot === null) ? null : data.daily_slot;
  g.isDaily = g.dailySlot !== null;
  if (data.stats) g.stats = data.stats;
  // carried in stats, so it reloads with the run and a reload cannot shake it
  g.hotHand = !!(g.stats && g.stats.hot_hand);
  g.weapon = data.weapon || null;
  g.pending = (data.pending && typeof data.pending === "object") ? Object.assign({}, data.pending) : null;
  g.day = data.day;
  g.finished = !!data.finished;
  /* a save written past the last day is a finished run whatever it says: the
     bug that produced one is fixed, and the runs it already produced must
     still be able to close and be scored rather than load into limbo */
  if (g.day > g.days) g.finished = true;
  g.station = STATIONS.find(s => s.name === data.station) || STATIONS[9];
  g.log = (data.log || []).slice();
  const p = data.player;
  g.player = { cash: p.cash, debt: p.debt, vault: p.vault, capacity: p.capacity,
               vpn: p.vpn || 0, wallet: {} };
  for (const [sym, h] of Object.entries(p.wallet || {})) {
    if (COIN[sym]) g.player.wallet[sym] = { qty: h.qty, cost: h.cost };
  }
  for (const c of COINS) {
    if (data.levels[c.symbol] === undefined) throw new Error("that save predates " + c.symbol);
  }
  g.state.levels = Object.assign({}, data.levels);
  const savedHistory = data.history || {};
  g.state.history = {};
  for (const c of COINS) {
    const past = (savedHistory[c.symbol] || []).map(Number).filter(v => v > 0);
    g.state.history[c.symbol] = past.length ? past : [g.state.levels[c.symbol]];
  }
  const savedTrends = data.trends || {};
  g.state.trends = {};
  for (const c of COINS) g.state.trends[c.symbol] = Number(savedTrends[c.symbol]) || 0;
  g.market = { station: g.station, prices: Object.assign({}, data.market.prices),
               shock: data.market.shock ? Object.assign({ crash: data.market.shock.factor < 1 },
                                                        data.market.shock) : null,
               headline: data.market.shock ? data.market.shock.headline : null };
  return g;
}

function writeSave(g) {
  try { localStorage.setItem(SAVE_KEY, JSON.stringify(saveToDict(g))); return true; }
  catch (e) { return false; }
}
/* When this browser's copy was written, or 0. Read from the raw record
   rather than the rebuilt Game, which does not carry the timestamp - the
   cloud restore needs to know which copy is newer. */
function savedAt() {
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (!raw) return 0;
    const data = JSON.parse(raw);
    return (data && !data.finished && data.saved_at) ? data.saved_at : 0;
  } catch (e) { return 0; }
}
function readSave() {
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (!raw) return null;
    return saveFromDict(JSON.parse(raw));
  } catch (e) { clearSave(); return null; }
}
function clearSave() { try { localStorage.removeItem(SAVE_KEY); } catch (e) {} }

function readScores() {
  try {
    const raw = JSON.parse(localStorage.getItem(SCORE_KEY) || "[]");
    if (!Array.isArray(raw)) return [];
    return raw.filter(r => r && typeof r.net_worth === "number")
              .sort((a, b) => b.net_worth - a.net_worth);
  } catch (e) { return []; }
}
/* Used by a restore: the board a backup carried, put back as it came. */
function writeScores(scores) {
  const kept = (Array.isArray(scores) ? scores : [])
    .filter(r => r && typeof r.net_worth === "number")
    .sort((a, b) => b.net_worth - a.net_worth)
    .slice(0, MAX_SCORES);
  try { localStorage.setItem(SCORE_KEY, JSON.stringify(kept)); } catch (e) {}
  return kept;
}
function recordScore(g) {
  const scores = readScores();
  if (!countsForProgress(g)) return scores;   // an ineligible run is not a result
  scores.push({ net_worth: g.finalScore(), day: Math.min(g.day, DAYS),
                verdict: g.verdict(), finished_at: Date.now() / 1000, seed: g.seed });
  scores.sort((a, b) => b.net_worth - a.net_worth);
  const kept = scores.slice(0, MAX_SCORES);
  try { localStorage.setItem(SCORE_KEY, JSON.stringify(kept)); } catch (e) {}
  return kept;
}

/* ------------------------------ helpers ------------------------------- */
function fmtQty(q) {
  if (q >= 1000) return q.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (q >= 1) return q.toLocaleString(undefined, { maximumFractionDigits: 3 });
  return q.toFixed(6);
}
function fmtPrice(v) {
  if (v >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (v >= 1) return v.toFixed(2);
  if (v >= 0.001) return v.toFixed(4);
  return v.toFixed(8);
}
function fmtMoney(v) {
  const s = Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (v < 0 ? "-$" : "$") + s;
}

if (typeof module !== "undefined") {
  module.exports = { Game, STATIONS, COINS, COIN, RNG, MarketState, generate, DAYS, SUBWAY_FARE,
                     fmtQty, fmtPrice, fmtMoney, saveToDict, saveFromDict, SAVE_VERSION,
                     savedAt, BACKUP_VERSION, BACKUP_PREFIX, fnv1a, backupEncode, backupDecode,
                     makeBackup, readBackup, writeScores, storageWorks,
                     ACHIEVEMENTS, PERKS, TIERS, award, blankProfile, dailySeed,
                     unlockedPerks, maxTier, RUNS_PER_DAY, GRADES, tierMult,
                     DIFFICULTIES, DIFFICULTY_BY_KEY, DEFAULT_DIFFICULTY,
                     difficultyOf, difficultyMult,
                     WEAPONS, WEAPON_BY_KEY, FOR_SALE, weaponOf, carryHeat,
                     REP_MAX, REP_ODDS, repOf, bumpRep, MAX_LOAD_PENALTY,
                     RUN_BASE, FIGHT_BASE, loadPenalty, encounterOdds, KINDS,
                     KIND_BY_KEY, openStandoff, encounterChoices, resolveStandoff,
                     payCost, stickup, bestChoice, TAKE_CASH, lawyerCost,
                     collectorDemand, LAWYER_SHARE, LAWYER_MIN, LAWYER_SAVES,
                     DRAIN_REAL, DRAIN_PAYS, DRAIN_TAKES, CHECK_SHARE, CHECK_MIN,
                     RELAY_SHARE, RELAY_BASE, RELAY_TAKES, checkCost, gasFee, nerveOf,
                     SHARK_FEE_RAN, SHARK_FEE_FOUGHT, CAUGHT_MULTIPLIER, TAKE_BAG, HOSPITAL_CHANCE,
                     RAID_GRACE, RAID_RAMP_TO, raidPressure, eventWeights, raidChance,
                     THREAT, THREAT_BARS, WIRE_LINES, threatLevel, standingHeat, wire, EVENTS,
                     runPoints, gradeFor, gradeBlurb, dailySeeds, rollDay,
                     runsToday, nextSlot, dailyTotal, recordDaily,
                     PROGRESS_VERSION, CLASSES, CLASS_OF, GEAR, GEAR_BY_KEY, MAX_LEVEL,
                     WINS_FOR_LEVEL, LUCK_PER_LEVEL, WIN_AT, levelFor, levelsFromWins,
                     luckOf, luckBySymbol, bestLuck, winningClass, creditWin,
                     stationMarkup, BIAS_COMPRESSION, TREND_FLIP, TREND_STRENGTH,
                     HISTORY_KEPT, SPARK_DAYS,
                     TIP_CHANCE, TIP_ACCURACY, TIP_MIN_RUN, TIP_FRESH_FOR,
                     RETUNE_COST, MAX_NAME, displayName, cleanName, renameGear, retuneGear,
                     creditWheel, WHEEL, WHEEL_LINES,
                     BROKER_PRICE, brokerOffer,
                     DICE_EVERY, DICE_SIDES, DICE_TOP_PRIZE, DICE_LADDER, diceTier,
                     HOT_HAND, HOT_HAND_CHANCE, HOT_HAND_MIN,
                     HOT_HAND_MAX, UNRANKED_GRADE,
                     countsForProgress, runGrade };
}
