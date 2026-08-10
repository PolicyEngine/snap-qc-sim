// SNAP payment error simulator — in-browser Monte Carlo over the state's
// QC sample. The no-scenario engine mirrors snap_qc_sim.simulate (Python)
// exactly; the policy scenario draws every case from the fitted error model
// (model_data.json) and its SMD-flipped counterpart (model_scenarios.json).

const TIERS = [[6, 0], [8, 5], [10, 10], [Infinity, 15]];
const TIER_LABELS = { 0: "0% share", 5: "5% share", 10: "10% share", 15: "15% share" };
const TIER_VARS = { 0: "--tier-0", 5: "--tier-5", 10: "--tier-10", 15: "--tier-15" };
const DRAWS = 4000;
const ASSET_V = "20260809c"; // bump with index.html's app.js?v= on every deploy that changes any asset
const SCEN_SCHEMA = "snap_qc_sim.model_scenarios.v1";

const fmtM = (v) => {
  const m = v / 1e6;
  return m >= 1000 ? `$${(m / 1000).toFixed(2)}B` : `$${m.toFixed(0)}M`;
};
const fmtPP = (v, digits = 3) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}`;
const tierOf = (r) => { for (const [cut, s] of TIERS) if (r < cut) return s; return 15; };

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
const $ = (id) => document.getElementById(id);
const tooltip = document.createElement("div");
tooltip.className = "tooltip";
tooltip.hidden = true;
document.body.appendChild(tooltip);

// ---- Observed-resample engine (no scenario) ------------------------------

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

// ---- FY2026 election lens ------------------------------------------------
// The FY2028 cost share keys to the state's FY2025 or FY2026 rate, at its
// election (7 USC 2013(a)(2)(B)(ii)). FY2025 is published and locked; the
// draws simulate a QC-sized FY2026 measurement centered at the FY2025 level
// (sampling noise only — a lower bound on true FY2026 uncertainty, since
// year-over-year process movement is excluded; see analysis/FY2025_MOVEMENT).
function electionStats(st, draws) {
  const fy25 = st.official_fy2025;
  const lockShare = tierOf(fy25);
  let win = 0, effCost = 0, delay26 = 0;
  for (const d of draws) {
    if (d < fy25) win++;
    effCost += (tierOf(Math.min(d, fy25)) / 100) * st.issuance;
    if (d * 1.5 >= 20) delay26++;
  }
  return {
    fy25,
    lockShare,
    lockCost: (lockShare / 100) * st.issuance,
    pWin: win / draws.length,
    electCost: effCost / draws.length,
    pDelay26: delay26 / draws.length,
    delay25: fy25 * 1.5 >= 20,
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
  const bins = 60, W = 920, H = 260, L = 42, R = 12, T = 12, B = 30;
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
    s += `<text x="${(xa + xb) / 2}" y="${T + 13}" text-anchor="middle" font-size="10" fill="${ink}">${TIER_LABELS[t]}</text>`;
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
  s += `<text x="${x(official) + 4}" y="${H - B - 6}" font-size="10" fill="${ink}">FY25 official ${official.toFixed(2)}%</text>`;
  for (let v = Math.ceil(lo); v <= hi; v += 2) {
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
  const W = 920, H = 46 * rows.length + 8, L = 78, R = 12;
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
      if (pt[t] >= 0.07) {
        const darkMode = document.documentElement.classList.contains("dark");
        const light = darkMode ? t >= 10 : t <= 5;
        const cost = t > 0 && pt[t] >= 0.18 ? ` · ${fmtM((t / 100) * issuance)}/yr` : "";
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
      const sm = summarize(simulate(st, {}), st.issuance);
      const tier = tierOf(st.official_fy2025);
      NAT.set(code, {
        code,
        official: st.official,
        fy2025: st.official_fy2025,
        tier,
        pmis: 1 - sm.pt[tier],
        eShare: sm.eShare,
        sd: sm.sd,
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
  const totalE = rows.reduce((a, r) => a + r.eShare, 0);
  $("nat-takeaway").textContent =
    `At FY 2025 official rates and FY 2024 sample sizes, ${flip} of ${rows.length} jurisdictions have at least a 40% chance ` +
    `that a QC-sized FY 2026 measurement lands in a different cost-share tier than their locked FY 2025 rate. Summed expected cost across all ` +
    `jurisdictions under the FY 2028 tiers: ${fmtM(totalE)}/yr. Between FY 2024 and FY 2025, 18 jurisdictions changed tiers while only 10 moved beyond two-year sampling noise.`;
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
      <td>${r.code}${r.verified ? ' <span class="vmark" title="Benefit computation verified against every replayable FY 2024 QC case">✓</span>' : ""}</td>
      <td class="num">${r.official.toFixed(2)}%</td>
      <td class="num">${r.fy2025.toFixed(2)}%</td>
      <td><span class="dot" style="background:var(${TIER_VARS[r.tier]})"></span>${TIER_LABELS[r.tier]}</td>
      <td class="num">${(r.pmis * 100).toFixed(0)}%</td>
      <td class="num">${fmtM(r.eShare)}</td>
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
      document.querySelector(".controls").scrollIntoView({ behavior: "smooth" });
    });
  });
}

// ---- URL state -----------------------------------------------------------

function readUrl() {
  const p = new URLSearchParams(location.search);
  const st = p.get("state");
  if (st && DATA.states[st]) $("state").value = st;
  if (p.get("audits")) $("audits").value = Math.min(1000, Math.max(0, +p.get("audits") || 0));
  // Legacy accounting-lever params (levers, eff, mode) are ignored: those
  // scenarios suppressed observed error dollars by finding category, which
  // is an accounting bound, not a prediction, and were removed 2026-08-07.
  return p.get("smd") === "1";
}

function writeUrl() {
  const p = new URLSearchParams();
  p.set("state", $("state").value);
  if (+$("audits").value) p.set("audits", $("audits").value);
  if ($("lever-smd").checked) p.set("smd", "1");
  history.replaceState(null, "", "?" + p.toString());
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

function mechanismLine(scenarioOn) {
  return scenarioOn
    ? "Sampling engine: model-based — each draw samples cases and draws each case's deviation from its fitted distribution (baseline) or its SMD-flipped distribution (scenario); levels anchored to the official rate."
    : "Sampling engine: resamples the state's observed FY 2024 QC error dollars, centered on the official rate.";
}

// ---- Render --------------------------------------------------------------

function render() {
  const code = $("state").value;
  const st = DATA.states[code];
  const extra = +$("audits").value;
  $("audits-val").textContent = "+" + extra;
  syncScenarioControl();
  const scenarioOn = $("lever-smd").checked && SCEN && !scenarioInfo(code)?.gated;

  let base, scen;
  const issuance = st.issuance;
  if (scenarioOn) {
    const anchor = modelAnchor(code, st.official_fy2025);
    base = shiftRates(anchor.rates, anchor.shift);
    scen = shiftRates(simulateModel(prepPatchedState(code), { extra }), anchor.shift);
  } else {
    base = simulate(st, {});
    scen = extra ? simulate(st, { extra }) : base;
  }
  const observed = scenarioOn ? simulate(st, {}) : base;
  const elec = electionStats(st, observed);
  $("mechanism").textContent = mechanismLine(scenarioOn);
  const sb = summarize(base, issuance);
  const ss = summarize(scen, issuance);

  $("t-official").textContent = st.official_fy2025.toFixed(2) + "%";
  $("t-official-24").textContent = "FY 2024: " + st.official.toFixed(2) + "%";
  $("t-expected").textContent = fmtM(ss.eShare) + "/yr";
  const d = sb.eShare - ss.eShare;
  $("t-delta").textContent = (d >= 0 ? "−" : "+") + fmtM(Math.abs(d)).slice(1) + " vs baseline";
  $("t-delta").className = "d " + (d >= 0 ? "delta-good" : "delta-bad");
  const top = Object.entries(ss.pt).sort((a, b) => b[1] - a[1])[0];
  $("t-tier").textContent = TIER_LABELS[top[0]];
  $("t-tierp").textContent = (top[1] * 100).toFixed(0) + "% of draws";
  $("t-sd").textContent = fmtM(ss.sd);
  $("t-sdd").textContent = "baseline " + fmtM(sb.sd);

  histogram($("hist"), base, scen, st.official_fy2025);
  tierBars($("tiers"), [["Baseline", sb.pt], ["Scenario", ss.pt]], st.issuance);

  const lockTier = TIER_LABELS[elec.lockShare];
  $("elect-locked").textContent =
    `${elec.fy25.toFixed(2)}% — ${lockTier} (${fmtM(elec.lockCost)}/yr)` +
    (elec.delay25 ? " · delay clause met: cost share starts FY 2029" : "");
  $("elect-pwin").textContent = (100 * elec.pWin).toFixed(0) + "%";
  $("elect-cost").textContent =
    `${fmtM(elec.electCost)}/yr vs ${fmtM(elec.lockCost)}/yr locking FY 2025 ` +
    `(saves ${fmtM(Math.max(0, elec.lockCost - elec.electCost))}/yr in expectation)`;
  $("elect-delay").textContent =
    (elec.delay25
      ? "met at FY 2025 (start moves to FY 2029); "
      : "not met at FY 2025; ") +
    (100 * elec.pDelay26).toFixed(0) +
    "% chance the simulated FY 2026 rate meets it (start FY 2030)";
  writeUrl();
  document.querySelectorAll("#nat-table tbody tr").forEach((tr) =>
    tr.classList.toggle("current", tr.dataset.code === code)
  );

  const badge = $("verified-badge");
  const cta = $("verify-cta");
  if (st.verified) {
    badge.hidden = false;
    badge.textContent = `Benefit computation verified: ${st.verified} of ${st.n} FY 2024 QC cases exact`;
    cta.innerHTML = `This state's encoded SNAP benefit computation is verified against its FY 2024 QC file — ${st.verified} of ${st.n} replayable reviews, each exact at every compared stage (gross income, standard and shelter deductions, net income, maximum allotment, benefit). QC-adjudicated deductions, utility allowances, and eligibility findings enter as inputs; excluded cases are enumerated program-structure classes. <a href="https://github.com/TheAxiomFoundation/axiom-oracles">Verification harness</a> · <a href="https://axiom.org/reports/colorado-snap-qc-fy2024">example state report</a>`;
  } else {
    badge.hidden = true;
    cta.innerHTML = `Simulation for this state uses the public QC file only — its encoded rules are not yet independently verified. Seven states are (CO, NY, CA, AZ, GA, MD, TX). Interested in verification for your state? <a href="mailto:hello@policyengine.org">hello@policyengine.org</a>`;
  }
}

