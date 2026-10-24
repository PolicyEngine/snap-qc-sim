// SNAP payment error simulator — in-browser Monte Carlo over the state's
// QC sample. The no-scenario engine mirrors snap_qc_sim.simulate (Python)
// exactly; the policy scenario draws every case from the fitted error model
// (model_data.json) and its SMD-flipped counterpart (model_scenarios.json).

const TIERS = [[6, 0], [8, 5], [10, 10], [Infinity, 15]];
const TIER_LABELS = { 0: "0% share", 5: "5% share", 10: "10% share", 15: "15% share" };
const TIER_VARS = { 0: "--tier-0", 5: "--tier-5", 10: "--tier-10", 15: "--tier-15" };
const DRAWS = 4000;
const ASSET_V = "20261024a"; // bump with index.html's app.js?v= on every deploy that changes any asset
const SCEN_SCHEMA = "snap_qc_sim.model_scenarios.v1";
const ENGINE_SCHEMA = "snap_qc_sim.engine_comparison.v1";
const INTERVENTIONS_SCHEMA = "snap_qc_sim.interventions.v1";
// SHA-256 of app/public/interventions_data.json, printed by
// analysis/build_interventions_app_data.py; the browser refuses a payload
// that does not hash to this pin.
const INTERVENTIONS_DATA_SHA256 =
  "97966429fcf82d8d6f883e601ed1ab3024b2ccb568de4487e0d175a56e52800d";
// SHA-256 of app/public/engine_data.json, printed by analysis/engine_comparison.py
// and locked by tests/test_engine_comparison.py; the browser refuses a payload
// that does not hash to this pin.
const ENGINE_DATA_SHA256 =
  "2517d26e151cbeb8f9808d16750e531d7fc078fc8e15e4c1869d14c10d30c599";
const ADOPT_SCHEMA = "snap_qc_sim.engine_scenario.v1";
// SHA-256 of app/public/engine_scenario_data.json, written by
// analysis/build_engine_scenario.py and locked by tests/test_engine_scenario.py;
// the browser refuses a payload that does not hash to this pin.
const ADOPT_DATA_SHA256 =
  "f64b9fd7408daabe0e5ffad8115ef658572b35e0bdd102deca860f4230e6c044";

// 7 USC 2013(a)(2)(B)(iii): a year whose rate × 1.5 reaches 20% delays the
// state's first billed year — FY 2025 crossing pushes the start to FY 2029,
// FY 2026 crossing to FY 2030 — mechanically, independent of the election.
// Above 13.33% (13.34% at published two-decimal precision) the FY 2028
// share is therefore 0%.
const DELAY_THRESHOLD = 20 / 1.5;
const delayMet = (rate) => rate * 1.5 >= 20;

// Published FY 2027 parameters. The FY 2027 repricing artifact predates them
// and carries projections; the panel says so while the two disagree.
// FNA, "SNAP – Fiscal Year 2027 Cost-of-Living Adjustments", August 21, 2026:
// 48 states and DC, household of four.
const FY27_MAX_4P_PUBLISHED = 1023;
// 7 USC 2025(c)(1)(A)(ii): floor(37 × June reference-family Thrifty Food Plan
// cost / 632.30). USDA's published June 2026 cost is $1,023.20.
const FY27_TFP_JUNE_2026 = 1023.2;
const FY27_TOLERANCE_PUBLISHED = Math.floor((37 * FY27_TFP_JUNE_2026) / 632.3);

// Inside the policyengine.org AppPage iframe the site shell provides the
// PolicyEngine header/footer; hide the standalone wordmark and mirror URL
// state up to the parent so the address bar stays shareable.
const FRAMED = window.self !== window.top;

