"""Builds preview.html: report/index.html with variant C injected (the guide's seam line, the see-all buttons shown,
section.html after the page's last script). Run from anywhere: python3 make-preview.py"""
import pathlib, re
here = pathlib.Path(__file__).resolve().parent
page = (here / "../../../index.html").read_text()
section = (here / "section.html").read_text()
seam = ('  root.qsBrowse = { show: (id, cur) => fill(card, G.q[id], cur || null),\n'
        '                    restore: (id) => { const i = CAT[st.cat].ids.indexOf(id); if (i >= 0) st.i = i; render(false); } };\n')
anchor = "  render(false);\n  const again = () =>"
assert page.count(anchor) == 1, "the guide's script moved"
page = page.replace(anchor, "  render(false);\n" + seam + "  const again = () =>")
page, n = re.subn(r'(<button type="button" class="qs-seeall" data-category="[^"]+") hidden>', r"\1>", page)
assert n, "no see-all buttons"
i = page.rfind("</script>") + len("</script>")
page = page[:i] + "\n" + section + page[i:]
(here / "preview.html").write_text(page)
print("preview.html written;", n, "see-all buttons shown")
