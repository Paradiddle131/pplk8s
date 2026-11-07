#!/usr/bin/env node
// Clipped-text detector for the semantic-bet report page.
// The page is in parts (tabs): the detector opens each part before checking it, and opens a control's part
// before using that control.
// Usage: node clipcheck.js [--url file:///...index.html] [--widths 1280,1024,768,400,360] [--themes light,dark,dark-button]
//                          [--json out.json] [--quick] [--selftest] [--font-delay ms]
// For every width and theme it loads the page and checks, in these states:
//   rest (each part, opened in turn); every question set selected in every set switch; every setup in the setup explorer;
//   every setup and rung in the setup map; each Figure 2 glider at 0 and at its end.
// A finding is text a reader cannot see in full:
//   clip      a text box reaching past the padding box of an ancestor that clips it (overflow hidden/clip,
//             clip-path, contain: paint, an <svg> viewport), or before the start of a scroll box (unreachable);
//   page      a text box left of the page's x = 0 or past its scroll width;
//   viewbox   SVG text whose getBBox, mapped to its <svg>'s user space, leaves the viewBox (clipped when the
//             svg's overflow is not visible; otherwise reported as "spills");
//   overflow  an element with overflow hidden/clip (or text-overflow other than clip) whose scrollWidth or
//             scrollHeight exceeds its client box and holds text;
//   overlap   two visible text boxes overlapping (more than 1 px across and 2 px down);
//   covered   text sample points (every 6 px along the line) covered by another painted element at every tested scroll position of the
//             page's horizontal scroll boxes (sticky columns, absolute positioning, negative margins).
// Exit code 1 when anything is found. Tolerance: 0.5 px horizontally, 1 px vertically.
const { chromium } = require("playwright");
const fs = require("fs");

const arg = (k, d) => { const i = process.argv.indexOf("--" + k); return i > 0 ? process.argv[i + 1] : d; };
const URL = arg("url", "file://" + require("path").resolve(__dirname, "../index.html"));
const WIDTHS = arg("widths", "1280,1024,768,400,360").split(",").map(Number);
const THEMES = arg("themes", "light,dark,dark-button").split(",");
const QUICK = process.argv.includes("--quick");
const JSON_OUT = arg("json", null);
const FONT_DELAY = +arg("font-delay", 0); // ms: hold the web fonts back, to check figures drawn before the font lands