const fmtM = (v) => {
  const m = v / 1e6;
  return m >= 1000 ? `$${(m / 1000).toFixed(2)}B` : `$${m.toFixed(0)}M`;
};
const fmtPP = (v, digits = 3) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}`;
const tierOf = (r) => { for (const [cut, s] of TIERS) if (r < cut) return s; return 15; };
// Prose forms for the plain-language answer. Both round first and pick the
// wording from the rounded value, so they never print "$1000 million",
// "0%" or "100%" (tests/test_front_page.py).
const fmtWords = (v) => {
  if (v <= 0) return "$0";
  const m = Math.round(v / 1e6);
  if (m < 1) return "under $1 million";
  return m >= 1000 ? `$${(v / 1e9).toFixed(2)} billion` : `$${m} million`;
};
const fmtChance = (p) => {
  const k = Math.round(100 * p);
  return k < 1 ? "less than 1%" : k > 99 ? "more than 99%" : `${k}%`;
};
const pct2 = (r) => r.toFixed(2) + "%";

const STATE_NAMES = {
  AK: "Alaska", AL: "Alabama", AR: "Arkansas", AZ: "Arizona", CA: "California",
  CO: "Colorado", CT: "Connecticut", DC: "District of Columbia", DE: "Delaware",
  FL: "Florida", GA: "Georgia", GU: "Guam", HI: "Hawaii", IA: "Iowa", ID: "Idaho",
  IL: "Illinois", IN: "Indiana", KS: "Kansas", KY: "Kentucky", LA: "Louisiana",
  MA: "Massachusetts", MD: "Maryland", ME: "Maine", MI: "Michigan", MN: "Minnesota",
  MO: "Missouri", MS: "Mississippi", MT: "Montana", NC: "North Carolina",
  ND: "North Dakota", NE: "Nebraska", NH: "New Hampshire", NJ: "New Jersey",
  NM: "New Mexico", NV: "Nevada", NY: "New York", OH: "Ohio", OK: "Oklahoma",
  OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina",
  SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VA: "Virginia",
  VI: "U.S. Virgin Islands", VT: "Vermont", WA: "Washington", WI: "Wisconsin",
  WV: "West Virginia", WY: "Wyoming",
};
const nameOf = (code) => STATE_NAMES[code] ?? code;
const possessive = (name) => name + (name.endsWith("s") ? "'" : "'s");

function quantile(draws, q) {
  const s = Float64Array.from(draws).sort();
  const i = (s.length - 1) * q;
  const lo = Math.floor(i);
  const hi = Math.min(lo + 1, s.length - 1);
  return s[lo] + (s[hi] - s[lo]) * (i - lo);
}

// Charts draw at the container's own pixel width, so labels keep a
// readable size on phones; a closed <details> reports 0 and gets the
// fallback until it opens and re-renders.
const chartWidth = (el, fallback = 920) => Math.round(el.clientWidth) || fallback;
// Rough SVG text width for label placement (Inter averages ~0.56em a glyph).
const textW = (str, size) => str.length * size * 0.56;
// Axis tick step (in rate points) that keeps tick labels at least ~30px apart.
const tickStep = (span, px) => [1, 2, 4, 5, 10].find((d) => (px * d) / span >= 30) ?? 10;
// A start-anchored label at x that would run past the right edge flips to end
// at the left of x instead. Returns the x and anchor attributes to splice in.
const edgeLabel = (x, str, size, W, gap = 4) =>
  x + gap + textW(str, size) > W - 2 ? `x="${x - gap}" text-anchor="end"` : `x="${x + gap}"`;

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

let DATA = null;
let FY27 = null;
let INTERVENTIONS = null;
const $ = (id) => document.getElementById(id);
const tooltip = document.createElement("div");
tooltip.className = "tooltip";
tooltip.hidden = true;
document.body.appendChild(tooltip);

// ---- Observed-resample engine (no scenario) ------------------------------

// Optional process-drift band (off by default): adds N(0, tau^2) to each
// draw from a dedicated seeded stream, common across engines so
// scenario-vs-baseline deltas stay unpolluted. tau is the robust
// method-of-moments estimate from the single realized FY2024->FY2025
// transition (analysis/fy2025_movement.json) — a candidate calibration,
// not a validated forecast band.
function driftDraws(tau, seed = 1107) {
  const rng = mulberry32(seed);
  const out = new Float64Array(DRAWS);
  for (let d = 0; d < DRAWS; d++) {
    const u1 = Math.max(rng(), 1e-12);
    const u2 = rng();
    out[d] = tau * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  }
  return out;
}

function addDrift(rates, drift) {
  if (!drift) return rates;
  const out = new Float64Array(rates.length);
  for (let d = 0; d < rates.length; d++) out[d] = rates[d] + drift[d];
  return out;
}

function simulate(st, { extra = 0, seed = 11, anchor } = {}) {
  const n = st.w.length;
  const we = new Float64Array(n), wi = new Float64Array(n);
  let sumWE = 0, sumWI = 0;
  for (let i = 0; i < n; i++) {
    we[i] = st.w[i] * st.err[i];
    wi[i] = st.w[i] * st.iss[i];
    sumWE += we[i];
    sumWI += wi[i];
  }
  // Center on the anchor rate (default: the FY 2025 official, the newest
  // published level): the file-derived point drops out, leaving the anchor
  // plus this draw's sampling deviation. Case composition stays FY 2024.
  const center = anchor ?? st.official_fy2025;
  const point = (100 * sumWE) / sumWI;
  const m = n + extra;
  const rng = mulberry32(seed);
  const rates = new Float64Array(DRAWS);
  for (let d = 0; d < DRAWS; d++) {
    let e = 0, s = 0;
    for (let j = 0; j < m; j++) {
      const i = (rng() * n) | 0;
      e += we[i]; s += wi[i];
    }
    rates[d] = center + (100 * e) / s - point;
  }
  return rates;
}

function unpackBits(encoded, n) {
  const bytes = Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0));
  return Array.from({ length: n }, (_, i) => (bytes[i >> 3] >> (i & 7)) & 1);
}

function stateSeed(code) {
  let seed = 20260820;
  for (const c of code) seed = Math.imul(seed ^ c.charCodeAt(0), 16777619);
  return seed >>> 0;
}

function weightedMembership(weights, scores, coverage) {
  const order = Array.from(scores.keys()).sort((a, b) => scores[b] - scores[a] || a - b);
  const target = coverage * weights.reduce((a, b) => a + b, 0);
  const membership = new Float64Array(weights.length);
  let used = 0;
  for (const i of order) {
    membership[i] = Math.max(0, Math.min(1, (target - used) / weights[i]));
    used += weights[i];
  }
  return membership;
}

function interventionMembership(code, st) {
  const rule = $("intervention-rule").value;
  let scores;
  if (rule === "model") {
    // The artifact's out-of-sample FY2024 scores, aligned to case order by
    // the build script's weight/issuance assertion — NOT the fitted p_dev
    // array, whose ranking differs from the committed grid.
    scores = INTERVENTIONS.model_scores[code];
  }
  else if (rule === "oracle") scores = st.err;
  else if (rule === "self_employment") scores = unpackBits(st.self_emp, st.n);
  else {
    const rng = mulberry32(stateSeed(code));
    scores = Array.from({ length: st.n }, () => rng());
  }
  return weightedMembership(st.w, scores, +$("intervention-coverage").value / 100);
}

function engineCutErr(st) {
  // Single-attribution: each case's error dollars scale by its share of
  // agency-coded findings in the computation class {17, 19, 20}.
  const x = +$("engine-cut-pct").value / 100;
  return st.err.map((value, i) => {
    const pair = st.agency_findings[i];
    return pair ? value * (1 - x * (pair[1] / pair[0])) : value;
  });
}

function interventionDraws(code, st, extra = 0, errBasis = st.err) {
  const membership = interventionMembership(code, st);
  const effectiveness = +$("intervention-effectiveness").value / 100;
  const err = errBasis.map((value, i) => value * (1 - effectiveness * membership[i]));
  const basePoint = pointRate(st, st.err);
  const shiftedPoint = pointRate(st, err);
  return {
    rates: simulate({ ...st, err }, {
      extra,
      anchor: st.official_fy2025 + shiftedPoint - basePoint,
    }),
    delta: shiftedPoint - basePoint,
  };
}

async function loadInterventionsArtifact() {
  const res = await fetch("interventions_data.json?v=" + ASSET_V);
  if (!res.ok) throw new Error("interventions artifact fetch failed");
  const bytes = await res.arrayBuffer();
  const hex = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
    .map((b) => b.toString(16).padStart(2, "0")).join("");
  if (hex !== INTERVENTIONS_DATA_SHA256)
    throw new Error("interventions_data.json sha256 does not match the committed pin");
  const payload = JSON.parse(new TextDecoder().decode(bytes));
  if (payload.schema !== INTERVENTIONS_SCHEMA) throw new Error("interventions schema mismatch");
  INTERVENTIONS = payload;
}

// ---- FY2026 election lens ------------------------------------------------
// The FY2028 cost share keys to the state's FY2025 or FY2026 rate, at its
// election (7 USC 2013(a)(2)(B)(ii)). FY2025 is published and locked; the
// draws simulate a QC-sized FY2026 measurement centered at the FY2025 level
// (sampling noise only — a lower bound on true FY2026 uncertainty, since
// year-over-year process movement is excluded; see analysis/FY2025_MOVEMENT).
function electionStats(st, draws) {
  const fy25 = st.official_fy2025;
  const lockShare = tierOf(fy25);
  const delay25 = delayMet(fy25);
  // Per draw d (the simulated FY 2026 measurement):
  //   FY 2028 bill — keyed to the elected FY 2025-or-FY 2026 rate, but $0
  //   whenever either year crosses the delay test (the delay is mechanical
  //   and election-independent).
  //   FY 2029 bill — keyed to the FY 2026 rate for every state (third
  //   preceding year), $0 when FY 2026 itself crosses (start moves to
  //   FY 2030, keyed to the unsimulated FY 2027).
  let win = 0, delay26 = 0;
  let lock28 = 0, elect28 = 0, elect28sq = 0, bill29 = 0;
  for (const d of draws) {
    if (d < fy25) win++;
    const crossed = delayMet(d);
    if (crossed) delay26++;
    const zero28 = delay25 || crossed;
    const l = zero28 ? 0 : (lockShare / 100) * st.issuance;
    const e = zero28 ? 0 : (tierOf(Math.min(d, fy25)) / 100) * st.issuance;
    lock28 += l;
    elect28 += e;
    elect28sq += e * e;
    bill29 += crossed ? 0 : (tierOf(d) / 100) * st.issuance;
  }
  const n = draws.length;
  const elect28Mean = elect28 / n;
  return {
    fy25,
    lockShare,
    delay25,
    lockTierCost: (lockShare / 100) * st.issuance,
    lock28: lock28 / n,
    elect28: elect28Mean,
    sd28: Math.sqrt(Math.max(0, elect28sq / n - elect28Mean * elect28Mean)),
    bill29: bill29 / n,
    pWin: win / n,
    pDelay26: delay26 / n,
  };
}

function summarize(rates, issuance) {
  let mean = 0;
  const pt = { 0: 0, 5: 0, 10: 0, 15: 0 };
  let eShare = 0, e2 = 0;
  for (const r of rates) {
    mean += r;
    const s = tierOf(r);
    pt[s]++;
    const d = (s / 100) * issuance;
    eShare += d; e2 += d * d;
  }
  mean /= rates.length;
  for (const k in pt) pt[k] /= rates.length;
  eShare /= rates.length;
  const sd = Math.sqrt(Math.max(0, e2 / rates.length - eShare * eShare));
  return { mean, pt, eShare, sd };
}

const cssVar = (name) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function histogram(el, base, scen, official) {
  const lo = Math.min(4, Math.floor(Math.min(...base, ...scen)) - 0.5);
  const hi = Math.max(12, Math.ceil(Math.max(...base, ...scen)) + 0.5);
  const W = chartWidth(el), narrow = W < 560;
  const bins = narrow ? 40 : 60, H = narrow ? 200 : 260, L = 34, R = 12, T = 12, B = 30;
  const bw = (hi - lo) / bins;
  const count = (rates) => {
    const c = new Array(bins).fill(0);
    for (const r of rates) {
      const b = Math.min(bins - 1, Math.max(0, Math.floor((r - lo) / bw)));
      c[b]++;
    }
    return c.map((v) => v / rates.length);
  };
  const cb = count(base), cs = count(scen);
  const ymax = Math.max(...cb, ...cs) * 1.12;
  const x = (r) => L + ((r - lo) / (hi - lo)) * (W - L - R);
  const y = (p) => T + (1 - p / ymax) * (H - T - B);
  const ink = cssVar("--muted-foreground") || "#475569";
  const border = cssVar("--border") || "#E2E8F0";
  const fill = cssVar("--chart-2") || "#0EA5E9";
  let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  const bands = [[lo, 6, 0], [6, 8, 5], [8, 10, 10], [10, hi, 15]];
  for (const [a, b, t] of bands) {
    if (b <= lo || a >= hi) continue;
    const xa = x(Math.max(a, lo)), xb = x(Math.min(b, hi));
    s += `<rect x="${xa}" y="${T}" width="${xb - xa}" height="${H - T - B}" fill="var(${TIER_VARS[t]})" opacity="0.10"/>`;
    s += `<text x="${(xa + xb) / 2}" y="${T + 13}" text-anchor="middle" font-size="10" fill="${ink}">${narrow ? `${t}%` : TIER_LABELS[t]}</text>`;
  }
  for (let b = 0; b < bins; b++) {
    if (cs[b] === 0) continue;
    const x0 = x(lo + b * bw) + 0.6, wpx = (W - L - R) / bins - 1.2;
    s += `<rect class="bin" data-b="${b}" x="${x0}" y="${y(cs[b])}" width="${wpx}" height="${y(0) - y(cs[b])}" rx="1.5" fill="${fill}" opacity="0.85"/>`;
  }
  let path = "";
  for (let b = 0; b < bins; b++) {
    const x0 = x(lo + b * bw), x1 = x(lo + (b + 1) * bw), yy = y(cb[b]);
    path += `${b === 0 ? "M" : "L"}${x0},${yy} L${x1},${yy} `;
  }
  s += `<path d="${path}" fill="none" stroke="${ink}" stroke-width="1.6" opacity="0.9"/>`;
  s += `<line x1="${x(official)}" x2="${x(official)}" y1="${T}" y2="${H - B}" stroke="${ink}" stroke-width="1.4" stroke-dasharray="4 3"/>`;
  const offLabel = `FY25 official ${official.toFixed(2)}%`;
  s += `<text class="halo" ${edgeLabel(x(official), offLabel, 10, W)} y="${H - B - 6}" font-size="10" fill="${ink}">${offLabel}</text>`;
  if (hi > DELAY_THRESHOLD) {
    const xd = x(DELAY_THRESHOLD);
    s += `<line x1="${xd}" x2="${xd}" y1="${T}" y2="${H - B}" stroke="${ink}" stroke-width="1" stroke-dasharray="2 3" opacity="0.7"/>`;
    const dl = narrow ? "delay" : "delay ≥13.34% → $0 in FY28";
    s += `<text ${edgeLabel(xd, dl, 10, W)} y="${T + 26}" font-size="10" fill="${ink}" opacity="0.85">${dl}</text>`;
  }
  const step = tickStep(hi - lo, W - L - R);
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    s += `<line x1="${x(v)}" x2="${x(v)}" y1="${H - B}" y2="${H - B + 4}" stroke="${border}"/>`;
    s += `<text x="${x(v)}" y="${H - 8}" text-anchor="middle" font-size="10" fill="${ink}">${v}%</text>`;
  }
  s += `<line x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}" stroke="${border}"/>`;
  s += "</svg>";
  el.innerHTML = s;
  el.querySelectorAll(".bin").forEach((r) => {
    r.addEventListener("mousemove", (ev) => {
      const b = +r.dataset.b;
      const a = lo + b * bw;
      tooltip.textContent = `${a.toFixed(1)}–${(a + bw).toFixed(1)}%: ${(cs[b] * 100).toFixed(1)}% of draws (baseline ${(cb[b] * 100).toFixed(1)}%)`;
      tooltip.style.left = ev.clientX + 12 + "px";
      tooltip.style.top = ev.clientY + 12 + "px";
      tooltip.hidden = false;
    });
    r.addEventListener("mouseleave", () => (tooltip.hidden = true));
  });
}

function tierBars(el, rows, issuance) {
  const W = chartWidth(el), H = 46 * rows.length + 8, L = 70, R = 12;
  const ink = cssVar("--muted-foreground") || "#475569";
  let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  rows.forEach(([name, pt], i) => {
    const y0 = 8 + i * 46;
    s += `<text x="0" y="${y0 + 20}" font-size="12" fill="${ink}">${name}</text>`;
    let xacc = L;
    for (const t of [0, 5, 10, 15]) {
      const w = pt[t] * (W - L - R);
      if (w <= 0) continue;
      s += `<rect class="seg" data-t="${t}" data-p="${pt[t]}" data-row="${name}" x="${xacc}" y="${y0}" width="${Math.max(0, w - 2)}" height="30" rx="3" fill="var(${TIER_VARS[t]})"/>`;
      if (pt[t] >= 0.07 && w >= 64) {
        const darkMode = document.documentElement.classList.contains("dark");
        const light = darkMode ? t >= 10 : t <= 5;
        const cost = t > 0 && pt[t] >= 0.18 && w >= 150 ? ` · ${fmtM((t / 100) * issuance)}/yr` : "";
        s += `<text x="${xacc + w / 2}" y="${y0 + 20}" text-anchor="middle" font-size="11" fill="${light ? "#1E293B" : "white"}">${TIER_LABELS[t].split(" ")[0]} · ${(pt[t] * 100).toFixed(0)}%${cost}</text>`;
      }
      xacc += w;
    }
  });
  s += "</svg>";
  el.innerHTML = s;
  el.querySelectorAll(".seg").forEach((r) => {
    r.addEventListener("mousemove", (ev) => {
      const t = +r.dataset.t;
      const cost = t > 0 ? ` — ${fmtM((t / 100) * issuance)}/yr if it lands there` : " — no state share";
      tooltip.textContent = `${r.dataset.row}: ${(r.dataset.p * 100).toFixed(1)}% chance of the ${TIER_LABELS[t]} tier${cost}`;
      tooltip.style.left = ev.clientX + 12 + "px";
      tooltip.style.top = ev.clientY + 12 + "px";
      tooltip.hidden = false;
    });
    r.addEventListener("mouseleave", () => (tooltip.hidden = true));
  });
}

// ---- All-states baseline table -------------------------------------------

const NAT = new Map(); // code -> {code, official, tier, pmis, eShare, sd, verified}
let natSort = { k: "pmis", dir: -1 };

