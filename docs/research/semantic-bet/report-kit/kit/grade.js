/* report-kit grade, opt-in. A container with data-rk-grade="40 70" (two cut points on the 0-100 scale) gives every
   bar fill (.rk-fill, its value in --v) and range span (.rk-span, its --hi) inside it a data-g: "lo" under the first
   cut, "mid" from the first to under the second, "hi" from the second up. data-rk-grade-dir="down" says lower is
   better, so the ends swap. An element that already has data-g keeps it. API: ReportKit.grade(root), which grades
   anything inside root again (after a generator's script adds rows). */
(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  const num = (el, name) => parseFloat(el.style.getPropertyValue(name) || getComputedStyle(el).getPropertyValue(name));
  function band(v, cuts, down) {
    const g = v < cuts[0] ? "lo" : v < cuts[1] ? "mid" : "hi";
    return down ? { lo: "hi", mid: "mid", hi: "lo" }[g] : g;
  }
  function grade(root = document) {
    const scopes = [...(root.matches && root.matches("[data-rk-grade]") ? [root] : []), ...root.querySelectorAll("[data-rk-grade]")];
    for (const s of scopes) {
      const cuts = s.dataset.rkGrade.trim().split(/[\s,]+/).map(Number).sort((a, b) => a - b);
      if (cuts.length !== 2 || cuts.some(Number.isNaN)) { console.warn("report-kit grade: data-rk-grade takes two cut points, as in \"40 70\"", s); continue; }
      const down = s.dataset.rkGradeDir === "down";
      for (const el of s.querySelectorAll(".rk-fill, .rk-span")) {
        if (el.dataset.g && !el.dataset.rkGraded) continue;
        const v = num(el, el.classList.contains("rk-span") ? "--hi" : "--v");
        if (Number.isNaN(v)) continue;
        el.dataset.g = band(v, cuts, down);
        el.dataset.rkGraded = "";
      }
    }
  }
  RK.grade = grade;
  (RK.inits = RK.inits || []).push(grade);
})();
