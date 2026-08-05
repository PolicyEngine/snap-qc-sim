// SNAP payment error simulator — in-browser Monte Carlo over the state's
// QC sample. Method mirrors snap_qc_sim.simulate (Python) exactly.

const TIERS = [[6, 0], [8, 5], [10, 10], [Infinity, 15]];
const TIER_LABELS = { 0: "0% share", 5: "5% share", 10: "10% share", 15: "15% share" };
const TIER_VARS = { 0: "--tier-0", 5: "--tier-5", 10: "--tier-10", 15: "--tier-15" };
const LEVER_IDS = ["smd", "ssed", "heat_and_eat", "bbce_resources"];
const DRAWS = 4000;

const fmtM = (v) => {
  const m = v / 1e6;
  return m >= 1000 ? `$${(m / 1000).toFixed(2)}B` : `$${m.toFixed(0)}M`;
};
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

function scenarioErrors(st, levers, eff) {
  const n = st.w.length;
  const err = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    let e = st.err[i];
    if (e > 0 && st.hits[i] !== 0) {
      const h = st.hits[i]; // [total, smd, ssed, hne, bbce]
      let hit = 0;
      for (let k = 0; k < 4; k++) if (levers[k]) hit += h[k + 1];
      e *= 1 - (eff * hit) / h[0];
    }
    err[i] = e;
  }
  return err;
}

function simulate(st, { extra = 0, levers = [0, 0, 0, 0], eff = 0.5, seed = 11 } = {}) {
  const n = st.w.length;
  const err = scenarioErrors(st, levers, eff);
  const we = new Float64Array(n), wi = new Float64Array(n);
  let sumWE0 = 0, sumWE = 0, sumWI = 0;
  for (let i = 0; i < n; i++) {
    we[i] = st.w[i] * err[i];
    wi[i] = st.w[i] * st.iss[i];
    sumWE0 += st.w[i] * st.err[i];
    sumWE += we[i];
    sumWI += wi[i];
  }
  const point0 = (100 * sumWE0) / sumWI;
  const point1 = (100 * sumWE) / sumWI;
  const level = st.official + (point1 - point0);
  const m = n + extra;
  const rng = mulberry32(seed);
  const rates = new Float64Array(DRAWS);
  for (let d = 0; d < DRAWS; d++) {
    let e = 0, s = 0;
    for (let j = 0; j < m; j++) {
      const i = (rng() * n) | 0;
      e += we[i]; s += wi[i];
    }
    rates[d] = level + (100 * e) / s - point1;
  }
  return rates;
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
  s += `<text x="${x(official) + 4}" y="${H - B - 6}" font-size="10" fill="${ink}">official ${official.toFixed(2)}%</text>`;
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

function tierBars(el, rows) {
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
        s += `<text x="${xacc + w / 2}" y="${y0 + 20}" text-anchor="middle" font-size="11" fill="${light ? "#1E293B" : "white"}">${TIER_LABELS[t].split(" ")[0]} · ${(pt[t] * 100).toFixed(0)}%</text>`;
      }
      xacc += w;
    }
  });
  s += "</svg>";
  el.innerHTML = s;
  el.querySelectorAll(".seg").forEach((r) => {
    r.addEventListener("mousemove", (ev) => {
      tooltip.textContent = `${r.dataset.row}: ${(r.dataset.p * 100).toFixed(1)}% chance of the ${TIER_LABELS[r.dataset.t]} tier`;
      tooltip.style.left = ev.clientX + 12 + "px";
      tooltip.style.top = ev.clientY + 12 + "px";
      tooltip.hidden = false;
    });
    r.addEventListener("mouseleave", () => (tooltip.hidden = true));
  });
}

function render() {
  const code = $("state").value;
  const st = DATA.states[code];
  const levers = LEVER_IDS.map((id) => ($("lever-" + id).checked ? 1 : 0));
  const eff = +$("eff").value / 100;
  const extra = +$("audits").value;
  $("audits-val").textContent = "+" + extra;
  $("eff-val").textContent = Math.round(eff * 100) + "%";

  const base = simulate(st, {});
  const scen = simulate(st, { extra, levers, eff });
  const sb = summarize(base, st.issuance);
  const ss = summarize(scen, st.issuance);

  $("t-official").textContent = st.official.toFixed(2) + "%";
  $("t-expected").textContent = fmtM(ss.eShare) + "/yr";
  const d = sb.eShare - ss.eShare;
  $("t-delta").textContent = (d >= 0 ? "−" : "+") + fmtM(Math.abs(d)).slice(1) + " vs baseline";
  $("t-delta").className = "d " + (d >= 0 ? "delta-good" : "delta-bad");
  const top = Object.entries(ss.pt).sort((a, b) => b[1] - a[1])[0];
  $("t-tier").textContent = TIER_LABELS[top[0]];
  $("t-tierp").textContent = (top[1] * 100).toFixed(0) + "% of draws";
  $("t-sd").textContent = fmtM(ss.sd);
  $("t-sdd").textContent = "baseline " + fmtM(sb.sd);

  histogram($("hist"), base, scen, st.official);
  tierBars($("tiers"), [["Baseline", sb.pt], ["Scenario", ss.pt]]);

  const badge = $("verified-badge");
  const cta = $("verify-cta");
  if (st.verified) {
    badge.hidden = false;
    badge.textContent = `Rules verified: ${st.verified}/${st.verified} QC cases exact`;
    cta.innerHTML = `This state's encoded SNAP rules are verified against all ${st.verified} of its FY 2024 QC reviews — every case and every computation stage exact. <a href="https://github.com/TheAxiomFoundation/axiom-oracles">Verification harness</a> · <a href="https://axiom.org/reports/colorado-snap-qc-fy2024">example state report</a>`;
  } else {
    badge.hidden = true;
    cta.innerHTML = `Simulation for this state uses the public QC file only — its encoded rules are not yet independently verified. Seven states are (CO, NY, CA, AZ, GA, MD, TX). Interested in verification for your state? <a href="mailto:hello@policyengine.org">hello@policyengine.org</a>`;
  }
}

async function main() {
  DATA = await (await fetch("data.json")).json();
  const sel = $("state");
  for (const [code, st] of Object.entries(DATA.states)) {
    const o = document.createElement("option");
    o.value = code;
    o.textContent = code + (st.verified ? " ✓" : "");
    sel.appendChild(o);
  }
  sel.value = "CO";
  const dark = matchMedia("(prefers-color-scheme: dark)");
  const setMode = () => document.documentElement.classList.toggle("dark", dark.matches);
  dark.addEventListener("change", () => { setMode(); render(); });
  setMode();
  let raf = 0;
  const queue = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(render); };
  sel.addEventListener("change", queue);
  $("audits").addEventListener("input", queue);
  $("eff").addEventListener("input", queue);
  for (const id of LEVER_IDS) $("lever-" + id).addEventListener("change", queue);
  render();
}
main();