function computeNational() {
  const codes = Object.keys(DATA.states);
  let i = 0;
  const step = () => {
    const t0 = performance.now();
    while (i < codes.length && performance.now() - t0 < 40) {
      const code = codes[i++];
      const st = DATA.states[code];
      const draws = simulate(st, {});
      const sm = summarize(draws, st.issuance);
      const el = electionStats(st, draws);
      const tier = tierOf(st.official_fy2025);
      const adopt = adoptStats(st, code, null);
      NAT.set(code, {
        code,
        name: nameOf(code),
        official: st.official,
        fy2025: st.official_fy2025,
        tier,
        delay25: el.delay25,
        pmis: 1 - sm.pt[tier],
        eShare: el.elect28,
        bill29: el.bill29,
        sd: el.sd28,
        adoptStrict28: adopt ? adopt.strict.el.elect28 : null,
        adoptBroad28: adopt ? adopt.broad.el.elect28 : null,
        verified: !!st.verified,
      });
    }
    renderNatTable();
    if (i < codes.length) setTimeout(step, 40); // leave the main thread room to paint
    else renderNatTakeaway();
  };
  step();
}

function renderNatTakeaway() {
  const rows = [...NAT.values()];
  const flip = rows.filter((r) => r.pmis >= 0.4).length;
  const delayed = rows.filter((r) => r.delay25).length;
  const totalE = rows.reduce((a, r) => a + r.eShare, 0);
  const withAdopt = rows.filter((r) => r.adoptStrict28 !== null);
  const adoptLine =
    withAdopt.length === rows.length
      ? ` If every jurisdiction adopted a verified rules engine, the same sum falls to ` +
        `${fmtM(withAdopt.reduce((a, r) => a + r.adoptBroad28, 0))}–` +
        `${fmtM(withAdopt.reduce((a, r) => a + r.adoptStrict28, 0))} a year under the broad-to-strict ` +
        `accounting scenarios in the adoption panel of the analyst tools.`
      : "";
  // The FY 2024→2025 counts come from analysis/fy2025_movement.json (18
  // tier changes, 7 of them among the 10 moves beyond the two-year noise
  // band); tests/test_front_page.py locks this copy to that artifact.
  $("nat-takeaway").textContent =
    `At FY 2025 official rates and FY 2024 sample sizes, ${flip} of ${rows.length} jurisdictions have at least a 40% chance ` +
    `that a QC-sized FY 2026 measurement lands in a different cost-share tier than their locked FY 2025 rate. Expected FY 2028 ` +
    `bills, each jurisdiction electing its better year and net of delayed starts, sum to ${fmtM(totalE)} a year. ${delayed} jurisdictions ` +
    `above the 13.33% delay threshold owe nothing for FY 2028 and are first billed in FY 2029, keyed to the FY 2026 rate. Between FY 2024 and ` +
    `FY 2025, 18 jurisdictions changed tiers, and 11 of those 18 changes sit inside the two-year sampling-noise band.` +
    adoptLine;
}

function renderNatTable() {
  const { k, dir } = natSort;
  const rows = [...NAT.values()].sort((a, b) => {
    const va = a[k], vb = b[k];
    return (typeof va === "string" ? va.localeCompare(vb) : va - vb) * dir;
  });
  const body = document.querySelector("#nat-table tbody");
  body.innerHTML = rows
    .map(
      (r) => `<tr data-code="${r.code}" class="${r.code === $("state").value ? "current" : ""}">
      <th scope="row">${r.name}${r.verified ? ' <span class="vmark" title="Benefit arithmetic reproduced for every replayable FY 2024 QC case; eligibility untested">✓</span>' : ""}</th>
      <td class="num">${r.official.toFixed(2)}%</td>
      <td class="num">${r.fy2025.toFixed(2)}%</td>
      <td><span class="dot" style="background:var(${TIER_VARS[r.tier]})"></span>${TIER_LABELS[r.tier]}${r.delay25 ? ' <span class="delaytag" title="Rate × 1.5 ≥ 20%: $0 in FY 2028, first bill FY 2029 keyed to the FY 2026 rate">delayed</span>' : ""}</td>
      <td class="num">${(r.pmis * 100).toFixed(0)}%</td>
      <td class="num">${r.delay25 ? `${fmtM(r.bill29)} <span class="muted">FY29</span>` : fmtM(r.eShare)}</td>
      <td class="num">${fmtM(r.sd)}</td>
    </tr>`
    )
    .join("");
  const pending = Object.keys(DATA.states).length - NAT.size;
  $("nat-note").textContent = pending > 0 ? `Computing… ${NAT.size}/${NAT.size + pending}` : "";
  document.querySelectorAll("#nat-table th button").forEach((b) => {
    b.classList.toggle("sorted", b.dataset.k === k);
    b.classList.toggle("desc", b.dataset.k === k && dir === -1);
  });
  body.querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("click", () => {
      $("state").value = tr.dataset.code;
      $("state").dispatchEvent(new Event("change"));
      $("answer").scrollIntoView({ behavior: "smooth" });
    });
  });
}

// ---- URL state -----------------------------------------------------------

function readUrl() {
  const p = new URLSearchParams(location.search);
  const st = p.get("state");
  if (st && DATA.states[st]) $("state").value = st;
  if (p.get("audits")) $("audits").value = Math.min(1000, Math.max(0, +p.get("audits") || 0));
  if (p.get("drift") === "1") $("lever-drift").checked = true;
  // Legacy accounting-lever params (levers, eff, mode) are ignored: those
  // scenarios suppressed observed error dollars by finding category, which
  // is an accounting bound, not a prediction, and were removed 2026-08-07.
  const smd = p.get("smd") === "1", engine = p.get("engine") === "1";
  // A shared link that carries any analyst setting opens the analyst tools.
  if (smd || engine || p.get("drift") === "1" || +p.get("audits") || location.hash === "#analyst")
    $("analyst").open = true;
  return { smd, engine };
}

function writeUrl() {
  const p = new URLSearchParams();
  p.set("state", $("state").value);
  if (+$("audits").value) p.set("audits", $("audits").value);
  if ($("lever-smd").checked) p.set("smd", "1");
  if ($("lever-drift").checked) p.set("drift", "1");
  if ($("engine-mode").checked) p.set("engine", "1");
  history.replaceState(null, "", "?" + p.toString());
  if (FRAMED) {
    // The AppPage shell listens for urlUpdate and mirrors the params onto
    // the parent address bar so copied links keep the app state.
    window.parent.postMessage({ type: "urlUpdate", params: p.toString() }, "*");
  }
}

// ---- Model-based scenario engine -----------------------------------------
// The scenario draws each case's deviation from the fitted distribution in
// model_data.json, mirroring analysis/predictive_process.py: piecewise-linear
// inverse CDF over [log(tolerance), q05..q99] in log-dollar space, exponential
// tail in logs beyond q99, error dollars = |D| strictly above the threshold.
// model_scenarios.json supplies each state's SMD-flipped per-case parameters
// as a sparse patch, valid only against the exact model_data.json it pins by
// SHA-256 (verified at load). Both endpoints are anchored so the model's own
// baseline mean sits at the official rate; the per-state raw-level gap is
// documented in analysis/FINDINGS.md and gates seven states out entirely.

let MODEL = null;        // model_data.json payload
let SCEN = null;         // model_scenarios.json payload
let ARTIFACTS = null;    // load promise
let ARTIFACT_ERROR = null;
let MODEL_PREP = {};     // per-state baseline arrays
let PATCH_PREP = {};     // per-state SMD-flipped arrays

async function loadModelArtifacts() {
  if (!ARTIFACTS) {
    ARTIFACTS = (async () => {
      const [mdRes, scRes] = await Promise.all([
        fetch("model_data.json?v=" + ASSET_V),
        fetch("model_scenarios.json?v=" + ASSET_V),
      ]);
      if (!mdRes.ok || !scRes.ok) throw new Error("model artifact fetch failed");
      const mdBytes = await mdRes.arrayBuffer();
      const scen = await scRes.json();
      if (scen.schema !== SCEN_SCHEMA)
        throw new Error(`unexpected scenario schema ${scen.schema}`);
      if (scen.delta_direction !== "adopted_minus_not_adopted")
        throw new Error("unexpected scenario delta direction");
      if (!scen.included_levers.includes("smd"))
        throw new Error("scenario export does not include the SMD lever");
      const digest = await crypto.subtle.digest("SHA-256", mdBytes);
      const hex = [...new Uint8Array(digest)]
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
      if (hex !== scen.base_model.sha256)
        throw new Error(
          `model_data.json sha256 ${hex.slice(0, 12)}… does not match the scenario export's pin ${scen.base_model.sha256.slice(0, 12)}…`
        );
      MODEL = JSON.parse(new TextDecoder().decode(mdBytes));
      SCEN = scen;
    })().catch((err) => {
      ARTIFACT_ERROR = err;
      throw err;
    });
  }
  return ARTIFACTS;
}

function prepModelState(code) {
  if (MODEL_PREP[code]) return MODEL_PREP[code];
  const st = MODEL.states[code];
  const n = st.n;
  const q = new Float64Array(n * 9);
  const minLog = Math.log(MODEL.deviation_tolerance);
  // The export guarantees floored, monotone quantile vectors (enforced at
  // predict time and re-validated at export). Assert rather than silently
  // repair with a non-equivalent operator.
  for (let i = 0; i < n; i++) {
    for (let k = 0; k < 9; k++) {
      const v = st.q[i][k];
      if (v < minLog) throw new Error(`model_data ${code}[${i}][${k}] below floor`);
      if (k > 0 && v < st.q[i][k - 1])
        throw new Error(`model_data ${code}[${i}] not monotone at ${k}`);
      q[i * 9 + k] = v;
    }
  }
  MODEL_PREP[code] = {
    n,
    w: Float64Array.from(st.w),
    wiss: Float64Array.from(st.w, (v, i) => v * st.iss[i]),
    pDev: Float64Array.from(st.p_dev),
    q,
    minLog,
    baseRates: null,
    baseMean: null,
  };
  return MODEL_PREP[code];
}

function prepPatchedState(code) {
  if (PATCH_PREP[code]) return PATCH_PREP[code];
  const base = prepModelState(code);
  const patch = SCEN.states[code].levers.smd.per_case;
  const idx = patch.i;
  if (idx.length !== patch.p_dev.length || idx.length !== patch.q.length)
    throw new Error(`scenario patch ${code}: ragged patch arrays`);
  const pDev = Float64Array.from(base.pDev);
  const q = Float64Array.from(base.q);
  let prev = -1;
  for (let r = 0; r < idx.length; r++) {
    const i = idx[r];
    if (!Number.isInteger(i) || i <= prev || i >= base.n)
      throw new Error(`scenario patch ${code}: bad index ${i}`);
    prev = i;
    const p = patch.p_dev[r];
    if (!(p >= 0 && p <= 1)) throw new Error(`scenario patch ${code}[${i}]: p_dev ${p}`);
    pDev[i] = p;
    const row = patch.q[r];
    if (row.length !== 9) throw new Error(`scenario patch ${code}[${i}]: quantile row length`);
    for (let k = 0; k < 9; k++) {
      const v = row[k];
      if (v < base.minLog) throw new Error(`scenario patch ${code}[${i}][${k}] below floor`);
      if (k > 0 && v < row[k - 1])
        throw new Error(`scenario patch ${code}[${i}] not monotone at ${k}`);
      q[i * 9 + k] = v;
    }
  }
  PATCH_PREP[code] = { n: base.n, w: base.w, wiss: base.wiss, pDev, q, minLog: base.minLog };
  return PATCH_PREP[code];
}

