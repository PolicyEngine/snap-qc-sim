// Render app/public/app.js against a minimal fake DOM in node and print, as
// JSON, what a reader sees for every jurisdiction: the answer, the FY 2027
// section, the verification note, the all-states rows, and (with --analyst)
// the analyst panels. tests/test_front_page_render.py checks the output.
//
//   node tests/render_harness.mjs <app/public> <width> [--analyst] [--states=CO,NY]
//
// --states keeps only those jurisdictions in data.json, so the all-states
// pass simulates just them (a full run takes minutes in node).
import fs from "node:fs";
import vm from "node:vm";

const [PUB, widthArg, ...flags] = process.argv.slice(2);
const WIDTH = +(widthArg || 390);
const ANALYST = flags.includes("--analyst");
const ONLY = flags.find((f) => f.startsWith("--states="))?.slice(9).split(",");

const els = new Map();
function mkEl(id) {
  const classes = new Set();
  return {
    id, _html: "", textContent: "", value: "", checked: false, disabled: false, hidden: false, open: false,
    className: "", dataset: {}, attrs: {}, listeners: {}, clientWidth: WIDTH, style: {},
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); },
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
const $ = (id) => { if (!els.has(id)) els.set(id, mkEl(id)); return els.get(id); };
// Control defaults from index.html.
$("audits").value = "0";
$("intervention-rule").value = "model";
$("intervention-coverage").value = "5";
$("intervention-effectiveness").value = "50";
$("engine-cut-pct").value = "100";

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
  // A shared engine link opens the analyst tools and loads the engine view.
  location: { search: ANALYST ? "?engine=1" : "", hash: "" },
  history: { replaceState() {} },
  matchMedia: () => ({ matches: false, addEventListener() {} }),
  getComputedStyle: () => ({ getPropertyValue: () => "" }),
  addEventListener() {},
  innerWidth: WIDTH,
  Event: class { constructor(t) { this.type = t; } },
  fetch: async (u) => {
    const buf = fs.readFileSync(PUB + "/" + u.split("?")[0]);
    return {
      ok: true,
      arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength),
      json: async () => {
        const payload = JSON.parse(buf.toString());
        if (ONLY && u.startsWith("data.json"))
          payload.states = Object.fromEntries(ONLY.map((c) => [c, payload.states[c]]));
        return payload;
      },
    };
  },
};
ctx.window = ctx;
ctx.self = ctx;
ctx.top = ctx;
vm.createContext(ctx);
const src = fs.readFileSync(PUB + "/app.js", "utf8").replace(/\nmain\(\);\s*$/, "\n") + `
globalThis.__t = {
  main, render, electionStats, simulate, fmtWords, fmtChance,
  NAT: () => NAT, DATA: () => DATA, INTERVENTIONS: () => INTERVENTIONS, ENGINE: () => ENGINE,
};`;
vm.runInContext(src, ctx);
const T = ctx.__t;

const until = (ok) => new Promise((resolve, reject) => {
  const t0 = Date.now();
  const tick = () => (ok() ? resolve() : Date.now() - t0 > 120000 ? reject(new Error("timeout")) : setTimeout(tick, 25));
  tick();
});
await T.main();
const n = Object.keys(T.DATA().states).length;
await until(() => T.NAT().size === n && $("nat-takeaway").textContent);
if (ANALYST) await until(() => T.INTERVENTIONS() && T.ENGINE());

// Inline tags vanish and block tags become spaces, so "<strong>48%</strong>,"
// reads as "48%,".
const text = (h) =>
  h.replace(/<\/?(?:strong|em|a|span|b|i)\b[^>]*>/g, "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
// Reader paragraphs: each <p>, <li> and answer point, as plain text.
const paras = (h) => h.split(/<\/(?:p|li|dd)>/).map(text).filter(Boolean);
const out = { takeaway: $("nat-takeaway").textContent, states: {} };
for (const code of Object.keys(T.DATA().states)) {
  $("state").value = code;
  T.render();
  const st = T.DATA().states[code];
  const el = T.electionStats(st, T.simulate(st, {}));
  const row = T.NAT().get(code);
  out.states[code] = {
    lead: text($("answer-lead").innerHTML),
    points: text($("answer-points").innerHTML),
    strip: $("answer-strip").innerHTML,
    fy27: text($("fy2027-body").innerHTML),
    cta: text($("verify-cta").innerHTML),
    paragraphs: [
      ...paras($("answer-points").innerHTML),
      ...paras($("fy2027-body").innerHTML),
      text($("verify-cta").innerHTML),
      ...(ANALYST
        ? ["interventions-live", "interventions-sustained-body", "adoption-body", "engine-body"]
            .flatMap((id) => paras($(id).innerHTML))
        : []),
    ],
    delay25: el.delay25,
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
    ...(ANALYST
      ? {
          live: text($("interventions-live").innerHTML),
          sustained: text($("interventions-sustained-body").innerHTML),
          adoption: text($("adoption-body").innerHTML),
          engine: text($("engine-body").innerHTML),
          tiles: ["t-expected", "t-delta", "t-tier", "t-tierp", "t-pwin", "t-pwind", "t-sd", "t-sdd"].map((k) => $(k).textContent),
          mechanism: $("mechanism").textContent,
        }
      : {}),
  };
}
process.stdout.write(JSON.stringify(out));
