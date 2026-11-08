#!/usr/bin/env node
// Inlines report-kit into report pages, so each stays one standalone HTML file. A page names what it uses in
// three opening markers; the build writes the kit's current files after each, up to its closing marker:
//   /* report-kit:css tokens base section table-sort tip */ ... /* /report-kit:css */   (inside a <style>)
//   /* report-kit:js table-sort tip */ ... /* /report-kit:js */                         (inside a <script>)
//   <!-- report-kit:vendor plot --> ... <!-- /report-kit:vendor -->                    (where scripts may go)
// A missing closing marker is added, so a generator may write the opening markers alone; running the build
// again replaces what it inlined before. A component's dependencies come with it (dots brings marks); "all"
// names every component. Vendored files are checked against kit/vendor/checksums.txt before they are inlined.
// scope=<selector> in the css and js markers runs the kit inside part of a page: the CSS is nested under the
// selector (:root and body map onto it, so the tokens and the ground live on the scope and nothing leaks out), and
// the scripts wire only what sits inside each element the selector matches.
// Usage: node bin/build.cjs <page.html>...      (or: --list, to print the components)
const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const crypto = require('crypto');

const KIT = path.join(__dirname, '..', 'kit');
// Every component, in the order its CSS and JS are inlined; deps come along when a page names the component.
const ORDER = ['tokens', 'base', 'section', 'marks', 'dots', 'bar', 'range', 'grade', 'tint', 'slope', 'tabs', 'switch', 'filter', 'fold', 'step', 'dialog', 'table-sort', 'tip', 'highlight', 'plot-theme'];
const DEPS = { dots: ['marks'], slope: ['marks'], highlight: ['marks'] };
const VENDOR = { d3: ['d3-7.9.0.min.js'], plot: ['d3-7.9.0.min.js', 'plot-0.6.17.umd.min.js'] };

const has = (name, ext) => fs.existsSync(path.join(KIT, `${name}.${ext}`));
const esc = t => t.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');

function expand(names, ext, file) {
  const want = new Set();
  const add = n => {
    if (!ORDER.includes(n)) throw new Error(`${file}: no report-kit component "${n}" (node bin/build.cjs --list)`);
    want.add(n);
    (DEPS[n] || []).forEach(add);
  };
  for (const n of names) (n === 'all' ? ORDER : [n]).forEach(add);
  return ORDER.filter(n => want.has(n) && has(n, ext));
}

// opening marker (its list in group 1), then either everything up to the closing marker or nothing
function region(src, open, close, file, body) {
  const re = new RegExp(`(${open})([\\s\\S]*?)(${esc(close)})`);
  const lone = new RegExp(open);
  if (re.test(src)) return src.replace(re, (_, a, _old, b) => `${a}\n${body(a)}\n${b}`);
  if (lone.test(src)) return src.replace(lone, a => `${a}\n${body(a)}\n${close}`);
  return null;
}
const words = marker => marker.replace(/^.*?report-kit:\w+\s*/, '').replace(/\s*(\*\/|-->)$/, '').split(/[\s,]+/).filter(Boolean);
const listOf = marker => words(marker).filter(w => !w.includes('='));
const scopeOf = marker => { const w = words(marker).find(x => x.startsWith('scope=')); return w ? w.slice(6) : null; };

