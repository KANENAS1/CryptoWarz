/* Print the JS port's game data as JSON so tests can diff it against the
   Python package. Structural drift - a coin retuned in coins.py but not in
   game.js, a station bias changed on one side only - is silent otherwise, and
   would quietly make the phone version a different game from the terminal one. */
const COINS_EQUAL = (a, b) =>
  JSON.stringify(a) === JSON.stringify(b);
const G = require("./game.js");
/* Bots face the same standoffs a player does rather than being exempt: a
   pending encounter blocks every other action, so a harness that ignored one
   would simply stop. */
function travelAndAnswer(g, to) {
  const said = g.travel(to);
  if (g.pending) for (const m of g.resolve(G.bestChoice(g))) said.push(m);
  return said;
}

const out = {
  constants: {
    DAYS: G.DAYS,
    SUBWAY_FARE: G.SUBWAY_FARE,
    START_CASH: new G.Game(1).player.cash,
    START_DEBT: new G.Game(1).player.debt,
    START_CASH_CAP: new G.Game(1).player.cash_cap,
  },
  coins: G.COINS.map(c => ({
    symbol: c.symbol, name: c.name, low: c.low, high: c.high, meme: c.meme,
    vol: c.vol, pull: c.pull, note: c.note,
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
  market: {
    trend_flip: G.TREND_FLIP, trend_strength: G.TREND_STRENGTH,
    tip_chance: G.TIP_CHANCE, tip_accuracy: G.TIP_ACCURACY,
    tip_min_run: G.TIP_MIN_RUN, tip_fresh_for: G.TIP_FRESH_FOR,
    /* measured, not read off the constants: a trend that does not persist is
       not a trend, and a market that does not swing is not the one we tuned */
    shape: (() => {
      const runs = [], swings = [];
      for (let seed = 0; seed < 400; seed++) {
        const g = new G.Game(seed);
        const base = g.state.levels.DOGE;
        const path = [];
        let flips = 0, prev = g.state.running("DOGE");
        for (let d = 0; d < 30; d++) {
          g.state.drift(g.rng);
          path.push(g.state.levels.DOGE / base);
          const now = g.state.running("DOGE");
          if (now !== prev) { flips++; prev = now; }
        }
        runs.push(flips);
        swings.push(Math.max(...path) / Math.min(...path));
      }
      const mid = a => a.slice().sort((x, y) => x - y)[Math.floor(a.length / 2)];
      return { trend_changes_per_run: mid(runs), doge_swing: Math.round(mid(swings) * 10) / 10 };
    })(),
    history_kept: G.HISTORY_KEPT, spark_days: G.SPARK_DAYS,
    /* a chart that lies is worse than no chart, so this is measured: a coin
       that moved must be drawn moving, and the peg must be drawn flat */
    chart_truth: (() => {
      const g = new G.Game(5);
      g.player.capacity = 1e9;
      for (let i = 0; i < 12; i++) {
        g.player.cash += 800;
        const here = G.STATIONS.findIndex(s => s.name === g.station.name);
        try { travelAndAnswer(g, (here + 3) % G.STATIONS.length); } catch (e) { break; }
      }
      const range = sym => {
        const h = g.state.history[sym];
        const lo = Math.min(...h), hi = Math.max(...h);
        return hi > 0 ? (hi - lo) / hi : 0;
      };
      return {
        days_recorded: g.state.history.DOGE.length,
        /* the invariant, not a magic number: one price per day, INCLUDING the
           days a stopped train or a beating takes off you - those used to move
           the clock without moving the market, which is exactly how the older
           bug hid */
        one_point_per_day: g.state.history.DOGE.length === g.day,
        day: g.day,
        peg_barely_moves: range("USDC") < 0.05,
        memecoin_really_moves: range("WIF") > 0.05,
        /* a shock corrects the day rather than adding one, so the chart shows
           the pump it exists to show and the invariant still holds */
        shock_reaches_the_chart: (() => {
          const st = new G.MarketState(new G.RNG(3));
          const before = st.history.BONK.length;
          st.apply("BONK", 1.8, G.COIN.BONK);
          return st.history.BONK.length === before
                 && Math.abs(st.history.BONK[st.history.BONK.length - 1] - st.levels.BONK) < 1e-9;
        })(),
        first_point_is_the_opening_level: Math.abs(
          new G.Game(3).state.history.DOGE[0] - new G.Game(3).state.levels.DOGE) < 1e-9,
      };
    })(),
    /* the percentage beside a held coin must be YOUR profit at THIS stop */
    profit_reads: (() => {
      const g = new G.Game(5);
      g.player.cash = 60000; g.player.capacity = 1e9;
      g.buy("DOGE", g.maxBuyable("DOGE") * 0.2);
      const h = g.player.wallet.DOGE;
      const paid = h.cost / h.qty;
      return {
        against_station_price: Math.round((g.market.prices.DOGE / paid - 1) * 1e6) / 1e6,
        against_level: Math.round((g.state.levels.DOGE / paid - 1) * 1e6) / 1e6,
      };
    })(),
    trends_survive_a_reload: (() => {
      const g = new G.Game(7);
      for (let i = 0; i < 6; i++) g.state.drift(g.rng);
      const back = G.saveFromDict(G.saveToDict(g));
      return COINS_EQUAL(back.state.trends, g.state.trends)
          && COINS_EQUAL(back.state.history, g.state.history);
    })(),
  },
  dice: (() => {
    /* Constants both sides must agree on, plus the behaviours that keep a run
       the board must not rank from reaching it - asserted here rather than
       described, so a port that quietly stops gating fails the parity suite. */
    const ride = (g, n) => {
      for (let i = 0; i < n; i++) {
        g.player.cash += 500;
        const here = G.STATIONS.findIndex(s => s.name === g.station.name);
        travelAndAnswer(g, (here + 3) % G.STATIONS.length);
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
      every: G.DICE_EVERY, sides: G.DICE_SIDES, top_prize: G.DICE_TOP_PRIZE,
      ladder: G.DICE_LADDER.map(([reach, label, share]) => ({ reach, label, share })),
      /* what each distance pays, and what one offer is worth for every call -
         the shape of the thing, measured rather than read off the constants */
      tiers: [0, 1, 2, 3, 4, 5, 9].map(d => G.diceTier(d).share),
      ev_by_call: Array.from({ length: G.DICE_SIDES }, (_, i) => {
        let ev = 0;
        for (let r = 1; r <= G.DICE_SIDES; r++) ev += G.diceTier(Math.abs(i + 1 - r)).share;
        return Math.round(G.DICE_TOP_PRIZE * ev / G.DICE_SIDES);
      }),
      gear_lifts_the_prize: (() => {
        const bare = new G.Game(5), geared = new G.Game(5, 1, null, { meme: 3 });
        for (const g of [bare, geared]) {
          g.player.capacity = 1e9; g.player.cash = 1e6;
          g.holding("DOGE").qty = 1000; g.holding("DOGE").cost = 1000;
          g.stats.dice_days = []; g.day = 4;
          g.rng.random = () => 0;            // the dice come up 1
        }
        const before = [bare.usedCapacity(), geared.usedCapacity()];
        bare.rollDice(1); geared.rollDice(1);
        return (geared.usedCapacity() - before[1]) > (bare.usedCapacity() - before[0]);
      })(),
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
        g.player.cash_cap = 1e9;               // nothing is clipped any more
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
  gear: (() => {
    const full = {}; for (const k of Object.keys(G.CLASSES)) full[k] = G.MAX_LEVEL;
    const held = sym => { const g = new G.Game(5, 1, null, full);
      g.player.capacity = 1e9; g.holding(sym).qty = 1; return g.luck; };
    const mixed = () => { const g = new G.Game(5, 1, null, { meme: 1, major: 3 });
      g.holding("DOGE").qty = 1; g.holding("BTC").qty = 1; return g.luck; };
    const win = (symbols, net, streak) => {
      const g = new G.Game(5); g.player.debt = 0; g.player.wallet = {};
      g.player.capacity = 1e9; g.player.cash = net; g.hotHand = !!streak;
      for (const sym of symbols) {
        const h = g.holding(sym); h.qty += 1000 / g.market.prices[sym]; h.cost += 1000;
        g.player.cash -= 1000;
      }
      g.finalise();
      const profile = G.blankProfile();
      const out = G.creditWin(profile, g);
      return { wins: profile.gear_wins, key: out ? out[0].key : null };
    };
    return {
      classes: G.CLASSES,
      pieces: G.GEAR.map(x => ({ key: x.key, name: x.name, covers: x.covers, blurb: x.blurb })),
      max_level: G.MAX_LEVEL, wins_for_level: G.WINS_FOR_LEVEL,
      luck_per_level: G.LUCK_PER_LEVEL, win_at: G.WIN_AT,
      levels: [0, 1, 2, 3, 6, 7, 40].map(G.levelFor),
      /* the two properties the feature stands on */
      empty_wallet_is_zero: new G.Game(5, 1, null, full).luck,
      four_pieces_equal_the_best: ["DOGE", "SOL", "BTC", "USDC"]
        .every(sym => Math.abs(held(sym) - G.MAX_LEVEL * G.LUCK_PER_LEVEL) < 1e-9),
      mixed_bag_takes_the_better: mixed(),
      /* earning it */
      win_credits_what_you_held: win(["DOGE"], 60000).wins,
      cash_finish_earns_nothing: win([], 60000).wins,
      loss_earns_nothing: win(["DOGE"], -4000).wins,
      unrankable_run_earns_nothing: win(["DOGE"], 600000, true).wins,
    };
  })(),
  custom: (() => {
    const p = G.blankProfile(); p.gear_wins = { meme: 4 };
    const named = G.renameGear(p, "meme", "  Lucky   Rat  ");
    const shown = G.displayName(p, G.GEAR_BY_KEY.meme);
    const moved = G.retuneGear(p, "meme", "major");
    let refusedUnearned = false, refusedBroke = false;
    try { G.renameGear(G.blankProfile(), "alt", "x"); } catch (e) { refusedUnearned = true; }
    try { G.retuneGear(G.blankProfile(), "alt", "meme"); } catch (e) { refusedBroke = true; }
    return {
      retune_cost: G.RETUNE_COST, max_name: G.MAX_NAME,
      cleaned: shown, wins_after_move: p.gear_wins,
      refused_unearned_rename: refusedUnearned, refused_broke_retune: refusedBroke,
      drops_the_name_when_the_piece_is_gone: (() => {
        const q = G.blankProfile(); q.gear_wins = { meme: 2 };
        G.renameGear(q, "meme", "Ratty"); G.retuneGear(q, "meme", "alt");
        return !q.gear_names.meme;
      })(),
    };
  })(),
  backup: (() => {
    const loaded = () => {
      const p = G.blankProfile();
      p.runs = 37; p.best_net = 812345; p.best_tier_cleared = 3;
      p.achievements = ["first_run", "in_the_black"];
      p.gear_wins = { meme: 7, major: 3 };
      p.gear_names = { meme: "Ratty — the good one" };
      return p;
    };
    const refuses = text => { try { G.readBackup(text); return false; } catch (e) { return true; } };
    const line = G.makeBackup(loaded());
    const withRun = (() => {
      const g = new G.Game(5, 1, null, {}, "hard"); g.day = 9;
      const back = G.readBackup(G.makeBackup(loaded(), G.saveToDict(g))).save;
      const replayed = G.saveFromDict(back);
      return { day: replayed.day, difficulty: replayed.difficulty,
               station: replayed.station.name, debt: Math.round(replayed.player.debt * 100) / 100 };
    })();
    return {
      version: G.BACKUP_VERSION, prefix: G.BACKUP_PREFIX,
      /* the published 32-bit FNV-1a vectors, so the checksum cannot drift */
      fnv: ["", "a", "foobar"].map(t => G.fnv1a(t)),
      /* a line this port wrote, for Python to read - and the profile it holds */
      line: line,
      round_trip: G.readBackup(line).profile,
      short_enough_to_paste: line.length < 1000,
      with_a_run: withRun,
      /* it refuses rather than half-loading */
      refuses_truncated: refuses(line.slice(0, -6)),
      refuses_rubbish: ["", "hello", "CW1.deadbeef", "CW9.deadbeef.aaaa"].every(refuses),
      refuses_a_newer_version: refuses(G.backupEncode({ v: G.BACKUP_VERSION + 1, profile: {} })),
      forgives_line_breaks: (() => {
        const wrapped = line.match(/.{1,40}/g).join("\n");
        return G.readBackup(wrapped).profile.runs;
      })(),
      drops_an_unknown_goal: (() => {
        const p = loaded(); p.achievements = p.achievements.concat(["nonsense_award"]);
        return G.readBackup(G.makeBackup(p)).profile.achievements;
      })(),
      unicode: (() => {
        const p = G.blankProfile();
        p.gear_wins = { major: 2 }; p.gear_names = { major: "Старый — 日本" };
        return G.readBackup(G.makeBackup(p)).profile.gear_names;
      })(),
    };
  })(),
  encounter: (() => {
    const cornered = (cash, weapon, rep, load) => {
      const g = new G.Game(11);
      g.player.cash = cash === undefined ? 8000 : cash;
      g.player.capacity = 25000;
      g.weapon = weapon || null;
      g.stats.rep = rep || 0;
      if (load) { const h = g.holding("DOGE"); h.cost = g.player.capacity * load; h.qty = 1; }
      G.openStandoff(g);
      return g;
    };
    const blocked = () => {
      const calls = [["buy", ["BTC", 0.001]], ["sell", ["BTC", 0.001]], ["travel", [0]],
                     ["spinWheel", []], ["rollDice", [3]], ["borrow", [100]],
                     ["repay", [10]], ["deposit", [10]], ["withdraw", [10]],
                     ["buyCapacity", []], ["buyVpn", []], ["buyWeapon", ["pipe"]]];
      return calls.every(([name, args]) => {
        const g = cornered();
        try { g[name].apply(g, args); return false; }
        catch (e) { return /in front of you/.test(e.message); }
      });
    };
    return {
      weapons: G.WEAPONS.map(w => ({ key: w.key, name: w.name, blurb: w.blurb,
        edge: w.edge, heat: w.heat, breaks: w.breaks, price: w.price })),
      for_sale: G.FOR_SALE,
      kinds: G.KINDS.map(k => ({ key: k.key, title: k.title, severity: k.severity,
        armable: k.armable, opening: k.opening })),
      numbers: { run: G.RUN_BASE, fight: G.FIGHT_BASE, load: G.MAX_LOAD_PENALTY,
                 rep_max: G.REP_MAX, rep_odds: G.REP_ODDS,
                 take_cash: G.TAKE_CASH, take_bag: G.TAKE_BAG,
                 hospital: G.HOSPITAL_CHANCE },
      /* the properties the feature stands on */
      blocks_everything: blocked(),
      survives_a_save: (() => {
        const g = cornered(8000, "bat");
        const back = G.saveFromDict(G.saveToDict(g));
        let stillBlocked = false;
        try { back.travel(0); } catch (e) { stillBlocked = /in front of you/.test(e.message); }
        return { kind: back.pending && back.pending.kind, weapon: back.weapon,
                 blocked: stillBlocked };
      })(),
      old_save_has_neither: (() => {
        const data = G.saveToDict(new G.Game(4));
        delete data.pending; delete data.weapon;
        const back = G.saveFromDict(data);
        return back.pending === null && back.weapon === null;
      })(),
      /* the odds, which are the whole decision */
      odds_empty: G.encounterOdds(cornered(8000, null, 0, 0), "run"),
      odds_loaded: G.encounterOdds(cornered(8000, null, 0, 1), "run"),
      odds_by_weapon: G.WEAPONS.map(w =>
        Math.round(G.encounterOdds(cornered(8000, w.key), "weapon") * 10000) / 10000),
      odds_rep: [-3, 0, 3].map(r =>
        Math.round(G.encounterOdds(cornered(8000, null, r), "fight") * 10000) / 10000),
      pay_is_certain: G.encounterOdds(cornered(), "pay"),
      pay_cost: Math.round(G.payCost(cornered(10000))),
      choices_bare: G.encounterChoices(cornered()).map(c => c.key),
      choices_armed: G.encounterChoices(cornered(8000, "bat")).map(c => c.key),
      /* a weapon cuts both ways */
      carry_cuts_both_ways: (() => {
        const bare = new G.Game(5), armed = new G.Game(5);
        bare.day = armed.day = 22; armed.weapon = "taser";
        const i = G.EVENTS.findIndex(e => e[0] === G.stickup);
        return { raid_up: G.raidChance(armed) > G.raidChance(bare),
                 stickup_down: G.eventWeights(armed)[i] < G.eventWeights(bare)[i] };
      })(),
      /* the answer you price yourself, and the fares you buy early */
      broke: (() => {
        const at2 = (share) => { const g = new G.Game(11);
          g.player.cash = g.player.cash_cap * share;
          G.openStandoff(g, "stickup"); return g; };
        const offered = (kind) => { const g = new G.Game(11);
          G.openStandoff(g, kind); return g.choices().some(c => c.key === "broke"); };
        return {
          base: G.BROKE_BASE, loaded: G.BROKE_LOADED,
          curve: [0, 0.25, 0.5, 0.75, 1].map(x =>
            Math.round(G.encounterOdds(at2(x), "broke") * 10000) / 10000),
          offered_by_people: ["stickup", "followed", "collector"].every(offered),
          not_by_the_badge: ["badge", "drain", "gas"].every(k => !offered(k)),
        };
      })(),
      card: (() => {
        const g = new G.Game(5); g.player.cash = 20; g.buyRides();
        const rides = g.player.rides;
        g.player.cash = 0.5;
        const before = g.player.cash;
        g.travel(G.STATIONS.findIndex(s2 => s2.name !== g.station.name));
        const stranded = (() => { const x = new G.Game(5); x.player.cash = 20;
          x.buyRides(); x.player.cash = 0; x.player.wallet = {};
          const withCard = x.stranded; x.player.rides = 0;
          return { with_card: withCard, without: x.stranded }; })();
        return {
          rides: G.OMNY_RIDES, price: G.OMNY_PRICE,
          cheaper_than_singles: G.OMNY_PRICE < G.OMNY_RIDES * G.SUBWAY_FARE,
          bought: rides, after_a_ride: g.player.rides,
          cash_untouched: Math.abs(g.player.cash - before) < 0.01,
          stranded: stranded,
          survives_a_save: G.saveFromDict(G.saveToDict(g)).player.rides,
        };
      })(),
      /* the two encounters that replaced an event */
      collector: (() => {
        const make = () => { const g = new G.Game(13);
          g.player.cash = 9000; g.player.debt = 12000; g.player.capacity = 1e9;
          const h = g.holding("BTC"); h.qty = 1; h.cost = 5000;
          G.openStandoff(g, "collector"); return g; };
        const after = (choice) => { const g = make(); g.resolve(choice);
          return { cash: Math.round(g.player.cash), debt: Math.round(g.player.debt) }; };
        return { options: G.encounterChoices(make()).map(c => c.key),
                 demand: Math.round(G.collectorDemand(make())),
                 pay: after("pay"), run: after("run"),
                 fee_ran: G.SHARK_FEE_RAN, fee_fought: G.SHARK_FEE_FOUGHT };
      })(),
      badge: (() => {
        const make = () => { const g = new G.Game(13);
          g.player.cash = 9000; g.player.debt = 12000; g.player.capacity = 1e9;
          const h = g.holding("BTC"); h.qty = 1; h.cost = 5000;
          G.openStandoff(g, "badge"); return g; };
        const after = (choice) => { const g = make(); g.resolve(choice);
          return { cash: Math.round(g.player.cash), raids: g.stats.raids }; };
        return { options: G.encounterChoices(make()).map(c => c.key),
                 no_weapon_offered: (() => { const g = make(); g.weapon = "bat";
                   return !G.encounterChoices(g).some(c => c.key === "weapon"); })(),
                 lawyer_cost: Math.round(G.lawyerCost(make())),
                 lawyer_saves: G.LAWYER_SAVES, caught: G.CAUGHT_MULTIPLIER,
                 comply: after("comply"), lawyer: after("lawyer") };
      })(),
      /* the inversion: coins uncapped, pockets capped */
      wallet: (() => {
        const g = new G.Game(5);
        const start = g.player.cash_cap;
        g.player.cash = 10000000;
        g.buy("DOGE", 1000000); g.buy("DOGE", 1000000);
        const uncapped = Math.round(g.usedCapacity());
        const sell = new G.Game(5);
        sell.player.cash = 0; sell.player.cash_cap = 50000;
        const price = sell.market.prices.DOGE;
        sell.holding("DOGE").qty = 400000 / price; sell.holding("DOGE").cost = 400000;
        let refused = false;
        try { sell.sell("DOGE", sell.holding("DOGE").qty); } catch (e) { refused = /carry/.test(e.message); }
        const gift = new G.Game(5);
        gift.holding("BTC").qty = 10; gift.holding("BTC").cost = 5000000;
        const before = gift.usedCapacity(); gift.gift(5000, "Here");
        const up = new G.Game(5); up.station = G.STATIONS.find(s2 => s2.shop);
        up.player.cash = 999999; const cost = up.upgradeCost(); up.buyCapacity();
        return {
          start_cap: start,
          /* the VALUE cannot be compared across ports - two generators give
             two DOGE prices from one seed - so compare the property: far past
             any ceiling the old rule would have imposed */
          coins_are_uncapped: uncapped > 500000,
          sellable_is_the_carry_room: Math.round(sell.maxSellable("DOGE") * price),
          selling_is_capped: refused,
          gift_always_lands: Math.round(gift.usedCapacity() - before),
          upgrade_cost: Math.round(cost), cap_after_upgrade: up.player.cash_cap,
          over_carrying: (() => { const o = new G.Game(5); o.player.cash = 61000;
            return Math.round(o.overCarrying()); })(),
          load_is_cash: (() => { const a = new G.Game(5), b = new G.Game(5);
            a.player.cash = 0; b.player.cash = b.player.cash_cap;
            return [Math.round(G.loadPenalty(a) * 1000) / 1000,
                    Math.round(G.loadPenalty(b) * 1000) / 1000]; })(),
          old_save_gets_standard_pockets: (() => {
            const d = G.saveToDict(new G.Game(5)); delete d.player.cash_cap;
            return G.saveFromDict(d).player.cash_cap; })(),
        };
      })(),
      /* a day lost at the end must close the run, on both ports */
      last_day: (() => {
        const g = new G.Game(5); g.day = g.days; g.loseADay();
        const limbo = G.saveToDict(new G.Game(5));
        limbo.day = limbo.day + 40; limbo.finished = false;
        return { day_after: g.day, finished: g.finished,
                 limbo_loads_finished: G.saveFromDict(limbo).finished,
                 ordinary_untouched: (() => { const o = new G.Game(5); o.day = 12;
                   return G.saveFromDict(G.saveToDict(o)).finished; })() };
      })(),
      /* a weapon is worth luck, and luck is still never a sum */
      nerve: G.WEAPONS.map(w => w.nerve),
      nerve_is_luck: (() => { const g = new G.Game(3); g.weapon = "taser"; return g.luck; })(),
      nerve_never_stacks: (() => {
        const g = new G.Game(3, 1, null, { major: 3 });
        g.holding("BTC").qty = 1; g.weapon = "taser";
        return g.luck;
      })(),
      drain: (() => {
        const make = () => { const g = new G.Game(4);
          g.player.cash = 9000; g.player.capacity = 1e9;
          const h = g.holding("BTC"); h.qty = 1; h.cost = 5000;
          G.openStandoff(g, "drain"); return g; };
        const g = make();
        const real = g.pending.real;
        const afterCheck = (() => { const x = make(); x.resolve("check");
          return { known: !!x.pending.known, options: x.choices().map(c => c.key),
                   cash: Math.round(x.player.cash) }; })();
        return { options: g.choices().map(c => c.key), real_rate: G.DRAIN_REAL,
                 check_cost: Math.round(G.checkCost(g)), after_check: afterCheck,
                 walk_costs_nothing: (() => { const x = make();
                   const before = x.player.cash; x.resolve("walk");
                   return x.player.cash === before; })() };
      })(),
      gas_is_owed: (() => {
        const gassed = (cash, coins) => {
          const g = new G.Game(13); g.player.cash = cash; g.player.capacity = 1e9;
          if (coins !== false) { const h = g.holding("BTC"); h.qty = 1; h.cost = 40000; }
          G.openStandoff(g, "gas"); g.pending.fee = 640; return g;
        };
        const cost = (choice, cash, coins) => {
          const g = gassed(cash, coins);
          const before = g.portfolioValue();
          const said = g.resolve(choice).join(" ");
          return { took: Math.round((before - g.portfolioValue()) * 100) / 100,
                   cash: Math.round(g.player.cash * 100) / 100, said: said };
        };
        return {
          broke_pays_from_the_bag: cost("paygas", 0).took,
          broke_relay_pays_too: cost("relay", 0).took > 0,
          cash_first: cost("paygas", 9000).cash,
          nothing_at_all: cost("paygas", 0, false).said,
          no_zero_line: !/\$0\.00/.test(cost("relay", 0, false).said),
        };
      })(),
      gas: (() => {
        const make = () => { const g = new G.Game(4);
          g.player.cash = 9000; g.player.capacity = 1e9;
          const h = g.holding("BTC"); h.qty = 1; h.cost = 5000;
          G.openStandoff(g, "gas"); return g; };
        const g = make();
        return { options: g.choices().map(c => c.key), fee: Math.round(g.pending.fee),
                 relay_share: G.RELAY_SHARE, relay_base: G.RELAY_BASE,
                 paid: (() => { const x = make(); x.resolve("paygas");
                   return Math.round(x.player.cash); })(),
                 /* nerve tilts the relay, which is the one place it pays off
                    outside a fight */
                 relay_odds_bare: G.encounterOdds(make(), "relay"),
                 relay_odds_armed: (() => { const x = make(); x.weapon = "taser";
                   return Math.round(G.encounterOdds(x, "relay") * 10000) / 10000; })() };
      })(),
      /* paying keeps the bag; it is the point of paying */
      paying_keeps_the_bag: (() => {
        const g = cornered(10000);
        g.holding("BTC").qty = 1;
        g.resolve("pay");
        return { qty: g.holding("BTC").qty, rep: G.repOf(g), cheaper: g.player.cash < 10000 };
      })(),
    };
  })(),
  hardness: (() => {
    const made = G.DIFFICULTIES.map(d => {
      const g = new G.Game(1, 1, null, {}, d.key);
      return { key: g.difficulty, cash: g.player.cash, debt: Math.round(g.player.debt * 100) / 100,
               shark: g.sharkRate, heat_mult: g.heatMult };
    });
    const scored = (() => {
      const out = {};
      for (const d of G.DIFFICULTIES) {
        const g = new G.Game(9, 1, null, {}, d.key);
        g.player.debt = 0; g.player.wallet = {}; g.player.cash = 100000;
        g.finalise();
        out[d.key] = Math.round(G.runPoints(g));
      }
      return out;
    })();
    return {
      table: G.DIFFICULTIES.map(d => ({ key: d.key, name: d.name, blurb: d.blurb,
        cash: d.cash, debt_mult: d.debtMult, shark: d.shark,
        heat_mult: d.heatMult, mult: d.mult })),
      default: G.DEFAULT_DIFFICULTY,
      made: made,
      /* an unknown key must fall back rather than throw - an old save has none */
      unknown_falls_back: G.difficultyOf("nonsense").key,
      fixer_still_gets_its_discount: new G.Game(1, 1, "fixer").sharkRate,
      points_by_difficulty: scored,
      /* the save has to carry it, or a reload changes the rules mid-run */
      survives_a_save: (() => {
        const g = new G.Game(4, 1, null, {}, "hard"); g.day = 12;
        const back = G.saveFromDict(G.saveToDict(g));
        return { difficulty: back.difficulty, debt: Math.round(back.player.debt * 100) / 100,
                 shark: back.sharkRate };
      })(),
      old_save_loads_as_express: (() => {
        const g = new G.Game(4); const data = G.saveToDict(g);
        delete data.difficulty;
        return G.saveFromDict(data).difficulty;
      })(),
    };
  })(),
  enforcement: (() => {
    const at = (day, difficulty, vpn) => {
      const g = new G.Game(3, 1, null, {}, difficulty || "normal");
      g.day = day; g.player.vpn = vpn || 0;
      return g;
    };
    const mapAt = (day, difficulty, vpn) => G.STATIONS.map(s =>
      G.threatLevel(G.raidChance(at(day, difficulty, vpn), s, day))[0][0]).join("");
    const raidIndex = G.EVENTS.findIndex(e => e[1] === 10 && e[2] === true);
    return {
      grace: G.RAID_GRACE, ramp_to: G.RAID_RAMP_TO,
      thresholds: G.THREAT.map(t => [t[0], t[1], t[2]]), bars: G.THREAT_BARS,
      /* the grace is absolute: no weight at all, not merely less */
      pressure: [1, 8, 15, 16, 22, 30].map(d => {
        const g = at(d); return Math.round(G.raidPressure(g, d) * 1000) / 1000;
      }),
      chance_in_grace: G.raidChance(at(8), null, 8),
      raid_weight_in_grace: G.eventWeights(at(8), null, 8)[raidIndex],
      /* the shape of the run: the map gets worse as it goes on */
      map_by_day: { 16: mapAt(16), 22: mapAt(22), 30: mapAt(30) },
      /* a VPN is the thing the meter visibly buys */
      map_with_vpn: mapAt(22, "normal", 2),
      chance_here: [16, 22, 30].map(d => Math.round(G.raidChance(at(d), null, d) * 10000) / 10000),
      /* the news post itself */
      wire_quiet: (() => { const w = G.wire(at(8), null, 8);
        return { label: w.label, bars: w.bars, grace_left: w.grace_left, text: w.text }; })(),
      wire_late: (() => { const w = G.wire(at(24), null, 24);
        return { label: w.label, bars: w.bars, two_stops: Math.round(w.two_stops * 10000) / 10000,
                 text: w.text }; })(),
      lines: G.WIRE_LINES,
      /* a stop remembers your face, and a VPN does not erase that */
      visits: (() => {
        const at2 = (vpn) => { const g = new G.Game(3); g.day = 22; g.player.vpn = vpn || 0;
                               return g; };
        const g = at2();
        const climb = [], labels = [];
        for (let n = 1; n <= 8; n++) {
          g.stats.visits[g.station.name] = n;
          climb.push(Math.round(G.raidChance(g, g.station) * 10000) / 10000);
          labels.push(G.visitLabel(g, g.station));
        }
        const bare = at2(0), safe = at2(3);
        bare.stats.visits[bare.station.name] = 8;
        safe.stats.visits[safe.station.name] = 8;
        return {
          step: G.VISIT_STEP, max: G.VISIT_MAX,
          levels: G.VISIT_LEVELS.map(l => [l[0], l[1]]),
          first_visit_is_free: G.visitPressure(at2(), at2().station),
          climb: climb, labels: labels,
          capped: (() => { const c = at2(); c.stats.visits[c.station.name] = 500;
                           return Math.round(G.visitPressure(c, c.station) * 1000) / 1000; })(),
          vpn_cools_the_threat: G.raidChance(safe, safe.station) < G.raidChance(bare, bare.station),
          vpn_keeps_the_memory: G.visitLabel(safe, safe.station),
          start_counts_as_visited: G.visitsTo(new G.Game(3), new G.Game(3).station),
        };
      })(),
      standing_heat: G.STATIONS.map(s => G.standingHeat(s)),
    };
  })(),
  broker: (() => {
    const SHOP = G.STATIONS.find(s => s.shop), BARE = G.STATIONS.find(s => !s.shop);
    const rich = (cash, station, holding, streak) => {
      const g = new G.Game(5);
      g.station = station || SHOP;
      g.player.capacity = 1e9; g.player.wallet = {};
      g.player.cash = cash === undefined ? G.BROKER_PRICE : cash;
      g.hotHand = !!streak;
      if (holding) {
        const h = g.holding(holding);
        h.qty += 1000 / g.market.prices[holding]; h.cost += 1000;
      }
      return g;
    };
    const refuses = g => { try { g.buyGear(); return false; } catch (e) { return true; } };
    const paid = (() => {
      const before = rich(G.BROKER_PRICE + 25000), after = rich(G.BROKER_PRICE + 25000);
      after.buyGear();
      return before.finalScore() - after.finalScore();
    })();
    const twice = (() => {
      const g = rich(G.BROKER_PRICE * 3); g.buyGear();
      const cash = g.player.cash;
      return { offer: G.brokerOffer(g), refused: refuses(g), kept_the_cash: g.player.cash === cash };
    })();
    const bought = (() => {
      const g = rich(G.BROKER_PRICE, null, "BTC"); g.buyGear();
      const profile = G.blankProfile();
      G.creditWheel(profile, g.gearAward);
      return { award: g.gearAward, wins: profile.gear_wins };
    })();
    return {
      price: G.BROKER_PRICE,
      /* when there is a deal */
      at_a_shop_with_the_money: G.brokerOffer(rich()),
      a_dollar_short: G.brokerOffer(rich(G.BROKER_PRICE - 1)),
      no_shop_no_dealer: G.brokerOffer(rich(undefined, BARE)),
      unrankable_run_cannot_buy: G.brokerOffer(rich(undefined, null, null, true)),
      unrankable_run_is_refused: refuses(rich(undefined, null, null, true)),
      sells_what_you_carry: [G.brokerOffer(rich(undefined, null, "BTC")),
                             G.brokerOffer(rich(undefined, null, "DOGE"))],
      /* the price is real, and it lands on the score */
      cash_after: (() => { const g = rich(G.BROKER_PRICE + 25000); g.buyGear();
                           return Math.round(g.player.cash); })(),
      off_the_score: Math.round(paid),
      /* one per run, and it banks */
      second_visit: twice,
      award_banks_a_win: bought,
    };
  })(),
  stranded: (() => {
    const BARE = G.STATIONS.find(s => !s.shark && !s.vault);
    const SHARK = G.STATIONS.find(s => s.shark);
    const VAULT = G.STATIONS.find(s => s.vault);
    const cornered = station => {
      const g = new G.Game(5);
      g.player.cash = 1.40; g.player.wallet = {}; g.player.vault = 0;
      g.station = station || BARE;
      return g;
    };
    const withSomethingToSell = () => { const g = cornered(); g.holding("DOGE").qty = 1000; return g; };
    const maxedShark = () => { const g = cornered(SHARK); g.player.debt = g.borrowLimit() * 2; return g; };
    const vaultCash = station => { const g = cornered(station); g.player.vault = 500; return g; };
    const freeRide = () => {
      const g = new G.Game(5, 1, "metrocard");
      g.player.cash = 0; g.player.wallet = {}; g.station = BARE;
      return g;
    };
    const gave = cornered();
    const said = gave.giveUp();
    return {
      fresh: new G.Game(5).stranded,
      bare_stop: cornered().stranded,
      something_to_sell: withSomethingToSell().stranded,
      at_the_shark: cornered(SHARK).stranded,
      maxed_out_shark: maxedShark().stranded,
      vault_at_a_vault: vaultCash(VAULT).stranded,
      vault_elsewhere: vaultCash(BARE).stranded,
      free_ride: freeRide().stranded,
      give_up_finishes: gave.finished,
      give_up_says_so: /give up/i.test(said.join(" ")),
      give_up_twice_is_harmless: gave.giveUp().length === 0,
    };
  })(),
  wheel: (() => {
    const stop = G.STATIONS.find(s => s.wheel);
    const spins = 6000;
    const counts = {};
    let gears = 0;
    for (let i = 0; i < spins; i++) {
      const g = new G.Game(i); g.station = stop; g.player.capacity = 1e9;
      const before = g.usedCapacity();
      const said = g.spinWheel().join(" ");
      const label = G.WHEEL.map(w => w[0]).find(l => said.includes(G.WHEEL_LINES[l]));
      counts[label] = (counts[label] || 0) + 1;
      if (g.wheelAward) gears++;
      if (Math.abs((g.usedCapacity() - before)
                   - G.WHEEL.find(w => w[0] === label)[2]) > 0.01) {
        throw new Error("a wedge paid something other than its own number");
      }
    }
    const again = (() => {
      const g = new G.Game(1); g.station = stop; g.spinWheel();
      return g.wheelReady;
    })();
    return {
      table: G.WHEEL.map(([label, weight, cash, gear]) => ({ label, weight, cash, gear })),
      /* the measured share of each wedge, so a port whose weights drifted shows
         up here even if its table still reads the same */
      shares: Object.fromEntries(Object.entries(counts)
        .map(([k, v]) => [k, Math.round(v / spins * 1000) / 1000])),
      gear_rate: Math.round(gears / spins * 1000) / 1000,
      second_spin_at_the_same_stop: again,
    };
  })(),
  stations: G.STATIONS.map(s => ({
    name: s.name, lines: s.lines, borough: s.borough, heat: s.heat, bias: s.bias,
    /* the badge the player reads must be the same number the till uses */
    markup: Object.fromEntries(G.COINS.map(c => [c.symbol, G.stationMarkup(s, c.symbol)])),
    shark: !!s.shark, vault: !!s.vault, shop: !!s.shop, wheel: !!s.wheel,
  })),
};
/* A representative save, so the Python side can check both implementations
   still agree on the format. Two front ends that disagree about what a save
   looks like is the same silent-drift problem as disagreeing about a coin. */
if (process.argv.includes("--save")) {
  const g = new G.Game(21);
  const q = g.maxBuyable("DOGE") * 0.3;
  if (q > 0) g.buy("DOGE", q);
  try { travelAndAnswer(g, 0); } catch (e) { /* fare */ }
  process.stdout.write(JSON.stringify({ save_version: G.SAVE_VERSION, save: G.saveToDict(g) }, null, 2));
} else {
  process.stdout.write(JSON.stringify(out, null, 2));
}
