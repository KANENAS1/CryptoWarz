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
const COINS = [
  { symbol: "SHIB", name: "Shiba Inu", low: 0.000008, high: 0.000075, meme: true,  note: "fractions of a cent, whole lot of hope" },
  { symbol: "PEPE", name: "Pepe",      low: 0.000002, high: 0.000031, meme: true,  note: "pure vibes, no roadmap" },
  { symbol: "DOGE", name: "Dogecoin",  low: 0.06,     high: 0.71,     meme: true,  note: "started as a joke, still is" },
  { symbol: "XRP",  name: "Ripple",    low: 0.38,     high: 3.40,     meme: false, note: "perpetually in court" },
  { symbol: "USDC", name: "USD Coin",  low: 0.97,     high: 1.03,     meme: false, note: "a dollar, mostly - park cash here when it gets hot" },
  { symbol: "SOL",  name: "Solana",    low: 18.0,     high: 260.0,    meme: false, note: "fast chain, frequent outages" },
  { symbol: "ETH",  name: "Ethereum",  low: 1100.0,   high: 4900.0,   meme: false, note: "gas fees will eat you alive" },
  { symbol: "BTC",  name: "Bitcoin",   low: 21000.0,  high: 109000.0, meme: false, note: "the original, and the heaviest to carry" },
];
COINS.forEach(c => { c.mid = (c.low + c.high) / 2; });
const COIN = Object.fromEntries(COINS.map(c => [c.symbol, c]));

/* ---------------------------- stations.py ----------------------------- */
const STATIONS = [
  { name: "Wall Street", lines: ["4", "5"], borough: "Manhattan",
    flavor: "Suits everywhere. Someone is explaining an ETF to a tourist.",
    bias: { BTC: 1.30, ETH: 1.22, USDC: 1.02, DOGE: 0.62, SHIB: 0.55, PEPE: 0.50 },
    heat: 0.85, vault: true },
  { name: "Jefferson St", lines: ["L"], borough: "Brooklyn",
    flavor: "Bushwick. Three people in this car are launching a token this week.",
    bias: { PEPE: 1.75, SHIB: 1.62, DOGE: 1.45, SOL: 1.14, BTC: 0.80 },
    heat: 0.55, shop: true },
  { name: "Times Sq-42 St", lines: ["N", "Q", "R", "W", "1", "2", "3", "7"], borough: "Manhattan",
    flavor: "Tourist money. Everything here costs more and everyone knows it.",
    bias: { BTC: 1.18, ETH: 1.15, SOL: 1.20, DOGE: 1.25, XRP: 1.15 }, heat: 0.80 },
  { name: "Coney Island-Stillwell Av", lines: ["D", "F", "N", "Q"], borough: "Brooklyn",
    flavor: "End of the line. Salt air, dead arcade, suspiciously cheap everything.",
    bias: { SHIB: 0.45, PEPE: 0.42, DOGE: 0.58, XRP: 0.70, SOL: 0.82 }, heat: 0.30 },
  { name: "125 St", lines: ["4", "5", "6"], borough: "Manhattan",
    flavor: "Harlem. A man with a folding table will sell you anything.",
    bias: { DOGE: 1.30, XRP: 1.34, SHIB: 1.20, ETH: 0.88 }, heat: 0.60, shark: true },
  { name: "Grand Central-42 St", lines: ["4", "5", "6", "7", "S"], borough: "Manhattan",
    flavor: "Commuters moving with purpose. Liquidity, but no bargains.",
    bias: { BTC: 1.08, ETH: 1.10, USDC: 1.01, SOL: 1.05 }, heat: 0.70, vault: true },
  { name: "Flushing-Main St", lines: ["7"], borough: "Queens",
    flavor: "The busiest station outside Manhattan. Cash moves fast here.",
    bias: { XRP: 0.62, USDC: 0.98, SOL: 0.86, ETH: 0.92 }, heat: 0.45 },
  { name: "161 St-Yankee Stadium", lines: ["4", "B", "D"], borough: "Bronx",
    flavor: "Game day. Everyone is up, everyone is buying, nobody is reading.",
    bias: { DOGE: 1.52, SHIB: 1.40, PEPE: 1.38, BTC: 0.92 }, heat: 0.65, shark: true },
  { name: "St George", lines: ["SIR"], borough: "Staten Island",
    flavor: "Off the ferry. Quiet, cheap, and a long way from anywhere.",
    bias: { BTC: 0.78, ETH: 0.80, SOL: 0.74, USDC: 0.99 }, heat: 0.20, shop: true },
  { name: "14 St-Union Sq", lines: ["4", "5", "6", "L", "N", "Q", "R", "W"], borough: "Manhattan",
    flavor: "Everything connects here. Fair prices, which is its own kind of trap.",
    bias: {}, heat: 0.50, vault: true, shop: true },
];
const bias = (st, sym) => (st.bias[sym] !== undefined ? st.bias[sym] : 1.0);

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

function MarketState(rng) {
  this.levels = {};
  for (const c of COINS) {
    // clamped to the coin's own range - an unclamped USDC opened as low as
    // $0.78, which made the safe asset the best trade on the board
    this.levels[c.symbol] = Math.max(c.low, Math.min(c.mid * rng.uniform(0.8, 1.2), c.high));
  }
}
MarketState.prototype.drift = function (rng) {
  for (const c of COINS) {
    let level = this.levels[c.symbol];
    if (c.symbol === "USDC") {
      this.levels.USDC = Math.max(0.97, Math.min(1.03, level * rng.uniform(0.997, 1.003)));
      continue;
    }
    const vol = c.meme ? 0.30 : 0.13;
    const step = rng.gauss(0, vol);
    const pull = level > 0 ? 0.18 * Math.log(c.mid / level) : 0;
    level *= Math.exp(step + pull);
    this.levels[c.symbol] = Math.max(c.low * 0.4, Math.min(level, c.high * 1.6));
  }
};
MarketState.prototype.apply = function (symbol, factor, c) {
  const level = this.levels[symbol] * factor;
  this.levels[symbol] = Math.max(c.low * 0.15, Math.min(level, c.high * 2.2));
};

