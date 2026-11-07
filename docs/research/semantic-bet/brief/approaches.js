/* The Approaches sections' own behaviour over report-kit: the route lifts off when a number sorts the table and
   comes back with the native-to-custom order. The question sets' tables keep one sort (the kit's sort group), so
   each table's route follows the order it now shows. */
(() => {
  function setup() {
    const tables = [...document.querySelectorAll("table.ap-table")];
    const route = t => {
      const home = t.querySelector('th[data-sort="default"]');
      t.dataset.route = home && home.getAttribute("aria-sort") === "ascending" ? "on" : "off";
    };
    document.addEventListener("rk:sort", e => { if (e.target.closest && e.target.closest("table.ap-table")) tables.forEach(route); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup); else setup();
})();
