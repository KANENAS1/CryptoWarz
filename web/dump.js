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
  dice: (() => {
    /* Constants both sides must agree on, plus the behaviours that keep a run
       the board must not rank from reaching it - asserted here rather than
       described, so a port that quietly stops gating fails the parity suite. */
    const ride = (g, n) => {
      for (let i = 0; i < n; i++) {
        g.player.cash += 500;
        const here = G.STATIONS.findIndex(s => s.name === g.station.name);
        g.travel((here + 3) % G.STATIONS.length);
      }
    };
    const play = picks => {
      const g = new G.Game(5);
      for (const pick of picks) {
        while (!g.diceReady) ride(g, 1);
        g.rollDice(pick);
      }
      return g;
    };
    const streak = play(G.HOT_HAND);
    streak.player.debt = 0; streak.player.wallet = {}; streak.player.cash = 900000;
    streak.finalise();
    const profile = G.blankProfile();
    G.award(profile, streak);
    G.recordDaily(profile, streak, 0);
    return {
      every: G.DICE_EVERY, sides: G.DICE_SIDES,
      near_prize: G.DICE_NEAR_PRIZE, exact_prize: G.DICE_EXACT_PRIZE,
      streak_calls: G.HOT_HAND, streak_chance: G.HOT_HAND_CHANCE,
      streak_min: G.HOT_HAND_MIN, streak_max: G.HOT_HAND_MAX,
      unranked_grade: G.UNRANKED_GRADE,
      ready_on_day_one: new G.Game(1).diceReady,
      calls_start_it: streak.hotHand,
      reversed_does_not: play(G.HOT_HAND.slice().reverse()).hotHand,
      grade_shown: G.runGrade(streak),
      unlocks_nothing: profile.achievements.length === 0 && profile.runs === 0,
      spends_no_ranked_slot: G.nextSlot(profile) === 0,
      survives_reload: G.saveFromDict(G.saveToDict(streak)).hotHand,
      /* the shape of the payout, measured rather than asserted from the
         constants: the two ports must skip and pay about as often as each
         other, and neither may ever exceed the ceiling */
      payouts: (() => {
        const g = new G.Game(77);
        g.hotHand = true;
        g.player.capacity = 1e9;               // so nothing is clipped
        let paid = 0, skipped = 0, biggest = 0, smallest = Infinity;
        for (let i = 0; i < 4000; i++) {
          const before = g.usedCapacity();
          const said = g.streakGift();
          const got = g.usedCapacity() - before;
          if (said.length && got > 0) {
            paid++;
            biggest = Math.max(biggest, got);
            smallest = Math.min(smallest, got);
          } else skipped++;
        }
        return { paid_share: paid / (paid + skipped), biggest, smallest,
                 distinct_enough: biggest - smallest > 1000 };
      })(),
    };
  })(),
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
