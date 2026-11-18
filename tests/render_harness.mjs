// Render app/public/app.js against a minimal fake DOM in node and print, as
// JSON, what a reader sees for every jurisdiction: the answer, the FY 2027
// section, the verification note, the all-states rows, and (with --analyst
// or --toggle) the analyst panels. tests/test_front_page_render.py checks
// the output.
//
//   node tests/render_harness.mjs <app/public> <width> [--analyst] [--toggle]
//        [--search=?drift=1] [--states=CO,NY] [--today=2027-06-15]
//        [--pdelay=0.0049,0.005]
//
// --analyst opens the tools from a shared engine link (?engine=1).
// --toggle loads the page closed, then opens the tools the way a reader
//   does, so the lazy analyst loads run.
// --search sets location.search (overriding --analyst's ?engine=1).
// --states keeps only those jurisdictions in data.json, so the all-states
//   pass simulates just them (a full run takes minutes in node).
// --today fixes the app's clock (new Date() with no arguments) at noon
//   local time on that date, so date-dependent copy renders on both sides
//   of each switch.
// --pdelay also renders each answer with the FY 2026 delay chance set to
//   each listed value, so the wording thresholds are tested even where no
//   jurisdiction's simulated odds fall.
import fs from "node:fs";
import vm from "node:vm";

const [PUB, widthArg, ...flags] = process.argv.slice(2);
const WIDTH = +(widthArg || 390);
const ANALYST = flags.includes("--analyst");
const TOGGLE = flags.includes("--toggle");
const SEARCH = flags.find((f) => f.startsWith("--search="))?.slice(9);
const ONLY = flags.find((f) => f.startsWith("--states="))?.slice(9).split(",");
const TODAY = flags.find((f) => f.startsWith("--today="))?.slice(8);
const PDELAY = flags.find((f) => f.startsWith("--pdelay="))?.slice(9).split(",").map(Number);

// Every id the app asks for, and every file it fetches.
const requested = new Set();
const fetched = [];

const els = new Map();
const escape = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
function mkEl(id) {
  const classes = new Set();
  return {
    id, _html: "", _text: "", value: "", checked: false, disabled: false, hidden: false, open: false,
    className: "", dataset: {}, attrs: {}, listeners: {}, clientWidth: WIDTH, style: {},
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); this._text = this._html.replace(/<[^>]+>/g, ""); },
    // Setting textContent replaces the markup, as in a browser.
    get textContent() { return this._text; },
    set textContent(v) { this._text = String(v); this._html = escape(this._text); },
    classList: {
      toggle(c, on) { (on ?? !classes.has(c)) ? classes.add(c) : classes.delete(c); },
      add(c) { classes.add(c); },
      contains(c) { return classes.has(c); },
    },
    setAttribute(k, v) { this.attrs[k] = String(v); },
    addEventListener(t, f) { (this.listeners[t] ||= []).push(f); },
    dispatchEvent(ev) { (this.listeners[ev.type] || []).forEach((f) => f(ev)); },
    appendChild() {},
    querySelectorAll() { return []; },
    querySelector() { return mkEl("q"); },
    scrollIntoView() {},
  };
}
const $ = (id) => {
  requested.add(id);
  if (!els.has(id)) els.set(id, mkEl(id));
  return els.get(id);
};
// Control defaults from index.html.
$("audits").value = "0";
$("intervention-rule").value = "model";
$("intervention-coverage").value = "5";
$("intervention-effectiveness").value = "50";
$("engine-cut-pct").value = "100";

// The page defaults to Colorado; a --states run without it starts on the
// first state listed, as a ?state= link would.
const search = new URLSearchParams(SEARCH ?? (ANALYST ? "?engine=1" : ""));
if (ONLY && !ONLY.includes("CO") && !search.has("state")) search.set("state", ONLY[0]);

const tbody = mkEl("tbody");
const ctx = {
  document: {
    getElementById: $,
    createElement: (t) => mkEl(t),
    body: mkEl("body"),
    documentElement: mkEl("html"),
    querySelector: (s) => (s === "#nat-table tbody" ? tbody : mkEl(s)),
    querySelectorAll: () => [],
  },
  console, setTimeout, clearTimeout, performance, crypto: globalThis.crypto,
  TextDecoder, Uint8Array, Float64Array, URLSearchParams,
  location: { search: search.toString() ? "?" + search : "", hash: "" },
  history: { replaceState() {} },
  matchMedia: () => ({ matches: false, addEventListener() {} }),
  getComputedStyle: () => ({ getPropertyValue: () => "" }),
  addEventListener() {},
  innerWidth: WIDTH,
  Event: class { constructor(t) { this.type = t; } },
  fetch: async (u) => {
    const file = u.split("?")[0];
    fetched.push(file);
    const buf = fs.readFileSync(PUB + "/" + file);
    return {
      ok: true,
      arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength),
      json: async () => {
        const payload = JSON.parse(buf.toString());
        if (ONLY && file === "data.json")
          payload.states = Object.fromEntries(ONLY.map((c) => [c, payload.states[c]]));
        return payload;
      },
    };
  },
};
if (TODAY) {
  const [y, m, d] = TODAY.split("-").map(Number);
  const fixed = new Date(y, m - 1, d, 12).getTime();
  ctx.Date = class extends Date {
    constructor(...a) {
      if (a.length) super(...a);
      else super(fixed);
    }
    static now() {
      return fixed;
    }
  };
}
ctx.window = ctx;
ctx.self = ctx;
ctx.top = ctx;
vm.createContext(ctx);
const src = fs.readFileSync(PUB + "/app.js", "utf8").replace(/\nmain\(\);\s*$/, "\n") + `
// --pdelay: report a set FY 2026 delay chance while __P is set.
electionStats = ((orig) => (st, d) => {
  const r = orig(st, d);
  return globalThis.__P == null ? r : { ...r, pDelay26: globalThis.__P };
})(electionStats);
globalThis.__t = {
  main, render, electionStats, simulate, fmtWords, fmtChance,
  NAT: () => NAT, DATA: () => DATA, INTERVENTIONS: () => INTERVENTIONS, ENGINE: () => ENGINE,
  SCEN: () => SCEN,
  errors: () => ({ INTERVENTIONS_ERROR, ARTIFACT_ERROR, ENGINE_ERROR, ADOPT_ERROR }),
};`;
vm.runInContext(src, ctx);
const T = ctx.__t;