// Runs in the page. root: a selector or null for the whole page. occl: run the covered-text test.
async function inPage({ rootSel, occl }) {
  const TX = 0.5, TY = 1;
  const root = rootSel ? document.querySelector(rootSel) : document.body;
  if (!root) return [];
  const out = [];
  const visible = (el) => !el.checkVisibility || el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true });
  const isSvg = (el) => el instanceof SVGElement;
  const desc = (el) => {
    const parts = []; let e = el;
    for (let i = 0; e && e !== document.body && i < 4; i++, e = e.parentElement) {
      let s = e.tagName.toLowerCase();
      if (e.id) s += "#" + e.id;
      const c = typeof e.className === "string" ? e.className : (e.className && e.className.baseVal) || "";
      if (c.trim()) s += "." + c.trim().split(/\s+/).slice(0, 2).join(".");
      parts.unshift(s);
    }
    return parts.join(" > ");
  };
  const sectionOf = (el) => { const s = el.closest("section[id], section[aria-labelledby], figure[id], section"); if (!s) return "page"; const h = s.querySelector("h2"); return (s.id ? "#" + s.id + " " : "") + (h ? "“" + h.textContent.trim().slice(0, 50) + "”" : ""); };
  const clipsOf = (cs, el) => {
    if (cs.overflowX !== "visible" || cs.overflowY !== "visible") return { x: cs.overflowX, y: cs.overflowY };
    if (cs.clipPath && cs.clipPath !== "none") return { x: "clip-path", y: "clip-path" };
    if (/paint|strict|content/.test(cs.contain || "")) return { x: "contain", y: "contain" };
    return null;
  };
  // padding box of a clipping ancestor, in viewport px
  const boxOf = (a) => {
    const r = a.getBoundingClientRect();
    if (isSvg(a)) {
      if (a.ownerSVGElement) { // nested <svg>: its viewport is x/y/width/height
        return { l: r.left, t: r.top, r: r.right, b: r.bottom };
      }
      const cs = getComputedStyle(a); const bl = parseFloat(cs.borderLeftWidth) || 0, bt = parseFloat(cs.borderTopWidth) || 0;
      const pl = parseFloat(cs.paddingLeft) || 0, pt = parseFloat(cs.paddingTop) || 0, pr = parseFloat(cs.paddingRight) || 0, pb = parseFloat(cs.paddingBottom) || 0;
      return { l: r.left + bl, t: r.top + bt, r: r.right - (parseFloat(cs.borderRightWidth) || 0), b: r.bottom - (parseFloat(cs.borderBottomWidth) || 0), pl, pt, pr, pb };
    }
    return { l: r.left + a.clientLeft, t: r.top + a.clientTop, r: r.left + a.clientLeft + a.clientWidth, b: r.top + a.clientTop + a.clientHeight };
  };
  const scrollable = (v) => v === "auto" || v === "scroll";
  const tiny = (b) => (b.r - b.l) <= 2 || (b.b - b.t) <= 2; // screen-reader-only boxes

  // ---- gather text boxes: HTML text nodes (range rects) and SVG <text> elements
  const items = [];
  const seenSvgText = new Set();
  const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    if (!n.nodeValue.trim()) continue;
    let el = n.parentElement; if (!el) continue;
    if (el.closest("script,style,title,desc,template,noscript")) continue;
    if (isSvg(el)) {
      const t = el.closest("text"); if (!t || seenSvgText.has(t)) continue; seenSvgText.add(t);
      if (!visible(t)) continue;
      const r = t.getBoundingClientRect(); if (!r.width || !r.height) continue;
      items.push({ el: t, rects: [r], text: t.textContent.trim(), svg: true, rectsNow: () => [t.getBoundingClientRect()] });
      continue;
    }
    if (!visible(el)) continue;
    // screen-reader text whose own box is the 1 px clip (the report kit's .rk-sr), not an ancestor's
    if (clipsOf(getComputedStyle(el), el) && tiny(boxOf(el))) continue;
    const rg = document.createRange(); rg.selectNodeContents(n);
    const rects = [...rg.getClientRects()].filter((r) => r.width > 0.5 && r.height > 0.5);
    if (rects.length) items.push({ el, rects, text: n.nodeValue.trim(), rectsNow: () => { const q = document.createRange(); q.selectNodeContents(n); return [...q.getClientRects()].filter((r) => r.width > 0.5 && r.height > 0.5); } });
  }

  const docW = document.documentElement.scrollWidth;
  const ancCache = new Map();
  const clippers = (el) => {
    if (ancCache.has(el)) return ancCache.get(el);
    const list = [];
    for (let a = el.parentElement || el.parentNode; a && a.nodeType === 1; a = a.parentElement || a.parentNode) {
      if (a === document.documentElement || a === document.body) break;
      const cs = getComputedStyle(a); const c = clipsOf(cs, a);
      if (c) list.push({ a, c, cs });
    }
    ancCache.set(el, list); return list;
  };
  // A text box is clipped when it is cut at every tested position of the page's horizontal scroll boxes
  // (start, quarters, end; a scroll event is sent, so boxes the page keeps in step, like a sticky header, follow).
  const clipNow = (it) => {
    const rects = it.rectsNow();
    for (const { a, c } of clippers(it.el)) {
      const b = boxOf(a); if (tiny(b)) return "sr";
      for (const r of rects) {
        let dl = b.l - r.left, dr = r.right - b.r, dt = b.t - r.top, db = r.bottom - b.b;
        // a scroll box shows its overflow past the end, and before the start only as far as it is scrolled
        const sx = scrollable(c.x), sy = scrollable(c.y);
        if (sx) { dl -= a.scrollLeft; dr = -1; } if (sy) { dt -= a.scrollTop; db = -1; }
        if (c.x === "visible") { dl = dr = -1; } if (c.y === "visible") { dt = db = -1; }
        if (dl > TX || dr > TX || dt > TY || db > TY) return { kind: "clip", by: desc(a), how: (c.x === c.y ? c.x : c.x + "/" + c.y),
          cut: { left: +Math.max(0, dl).toFixed(1), right: +Math.max(0, dr).toFixed(1), top: +Math.max(0, dt).toFixed(1), bottom: +Math.max(0, db).toFixed(1) } };
      }
    }
    return null;
  };
  const hScrollers = [...document.querySelectorAll("*")].filter((e) => scrollable(getComputedStyle(e).overflowX) && e.scrollWidth > e.clientWidth + 1);
  const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  const clipState = new Map(items.map((it) => [it, { first: undefined, ok: false }]));
  for (const f of hScrollers.length ? [0, 0.25, 0.5, 0.75, 1] : [0]) {
    hScrollers.forEach((s) => { s.scrollLeft = Math.round((s.scrollWidth - s.clientWidth) * f); s.dispatchEvent(new Event("scroll")); });
    await frame();
    for (const it of items) {
      const st = clipState.get(it); if (st.ok) continue;
      const c = clipNow(it);
      if (st.first === undefined) st.first = c;
      if (!c || c === "sr") st.ok = c === null ? true : "sr";
    }
  }
  hScrollers.forEach((s) => { s.scrollLeft = 0; s.dispatchEvent(new Event("scroll")); }); await frame();
  for (const it of items) {
    const st = clipState.get(it); if (st.ok === "sr" || st.first === "sr") continue;
    let found = st.ok ? null : st.first;
    const inScroller = clippers(it.el).some(({ c }) => c.x !== "visible"); // a box that clips or scrolls bounds it: the clip test covers it
    if (!found && !inScroller) for (const r of it.rects) {
      const L = r.left + scrollX, R = r.right + scrollX;
      if (L < -TX || R > docW + TX) { found = { kind: "page", how: "past the page's scrollable width (unreachable)", cut: { left: +Math.max(0, -L).toFixed(1), right: +Math.max(0, R - docW).toFixed(1) } }; break; }
    }
    if (found) out.push(Object.assign({ where: sectionOf(it.el), el: desc(it.el), text: it.text.slice(0, 80) }, found));
  }

  // ---- text over text: the visible parts of two text boxes overlapping by more than 1 px across and 2 px down
  {
    const vis = [];
    for (const it of items) {
      const boxes = clippers(it.el).map(({ a, c }) => ({ b: boxOf(a), c }));
      for (const r of it.rects) {
        let l = r.left, t = r.top, rr = r.right, bb = r.bottom;
        for (const { b, c } of boxes) { if (c.x !== "visible") { l = Math.max(l, b.l); rr = Math.min(rr, b.r); } if (c.y !== "visible") { t = Math.max(t, b.t); bb = Math.min(bb, b.b); } }
        if (rr - l > 1 && bb - t > 1) vis.push({ it, l, t, r: rr, b: bb });
      }
    }
    vis.sort((a, b) => a.t - b.t);
    const seenPair = new Set();
    for (let i = 0; i < vis.length; i++) {
      const A = vis[i];
      for (let j = i + 1; j < vis.length && vis[j].t < A.b - 2; j++) {
        const B = vis[j]; if (A.it === B.it) continue;
        const ox = Math.min(A.r, B.r) - Math.max(A.l, B.l), oy = Math.min(A.b, B.b) - Math.max(A.t, B.t);
        if (ox <= 1 || oy <= 2) continue;
        const ea = A.it.el, eb = B.it.el;
        if (ea.contains(eb) || eb.contains(ea)) continue;
        if (A.it.text === B.it.text && Math.abs(A.l - B.l) < 1 && Math.abs(A.t - B.t) < 1) continue; // a halo copy
        const key = [A.it.text, B.it.text].sort().join("|"); if (seenPair.has(key)) continue; seenPair.add(key);
        out.push({ kind: "overlap", where: sectionOf(ea), el: desc(ea), text: A.it.text.slice(0, 60), by: desc(eb) + " “" + B.it.text.slice(0, 40) + "”", cut: { x: +ox.toFixed(1), y: +oy.toFixed(1) } });
      }
    }
  }

  // ---- SVG text against its viewBox
  for (const t of seenSvgText) {
    if (!visible(t)) continue;
    const svg = t.ownerSVGElement; if (!svg) continue;
    const vb = svg.viewBox && svg.viewBox.baseVal; if (!vb || !vb.width || !vb.height) continue;
    let bb; try { bb = t.getBBox(); } catch (e) { continue; }
    if (!bb.width) continue;
    const sm = svg.getScreenCTM(), tm = t.getScreenCTM(); if (!sm || !tm) continue;
    const m = sm.inverse().multiply(tm);
    const pts = [[bb.x, bb.y], [bb.x + bb.width, bb.y], [bb.x, bb.y + bb.height], [bb.x + bb.width, bb.y + bb.height]].map(([x, y]) => new DOMPoint(x, y).matrixTransform(m));
    const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
    const cut = { left: vb.x - Math.min(...xs), right: Math.max(...xs) - (vb.x + vb.width), top: vb.y - Math.min(...ys), bottom: Math.max(...ys) - (vb.y + vb.height) };
    if (cut.left > TX || cut.right > TX || cut.top > TY || cut.bottom > TY) {
      const ov = getComputedStyle(svg).overflow;
      Object.keys(cut).forEach((k) => (cut[k] = +Math.max(0, cut[k]).toFixed(1)));
      out.push({ kind: "viewbox", how: ov === "visible" ? "spills (overflow visible)" : "clipped (overflow " + ov + ")", where: sectionOf(t), el: desc(t), text: t.textContent.trim().slice(0, 80), cut, viewBox: [vb.x, vb.y, vb.width, vb.height].join(" ") });
    }
  }

  // ---- overflowing non-scrolling boxes that hold text, unless the page scrolls them in step with a
  // scroll box (checked with every horizontal scroll box at its end)
  const ovf = [];
  for (const el of root.querySelectorAll("*")) {
    if (isSvg(el) && el.tagName.toLowerCase() !== "svg") continue;
    if (!visible(el)) continue;
    const cs = getComputedStyle(el);
    const hidX = cs.overflowX === "hidden" || cs.overflowX === "clip", hidY = cs.overflowY === "hidden" || cs.overflowY === "clip";
    const ell = cs.textOverflow && cs.textOverflow !== "clip";
    if (!hidX && !hidY && !ell) continue;
    if (!el.textContent.trim()) continue;
    if (el.clientWidth <= 2 || el.clientHeight <= 2) continue;
    const ox = el.scrollWidth - el.clientWidth, oy = el.scrollHeight - el.clientHeight;
    if ((hidX && ox > 1) || (hidY && oy > 1) || (ell && ox > 0)) ovf.push({ el, cs, ox, oy, hidX, hidY, ell });
  }
  if (ovf.length) {
    hScrollers.forEach((s) => { s.scrollLeft = s.scrollWidth; s.dispatchEvent(new Event("scroll")); }); await frame();
    for (const o of ovf) {
      const reachX = o.el.scrollLeft + o.el.clientWidth >= o.el.scrollWidth - 1;
      if ((o.hidX && o.ox > 1 && !reachX) || (o.hidY && o.oy > 1) || (o.ell && o.ox > 0))
        out.push({ kind: "overflow", where: sectionOf(o.el), el: desc(o.el), text: o.el.textContent.trim().slice(0, 60), how: o.cs.overflowX + "/" + o.cs.overflowY + (o.ell ? " text-overflow:" + o.cs.textOverflow : ""), cut: { x: o.ox, y: o.oy } });
    }
    hScrollers.forEach((s) => { s.scrollLeft = 0; s.dispatchEvent(new Event("scroll")); }); await frame();
  }

  // ---- covered text (sticky columns, absolute positioning, negative margins)
  // Each text box is sampled every 6 px along its middle line. The page is scrolled in half-viewport steps,
  // and every scroll box (both axes) is set to its start, middle and end; at each position a sample point
  // inside the viewport's middle band and inside every clipping ancestor is tested with elementsFromPoint.
  // A point is fine once the text (or its own element) is the topmost painted thing there. Text whose points
  // are still not fine then gets a second chance, scrolled into view (centre, start, end); text still not
  // fine is reported as covered.
  if (occl) {
    const st = document.createElement("style"); st.textContent = "*{pointer-events:auto!important}"; document.head.appendChild(st);
    const scrollers = [...document.querySelectorAll("*")].filter((e) => { const cs = getComputedStyle(e); return (scrollable(cs.overflowX) && e.scrollWidth > e.clientWidth + 1) || (scrollable(cs.overflowY) && e.scrollHeight > e.clientHeight + 1); });
    const transparent = (c) => !c || c === "transparent" || /rgba\([^)]*,\s*0\)$/.test(c);
    const paints = (e) => {
      const cs = getComputedStyle(e); if (+cs.opacity === 0 || cs.visibility === "hidden") return false;
      if (isSvg(e)) {
        const tag = e.tagName.toLowerCase(); if (tag === "svg" || tag === "g" || tag === "a") return false;
        if (tag === "text" || tag === "tspan") return true;
        if (!transparent(cs.fill) && cs.fill !== "none" && +cs.fillOpacity > 0) return true;
        // a shape with no fill is hit only on its stroke
        return cs.fill === "none" && cs.stroke !== "none" && !transparent(cs.stroke) && +cs.strokeOpacity > 0 && parseFloat(cs.strokeWidth) > 0;
      }
      if (/^(IMG|CANVAS|VIDEO|INPUT)$/.test(e.tagName)) return true;
      if (!transparent(cs.backgroundColor)) return true;
      if (cs.backgroundImage && cs.backgroundImage !== "none") return true;
      for (const c of e.childNodes) if (c.nodeType === 3 && c.nodeValue.trim()) return true;
      return false;
    };
    const H = innerHeight, W = document.documentElement.clientWidth;
    const docH = document.documentElement.scrollHeight;
    const sx0 = scrollX, sy0 = scrollY;
    const state = items.map((it) => ({ it, pts: [], done: false }));
    const test = (s, y0, y1) => {
      const boxes = clippers(s.it.el).map(({ a }) => boxOf(a));
      let k = 0;
      for (const r of s.it.rectsNow()) {
        if (r.width < 3) continue;
        const vy = r.top + r.height / 2;
        const xs = []; for (let x = r.left + Math.min(2, r.width / 4); x < r.right - 1; x += 6) xs.push(x); xs.push(r.right - Math.min(2, r.width / 4));
        for (const vx of xs) {
          const p = s.pts[k] || (s.pts[k] = { seen: false, tested: false, hit: null }); k++;
          if (p.seen) continue;
          if (vx < 0 || vx >= W || vy < y0 || vy >= y1) continue;
          if (boxes.some((b) => vx < b.l || vx > b.r || vy < b.t || vy > b.b)) continue;
          p.tested = true;
          // covered only when a painted element sits above the text in the hit stack (a point between two
          // SVG glyphs hits nothing of the text, and proves nothing)
          const el = s.it.el; let ok = false, by = null, under = false;
          for (const h of document.elementsFromPoint(vx, vy)) {
            // a sticky copy laid exactly over its original (data-mirror names the original) shows the same text
            const mirror = h.closest && h.closest("[data-mirror]");
            if (mirror && el.closest && el.closest(mirror.dataset.mirror)) { ok = true; break; }
            const own = h === el || (s.it.svg && el.contains(h)); // the text itself (an SVG <text> holds its tspans)
            const mine = own || h.contains(el);
            if (mine && !by) { ok = true; break; }
            if (own) { under = true; break; }
            if (!by && paints(h)) by = h;
          }
          if (ok) p.seen = true; else if (by && under) p.hit = by;
        }
      }
      if (s.pts.length && s.pts.every((p) => p.seen)) s.done = true;
    };
    const rootTop = root.getBoundingClientRect().top + scrollY, rootBot = root.getBoundingClientRect().bottom + scrollY;
    for (const f of [0, 0.5, 1]) {
      scrollers.forEach((s) => { s.scrollLeft = (s.scrollWidth - s.clientWidth) * f; s.scrollTop = (s.scrollHeight - s.clientHeight) * f; s.dispatchEvent(new Event("scroll")); });
      for (let top = Math.max(0, rootTop - H); top < Math.min(docH, rootBot + H); top += H / 2) {
        window.scrollTo(0, top);
        const y0 = scrollY <= 0 ? 0 : H * 0.15, y1 = scrollY + H >= docH - 1 ? H : H * 0.9;
        for (const s of state) if (!s.done) test(s, y0, y1);
      }
    }
    scrollers.forEach((s) => { s.scrollLeft = 0; s.scrollTop = 0; s.dispatchEvent(new Event("scroll")); });
    for (const s of state) {
      if (s.done || !s.pts.some((p) => p.tested && !p.seen && p.hit)) continue;
      for (const inline of ["center", "start", "end", "nearest"]) {
        if (s.done) break;
        s.it.el.scrollIntoView({ block: "center", inline });
        test(s, H * 0.15, H * 0.9);
      }
      scrollers.forEach((x) => { x.scrollLeft = 0; x.scrollTop = 0; });
    }
    window.scrollTo(sx0, sy0); st.remove();
    for (const s of state) {
      const bad = s.pts.filter((p) => p.tested && !p.seen && p.hit);
      if (bad.length) out.push({ kind: "covered", where: sectionOf(s.it.el), el: desc(s.it.el), text: s.it.text.slice(0, 80), by: desc(bad[0].hit), points: bad.length });
    }
  }
  return out;
}

