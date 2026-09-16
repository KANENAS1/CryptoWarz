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
// reserving the fare exactly is not enough: rounding leaves $2.8999999999 and
// a player who cannot afford the fare the reserve was protecting
const FARE_BUFFER = 0.01;

function Game(seed, tier, perk) {
  // kept so a save records which run this was - the RNG state is what restores
  // the dice, but the seed is what lets you tell someone else to try it
  this.seed = (seed === undefined || seed === null) ? (Math.random() * 1e9) | 0 : seed;
  this.tier = tier || 1;
  this.perk = perk || null;
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
                 best_multiple: 0, worth_by_day: [] };
  this.log = [];
  this.state = new MarketState(this.rng);
  this.market = generate(this.station, this.rng, this.state);
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
  this.market = generate(this.station, this.rng, this.state);
  const messages = [`Day ${this.day}. ${target.name}.`, target.flavor];
  if (this.market.headline) messages.push(this.market.headline);
  for (const m of rollEvent(this)) messages.push(m);
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
  const weights = EVENTS.map(([, w, scales]) => (scales ? w * (0.35 + 1.4 * heat) * shelter : w));
  return game.rng.choices(EVENTS.map(e => e[0]), weights)(game);
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
  { key: "tourist",      name: "The Whole Map",       blurb: "Visit all ten stations in one run.",
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
const PROGRESS_VERSION = 2;

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
           best_daily: 0, best_daily_day: null, updated_at: 0 };
}
function readProfile() {
  try {
    const raw = JSON.parse(localStorage.getItem(PROGRESS_KEY) || "null");
    // a version 1 profile predates ranked runs; its achievements were still
    // earned, so it migrates rather than being thrown away
    if (!raw || (raw.version !== PROGRESS_VERSION && raw.version !== 1)) return blankProfile();
    const known = new Set(ACHIEVEMENTS.map(a => a.key));
    raw.achievements = (raw.achievements || []).filter(k => known.has(k));
    if (!Array.isArray(raw.daily_runs)) raw.daily_runs = [];
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
  const g = new Game(data.seed === undefined ? 0 : data.seed, data.tier || 1, data.perk || null);
  g.rng.setState(data.rng);
  g.dailySlot = (data.daily_slot === undefined || data.daily_slot === null) ? null : data.daily_slot;
  g.isDaily = g.dailySlot !== null;
  if (data.stats) g.stats = data.stats;
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
                     fmtQty, fmtPrice, fmtMoney, saveToDict, saveFromDict, SAVE_VERSION,
                     ACHIEVEMENTS, PERKS, TIERS, award, blankProfile, dailySeed,
                     unlockedPerks, maxTier, RUNS_PER_DAY, GRADES, tierMult,
                     runPoints, gradeFor, gradeBlurb, dailySeeds, rollDay,
                     runsToday, nextSlot, dailyTotal, recordDaily,
                     PROGRESS_VERSION };
}
