/* report-kit definition bubble. Any element with data-tip="text" shows the text in one bubble on hover, on
   keyboard focus and on tap (a tap shows it for a moment); Escape closes it. Screen readers get the same text
   through aria-describedby, added when the element has none, and a non-control element is made focusable.
   Options on the bubble, <div class="rk-tip" id="rk-tip" data-pin hidden></div> (made when absent):
   data-pin lets a click or Enter on a non-control element pin its definition, which can then be dragged by its
   handle (or moved with the arrow keys) and closed; data-tip-more="#id" on the element adds a link to a fuller
   entry, labelled by data-tip-more-label. A bubble on an element the keyboard rests on stays through a scroll and
   follows it; the pointer's bubble closes on a scroll. With the kit scoped to part of a page, each root has its
   own bubble, inside the root (so it wears the root's tokens). API: ReportKit.tip.show(el), .hide(), .unpin(). */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  const GRIP = '<svg viewBox="0 0 8 12" width="8" height="12" aria-hidden="true" fill="currentColor"><circle cx="2" cy="2" r="1.1"/>' +
    '<circle cx="6" cy="2" r="1.1"/><circle cx="2" cy="6" r="1.1"/><circle cx="6" cy="6" r="1.1"/><circle cx="2" cy="10" r="1.1"/><circle cx="6" cy="10" r="1.1"/></svg>';
  const CROSS = '<svg viewBox="0 0 14 14" width="14" height="14" aria-hidden="true"><path d="M2 2 12 12M12 2 2 12" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>';
  let uid = 0;
  const CONTROL = "a[href], button, input, select, textarea, summary, [role=tab], [role=button]";
  function init(root) {
    const whole = root === document;
    const els = [...root.querySelectorAll("[data-tip]")];
    let box = root.querySelector(".rk-tip");
    if (!box) {
      if (!els.length) return;
      box = document.createElement("div");
      if (whole) box.id = "rk-tip";
      box.className = "rk-tip"; box.hidden = true;
      (whole ? document.body : root).append(box);
    }
    box.setAttribute("aria-hidden", "true");
    const canPin = box.hasAttribute("data-pin");
    const texts = document.createElement("div");
    texts.hidden = true;
    (whole ? document.body : root).append(texts);
    for (const el of els) {
      if (!el.hasAttribute("aria-describedby")) {
        const d = document.createElement("span");
        d.id = `rk-tip-${++uid}`; d.textContent = el.dataset.tip;
        texts.append(d);
        el.setAttribute("aria-describedby", d.id);
      }
      if (!el.matches(CONTROL) && !el.hasAttribute("tabindex")) el.tabIndex = 0;
    }
    const pinnable = el => canPin && !el.matches(CONTROL);

    let owner = null, pinned = false, timer = 0, touched = false, drag = null, quiet = false;
    addEventListener("pointerdown", e => { touched = e.pointerType === "touch"; }, { capture: true, passive: true });
    addEventListener("keydown", () => { touched = false; }, { capture: true });

    function place(el) {
      const r = el.getBoundingClientRect(), b = box.getBoundingClientRect();
      const vw = document.documentElement.clientWidth, vh = innerHeight;
      const left = Math.max(16, Math.min(r.left, vw - 16 - b.width));
      const below = r.bottom + 8 + b.height <= vh - 8;
      const top = below ? r.bottom + 8 : Math.max(8, r.top - 8 - b.height);
      moveTo(left, top);
    }
    // left, top in viewport px; a pinned bubble lives in page coordinates, so it scrolls with what it explains
    function moveTo(left, top) {
      const vw = document.documentElement.clientWidth, vh = innerHeight, b = box.getBoundingClientRect();
      left = Math.max(8, Math.min(left, vw - 8 - b.width));
      top = Math.max(8, Math.min(top, Math.max(8, vh - 8 - b.height)));
      box.style.left = Math.round(left + (pinned ? scrollX : 0)) + "px";
      box.style.top = Math.round(top + (pinned ? scrollY : 0)) + "px";
    }
    function show(el) {
      if (pinned) return;
      clearTimeout(timer);
      owner = el;
      box.textContent = el.dataset.tip;
      box.hidden = false;
      place(el);
    }
    function hide(now) {
      if (pinned) return;
      clearTimeout(timer);
      const go = () => { box.hidden = true; owner = null; };
      if (now) go(); else timer = setTimeout(go, 120);
    }
    function pin(el) {
      unpin(false);
      clearTimeout(timer);
      owner = el;
      const title = (el.dataset.tipTitle || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 48);
      box.innerHTML = `<div class="rk-tip-bar"><span class="rk-tip-handle" role="button" tabindex="0" aria-label="Move this definition: drag it, or use the arrow keys">${GRIP}<span></span></span>` +
        `<button type="button" class="rk-tip-close" aria-label="Close">${CROSS}</button></div><p class="rk-tip-body"></p>`;
      box.querySelector(".rk-tip-handle span").textContent = title;
      box.querySelector(".rk-tip-body").textContent = el.dataset.tip;
      const more = el.dataset.tipMore;
      if (more) {
        const p = document.createElement("p"), a = document.createElement("a");
        p.className = "rk-tip-more"; a.href = more; a.textContent = el.dataset.tipMoreLabel || "More";
        a.addEventListener("click", () => unpin(false));
        p.append(a); box.append(p);
      }
      const at = box.hidden ? null : box.getBoundingClientRect();
      pinned = true;
      box.classList.add("is-pinned");
      box.setAttribute("role", "dialog");
      box.setAttribute("aria-label", title ? `Definition: ${title}` : "Definition");
      box.removeAttribute("aria-hidden");
      box.hidden = false;
      if (at) moveTo(at.left, at.top); else place(el);
    }
    function unpin(refocus) {
      if (!pinned) return;
      pinned = false; drag = null;
      box.classList.remove("is-pinned", "is-dragging");
      box.removeAttribute("role"); box.removeAttribute("aria-label");
      box.setAttribute("aria-hidden", "true");
      box.hidden = true;
      const el = owner; owner = null;
      // back on its element, quietly: the definition was just closed, so focus does not reopen it
      if (refocus && el && document.contains(el)) { quiet = true; el.focus({ preventScroll: true }); quiet = false; }
    }

    for (const el of els) {
      el.addEventListener("pointerenter", e => { if (e.pointerType !== "touch") show(el); });
      el.addEventListener("pointerleave", () => hide(false));
      el.addEventListener("focus", () => { if (quiet) return; show(el); if (touched && !pinnable(el)) timer = setTimeout(() => hide(true), 2600); });
      el.addEventListener("blur", () => hide(true));
      if (pinnable(el)) {
        el.addEventListener("click", () => pin(el));
        el.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pin(el); } });
      }
    }
    box.addEventListener("pointerenter", () => clearTimeout(timer));
    box.addEventListener("pointerleave", () => hide(false));
    box.addEventListener("click", e => { if (e.target.closest(".rk-tip-close")) unpin(true); });
    box.addEventListener("pointerdown", e => {
      const h = pinned && e.target.closest(".rk-tip-handle");
      if (!h || e.button) return;
      e.preventDefault();
      const b = box.getBoundingClientRect();
      drag = { id: e.pointerId, dx: e.clientX - b.left, dy: e.clientY - b.top };
      try { h.setPointerCapture(e.pointerId); } catch (err) { /* capture is a nicety */ }
      box.classList.add("is-dragging");
    });
    box.addEventListener("pointermove", e => { if (drag && e.pointerId === drag.id) moveTo(e.clientX - drag.dx, e.clientY - drag.dy); });
    const endDrag = e => { if (drag && e.pointerId === drag.id) { drag = null; box.classList.remove("is-dragging"); } };
    for (const t of ["pointerup", "pointercancel", "lostpointercapture"]) box.addEventListener(t, endDrag);
    box.addEventListener("keydown", e => {
      if (!pinned) return;
      if (e.target.closest(".rk-tip-handle")) {
        const s = e.shiftKey ? 40 : 10;
        const d = { ArrowLeft: [-s, 0], ArrowRight: [s, 0], ArrowUp: [0, -s], ArrowDown: [0, s] }[e.key];
        if (d) { e.preventDefault(); const b = box.getBoundingClientRect(); moveTo(b.left + d[0], b.top + d[1]); return; }
        if (e.key === "Tab" && e.shiftKey && owner) { e.preventDefault(); quiet = true; owner.focus({ preventScroll: true }); quiet = false; }
      }
    });
    // Tab from a pinned element goes into its bubble, so the keyboard can move and close it
    document.addEventListener("keydown", e => {
      if (e.key === "Escape") { if (pinned) unpin(true); else hide(true); return; }
      if (e.key === "Tab" && !e.shiftKey && pinned && document.activeElement === owner) {
        e.preventDefault();
        box.querySelector(".rk-tip-handle").focus({ preventScroll: true });
      }
    });
    // a scroll closes the pointer's bubble; the keyboard's stays on its element (the browser scrolls a focused
    // element into view, which would otherwise close the bubble it just opened) and follows it
    addEventListener("scroll", () => {
      if (pinned || !owner) return;
      if (document.activeElement === owner && owner.matches(":focus-visible") && !box.hidden) place(owner); else hide(true);
    }, { passive: true });
    addEventListener("resize", () => { if (pinned) { const b = box.getBoundingClientRect(); moveTo(b.left, b.top); } });
    document.addEventListener("rk:tab", () => unpin(false));
    RK.tip = { show, hide: () => hide(true), unpin: () => unpin(false), pin };
  }
  (RK.inits = RK.inits || []).push(init);
})();