async function settle(page) { await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))); }

// --selftest: inject one case of each kind into the page and require the detector to find each.
async function selftest(browser) {
  const page = await browser.newPage({ viewport: { width: 400, height: 900 } });
  await page.goto(URL, { waitUntil: "load" }); await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => {
    const s = document.createElement("section"); s.id = "zz-selftest";
    s.innerHTML = `<h2>selftest</h2>
      <div style="width:120px;overflow:hidden;white-space:nowrap"><span id="st-clip">a long line cut by overflow hidden</span></div>
      <div style="width:120px;overflow:auto;direction:ltr"><div style="margin-left:-40px;white-space:nowrap" id="st-scroll">starts before the scroll box</div></div>
      <p style="position:relative">covered words here<span style="position:absolute;left:0;top:0;width:90px;height:24px;background:#000"></span></p>
      <p style="width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">an ellipsis that truncates</p>
      <svg viewBox="0 0 100 30" width="100" height="30"><text x="-12" y="20">viewbox cut</text></svg>
      <p><span>one</span><span style="margin-left:-20px">two overlap</span></p>`;
    document.body.appendChild(s);
  });
  const f = await page.evaluate(inPage, { rootSel: "#zz-selftest", occl: true });
  const want = { clip: /cut by overflow|starts before|viewbox cut/, overflow: /ellipsis/, covered: /covered words/, viewbox: /viewbox cut/, overlap: /one|two overlap/ };
  let bad = 0;
  for (const [k, re] of Object.entries(want)) { const hit = f.filter((x) => x.kind === k && re.test(x.text)); console.log(`selftest ${k}: ${hit.length ? "found" : "MISSED"}`); if (!hit.length) bad++; }
  const scroll = f.some((x) => x.kind === "clip" && /starts before/.test(x.text)); console.log(`selftest clip before a scroll box's start: ${scroll ? "found" : "MISSED"}`); if (!scroll) bad++;
  await page.close();
  return bad;
}