// An artifact that fails its integrity check stops the run at once,
// naming the artifact, instead of waiting out the timeout.
const until = (ok) => new Promise((resolve, reject) => {
  const t0 = Date.now();
  const tick = () => {
    const bad = Object.entries(T.errors()).find(([, e]) => e);
    if (bad) return reject(new Error(`${bad[0]}: ${bad[1].message}`));
    if (ok()) return resolve();
    if (Date.now() - t0 > 900000) return reject(new Error("timeout"));
    setTimeout(tick, 25);
  };
  tick();
});
await T.main();
const n = Object.keys(T.DATA().states).length;
await until(() => T.NAT().size === n && $("nat-takeaway").textContent);
const fetchedBeforeToggle = [...fetched];
if (TOGGLE) {
  $("analyst").open = true;
  $("analyst").dispatchEvent(new ctx.Event("toggle"));
  await until(() => T.INTERVENTIONS() && T.SCEN());
}
if (ANALYST) await until(() => T.INTERVENTIONS() && T.ENGINE());
if (search.get("smd") === "1") await until(() => T.SCEN());
const SHOW_ANALYST = ANALYST || TOGGLE;

// Inline tags vanish and block tags become spaces, so "<strong>48%</strong>,"
// reads as "48%,".
const text = (h) =>
  h.replace(/<\/?(?:strong|em|a|span|b|i)\b[^>]*>/g, "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
// Reader paragraphs: each <p>, <li> and answer point, as plain text.
const paras = (h) => h.split(/<\/(?:p|li|dd)>/).map(text).filter(Boolean);
const out = {
  takeaway: $("nat-takeaway").textContent,
  adoptNational: $("adopt-national").textContent,
  states: {},
};
for (const code of Object.keys(T.DATA().states)) {
  $("state").value = code;
  // A ?smd=1 link to this state checks the box; the app unchecks it where
  // the state has no ungated scenario.
  if (search.get("smd") === "1") $("lever-smd").checked = true;
  T.render();
  const st = T.DATA().states[code];
  const el = T.electionStats(st, T.simulate(st, {}));
  const row = T.NAT().get(code);
  out.states[code] = {
    lead: text($("answer-lead").innerHTML),
    points: text($("answer-points").innerHTML),
    strip: $("answer-strip").innerHTML,
    fy27: text($("fy2027-body").innerHTML),
    fy27Heading: $("fy2027-h").textContent,
    cta: text($("verify-cta").innerHTML),
    paragraphs: [
      ...paras($("answer-points").innerHTML),
      ...paras($("fy2027-body").innerHTML),
      text($("verify-cta").innerHTML),
      ...(SHOW_ANALYST
        ? ["interventions-live", "interventions-sustained-body", "adoption-body", "engine-body"]
            .flatMap((id) => paras($(id).innerHTML))
        : []),
    ],
    delay25: el.delay25,
    issuance: st.issuance,
    tier: el.lockShare,
    // The answer's figures, formatted by the app's own helpers, and the
    // all-states row they must agree with.
    expect: {
      pDelay26: T.fmtChance(el.pDelay26),
      pDelay26Raw: el.pDelay26,
      elect28: T.fmtWords(el.elect28),
      bill29: T.fmtWords(el.bill29),
    },
    row: { ...row, pmisWords: T.fmtChance(row.pmis), billWords: T.fmtWords(row.bill) },
    ...(SHOW_ANALYST
      ? {
          live: text($("interventions-live").innerHTML),
          sustained: text($("interventions-sustained-body").innerHTML),
          adoption: text($("adoption-body").innerHTML),
          engine: text($("engine-body").innerHTML),
          tiles: ["t-expected", "t-delta", "t-tier", "t-tierp", "t-pwin", "t-pwind", "t-sd", "t-sdd"].map((k) => $(k).textContent),
          mechanism: $("mechanism").textContent,
          auditsVal: $("audits-val").textContent,
          smdOn: $("lever-smd").checked,
        }
      : {}),
  };
}
if (PDELAY) {
  out.synthetic = {};
  for (const p of PDELAY) {
    ctx.__P = p;
    const rows = {};
    for (const code of Object.keys(T.DATA().states)) {
      $("state").value = code;
      T.render();
      rows[code] = {
        lead: text($("answer-lead").innerHTML),
        points: text($("answer-points").innerHTML),
        delay25: out.states[code].delay25,
        tier: out.states[code].tier,
      };
    }
    out.synthetic[String(p)] = { words: T.fmtChance(p), states: rows };
  }
  ctx.__P = null;
}
out.ids = [...requested].sort();
out.fetched = fetched;
out.fetchedBeforeToggle = fetchedBeforeToggle;
process.stdout.write(JSON.stringify(out));