async function main() {
  DATA = await (await fetch("data.json?v=" + ASSET_V)).json();
  const sel = $("state");
  for (const [code, st] of Object.entries(DATA.states)) {
    const o = document.createElement("option");
    o.value = code;
    o.textContent = code + (st.verified ? " ✓" : "");
    sel.appendChild(o);
  }
  sel.value = "CO";
  const wantScenario = readUrl();
  const dark = matchMedia("(prefers-color-scheme: dark)");
  const setMode = () => document.documentElement.classList.toggle("dark", dark.matches);
  dark.addEventListener("change", () => { setMode(); render(); });
  setMode();
  let pending = 0;
  const queue = () => { clearTimeout(pending); pending = setTimeout(render, 16); };
  sel.addEventListener("change", queue);
  $("audits").addEventListener("input", queue);
  $("lever-smd").addEventListener("change", async () => {
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
  document.querySelectorAll("#nat-table th button").forEach((b) => {
    b.addEventListener("click", () => {
      const k = b.dataset.k;
      natSort = { k, dir: natSort.k === k ? -natSort.dir : k === "code" ? 1 : -1 };
      renderNatTable();
    });
  });
  if (wantScenario) {
    try {
      await loadModelArtifacts();
      if (!scenarioInfo(sel.value)?.gated) $("lever-smd").checked = true;
    } catch {
      // Shared links to gated or broken scenarios load the observed view.
    }
  }
  render();
  setTimeout(computeNational, 60);
}
main();