function simulateModel(ms, { extra = 0, seed = 11 } = {}) {
  const levels = MODEL.quantile_levels;
  const nodeLevels = [0].concat(levels);
  const q99 = levels[8];
  const tail = MODEL.tail_scale_log;
  const thr = MODEL.threshold;
  const n = ms.n, m = n + extra;
  const rng = mulberry32(seed);
  const rates = new Float64Array(DRAWS);
  for (let d = 0; d < DRAWS; d++) {
    let e = 0, s = 0;
    for (let j = 0; j < m; j++) {
      const i = (rng() * n) | 0;
      s += ms.wiss[i];
      if (rng() < ms.pDev[i]) {
        const u = rng();
        let logD;
        if (u >= q99) {
          logD = ms.q[i * 9 + 8] + tail * Math.log((1 - q99) / (1 - u));
        } else {
          let k = 0;
          while (k < 8 && u >= nodeLevels[k + 1]) k++;
          const leftLog = k === 0 ? ms.minLog : ms.q[i * 9 + k - 1];
          const rightLog = ms.q[i * 9 + k];
          const span = nodeLevels[k + 1] - nodeLevels[k];
          logD = leftLog + ((u - nodeLevels[k]) / span) * (rightLog - leftLog);
        }
        const absD = Math.exp(logD);
        if (absD > thr) e += ms.w[i] * absD;
      }
    }
    rates[d] = (100 * e) / s;
  }
  return rates;
}

function modelAnchor(code, official) {
  const ms = prepModelState(code);
  if (ms.baseMean === null) {
    ms.baseRates = simulateModel(ms, {});
    let sum = 0;
    for (const r of ms.baseRates) sum += r;
    ms.baseMean = sum / ms.baseRates.length;
  }
  return { rates: ms.baseRates, shift: official - ms.baseMean };
}

const shiftRates = (r, shift) => {
  const out = new Float64Array(r.length);
  for (let i = 0; i < r.length; i++) out[i] = r[i] + shift;
  return out;
};

// ---- Scenario control state ----------------------------------------------

function scenarioInfo(code) {
  if (!SCEN) return null;
  const state = SCEN.states[code];
  const lever = state?.levers?.smd;
  if (!lever) return null;
  // ci_lo/ci_hi bracket delta_pp (adopted − not adopted); the flip-from-
  // current-policy delta negates all three when the state already adopts.
  const sign = lever.baseline_adopted ? -1 : 1;
  return {
    gated: !!state.level_flag,
    ratio: state.level_ratio,
    adopted: lever.baseline_adopted,
    flipDelta: lever.baseline_to_patch_delta_pp,
    flipLo: sign > 0 ? lever.ci_lo : -lever.ci_hi,
    flipHi: sign > 0 ? lever.ci_hi : -lever.ci_lo,
    flips: lever.feature_flip_n,
  };
}

function syncScenarioControl() {
  const code = $("state").value;
  const box = $("lever-smd");
  const label = $("smd-label");
  const hint = $("smd-hint");
  if (ARTIFACT_ERROR) {
    box.checked = false;
    box.disabled = true;
    hint.textContent = `Model artifacts failed integrity checks and the scenario is unavailable: ${ARTIFACT_ERROR.message}`;
    return;
  }
  if (!SCEN) {
    box.disabled = false;
    label.textContent = "Flip the standard medical deduction";
    hint.textContent =
      "Re-predicts every case from the fitted error model with the state's SMD documentation feature reversed. Loads the model on first use.";
    return;
  }
  const info = scenarioInfo(code);
  if (!info) {
    box.checked = false;
    box.disabled = true;
    hint.textContent = "No model scenario is exported for this jurisdiction.";
    return;
  }
  label.textContent = info.adopted
    ? "Drop the standard medical deduction"
    : "Adopt the standard medical deduction";
  if (info.gated) {
    box.checked = false;
    box.disabled = true;
    hint.textContent =
      `Model output is disabled for this state: its factor-adjusted FY 2024 model-to-observed ` +
      `dollar-rate ratio (${info.ratio.toFixed(2)}) is outside the inclusive [0.7, 1.4] validation range.`;
    return;
  }
  box.disabled = false;
  hint.textContent =
    `Model association from re-predicting ${info.flips} flipped cases: ` +
    `${fmtPP(info.flipDelta)}pp expected threshold-crossing rate ` +
    `(95% CI ${fmtPP(info.flipLo)} to ${fmtPP(info.flipHi)}pp, ` +
    `${SCEN.uncertainty.draws.toLocaleString()} paired bootstrap draws). ` +
    `An association from burden features adding +0.006 ROC AUC — not a causal estimate.`;
}

function mechanismLine(scenarioOn, driftOn) {
  const engine = scenarioOn
    ? "Sampling engine: model-based — each draw samples cases and draws each case's deviation from its fitted distribution (baseline) or its SMD-flipped distribution (scenario); levels anchored to the official rate."
    : "Sampling engine: resamples the state's observed FY 2024 QC error dollars, centered on the official rate.";
  return driftOn
    ? engine +
        " Drift on: each draw adds year-to-year program movement, a normal draw with a 1.07-point standard deviation, calibrated to the single realized FY 2024→2025 transition."
    : engine;
}

// ---- FY 2027 measurement-year panel --------------------------------------
// Static repriced bands from the committed FY2027-mode payload: the
// mechanical rate under future-year parameters and composition, re-anchored
// at the official FY 2025 level, bracketed by the two deviation-carry
// accounting conventions (each case's recorded deviation carried as fixed
// dollars, or in proportion to its repriced benefit). Verified states only;
// no case-level repricing exists for the other 46.

function fy2027BandSvg(st27, W = 920) {
  // Widen past 16% when a band end or the official rate runs higher, leaving
  // two points of room for the value label beside the dot.
  const vals = ["2026", "2027"].flatMap((y) => [st27.bands[y].anchored_fixed_pct, st27.bands[y].anchored_proportional_pct]);
  const lo = 4, hi = Math.max(16, Math.ceil(Math.max(...vals, st27.official_fy2025_pct)) + 2);
  const H = 128, L = 52, R = 12, T = 8, B = 26;
  const x = (r) => L + ((Math.min(Math.max(r, lo), hi) - lo) / (hi - lo)) * (W - L - R);
  const ink = cssVar("--muted-foreground") || "#475569";
  const border = cssVar("--border") || "#E2E8F0";
  let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  const bands = [[lo, 6, 0], [6, 8, 5], [8, 10, 10], [10, hi, 15]];
  for (const [a, b, t] of bands) {
    s += `<rect x="${x(a)}" y="${T}" width="${x(b) - x(a)}" height="${H - T - B}" fill="var(${TIER_VARS[t]})" opacity="0.10"/>`;
    s += `<text x="${(x(a) + x(b)) / 2}" y="${T + 12}" text-anchor="middle" font-size="10" fill="${ink}">${W < 560 ? `${t}%` : TIER_LABELS[t]}</text>`;
  }
  const dth = x(DELAY_THRESHOLD);
  s += `<line x1="${dth}" x2="${dth}" y1="${T}" y2="${H - B}" stroke="${ink}" stroke-width="1" stroke-dasharray="2 3" opacity="0.7"/>`;
  const rows = [
    ["FY 2026", st27.bands["2026"], 46],
    ["FY 2027", st27.bands["2027"], 78],
  ];
  for (const [label, band, y] of rows) {
    const a = x(band.anchored_fixed_pct), b = x(band.anchored_proportional_pct);
    s += `<text x="2" y="${y + 4}" font-size="11" fill="${ink}">${label}</text>`;
    s += `<line x1="${Math.min(a, b)}" x2="${Math.max(a, b)}" y1="${y}" y2="${y}" stroke="var(--primary)" stroke-width="6" stroke-linecap="round" opacity="0.85"/>`;
    for (const [px, anchor] of [[a, "end"], [b, "start"]]) {
      s += `<circle cx="${px}" cy="${y}" r="4" fill="var(--primary)"/>`;
    }
    s += `<text x="${Math.min(a, b) - 6}" y="${y + 4}" text-anchor="end" font-size="10" fill="${ink}">${Math.min(band.anchored_fixed_pct, band.anchored_proportional_pct).toFixed(1)}%</text>`;
    s += `<text x="${Math.max(a, b) + 6}" y="${y + 4}" font-size="10" fill="${ink}">${Math.max(band.anchored_fixed_pct, band.anchored_proportional_pct).toFixed(1)}%</text>`;
  }
  const off = x(st27.official_fy2025_pct);
  s += `<line x1="${off}" x2="${off}" y1="${T}" y2="${H - B}" stroke="${ink}" stroke-width="1.4" stroke-dasharray="4 3"/>`;
  const ol = `FY25 official ${st27.official_fy2025_pct.toFixed(2)}%`;
  s += `<text ${edgeLabel(off, ol, 10, W)} y="${H - B - 4}" font-size="10" fill="${ink}">${ol}</text>`;
  for (let v = lo, step = tickStep(hi - lo, W - L - R); v <= hi; v += step) {
    s += `<text x="${x(v)}" y="${H - 8}" text-anchor="middle" font-size="10" fill="${ink}">${v}%</text>`;
  }
  s += `<line x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}" stroke="${border}"/>`;
  return s + "</svg>";
}

function renderFy2027(code) {
  const el = $("fy2027-body");
  if (!FY27) { el.textContent = "FY 2027 payload unavailable."; return; }
  const name = nameOf(code);
  const st27 = FY27.states[code];
  const t27 = FY27.thresholds["2027"];
  const projMax = FY27.fy2027_max_allotment_4p_48dc.dollars;
  const projected =
    projMax !== FY27_MAX_4P_PUBLISHED || t27.threshold_dollars_strictly_greater_than !== FY27_TOLERANCE_PUBLISHED;
  // 7 CFR 272.2(e)(4)(ii): major sampling-plan changes go to FNS for approval
  // at least 60 days before implementation, minor ones at least 30.
  const facts =
    `<p>FY 2027 began October 1, 2026 and runs through September 30, 2027. Its rate sets each state's FY 2030 bill, ` +
    `and two kinds of change still reach it. How a state runs SNAP from here shows up in the months not yet sampled. ` +
    `And a state can change its QC sampling plan with FNA approval, filed at least 60 days before a major change takes effect ` +
    `or 30 days before a minor one (7 CFR 272.2(e)(4)).</p>` +
    `<p class="sub">FNA's FY 2027 cost-of-living notice (August 21, 2026) set the 48-state four-person maximum allotment at ` +
    `$${FY27_MAX_4P_PUBLISHED.toLocaleString()}. QC disregards FY 2027 errors of $${FY27_TOLERANCE_PUBLISHED} or less ` +
    `(7 U.S.C. 2025(c)(1)(A)(ii), from the June 2026 Thrifty Food Plan cost of $${FY27_TFP_JUNE_2026.toLocaleString("en-US", { minimumFractionDigits: 2 })}).</p>`;
  if (!st27) {
    el.innerHTML =
      facts +
      `<p class="sub">Repriced FY 2027 projections need a verified encoding of the state's rules. ${possessive(name)} rules are not yet independently verified, so no case-level repricing exists for it. Parameter-scaling inputs ship in the committed artifacts.</p>`;
    return;
  }
  const b27 = st27.bands["2027"];
  const loP = Math.min(b27.anchored_fixed_pct, b27.anchored_proportional_pct);
  const hiP = Math.max(b27.anchored_fixed_pct, b27.anchored_proportional_pct);
  el.innerHTML =
    facts +
    `<p class="sub">Repricing ${possessive(name)} FY 2024 cases under ${projected ? "projected " : ""}FY 2027 parameters and a projected caseload mix, then re-anchoring at its official FY 2025 rate, puts its mechanical FY 2027 rate between <strong>${loP.toFixed(1)}%</strong> and <strong>${hiP.toFixed(1)}%</strong>. ` +
    `The range comes from one accounting choice: whether each case's recorded error carries forward as the same dollar amount or in proportion to its repriced benefit. ` +
    `It is not a confidence interval, and neither end predicts how the state will behave.` +
    (projected
      ? ` The projected parameters predate FNA's notice (a $${projMax.toLocaleString()} maximum allotment against the published ` +
        `$${FY27_MAX_4P_PUBLISHED.toLocaleString()}), so this range is provisional until it is rerun on the published values.`
      : "") +
    `</p>` +
    `<div class="chart" role="img" aria-label="Anchored FY 2026 and FY 2027 repriced bands across cost-share tiers">${fy2027BandSvg(st27, chartWidth(el))}</div>`;
}