(async () => {
  const browser = await chromium.launch();
  if (process.argv.includes("--selftest")) { const bad = await selftest(browser); await browser.close(); process.exit(bad ? 1 : 0); }
  const all = []; const pageIssues = [];
  for (const theme of THEMES) for (const w of WIDTHS) {
    const scheme = theme === "light" || theme === "dark-button" ? "light" : "dark";
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, deviceScaleFactor: 1, colorScheme: scheme, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    const errs = [];
    page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
    page.on("pageerror", (e) => errs.push(String(e)));
    if (FONT_DELAY) await page.route(/fonts\.gstatic\.com/, async (route) => { await new Promise((r) => setTimeout(r, FONT_DELAY)); route.continue(); });
    await page.goto(URL, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(300);
    if (theme === "dark-button") { await page.click("#themebtn"); await settle(page); }
    const tag = `${w}px ${theme}`;
    const dt = await page.evaluate(() => document.documentElement.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark(system)" : "light(system)"));
    const hs = async (state) => {
      const h = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
      if (h.sw > h.cw) pageIssues.push(`${tag} ${state}: horizontal page scroll ${h.sw} > ${h.cw}`);
    };
    // every state is checked from the page's top, as the rest state is: the stuck tab strip paints over text
    // scrolled beneath it, which the overlap test (geometry only) would report; the covered test handles it
    const run = async (state, rootSel, occl) => {
      await page.evaluate(() => window.scrollTo(0, 0)); await settle(page);
      const f = await page.evaluate(inPage, { rootSel, occl });
      f.forEach((x) => all.push(Object.assign({ width: w, theme, state }, x)));
      await hs(state);
    };
    const openView = async (sel) => { await page.evaluate((sel) => { const el = document.querySelector(sel); const v = el && el.closest(".view"); if (v && !v.classList.contains("on")) window.__reportViews.show(v.dataset.view); }, sel); await settle(page); };
    const viewNames = await page.$$eval(".view", (vs) => vs.map((v) => v.dataset.view));
    if (!viewNames.length) await run("rest", null, true);
    for (const vn of viewNames) { await page.evaluate((vn) => window.__reportViews.show(vn), vn); await settle(page); await run("rest view=" + vn, null, true); }
    // set switches: every set in every switch
    const sets = await page.$$eval(".seg button[data-set]", (bs) => [...new Set(bs.map((b) => b.dataset.set))]);
    for (const s of sets) {
      const n = await page.$$eval(".seg", (x) => x.length);
      for (let i = 0; i < n; i++) { const b = page.locator(".seg").nth(i).locator(`button[data-set="${s}"]`); if (await b.count()) { await page.evaluate((i) => { const v = document.querySelectorAll(".seg")[i].closest(".view"); if (v && !v.classList.contains("on")) window.__reportViews.show(v.dataset.view); }, i); await settle(page); await b.click(); await settle(page); await run("set=" + s + " seg" + i, null, !QUICK); } }
    }
    // the setup explorer: every setup
    const chips = await page.$$eval(".sxb .sxb-chip", (cs) => cs.map((c) => c.dataset.arm));
    if (chips.length) await openView(".sxb");
    for (const a of chips) {
      await page.click(`.sxb .sxb-chip[data-arm="${a}"]`); await settle(page);
      await run("explorer=" + a, "section.sxb", !QUICK);
    }
    // the setup map: every setup and rung
    const smTargets = await page.$$eval(".sm .sm-s[data-arm], .sm button.sm-rhd[data-rung]", (bs) => bs.map((b) => b.dataset.arm ? `.sm .sm-s[data-arm="${b.dataset.arm}"]` : `.sm button.sm-rhd[data-rung="${b.dataset.rung}"]`));
    for (const sel of smTargets) {
      await page.click(sel); await settle(page);
      await run("map=" + sel.replace(/^.*data-(arm|rung)="([^"]+)".*$/, "$1:$2"), "section.sm", false);
      await page.click(sel); await settle(page); // let go
    }
    // Figure 2's gliders at 0 and at the end
    await openView("#forest");
    const gl = await page.$$("#forest .glider");
    for (let i = 0; i < gl.length; i++) {
      for (const key of ["End", "Home"]) {
        await gl[i].focus(); await page.keyboard.press(key);
        if (key === "Home") { for (let k = 0; k < 12; k++) await page.keyboard.press("PageDown"); }
        await settle(page);
        await run(`glider${i}=${key === "End" ? "end" : "0"}`, "#forest", false);
      }
      await gl[i].focus(); await page.keyboard.press("Home"); await settle(page);
    }
    errs.forEach((e) => pageIssues.push(`${tag}: console error: ${e}`));
    console.error(`checked ${tag} (theme ${dt}): ${sets.length} sets, ${chips.length} explorer setups, ${smTargets.length} map targets, ${gl.length} gliders`);
    await ctx.close();
  }
  await browser.close();

  // group by finding across states
  const groups = new Map();
  for (const f of all) {
    const k = [f.kind, f.where, f.el, f.text, f.how || "", f.by || ""].join("|");
    if (!groups.has(k)) groups.set(k, { f, at: [] });
    groups.get(k).at.push(`${f.width}/${f.theme}/${f.state}${f.cut ? " " + JSON.stringify(f.cut) : ""}${f.points ? " pts=" + f.points : ""}`);
  }
  const res = [...groups.values()].map(({ f, at }) => ({ kind: f.kind, where: f.where, el: f.el, text: f.text, how: f.how, by: f.by, viewBox: f.viewBox, count: at.length, at }));
  for (const g of res) {
    console.log(`\n[${g.kind}] ${g.where}\n  text: “${g.text}”\n  el:   ${g.el}${g.how ? "\n  how:  " + g.how : ""}${g.by ? "\n  by:   " + g.by : ""}${g.viewBox ? "\n  viewBox: " + g.viewBox : ""}\n  ${g.count} state(s): ${g.at.slice(0, 6).join("; ")}${g.count > 6 ? " …" : ""}`);
  }
  console.log(`\nPage: ${pageIssues.length ? pageIssues.join("\n") : "no console errors, no horizontal page scroll"}`);
  console.log(`Findings: ${res.length} distinct (${all.length} across states)`);
  if (JSON_OUT) fs.writeFileSync(JSON_OUT, JSON.stringify({ findings: res, pageIssues }, null, 1));
  process.exit(res.length || pageIssues.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