function stationPrice(c, level, st, rng) {
  const b = 1.0 + (bias(st, c.symbol) - 1.0) * 0.62;
  const noise = c.meme ? rng.uniform(0.94, 1.06) : rng.uniform(0.975, 1.025);
  const price = level * b * noise;
  if (c.symbol === "USDC") return Math.max(c.low, Math.min(price, c.high));
  return Math.max(c.low * 0.1, price);
}

function generate(st, rng, state, shockChance) {
  if (shockChance === undefined) shockChance = 0.24;
  let shock = null;
  if (rng.random() < shockChance) {
    const pool = COINS.filter(c => c.symbol !== "USDC");
    const target = rng.choice(pool);
    let entry;
    if (rng.random() < 0.5) entry = rng.choice(CRASHES);
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

function Game(seed) {
  // kept so a save records which run this was - the RNG state is what restores
  // the dice, but the seed is what lets you tell someone else to try it
  this.seed = (seed === undefined || seed === null) ? (Math.random() * 1e9) | 0 : seed;
  this.rng = new RNG(this.seed);
  this.day = 1;
  this.finished = false;
  this.station = STATIONS[9];              // 14 St-Union Sq
  this.player = { cash: START_CASH, debt: START_DEBT, vault: 0,
                  capacity: START_CAPACITY, vpn: 0, wallet: {} };
  this.log = [];
  this.state = new MarketState(this.rng);
  this.market = generate(this.station, this.rng, this.state);
  this.say(`Day 1. You're at ${this.station.name} with $${START_CASH.toLocaleString()} and a $${START_DEBT.toLocaleString()} problem.`);
  if (this.market.headline) this.say(this.market.headline);
}
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
  const spendable = Math.max(0, this.player.cash - SUBWAY_FARE);
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
  const profit = proceeds - released;
  h.qty -= qty; h.cost -= released;
  if (h.qty <= 1e-12) { h.qty = 0; h.cost = 0; }
  this.dropEmpty();
  this.player.cash += proceeds;
  return { text: `Sold ${fmtQty(qty)} ${sym} for $${proceeds.toFixed(2)} (${profit >= 0 ? "made" : "lost"} $${Math.abs(profit).toFixed(2)})`,
           good: profit >= 0, profit };
};
Game.prototype.borrow = function (amount) {
  if (!this.station.shark) throw new Error("The Shark doesn't work this station");
  if (!(amount > 0)) throw new Error("borrow how much?");
  const ceiling = Math.max(2000, this.netWorth() * 2);
  if (this.player.debt + amount > ceiling)
    throw new Error(`The Shark looks you up and down. Not a chance over $${Math.max(0, ceiling - this.player.debt).toFixed(0)}`);
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
  const target = STATIONS[index];
  if (target.name === this.station.name) throw new Error("you're already here");
  if (this.player.cash < SUBWAY_FARE) throw new Error(`you can't even make the $${SUBWAY_FARE.toFixed(2)} fare`);
  this.player.cash -= SUBWAY_FARE;
  this.station = target;
  this.day += 1;
  this.player.debt *= (1 + SHARK_RATE);
  this.player.vault *= (1 + VAULT_RATE);
  this.state.drift(this.rng);
  this.market = generate(this.station, this.rng, this.state);
  const messages = [`Day ${this.day}. ${target.name}.`, target.flavor];
  if (this.market.headline) messages.push(this.market.headline);
  for (const m of rollEvent(this)) messages.push(m);
  messages.forEach(m => this.say(m));
  if (this.day > DAYS) { this.finished = true; messages.push("Thirty days gone. That's the run."); }
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
    const fine = takeCash(g, 400 + g.rng.random() * 900);
    return [`SEC agents stop you at the turnstile. Nothing to seize, so they write you a $${fine.toFixed(2)} fine instead.`];
  }
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
  g.day += 1; g.player.debt *= 1.10;
  return ["Signal problems at Chambers St. You lose a day on a stopped train while your debt keeps compounding."];
}
const quiet = () => [];

const EVENTS = [
  [secRaid, 10, true], [phishing, 8, true], [gasSpike, 9, false], [sharkVisit, 7, false],
  [delayEvent, 5, false], [airdrop, 8, false], [foundWallet, 6, false], [whaleOffer, 6, false],
  [quiet, 34, false],
];
function rollEvent(game) {
  const heat = game.station.heat;
  const shelter = 1.0 - Math.min(0.66, 0.22 * game.player.vpn);
  const weights = EVENTS.map(([, w, scales]) => (scales ? w * (0.35 + 1.4 * heat) * shelter : w));
  return game.rng.choices(EVENTS.map(e => e[0]), weights)(game);
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
    day: g.day,
    finished: g.finished,
    station: g.station.name,
    player: { cash: g.player.cash, debt: g.player.debt, vault: g.player.vault,
              capacity: g.player.capacity, vpn: g.player.vpn, wallet },
    levels: Object.assign({}, g.state.levels),
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
  const g = new Game(data.seed === undefined ? 0 : data.seed);
  g.rng.setState(data.rng);
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
                     fmtQty, fmtPrice, fmtMoney, saveToDict, saveFromDict, SAVE_VERSION };
}