// ---- Axiom rules-engine comparison mode ----------------------------------
// The engine mode surfaces precomputed verification artifacts: the committed
// axiom-oracles suite reports (stage-by-stage parity of the Axiom RuleSpec
// computation against the QC file's computed benefit chain) and
// the formula-benefit divergence catalog built by analysis/engine_comparison.py.
// It does not change the Monte Carlo simulation — engine runs are precomputed,
// never recomputed in the browser.

let ENGINE = null;         // engine_data.json payload
let ENGINE_LOAD = null;    // load promise
let ENGINE_ERROR = null;

async function loadEngineArtifact() {
  if (!ENGINE_LOAD) {
    ENGINE_LOAD = (async () => {
      const res = await fetch("engine_data.json?v=" + ASSET_V);
      if (!res.ok) throw new Error("engine artifact fetch failed");
      const bytes = await res.arrayBuffer();
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      const hex = [...new Uint8Array(digest)]
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
      if (hex !== ENGINE_DATA_SHA256)
        throw new Error(
          `engine_data.json sha256 ${hex.slice(0, 12)}… does not match the committed pin ${ENGINE_DATA_SHA256.slice(0, 12)}…`
        );
      const payload = JSON.parse(new TextDecoder().decode(bytes));
      if (payload.schema !== ENGINE_SCHEMA)
        throw new Error(`unexpected engine schema ${payload.schema}`);
      ENGINE = payload;
    })().catch((err) => {
      ENGINE_ERROR = err;
      throw err;
    });
  }
  return ENGINE_LOAD;
}

const pct = (share, digits = 1) => (100 * share).toFixed(digits) + "%";

function enginePanelBody(code) {
  const st = ENGINE.states[code];
  const totals = ENGINE.totals;
  const nat = ENGINE.national;
  const prov = ENGINE.provenance;
  const provLine =
    `<p class="engine-prov">Suite reports committed in ` +
    `<a href="https://github.com/TheAxiomFoundation/axiom-oracles">axiom-oracles</a> @ ${prov.oracle_commit.slice(0, 12)} ` +
    `(byte-identical copies and SHA-256 pins in <a href="https://github.com/PolicyEngine/snap-qc-sim/tree/main/paper/snapshot/oracle-suites">this repository</a>); ` +
    `QC source archive ${prov.qc_archive_sha256.slice(0, 12)}…; toolchain pinned by the Colorado reproducibility probe ` +
    `(<a href="https://github.com/PolicyEngine/snap-qc-sim/tree/main/paper/snapshot/cert">paper/snapshot/cert</a>): ` +
    `engine ${prov.certified_toolchain.engine_commit.slice(0, 12)} × rulespec-us ${prov.certified_toolchain.rulespec_us_commit.slice(0, 12)}. ` +
    `Catalog: <a href="https://github.com/PolicyEngine/snap-qc-sim/blob/main/analysis/ENGINE_COMPARISON.md">analysis/ENGINE_COMPARISON.md</a> · ` +
    `<a href="https://axiom.org/reports/colorado-snap-qc-fy2024">example state report</a></p>`;
  const conflates =
    `<h3>What the formula benefit conflates with error</h3>` +
    `<p>The file records three benefit anchors per case: the allotment the state issued (RAWBEN), ` +
    `the allotment corrected for the reviewer's findings (BENFIX), and the formula benefit Mathematica ` +
    `computes for USDA from the edited record with the QC Minimodel's benefit formula (FSBEN). |RAWBEN − BENFIX| equals the recorded error amount for every ` +
    `official-universe case in the seven verified states — nationally ${pct(nat.concordance_weighted.benfix, 3)} of ` +
    `weighted FY 2024 cases. Taking the formula benefit as the error anchor instead — |RAWBEN − FSBEN| — matches ` +
    `the recorded error for only ${pct(nat.concordance_weighted.fsben, 1)} weighted: a formula recomputation alone ` +
    `conflates recorded allotment adjustments with error. This simulator's deviation measure therefore anchors to ` +
    `BENFIX, and the engine exposes the full six-stage chain rather than one formula number.</p>`;
  if (!st) {
    return (
      `<p>This jurisdiction's encoded rules are not yet engine-verified. Across the seven states that are ` +
      `(CO, NY, CA, AZ, GA, MD, TX), the Axiom RuleSpec computation reproduces the QC file's recorded benefit ` +
      `chain for all ${totals.compared.toLocaleString()} replayable FY 2024 reviews — ` +
      `${totals.stage_cells.toLocaleString()} stage comparisons, zero tolerance, ` +
      `${totals.excluded} enumerated exclusions. Interested in verification for your state? ` +
      `<a href="mailto:hello@policyengine.org">hello@policyengine.org</a></p>` +
      conflates +
      provLine
    );
  }
  const cat = st.catalog;
  const cls = cat.classes;
  const adj = cls.allotment_adjustment;
  const corr = cls.error_correction_arithmetic;
  const rec = cls.recorded_correct_nonformula;
  const chips = st.stages
    .map(
      (s) =>
        `<span class="stage-chip" title="Zero-tolerance match of the engine's ${s.label} against the QC file's recorded value for every compared case"><span class="n">${s.matched}/${s.n}</span>${s.label}</span>`
    )
    .join("");
  const excl = st.excluded
    ? ` ${st.excluded} SSI-CAP standardized-benefit cases are excluded — an enumerated program-structure class using a separate benefit procedure (NYSCAP units follow the regular chain and are in scope).`
    : "";
  return (
    `<p><strong>${code}: the engine reproduces the file's recorded benefit chain for all ` +
    `${st.compared} replayable FY 2024 reviews</strong> — every stage below exact at zero tolerance.${excl} ` +
    `QC-adjudicated deductions, utility allowances, and eligibility findings enter as inputs, so parity ` +
    `checks the downstream benefit arithmetic given those intermediates and leaves eligibility untested.</p>` +
    `<div class="stage-chips">${chips}</div>` +
    conflates +
    `<p>In ${code}, the formula benefit differs from the corrected allotment for ` +
    `${cat.divergent} of ${cat.universe} cases (${pct(cat.divergent_weighted_share)} weighted) — the divergence catalog:</p>` +
    `<ul class="catalog-list">` +
    `<li><strong>Coded allotment adjustments:</strong> ${adj.n} cases (${adj.prorated_n} prorated benefits; ` +
    `${adj.no_error_n} with no recorded error at all — pure adjustments a formula-anchor would mislabel as error)</li>` +
    `<li><strong>Error-correction arithmetic:</strong> ${corr.n} cases where the reviewer's corrected allotment ` +
    `differs from the full recomputation (${corr.within_rounding_band_n} within $2, rounding-scale)</li>` +
    `<li><strong>Recorded-correct issuance outside the formula chain:</strong> ${rec.n} cases the review judged ` +
    `correct as issued (${rec.ssi_cap_coded_n} SSI-CAP-coded, ${rec.minimum_benefit_n} minimum-benefit)</li>` +
    `</ul>` +
    `<p class="hint">Counts are accounting classes recorded in the public file (ALLADJ, AMTERR, SSI_CAP, FSMINBEN), ` +
    `not causal attributions. The Monte Carlo simulation above is unchanged in this view: engine runs are ` +
    `precomputed verification artifacts, and the engine does not yet recompute counterfactual scenarios in this app.</p>` +
    provLine
  );
}

function renderEnginePanel() {
  const panel = $("engine-panel");
  const on = $("engine-mode").checked;
  panel.hidden = !on;
  if (!on) return;
  const body = $("engine-body");
  if (ENGINE_ERROR) {
    body.innerHTML = `<p>The engine comparison artifact failed its integrity check and this view is unavailable: ${ENGINE_ERROR.message}</p>`;
    return;
  }
  if (!ENGINE) {
    body.innerHTML = `<p>Loading the verification artifact…</p>`;
    return;
  }
  body.innerHTML = enginePanelBody($("state").value);
}

// ---- Rules-engine adoption panel -----------------------------------------
// Answers "what is adopting a verified rules engine worth" as accounting
// scenarios: per case, zero out the error dollars whose recorded QC cause codes
// sit in a computing-apparatus class (any-presence credits the whole case),
// re-anchor at official × (1 − class share of official error dollars), and
// re-run the same Monte Carlo through the FY 2026 election and delay math.
// FY 2025 stays locked history, so adoption flows only through the simulated
// FY 2026 measurement — exactly the counterfactual's shape. The strict and
// broad classes bracket the bound; neither is a causal adoption estimate.

let ADOPT = null;
let ADOPT_ERROR = null;

