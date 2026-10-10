"""Builds the round-2 prototype into out/ (reference only, not product code).

Reads the logo from the repo's own vector files, writes the four hero pages
(make_pages.py), copies src/ to out/ and injects the logo data into
out/kit/landing.js. Preview: `python3 build.py && cd out && python3 -m http.server`
then open http://127.0.0.1:8000/index-preview.html (three.js loads from
jsDelivr here; the product serves it itself).
"""
import json, pathlib, re, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p / "frontend/public/brand/neoori-logo.svg").exists())
logo = (REPO / "frontend/public/brand/neoori-logo.svg").read_text()
mark = (REPO / "frontend/public/brand/neoori-mark.svg").read_text()

grad = re.search(r'<linearGradient[^>]*x1="([\d.]+)"[^>]*x2="([\d.]+)"[^>]*>(.*?)</linearGradient>', logo, re.S)
stops = re.findall(r'offset="([\d.]+)" stop-color="(#[0-9a-fA-F]{6})"', grad.group(3))
navy = re.search(r'<g fill="(#[0-9a-fA-F]{6})"', logo).group(1)
paths = re.findall(r'<path([^>]*?)\sd="([^"]+)"', logo)
letters = [d for attrs, d in paths if "url(#" not in attrs][:4]
oo = next(d for attrs, d in paths if "url(#" in attrs)
data = {
    "navy": navy,
    "letters": dict(zip("neri", letters)),
    "oo": oo,
    "g": {"x1": float(grad.group(1)), "x2": float(grad.group(2)), "stops": stops},
    "mark": re.search(r'<path[^>]*\sd="([^"]+)"', mark).group(1),
}

subprocess.run([sys.executable, str(HERE / "make_pages.py")], check=True)
out = HERE / "out"
if out.exists():
    shutil.rmtree(out)
shutil.copytree(HERE / "src", out)
js = out / "kit/landing.js"
js.write_text(js.read_text().replace("/*LOGO_DATA*/", json.dumps(data, separators=(",", ":"))))
idx = (out / "index.html").read_text()
(out / "index-preview.html").write_text(
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    '<style>body{margin:0}[hidden]{display:none!important}</style></head><body>' + idx + "</body></html>")
print("built", out)
