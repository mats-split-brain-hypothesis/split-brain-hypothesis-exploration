"""Bundle the results site (the "Real or Graded" dashboard) into ONE local HTML file that opens from disk, offline.
Her request (27 Oct): "make the dashboard not an artifact, but a file".

    python src/dashboard_file.py <site_dir> <d3.min.js> <out.html>

<site_dir> holds the site's published files (index.html and the other pages, assets/, data/), e.g. a copy of the
artifact's files or results_site/site. Each page becomes a string inside the output; the page shown sits in a
full-window iframe. Into every page this inlines assets/*.css and *.js, d3 (instead of the CDN), and the data/*.json
datasets the page names, with a small shim that answers the site's fetch("data/<id>.json") from them. Links between
pages and to #sections are handled inside the file. Google Fonts stay a link (offline, the pages fall back to system
fonts). Content is copied as is: no number or text is changed.
"""
import json
import re
import sys
from pathlib import Path

SHIM = r"""<script>
(function () {
  var DATA = __DATA__;
  var realFetch = window.fetch;
  // answer after the page is parsed, as a network fetch would, so the sidebar exists when the data lands
  function ready() {
    return new Promise(function (res) {
      if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { setTimeout(res, 0); });
      else setTimeout(res, 0);
    });
  }
  window.fetch = function (u) {
    var m = String(u).match(/^(?:\.\/)?data\/([\w-]+)\.json$/);
    if (m) {
      var has = Object.prototype.hasOwnProperty.call(DATA, m[1]), d = DATA[m[1]];
      return ready().then(function () {
        return has ? { ok: true, status: 200, json: function () { return Promise.resolve(JSON.parse(JSON.stringify(d))); } }
                   : { ok: false, status: 404, json: function () { return Promise.reject(new Error("not bundled")); } };
      });
    }
    return realFetch ? realFetch.apply(this, arguments) : Promise.reject(new Error("no fetch"));
  };
  function scrollTo(id, tries) {
    var t = document.getElementById(id);
    if (t) { t.scrollIntoView({ block: "start" }); return; }
    if (tries > 0) setTimeout(function () { scrollTo(id, tries - 1); }, 100);
  }
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a) return;
    var h = a.getAttribute("href");
    if (/^#./.test(h)) { e.preventDefault(); scrollTo(decodeURIComponent(h.slice(1)), 0); return; }
    if (/^https?:/i.test(h)) { e.preventDefault(); window.open(h, "_blank", "noopener"); return; }
    var m = h.match(/^(?:\.\/)?([\w-]+\.html)(#.*)?$/);
    if (m) { e.preventDefault(); parent.postMessage({ rg_nav: m[1], frag: (m[2] || "").slice(1) }, "*"); }
  }, true);
  window.addEventListener("message", function (e) { if (e.data && e.data.rg_scroll) scrollTo(e.data.rg_scroll, 30); });
  document.addEventListener("DOMContentLoaded", function () { parent.postMessage({ rg_title: document.title }, "*"); });
})();
</script>
"""

OUTER = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Real or Graded</title>
<style>
html,body{margin:0;height:100%;background:#fff}
@media (prefers-color-scheme:dark){html,body{background:#14161a}}
iframe{display:block;border:0;width:100%;height:100vh}
</style></head>
<body>
<iframe id="page" title="Real or Graded"></iframe>
<script>
var PAGES = __PAGES__;
var frame = document.getElementById("page"), pendingFrag = "";
function show(name, frag) {
  if (!Object.prototype.hasOwnProperty.call(PAGES, name)) name = "index.html";
  pendingFrag = frag || "";
  frame.srcdoc = PAGES[name];
  if (location.hash.slice(1) !== name) history.replaceState(null, "", "#" + name);
}
frame.addEventListener("load", function () {
  if (pendingFrag) frame.contentWindow.postMessage({ rg_scroll: pendingFrag }, "*");
  pendingFrag = "";
});
window.addEventListener("message", function (e) {
  if (!e.data) return;
  if (e.data.rg_nav) { show(e.data.rg_nav, e.data.frag); }
  if (e.data.rg_title) document.title = e.data.rg_title;
});
window.addEventListener("hashchange", function () { show(location.hash.slice(1)); });
show(location.hash.slice(1) || "index.html");
</script>
</body></html>
"""


def _js_json(obj):
    """JSON safe inside an inline <script>: '<' escaped so no '</script' or '<!--' can appear."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def _inline_script(code):
    if re.search(r"</script|<!--", code, re.I):
        raise ValueError("script contains '</script' or '<!--'; can't inline safely")
    return f"<script>\n{code}\n</script>"


def bundle_page(html, site, d3, datasets):
    def css(m):
        return f"<style>\n{(site / m.group(1)).read_text()}\n</style>"

    def js(m):
        return _inline_script((site / m.group(1)).read_text())

    html = re.sub(r'<link[^>]*rel="stylesheet"[^>]*href="(assets/[\w.-]+\.css)"[^>]*>', css, html)
    html = re.sub(r'<script[^>]*src="(assets/[\w.-]+\.js)"[^>]*>\s*</script>', js, html)
    html, n = re.subn(r'<script[^>]*src="https://cdnjs\.cloudflare\.com/ajax/libs/d3/[^"]+"[^>]*>\s*</script>',
                      lambda m: _inline_script(d3), html)
    # every dataset the page (or the shared scripts it now carries) names, plus the manifest
    used = {k: v for k, v in datasets.items() if k == "manifest" or re.search(rf"(?<![\w]){re.escape(k)}(?![\w])", html)}
    shim = SHIM.replace("__DATA__", _js_json(used))
    i = html.find("<script")
    html = html[:i] + shim + html[i:] if i >= 0 else html + shim
    left = re.findall(r'(?:src|href)="(?!https?:|#|data:)([^"]+\.(?:js|css|json))"', html)
    if left:
        raise ValueError(f"unbundled local references left: {left}")
    return html, sorted(used), n


def main():
    site, d3_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    d3 = d3_path.read_text()
    datasets = {p.stem: json.loads(p.read_text()) for p in sorted((site / "data").glob("*.json"))}
    pages = {}
    for p in sorted(site.glob("*.html")):
        html, used, n = bundle_page(p.read_text(), site, d3, datasets)
        pages[p.name] = html
        print(f"{p.name}: {len(html):,} characters, {len(used)} datasets, d3 inlined {n}x")
    out.write_text(OUTER.replace("__PAGES__", _js_json(pages)))
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {len(pages)} pages, {len(datasets)} datasets)")


if __name__ == "__main__":
    main()