async function loadAdoptArtifact() {
  const res = await fetch("engine_scenario_data.json?v=" + ASSET_V);
  if (!res.ok) throw new Error("adoption artifact fetch failed");
  const bytes = await res.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const hex = [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  if (hex !== ADOPT_DATA_SHA256)
    throw new Error(
      `engine_scenario_data.json sha256 ${hex.slice(0, 12)}… does not match the committed pin ${ADOPT_DATA_SHA256.slice(0, 12)}…`
    );
  const payload = JSON.parse(new TextDecoder().decode(bytes));
  if (payload.schema !== ADOPT_SCHEMA)
    throw new Error(`unexpected adoption schema ${payload.schema}`);
  ADOPT = payload;
}

// The file-sample weighted rate for an error vector — simulate()'s `point`.
function pointRate(st, err) {
  let e = 0, s = 0;
  for (let i = 0; i < err.length; i++) {
    e += st.w[i] * err[i];
    s += st.w[i] * st.iss[i];
  }
  return (100 * e) / s;
}

// Additive anchor convention: the official rate exceeds the file rate by a
// federal re-review layer the app everywhere treats as a FIXED offset
// (simulate() centers as official + draw − point). Removing the flagged
// dollars lowers the file rate by (point0 − point1) percentage points, and
// the anchor shifts by exactly that — never scaled onto the adjustment
// layer, which the file's cause coding says nothing about.
function adoptDraws(st, flags, drift) {
  const err = st.err.map((e, i) => (flags[i] ? 0 : e));
  const anchor =
    st.official_fy2025 - (pointRate(st, st.err) - pointRate(st, err));
  return { draws: addDrift(simulate({ ...st, err }, { anchor }), drift), anchor };
}

function adoptStats(st, code, drift) {
  const ad = ADOPT?.states[code];
  if (
    !ad ||
    ad.any_strict.length !== st.err.length ||
    ad.any_broad.length !== st.err.length
  )
    return null;
  const out = {};
  for (const [key, flags] of [["strict", ad.any_strict], ["broad", ad.any_broad]]) {
    const share = ad.shares["any_" + key];
    const { draws, anchor } = adoptDraws(st, flags, drift);
    out[key] = {
      share,
      center: anchor,
      el: electionStats(st, draws),
    };
  }
  return out;
}

function adoptionBandSvg(official, strict, broad, W = 920) {
  const lo = 0, hi = Math.max(16, Math.ceil(official) + 1);
  // Labels sit on their own rows: the value pair above the range bar and the
  // official rate below it. Side-by-side labels collided whenever a band end
  // sat near the official rate, which is most states.
  const narrow = W < 560;
  const H = 112, L = 52, R = 12, T = 8, B = 26;
  const x = (r) => L + ((Math.min(Math.max(r, lo), hi) - lo) / (hi - lo)) * (W - L - R);
  const ink = cssVar("--muted-foreground") || "#475569";
  const border = cssVar("--border") || "#E2E8F0";
  let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  const bands = [[lo, 6, 0], [6, 8, 5], [8, 10, 10], [10, hi, 15]];
  for (const [a, b, t] of bands) {
    s += `<rect x="${x(a)}" y="${T}" width="${x(b) - x(a)}" height="${H - T - B}" fill="var(${TIER_VARS[t]})" opacity="0.10"/>`;
    s += `<text x="${(x(a) + x(b)) / 2}" y="${T + 12}" text-anchor="middle" font-size="10" fill="${ink}">${narrow ? `${t}%` : TIER_LABELS[t]}</text>`;
  }
  // The delay threshold drives the panel's nonmonotonicity — draw it like
  // the FY 2027 band chart so crossings are visible at a glance.
  const dth = x(DELAY_THRESHOLD);
  const dl = narrow ? "delay" : "delay 13.33%";
  s += `<line x1="${dth}" x2="${dth}" y1="${T}" y2="${H - B}" stroke="${ink}" stroke-width="1" stroke-dasharray="2 3" opacity="0.7"/>`;
  s += `<text ${edgeLabel(dth, dl, 9, W, 3)} y="${T + 24}" font-size="9" fill="${ink}" opacity="0.85">${dl}</text>`;
  const y = 60;
  const a = x(broad), b = x(strict);
  s += `<text x="2" y="${y + 4}" font-size="11" fill="${ink}">FY 2026</text>`;
  s += `<line x1="${Math.min(a, b)}" x2="${Math.max(a, b)}" y1="${y}" y2="${y}" stroke="var(--primary)" stroke-width="6" stroke-linecap="round" opacity="0.85"/>`;
  s += `<circle cx="${a}" cy="${y}" r="4" fill="var(--primary)"/><circle cx="${b}" cy="${y}" r="4" fill="var(--primary)"/>`;
  const pair = `broad ${broad.toFixed(1)}% · strict ${strict.toFixed(1)}%`;
  const pw = textW(pair, 10);
  const px = Math.min(Math.max((a + b) / 2, L + pw / 2), W - 2 - pw / 2);
  s += `<text x="${px}" y="${y - 10}" text-anchor="middle" font-size="10" fill="${ink}">${pair}</text>`;
  const off = x(official);
  const ol = narrow ? `FY25 ${official.toFixed(2)}%` : `FY25 official ${official.toFixed(2)}%`;
  s += `<line x1="${off}" x2="${off}" y1="${T}" y2="${H - B}" stroke="${ink}" stroke-width="1.4" stroke-dasharray="4 3"/>`;
  s += `<text ${edgeLabel(off, ol, 10, W)} y="${H - B - 4}" font-size="10" fill="${ink}">${ol}</text>`;
  for (let v = lo, step = tickStep(hi - lo, W - L - R); v <= hi; v += step) {
    s += `<text x="${x(v)}" y="${H - 8}" text-anchor="middle" font-size="10" fill="${ink}">${v}%</text>`;
  }
  s += `<line x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}" stroke="${border}"/>`;
  return s + "</svg>";
}

function renderAdoption(code, st, elec, drift) {
  const el = $("adoption-body");
  if (ADOPT_ERROR) {
    el.innerHTML = `<p>The adoption artifact failed its integrity check and this panel is unavailable: ${ADOPT_ERROR.message}</p>`;
    return;
  }
  if (!ADOPT) {
    el.textContent = "Adoption scenario artifact unavailable.";
    return;
  }
  const a = adoptStats(st, code, drift);
  if (!a) {
    el.textContent = "No case-aligned cause coding is available for this jurisdiction.";
    return;
  }
  const s = a.strict, b = a.broad;
  const pctShare = (v) => (100 * v).toFixed(1) + "%";
  const strictZero = s.share === 0;
  const shares =
    `<p class="sub">QC reviewers code up to nine causes per error. The <strong>strict</strong> class — computer programming, ` +
    `computer-generated mass change, arithmetic computation — carries <strong>${pctShare(s.share)}</strong> of this state's ` +
    `FY 2024 official error dollars; adding policy misapplication, computer-user error, and incorrect budgeting ` +
    `(<strong>broad</strong>) carries <strong>${pctShare(b.share)}</strong>. Removing those dollars centers a simulated ` +
    `FY 2026 measurement at <strong>${s.center.toFixed(2)}%</strong> (strict) to <strong>${b.center.toFixed(2)}%</strong> (broad), ` +
    `against the ${st.official_fy2025.toFixed(2)}% official FY 2025 level.` +
    (strictZero ? " This state's file codes no strict-class dollars, so the strict bound equals the baseline." : "") +
    `</p>`;
  const band = `<div class="chart" role="img" aria-label="Simulated FY 2026 rate under rules-engine adoption, broad and strict accounting scenarios across cost-share tiers">${adoptionBandSvg(st.official_fy2025, s.center, b.center, chartWidth(el))}</div>`;
  let dollars;
  if (elec.delay25) {
    dollars =
      `<p class="sub">This state's FY 2025 rate already meets the delay clause — $0 in FY 2028 — and at baseline ` +
      `${(100 * elec.pDelay26).toFixed(0)}% of simulated FY 2026 measurements cross the same test, deferring the first bill ` +
      `again to FY 2030, keyed to the FY 2027 rate this simulation does not price (see the FY 2027 panel). Expected FY 2029 ` +
      `bill at baseline: ${fmtM(elec.bill29)}/yr. Under adoption, fewer simulated FY 2026 measurements cross ` +
      `(${(100 * s.el.pDelay26).toFixed(0)}% strict / ${(100 * b.el.pDelay26).toFixed(0)}% broad), so billing more often starts ` +
      `in FY 2029, keyed to that lower FY 2026 rate: ${fmtM(s.el.bill29)} (strict) to ${fmtM(b.el.bill29)} (broad)/yr expected. ` +
      `Deferral is not forgiveness — a lower measured rate starts billing sooner at a lower rate, while deferral keys the first ` +
      `bill to a later, unsimulated year.</p>`;
  } else {
    const dS = elec.elect28 - s.el.elect28;
    const dB = elec.elect28 - b.el.elect28;
    const head =
      `<p class="sub">Through the FY 2026 election, the expected FY 2028 bill moves from <strong>${fmtM(elec.elect28)}/yr</strong> ` +
      `to <strong>${fmtM(b.el.elect28)}</strong> (broad) – <strong>${fmtM(s.el.elect28)}</strong> (strict)/yr`;
    // The election keys FY 2028 to min(draw, FY 2025), so a lower measured
    // rate can only reduce the billed tier; the one channel that can raise
    // the expected bill is the delay clause — fewer draws crossing 13.33%
    // means fewer deferrals to later, unsimulated years.
    const tail =
      dS >= 0 && dB >= 0
        ? ` — an expected saving of ${fmtM(Math.min(dS, dB))} to ${fmtM(Math.max(dS, dB))}/yr.</p>`
        : `. A scenario above the baseline is the delay clause, not a higher tier: at baseline ` +
          `${(100 * elec.pDelay26).toFixed(0)}% of simulated FY 2026 measurements cross the 13.33% delay test and defer ` +
          `the bill to later, unsimulated years; adoption removes most of that deferral chance ` +
          `(${(100 * s.el.pDelay26).toFixed(0)}% strict / ${(100 * b.el.pDelay26).toFixed(0)}% broad still cross), so the ` +
          `near-term expected bill can rise even as the measured rate falls. Deferral is not forgiveness.</p>`;
    dollars =
      head + tail +
      `<p class="sub">The chance the FY 2026 measurement beats the locked FY 2025 rate ` +
      `moves from ${(100 * elec.pWin).toFixed(0)}% to ${(100 * s.el.pWin).toFixed(0)}–${(100 * b.el.pWin).toFixed(0)}%; ` +
      `the FY 2029 bill (keyed to FY 2026) moves from ${fmtM(elec.bill29)}/yr to ${fmtM(b.el.bill29)} (broad) – ${fmtM(s.el.bill29)} (strict)/yr.</p>`;
  }
  const verifiedNote = st.verified
    ? `The Axiom engine already reproduces this state's recorded FY 2024 benefit chain case-exactly (verification view above) — adoption means running determinations through the engine, not only verifying them.`
    : `This state's encoded rules are not yet independently verified; the scenario above uses its own file's cause coding, and verification is the first step toward claiming it.`;
  // Quantify the fixed layer for THIS state so the reach of every scenario
  // is legible: the FY 2024 file-computable rate vs the FY 2024 official.
  const filePoint = pointRate(st, st.err);
  const wedge = st.official - filePoint;
  const wedgeLine =
    wedge >= 0
      ? `In FY 2024 this state's file-computable rate was ${filePoint.toFixed(2)}% against the ${st.official.toFixed(2)}% official — ` +
        `the ${wedge.toFixed(2)}pp remainder (federal re-review integration and ineligible-case error the file never records) ` +
        `is that fixed layer, ${((100 * wedge) / st.official).toFixed(0)}% of the official rate, beyond the reach of any scenario here. `
      : `In FY 2024 this state's file-computable rate (${filePoint.toFixed(2)}%) exceeded the ${st.official.toFixed(2)}% official — ` +
        `the re-review integration adjusted downward here, and that fixed layer is beyond the reach of any scenario. `;
  const hint =
    `<p class="hint">Accounting scenarios under the file's own cause coding, not causal adoption estimates or bounds on intermediate conventions: causes are ` +
    `reviewer judgments, the broad class includes policy misapplication an engine removes only where it drives the ` +
    `determination end-to-end, adoption could shift the error mix, and the FY 2024 cause mix is assumed for FY 2026. ` +
    `The anchor shifts by the file-rate reduction from the removed dollars; the official rate's re-review-and-ineligible ` +
    `layer is held fixed, matching the simulator's treatment of it everywhere. ` +
    wedgeLine +
    verifiedNote +
    `</p>`;
  el.innerHTML = shares + band + dollars + hint;
}

// ---- Render --------------------------------------------------------------

function interventionGridRows(code) {
  if (!INTERVENTIONS) return [];
  const rule = $("intervention-rule").value;
  const coverage = +$("intervention-coverage").value;
  const effectiveness = +$("intervention-effectiveness").value;
  let grid;
  if (effectiveness === 25 || effectiveness === 50) grid = [effectiveness];
  else grid = [25, 50];
  return grid.map((value) => INTERVENTIONS.scenarios.find((scenario) =>
    scenario.ranking_rule === rule && scenario.coverage_pct === coverage &&
    scenario.effectiveness_pct === value
  )).filter(Boolean).map((scenario) => [scenario.effectiveness_pct, scenario.states[code]]);
}

function renderInterventions(code, st, result) {
  const effectiveness = +$("intervention-effectiveness").value;
  $("intervention-effectiveness-val").textContent = effectiveness + "%";
  const summary = summarize(result.rates, st.issuance);
  const election = electionStats(st, result.rates);
  const engineOn = $("lever-engine-cut").checked && !$("lever-engine-cut").disabled;
  const engineNote = engineOn
    ? ` The cause-coded cut accounts for ${fmtPP(pointRate(st, engineCutErr(st)) - pointRate(st, st.err))} points of that change.`
    : "";
  $("interventions-live").innerHTML =
    `<p><strong>One measurement with the cut:</strong> the file rate ${result.delta <= 0 ? "falls" : "rises"} by ` +
    `${Math.abs(result.delta).toFixed(3)} points; the simulated measured rate averages ${summary.mean.toFixed(2)}%; ` +
    `the expected statutory share is ${(100 * summary.eShare / st.issuance).toFixed(2)}% of benefits; and the expected ` +
    `FY 2028 bill, counting the FY 2026 election and the delay clause, is ${fmtM(election.elect28)}/yr.${engineNote}</p>`;
  const rows = interventionGridRows(code);
  if (!rows.length) {
    $("interventions-sustained-body").textContent = "Precomputed grid unavailable.";
    return;
  }
  const engineCaveat = engineOn
    ? '<p class="hint">The sustained grid excludes the cause-coded cut.</p>'
    : "";
  const label = rows.length === 2
    ? "Precomputed at 25% and 50% effectiveness"
    : `Precomputed at ${rows[0][0]}% effectiveness`;
  $("interventions-sustained-body").innerHTML = engineCaveat + `<p class="hint">${label}</p>` + rows.map(([grid, value]) => {
    const years = Object.entries(value.sustained_fy2028_30)
      .map(([year, item]) => `FY ${year}: ${item.expected_share_pct}%`).join(" · ");
    return `<p><strong>${grid}%:</strong> ${years} · three-year cost ` +
      `${fmtM(value.sustained_expected_cost_share_dollars_3yr)}</p>`;
  }).join("");
}

// ---- The answer -----------------------------------------------------------
// The selected state in plain sentences, always at the published baseline:
// the same draws as the all-states table (sampling noise only, no scenario,
// no drift), so the two never disagree. The analyst tools change
// assumptions without touching it.

function rateStrip(el, st, q05, q95) {
  const fy25 = st.official_fy2025, fy24 = st.official;
  const W = chartWidth(el, 720), narrow = W < 520;
  const lo = Math.max(0, Math.min(2, Math.floor(Math.min(fy24, fy25, q05)) - 0.5));
  const hi = Math.max(16, Math.ceil(Math.max(fy24, fy25, q95)) + 1);
  const L = 6, R = 6, H = 96, top = 22, bandH = 30, mid = top + bandH / 2;
  const x = (r) => L + ((Math.min(Math.max(r, lo), hi) - lo) / (hi - lo)) * (W - L - R);
  const ink = cssVar("--muted-foreground") || "#475569";
  const fg = cssVar("--foreground") || "#000000";
  let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
  s += `<defs><pattern id="delay-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">` +
    `<line x1="0" y1="0" x2="0" y2="6" stroke="${ink}" stroke-width="1.2" opacity="0.5"/></pattern></defs>`;
  const xd = x(DELAY_THRESHOLD);
  const bands = [[lo, 6, 0], [6, 8, 5], [8, 10, 10], [10, hi, 15]];
  for (const [a, b, t] of bands) {
    s += `<rect x="${x(a)}" y="${top}" width="${x(b) - x(a)}" height="${bandH}" fill="var(${TIER_VARS[t]})" opacity="0.2"/>`;
    // Each tier's name sits under its own stretch of the axis; the 15% name
    // stops at the delay band, which gets its own.
    const right = t === 15 ? xd : x(b);
    s += `<text x="${(x(a) + right) / 2}" y="${H - 6}" text-anchor="middle" font-size="11" fill="${ink}">${narrow ? `${t}%` : `${t}% share`}</text>`;
  }
  s += `<rect x="${xd}" y="${top}" width="${x(hi) - xd}" height="${bandH}" fill="url(#delay-hatch)"/>`;
  s += `<text x="${(xd + x(hi)) / 2}" y="${H - 6}" text-anchor="middle" font-size="11" fill="${ink}">delay</text>`;
  for (const v of [6, 8, 10, DELAY_THRESHOLD]) {
    s += `<line x1="${x(v)}" x2="${x(v)}" y1="${top + bandH}" y2="${top + bandH + 5}" stroke="${ink}"/>`;
    s += `<text x="${x(v)}" y="${top + bandH + 18}" text-anchor="middle" font-size="11" fill="${ink}">${v === DELAY_THRESHOLD ? "13.33%" : v + "%"}</text>`;
  }
  s += `<rect x="${x(q05)}" y="${mid - 5}" width="${Math.max(3, x(q95) - x(q05))}" height="10" rx="5" fill="var(--primary)" opacity="0.45"/>`;
  s += `<circle cx="${x(fy24)}" cy="${mid}" r="5" fill="var(--background)" stroke="${fg}" stroke-width="1.5"/>`;
  s += `<circle cx="${x(fy25)}" cy="${mid}" r="6.5" fill="var(--primary)" stroke="var(--background)" stroke-width="1.5"/>`;
  // Centre the label on the FY 2025 dot, clamped inside the chart (bold
  // glyphs run a little wider than textW's average).
  const label = `FY 2024 ${pct2(fy24)} → FY 2025 ${pct2(fy25)}`;
  const half = (textW(label, 12) * 1.08) / 2;
  const ax = Math.min(Math.max(x(fy25), L + half), W - R - half);
  s += `<text x="${ax}" y="14" text-anchor="middle" font-size="12" font-weight="600" fill="${fg}">${label}</text>`;
  el.innerHTML = s + "</svg>";
  el.setAttribute(
    "aria-label",
    `${nameOf($("state").value)}: FY 2024 rate ${pct2(fy24)}, FY 2025 rate ${pct2(fy25)}; 90% of fresh same-size samples ` +
      `fall between ${pct2(q05)} and ${pct2(q95)}. Tier boundaries at 6, 8 and 10%; delay band above 13.33%.`
  );
}

function renderAnswer(code, st, draws) {
  const name = nameOf(code), its = possessive(name);
  const el = electionStats(st, draws);
  const sm = summarize(draws, st.issuance);
  const fy25 = st.official_fy2025, fy24 = st.official;
  const tier = el.lockShare;
  const q05 = quantile(draws, 0.05), q95 = quantile(draws, 0.95);
  const cases = st.n.toLocaleString();

  $("answer-lead").innerHTML = el.delay25
    ? `${its} FY 2025 payment error rate is <strong>${pct2(fy25)}</strong>, in the delay band: it owes ` +
      `<strong>nothing for FY 2028</strong>, and its first bill, for FY 2029, is set by its FY 2026 rate.`
    : tier === 0
      ? `${its} FY 2025 payment error rate is <strong>${pct2(fy25)}</strong>, below 6%, so at that rate it pays ` +
        `<strong>no share</strong> of its SNAP benefit costs.`
      : `${its} FY 2025 payment error rate is <strong>${pct2(fy25)}</strong>, in the <strong>${tier}% cost-share ` +
        `tier</strong>. At that tier it would pay <strong>${fmtWords(el.lockTierCost)} a year</strong>, ${tier}% of the ` +
        `${fmtWords(st.issuance)} in SNAP benefits it issued in FY 2024.`;

  rateStrip($("answer-strip"), st, q05, q95);

  const points = [];
  // Coverage figures: analysis/persistence_backtest_results.json (static vs
  // widened and rao_yu), locked by tests/test_front_page.py.
  const noiseOnly =
    "That counts sampling noise only, so it understates the uncertainty: in a backtest over FY 2016–2024, " +
    "90% ranges built from sampling noise alone caught the next year's rate 48% of the time, and adding " +
    "year-to-year movement raised that to 81–85%. The drift option in the analyst tools adds an estimate of that movement.";
  if (el.delay25) {
    points.push([
      "How sure",
      `FY 2025 is published, so the FY 2028 delay is settled. The FY 2026 rate is not: a fresh QC sample the size ` +
        `of ${its} FY 2024 one (${cases} cases) lands between ${pct2(q05)} and ${pct2(q95)} 90% of the time. ${noiseOnly}`,
    ]);
  } else {
    const nearest = [6, 8, 10].reduce((b, v) => (Math.abs(v - fy25) < Math.abs(b - fy25) ? v : b));
    const gap = fy25 - nearest;
    const edge = Math.abs(gap) < 1
      ? ` ${name} sits ${Math.abs(gap).toFixed(2)} points ${gap >= 0 ? "above" : "below"} the ${nearest}% boundary.`
      : "";
    const t24 = tierOf(fy24);
    const moved = t24 !== tier ? ` Its FY 2024 rate, ${pct2(fy24)}, was in the ${t24}% tier.` : "";
    points.push([
      "How sure",
      `The published rate comes from a sample of cases. A fresh QC sample the size of ${its} FY 2024 one ` +
        `(${cases} cases) lands in a different tier <strong>${fmtChance(1 - sm.pt[tier])} of the time</strong>, and 90% ` +
        `of such samples fall between ${pct2(q05)} and ${pct2(q95)}.${edge}${moved} ${noiseOnly}`,
    ]);
  }

  if (el.delay25) {
    points.push([
      "Delay band",
      `At ${pct2(fy25)}, 1.5 times the rate reaches 20%, so ${its} first bill moves from FY 2028 to FY 2029. ` +
        `A fresh FY 2026 sample lands in the delay band too ${fmtChance(el.pDelay26)} of the time, which would move ` +
        `the first bill to FY 2030, set by the FY 2027 rate.`,
    ]);
  } else {
    const cross = el.pDelay26 >= 0.005
      ? `, and a fresh FY 2026 sample crosses it <strong>${fmtChance(el.pDelay26)} of the time</strong>, which would ` +
        `move its first bill to FY 2030, set by its FY 2027 rate.`
      : `; a fresh FY 2026 sample crosses it less than 1% of the time.`;
    points.push([
      "Delay band",
      `Rates above 13.33% delay the first bill, since 1.5 times the rate then reaches 20%. ${name} is ` +
        `${(DELAY_THRESHOLD - fy25).toFixed(2)} points below that line${cross}`,
    ]);
  }

  const closed = "FY 2026's sample period ended September 30, 2026, and its rate is not yet published.";
  if (el.delay25) {
    points.push([
      "FY 2026 rate",
      `${closed} It sets ${its} first bill, for FY 2029: <strong>${fmtWords(el.bill29)} a year</strong> in ` +
        `expectation, counting the chance it lands in the delay band again.`,
    ]);
  } else if (tier === 0) {
    points.push([
      "FY 2026 rate",
      `${name} owes nothing for FY 2028 whichever year it uses. ${closed} That rate sets the FY 2029 bill: ` +
        `<strong>${fmtWords(el.bill29)} a year</strong> in expectation.`,
    ]);
  } else {
    points.push([
      "FY 2026 option",
      `For FY 2028, ${name} can elect its FY 2026 rate instead of its FY 2025 rate (7 U.S.C. 2013(a)(2)(B)(ii)). ` +
        `${closed} A fresh sample centered on the FY 2025 level comes in below ${pct2(fy25)} ${fmtChance(el.pWin)} of ` +
        `the time. Counting that option${el.pDelay26 >= 0.005 ? " and the chance of a delay" : ""}, the expected ` +
        `FY 2028 bill is <strong>${fmtWords(el.elect28)} a year</strong>. The FY 2026 rate also sets the FY 2029 bill: ` +
        `${fmtWords(el.bill29)} a year in expectation.`,
    ]);
  }

  points.push([
    "FY 2027, open now",
    `FY 2027 began October 1, 2026 and runs through September 30, 2027. Its rate sets ${its} FY 2030 bill, and ` +
      `the months still to be sampled reflect how the state runs SNAP from here. ` +
      `<a href="#fy2027" data-scroll="fy2027">What can still change</a>`,
  ]);

  $("answer-points").innerHTML = points
    .map(([k, v]) => `<div class="pt"><dt>${k}</dt><dd>${v}</dd></div>`)
    .join("");
}

function renderVerifyCta(code, st) {
  const cta = $("verify-cta");
  const name = nameOf(code);
  if (st.verified) {
    cta.innerHTML = `${possessive(name)} encoded SNAP benefit computation is verified against its FY 2024 QC file — ${st.verified} of ${st.n} replayable reviews, each exact at every compared stage (gross income, standard and shelter deductions, net income, maximum allotment, benefit). QC-adjudicated deductions, utility allowances, and eligibility findings enter as inputs, so the replay checks benefit arithmetic and leaves eligibility untested; excluded cases are enumerated program-structure classes. <a href="https://github.com/TheAxiomFoundation/axiom-oracles">Verification harness</a> · <a href="https://axiom.org/reports/colorado-snap-qc-fy2024">example state report</a>`;
  } else {
    cta.innerHTML = `Simulation for ${name} uses the public QC file only — its encoded rules are not yet independently verified. Seven states are (CO, NY, CA, AZ, GA, MD, TX). Interested in verification for your state? <a href="mailto:hello@policyengine.org">hello@policyengine.org</a>`;
  }
}

// ---- Render --------------------------------------------------------------

function renderAnalyst(code, st, plain) {
  const extra = +$("audits").value;
  $("audits-val").textContent = "+" + extra;
  const scenarioOn = $("lever-smd").checked && SCEN && !scenarioInfo(code)?.gated;
  const engineCutOn = $("lever-engine-cut").checked && !scenarioOn;
  const engineErr = engineCutOn ? engineCutErr(st) : st.err;

  const driftOn = $("lever-drift").checked && FY27;
  const drift = driftOn ? driftDraws(FY27.drift_tau_pp.robust) : null;

  let base, scen, interventionResult = null;
  const issuance = st.issuance;
  if (scenarioOn) {
    const anchor = modelAnchor(code, st.official_fy2025);
    base = shiftRates(anchor.rates, anchor.shift);
    scen = shiftRates(simulateModel(prepPatchedState(code), { extra }), anchor.shift);
  } else if (MODEL) {
    base = plain;
    interventionResult = interventionDraws(code, st, extra, engineErr);
    scen = interventionResult.rates;
  } else {
    base = plain;
    scen = extra || engineCutOn
      ? simulate({ ...st, err: engineErr }, {
          extra,
          anchor:
            st.official_fy2025 + pointRate(st, engineErr) - pointRate(st, st.err),
        })
      : base;
  }
  // One common drift stream across engines: scenario-vs-baseline deltas
  // stay clean, while election and delay odds widen with process movement.
  const scenIsBase = scen === base;
  base = addDrift(base, drift);
  scen = scenIsBase ? base : addDrift(scen, drift);
  const observed = scenarioOn ? addDrift(plain, drift) : base;
  const elec = electionStats(st, observed);
  const elecB = electionStats(st, base);
  const elecS = electionStats(st, scen);
  $("mechanism").textContent = mechanismLine(scenarioOn, driftOn);
  const sb = summarize(base, issuance);
  const ss = summarize(scen, issuance);
  if (interventionResult) renderInterventions(code, st, interventionResult);

  $("t-expected").textContent = fmtM(elecS.elect28) + "/yr";
  if (elecS.delay25) {
    $("t-delta").textContent = `delayed start — first bill FY 2029: ${fmtM(elecS.bill29)}/yr`;
    $("t-delta").className = "d";
  } else {
    const d = elecB.elect28 - elecS.elect28;
    $("t-delta").textContent = `${d >= 0 ? "−" : "+"}${fmtM(Math.abs(d))} vs baseline`;
    $("t-delta").className = "d " + (d >= 0 ? "delta-good" : "delta-bad");
  }
  const top = Object.entries(ss.pt).sort((a, b) => b[1] - a[1])[0];
  $("t-tier").textContent = TIER_LABELS[top[0]];
  $("t-tierp").textContent = (top[1] * 100).toFixed(0) + "% of draws";
  $("t-pwin").textContent = (100 * elecS.pWin).toFixed(0) + "%";
  $("t-pwind").textContent = elecS.delay25
    ? "FY 2028 is $0 either way (delay)"
    : `baseline ${(100 * elecB.pWin).toFixed(0)}%`;
  $("t-sd").textContent = fmtM(elecS.sd28);
  $("t-sdd").textContent = "baseline " + fmtM(elecB.sd28);

  histogram($("hist"), base, scen, st.official_fy2025);
  tierBars($("tiers"), [["Baseline", sb.pt], ["Scenario", ss.pt]], st.issuance);
  renderAdoption(code, st, elec, drift);
  renderEnginePanel();
}

function render() {
  const code = $("state").value;
  const st = DATA.states[code];
  syncScenarioControl();
  const plain = simulate(st, {});
  renderAnswer(code, st, plain);
  renderFy2027(code);
  renderVerifyCta(code, st);
  document.querySelectorAll("#nat-table tbody tr").forEach((tr) =>
    tr.classList.toggle("current", tr.dataset.code === code)
  );
  // Closed analyst tools skip their simulations; opening them re-renders.
  if ($("analyst").open) renderAnalyst(code, st, plain);
  writeUrl();
}

async function main() {
  if (FRAMED) document.documentElement.classList.add("framed");
  DATA = await (await fetch("data.json?v=" + ASSET_V)).json();
  await Promise.all([loadInterventionsArtifact(), loadModelArtifacts()]);
  try {
    FY27 = await (await fetch("fy2027_data.json?v=" + ASSET_V)).json();
  } catch {
    FY27 = null; // panel degrades to its unavailable message
  }
  try {
    await loadAdoptArtifact();
  } catch (err) {
    ADOPT_ERROR = err; // renderAdoption surfaces the message; never a silent fallback
  }
  const sel = $("state");
  const codes = Object.keys(DATA.states).sort((a, b) => nameOf(a).localeCompare(nameOf(b)));
  for (const code of codes) {
    const o = document.createElement("option");
    o.value = code;
    o.textContent = nameOf(code);
    sel.appendChild(o);
  }
  sel.value = "CO";
  const urlState = readUrl();
  const dark = matchMedia("(prefers-color-scheme: dark)");
  const setMode = () => document.documentElement.classList.toggle("dark", dark.matches);
  dark.addEventListener("change", () => { setMode(); render(); });
  setMode();
  // The footer build stamp renders from ASSET_V itself, so it can never
  // drift from the deployed build.
  const stampDate = ASSET_V.match(/^(\d{4})(\d{2})(\d{2})/);
  if (stampDate) {
    const when = new Date(
      Date.UTC(+stampDate[1], +stampDate[2] - 1, +stampDate[3])
    ).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      timeZone: "UTC",
    });
    $("build-stamp").innerHTML =
      `<a href="https://github.com/PolicyEngine/snap-qc-sim/commits/main" ` +
      `title="Build ${ASSET_V}">updated ${when}</a> · `;
  }
  let pending = 0;
  const queue = () => { clearTimeout(pending); pending = setTimeout(render, 16); };
  let resizing = 0;
  window.addEventListener("resize", () => { clearTimeout(resizing); resizing = setTimeout(render, 150); });
  sel.addEventListener("change", queue);
  $("analyst").addEventListener("toggle", queue);
  // In-page links scroll instead of navigating: <base href> would resolve a
  // bare #fragment against the base path and drop the ?state= query.
  $("answer-points").addEventListener("click", (ev) => {
    const a = ev.target.closest("a[data-scroll]");
    if (!a) return;
    ev.preventDefault();
    $(a.dataset.scroll).scrollIntoView({ behavior: "smooth" });
  });
  $("lever-drift").addEventListener("change", queue);
  $("audits").addEventListener("input", queue);
  $("intervention-rule").addEventListener("change", queue);
  $("intervention-coverage").addEventListener("change", queue);
  $("intervention-effectiveness").addEventListener("input", queue);
  $("lever-engine-cut").addEventListener("change", queue);
  $("engine-cut-pct").addEventListener("input", () => {
    $("engine-cut-val").textContent = $("engine-cut-pct").value + "%";
    queue();
  });
  $("lever-smd").addEventListener("change", async () => {
    // The model-based SMD path re-predicts every case; the cause-coded cut
    // is file arithmetic. The two do not compose; SMD wins while checked.
    $("lever-engine-cut").disabled = $("lever-smd").checked;
    if ($("lever-smd").checked) $("lever-engine-cut").checked = false;
    if ($("lever-smd").checked && !SCEN) {
      $("smd-hint").textContent = "Loading model distributions…";
      try {
        await loadModelArtifacts();
      } catch {
        // syncScenarioControl surfaces ARTIFACT_ERROR; never fall back silently.
      }
      if (scenarioInfo($("state").value)?.gated || ARTIFACT_ERROR) $("lever-smd").checked = false;
    }
    queue();
  });
  $("engine-mode").addEventListener("change", () => {
    if ($("engine-mode").checked && !ENGINE) {
      // Render immediately (the panel shows its loading line), then again
      // when the artifact arrives or its integrity check fails.
      loadEngineArtifact().catch(() => {}).finally(queue);
    }
    queue();
  });
  document.querySelectorAll("#nat-table th button").forEach((b) => {
    b.addEventListener("click", () => {
      const k = b.dataset.k;
      natSort = { k, dir: natSort.k === k ? -natSort.dir : k === "name" ? 1 : -1 };
      renderNatTable();
    });
  });
  if (urlState.smd) {
    try {
      await loadModelArtifacts();
      if (!scenarioInfo(sel.value)?.gated) $("lever-smd").checked = true;
    } catch {
      // Shared links to gated or broken scenarios load the observed view.
    }
  }
  if (urlState.engine) {
    $("engine-mode").checked = true;
    loadEngineArtifact().catch(() => {}).finally(queue);
  }
  render();
  setTimeout(computeNational, 60);
}
main();