// nests the kit's CSS under a scope selector: @keyframes move out (they cannot nest), a :root rule becomes
// ":root <scope>" (the static checker still sees its token blocks), html and body become the scope itself
function scoped(css, sel) {
  const frames = [];
  css = css.replace(/@keyframes[^{]+\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g, m => { frames.push(m); return ''; });
  css = css.replace(/(^|[},;]\s*|\n\s*)((?::root[^{,]*?|html|body))(\s*[{,])/g, (_, pre, s, post) => `${pre}${s === 'html' || s === 'body' ? '&' : `${s} &`}${post}`);
  return `${sel} {\n${css}\n}\n${frames.join('\n')}`;
}
// runs after the components: ReportKit.init(root) wires every component inside root; the page's roots are the
// scope's matches, else the whole document
const BOOT = `(() => {
  const RK = (window.ReportKit = window.ReportKit || {});
  const on = new WeakSet();
  RK.init = root => { if (on.has(root)) return; on.add(root); (RK.inits || []).forEach(f => f(root)); };
  const go = () => (RK.root ? [...document.querySelectorAll(RK.root)] : [document]).forEach(RK.init);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go); else go();
})();`;

let sums = null;
function vendorFile(name) {
  if (!sums) {
    sums = {};
    for (const line of fs.readFileSync(path.join(KIT, 'vendor', 'checksums.txt'), 'utf8').split('\n')) {
      const m = line.match(/^([0-9a-f]{64})\s+\*?(\S+)$/);
      if (m) sums[m[2]] = m[1];
    }
  }
  const raw = zlib.gunzipSync(fs.readFileSync(path.join(KIT, 'vendor', `${name}.gz`)));
  const got = crypto.createHash('sha256').update(raw).digest('hex');
  if (got !== sums[name]) throw new Error(`kit/vendor/${name}: sha256 ${got}, checksums.txt says ${sums[name] || 'nothing'}`);
  const text = raw.toString('utf8');
  if (/<\/script/i.test(text)) throw new Error(`kit/vendor/${name} holds a closing script tag; it cannot be inlined`);
  return text.trimEnd();
}

function build(file) {
  let src = fs.readFileSync(file, 'utf8');
  const done = [];
  const css = region(src, '\\/\\* report-kit:css [^*]*\\*\\/', '/* /report-kit:css */', file, m => {
    const names = expand(listOf(m), 'css', file);
    if (!names.includes('tokens')) throw new Error(`${file}: the css marker must name tokens (every component reads them)`);
    const scope = scopeOf(m);
    done.push(`css: ${names.join(' ')}${scope ? ` in ${scope}` : ''}`);
    const css = names.map(n => fs.readFileSync(path.join(KIT, `${n}.css`), 'utf8').trim()).join('\n');
    return scope ? scoped(css, scope) : css;
  });
  if (css !== null) src = css;
  const js = region(src, '\\/\\* report-kit:js [^*]*\\*\\/', '/* /report-kit:js */', file, m => {
    const names = expand(listOf(m), 'js', file);
    const scope = scopeOf(m);
    if (scope && /[`\\$]/.test(scope)) throw new Error(`${file}: scope=${scope}: a selector without backticks, backslashes or $`);
    done.push(`js: ${names.join(' ')}${scope ? ` in ${scope}` : ''}`);
    const root = scope ? [`(window.ReportKit = window.ReportKit || {}).root = ${JSON.stringify(scope)};`] : [];
    return [...root, ...names.map(n => fs.readFileSync(path.join(KIT, `${n}.js`), 'utf8').trim()), BOOT].join('\n');
  });
  if (js !== null) src = js;
  const vendor = region(src, '<!-- report-kit:vendor [^>]*-->', '<!-- /report-kit:vendor -->', file, m => {
    const files = [...new Set(listOf(m).flatMap(n => {
      if (!VENDOR[n]) throw new Error(`${file}: no vendored library "${n}" (${Object.keys(VENDOR).join(', ')})`);
      return VENDOR[n];
    }))];
    done.push(`vendor: ${files.join(' ')}`);
    return files.map(f => `<script>\n${vendorFile(f)}\n</script>`).join('\n');
  });
  if (vendor !== null) src = vendor;
  if (!done.length) throw new Error(`${file}: no report-kit markers (see the skill's REFERENCE.md, "Build markers")`);
  fs.writeFileSync(file, src);
  console.log(`${file}: inlined ${done.join('; ')}`);
}

const args = process.argv.slice(2);
if (args.includes('--list')) {
  console.log(`components: ${ORDER.join(' ')} (or all)\nvendor: ${Object.keys(VENDOR).join(' ')}`);
  process.exit(0);
}
if (!args.length) { console.error('usage: node bin/build.cjs <page.html>...'); process.exit(2); }
try { args.forEach(build); } catch (e) { console.error(e.message); process.exit(1); }
