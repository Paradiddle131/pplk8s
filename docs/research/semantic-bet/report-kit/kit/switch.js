/* report-kit switch. Markup: <div class="rk-switch" role="group" aria-label="..." data-rk-switch="name"> with
   <button type="button" data-value="v" aria-pressed="true|false"> segments; every element carrying
   data-rk-when="name=v" shows only while v is chosen. API: ReportKit.switches.set(name, v); event rk:switch
   {detail: {name, value}} on document. */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  const motion = () => !matchMedia("(prefers-reduced-motion: reduce)").matches;
  function set(name, value) {
    for (const g of document.querySelectorAll(`[data-rk-switch="${CSS.escape(name)}"]`)) {
      for (const b of g.querySelectorAll("button[data-value]")) b.setAttribute("aria-pressed", String(b.dataset.value === value));
    }
    for (const el of document.querySelectorAll("[data-rk-when]")) {
      const [n, v] = el.dataset.rkWhen.split("=");
      if (n !== name) continue;
      const show = v === value;
      if (show && el.hidden && motion()) requestAnimationFrame(() => el.animate([{ opacity: .35 }, { opacity: 1 }], { duration: 180, easing: "ease-out" }));
      el.hidden = !show;
    }
    document.dispatchEvent(new CustomEvent("rk:switch", { detail: { name, value } }));
  }
  function init(root) {
    for (const g of root.querySelectorAll("[data-rk-switch]")) {
      const name = g.dataset.rkSwitch;
      const buttons = [...g.querySelectorAll("button[data-value]")];
      for (const b of buttons) b.addEventListener("click", () => set(name, b.dataset.value));
      const first = buttons.find(b => b.getAttribute("aria-pressed") === "true") || buttons[0];
      if (first) set(name, first.dataset.value);
    }
  }
  RK.switches = { set };
  (RK.inits = RK.inits || []).push(init);
})();
