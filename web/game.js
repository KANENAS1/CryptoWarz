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
MarketState.prototype.apply = function (symbol, factor, c) {
  const level = this.levels[symbol] * factor;
  this.levels[symbol] = Math.max(c.low * 0.15, Math.min(level, c.high * 2.2));
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


function Game(seed, tier, perk, gear) {
  // kept so a save records which run this was - the RNG state is what restores
  // the dice, but the seed is what lets you tell someone else to try it
  this.seed = (seed === undefined || seed === null) ? (Math.random() * 1e9) | 0 : seed;
  this.tier = tier || 1;
  this.perk = perk || null;
  this.gear = gear || {};                  // {coin class: level}; see gear.py
  const t = TIER_BY_LEVEL[this.tier] || TIER_BY_LEVEL[1];
  this.days = t.days;
  this.heatMult = t.heat;
  this.rng = new RNG(this.seed);
  this.day = 1;
  this.finished = false;
  this.station = STATIONS[9];              // 14 St-Union Sq
  this.player = { cash: START_CASH, debt: t.debt, vault: 0,
                  capacity: t.capacity, vpn: 0, wallet: {} };
  if (this.perk === "seed_round") this.player.cash += 2000;
  if (this.perk === "cold_storage") this.player.capacity += 15000;
  this.stats = { stations: [this.station.name], raids: 0, peak_worth: 0,
                 best_multiple: 0, worth_by_day: [],
                 dice_picks: [], dice_days: [], hot_hand: false };
  this.hotHand = false;
  this.wheelAward = null;                  // a gear class for the caller to bank
  this.log = [];
  this.state = new MarketState(this.rng);
  this.market = generate(this.station, this.rng, this.state, undefined, this.luckBySymbol());
  this.markStats();
  this.say(`Day 1. You're at ${this.station.name} with $${Math.round(this.player.cash).toLocaleString()} and a $${Math.round(this.player.debt).toLocaleString()} problem.`);
  if (this.market.headline) this.say(this.market.headline);
}
Game.prototype.markStats = function () {
  const worth = this.netWorth();
  this.stats.peak_worth = Math.max(this.stats.peak_worth, worth);
  this.stats.worth_by_day.push(Math.round(worth * 100) / 100);
};
Object.defineProperty(Game.prototype, "fare", {
  get() { return this.perk === "metrocard" ? 0 : SUBWAY_FARE; } });
Object.defineProperty(Game.prototype, "sharkRate", {
  get() { return this.perk === "fixer" ? 0.085 : SHARK_RATE; } });
/* The best gear bonus you are holding for right now, 0 to 0.15. */
Object.defineProperty(Game.prototype, "luck", {
  get() { return bestLuck(this.gear, this.player.wallet); } });
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

/* ------------------------------ the wheel ---------------------------- */
Object.defineProperty(Game.prototype, "wheelReady", {
  get() {
    return !!this.station.wheel && !(this.stats.wheels || []).includes(this.station.name);
  } });
/* Sets wheelAward to a gear class on the rare wedge; the caller banks it,
   because the Game does not own the profile. */
Game.prototype.spinWheel = function () {
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
  if (!this.station.shark) throw new Error("The Shark doesn't work this station");
  if (!(amount > 0)) throw new Error("borrow how much?");
  if (this.player.debt + amount > this.borrowLimit())
    throw new Error(`The Shark looks you up and down. Not a chance over $${this.borrowable().toFixed(0)}`);
  this.player.debt += amount; this.player.cash += amount;
  return { text: `Borrowed $${amount.toFixed(2)}. The Shark smiles. That's never good.`, good: false };
};
Game.prototype.repay = function (amount) {
  if (!this.station.shark) throw new Error("The Shark doesn't work this station");
  amount = Math.min(amount, this.player.debt, this.player.cash);
  if (!(amount > 0)) throw new Error("nothing to repay, or nothing to repay it with");
  this.player.debt -= amount; this.player.cash -= amount;
  return { text: `Repaid $${amount.toFixed(2)}.${this.player.debt <= 0 ? " Debt cleared. You can breathe." : ""}`, good: true };
};
Game.prototype.deposit = function (amount) {
  if (!this.station.vault) throw new Error("no vault at this station");
  amount = Math.min(amount, this.player.cash);
  if (!(amount > 0)) throw new Error("deposit how much?");
  this.player.cash -= amount; this.player.vault += amount;
  return { text: `Deposited $${amount.toFixed(2)}. It earns 4% a day in there.`, good: true };
};
Game.prototype.withdraw = function (amount) {
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
  if (!this.station.shop) throw new Error("nowhere to buy hardware here");
  const price = this.upgradeCost();
  if (this.player.cash < price) throw new Error(`a bigger cold wallet costs $${price.toFixed(2)}`);
  this.player.cash -= price; this.player.capacity += 25000;
  return { text: `New cold wallet. Capacity now $${this.player.capacity.toLocaleString()}.`, good: true };
};
Game.prototype.buyVpn = function () {
  if (!this.station.shop) throw new Error("nowhere to buy hardware here");
  if (this.player.vpn >= 3) throw new Error("you are already as invisible as this gets");
  const price = this.vpnCost();
  if (this.player.cash < price) throw new Error(`that VPN costs $${price.toFixed(2)}`);
  this.player.cash -= price; this.player.vpn += 1;
  return { text: `VPN level ${this.player.vpn}. You draw less attention now.`, good: true };
};
Game.prototype.travel = function (index) {
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

function secRaid(g) {
  if (!hasCoins(g)) {
    g.stats.raids += 1;
    const fine = takeCash(g, 400 + g.rng.random() * 900);
    return [`SEC agents stop you at the turnstile. Nothing to seize, so they write you a $${fine.toFixed(2)} fine instead.`];
  }
  g.stats.raids += 1;
  const f = g.rng.uniform(0.18, 0.42), lost = confiscate(g, f);
  return [`SEC raid on the platform. They seize ${Math.round(f * 100)}% of your wallet - $${lost.toFixed(2)} at cost.`];
}
function phishing(g) {
  if (!hasCoins(g)) return ["A DM offers you a free NFT. You ignore it. Small victories."];
  const lost = confiscate(g, g.rng.uniform(0.08, 0.22));
  return [`You signed something you shouldn't have. A drainer takes $${lost.toFixed(2)} of your bags.`];
}
function gasSpike(g) {
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
function sharkVisit(g) {
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
  g.day += 1; g.player.debt *= (1 + g.sharkRate);
  return ["Signal problems at Chambers St. You lose a day on a stopped train while your debt keeps compounding."];
}
const quiet = () => [];

const EVENTS = [
  [secRaid, 10, true], [phishing, 8, true], [gasSpike, 9, false], [sharkVisit, 7, false],
  [delayEvent, 5, false], [airdrop, 8, false], [foundWallet, 6, false], [whaleOffer, 6, false],
  [quiet, 34, false],
];
function rollEvent(game) {
  const heat = Math.min(1, game.station.heat * (game.heatMult || 1));
  let shelter = 1.0 - Math.min(0.66, 0.22 * game.player.vpn);
  if (game.perk === "burner") shelter *= 0.66;
  // gear you are currently holding for; the best piece, never the sum
  shelter *= 1 - game.luck;
  const weights = EVENTS.map(([, w, scales]) => (scales ? w * (0.35 + 1.4 * heat) * shelter : w));
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
function runPoints(g) { return Math.max(0, g.finalScore()) * tierMult(g.tier || 1); }
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
    perk: g.perk,
    /* the gear the run started with, so a reload keeps the same luck */
    gear: Object.assign({}, g.gear || {}),
    /* which ranked run of today this is, or null for practice. Added after
       version 1 shipped and read with a default, so an in-progress save from
       the older build still loads - it simply resumes as practice. */
    daily_slot: g.dailySlot === undefined ? null : g.dailySlot,
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
                     data.perk || null, data.gear || {});
  g.rng.setState(data.rng);
  g.dailySlot = (data.daily_slot === undefined || data.daily_slot === null) ? null : data.daily_slot;
  g.isDaily = g.dailySlot !== null;
  if (data.stats) g.stats = data.stats;
  // carried in stats, so it reloads with the run and a reload cannot shake it
  g.hotHand = !!(g.stats && g.stats.hot_hand);
  g.day = data.day;
  g.finished = !!data.finished;
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
                     ACHIEVEMENTS, PERKS, TIERS, award, blankProfile, dailySeed,
                     unlockedPerks, maxTier, RUNS_PER_DAY, GRADES, tierMult,
                     runPoints, gradeFor, gradeBlurb, dailySeeds, rollDay,
                     runsToday, nextSlot, dailyTotal, recordDaily,
                     PROGRESS_VERSION, CLASSES, CLASS_OF, GEAR, GEAR_BY_KEY, MAX_LEVEL,
                     WINS_FOR_LEVEL, LUCK_PER_LEVEL, WIN_AT, levelFor, levelsFromWins,
                     luckOf, luckBySymbol, bestLuck, winningClass, creditWin,
                     stationMarkup, BIAS_COMPRESSION, TREND_FLIP, TREND_STRENGTH,
                     HISTORY_KEPT, SPARK_DAYS,
                     TIP_CHANCE, TIP_ACCURACY, TIP_MIN_RUN, TIP_FRESH_FOR,
                     RETUNE_COST, MAX_NAME, displayName, cleanName, renameGear, retuneGear,
                     credit_wheel: creditWheel, WHEEL, WHEEL_LINES,
                     DICE_EVERY, DICE_SIDES, DICE_TOP_PRIZE, DICE_LADDER, diceTier,
                     HOT_HAND, HOT_HAND_CHANCE, HOT_HAND_MIN,
                     HOT_HAND_MAX, UNRANKED_GRADE,
                     countsForProgress, runGrade };
}
