import json
from pathlib import Path

runs = Path(__file__).resolve().parents[1] / "job_scraper" / "linkedin_runs"
src = runs / "pass1b_20261026_1238_unique.json"
jobs = json.loads(src.read_text(encoding="utf-8-sig"))
out = runs / "pass1b_20261026_1238_unique_links.html"

rows = []
for j in jobs:
    title = str(j.get("title") or "").replace("<", "&lt;")
    company = str(j.get("company") or "").replace("<", "&lt;")
    loc = str(j.get("location") or "").replace("<", "&lt;")
    url = str(j.get("url") or "")
    date = str(j.get("date") or "")
    q = str(j.get("query") or "").replace("<", "&lt;")
    link = f'<a href="{url}" target="_blank" rel="noopener">{url}</a>' if url else "(sin url)"
    rows.append(
        f"<tr><td>{date}</td><td>{title}</td><td>{company}</td>"
        f"<td>{loc}</td><td>{q}</td><td>{link}</td></tr>"
    )

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LinkedIn jobs</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#111;color:#eee}}
input{{width:100%;max-width:480px;padding:8px;margin-bottom:12px;font-size:14px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border-bottom:1px solid #333;padding:8px;text-align:left;vertical-align:top}}
th{{position:sticky;top:0;background:#1a1a1a}}
a{{color:#6cb6ff;word-break:break-all}}
tr:hover{{background:#1c1c1c}}
.meta{{color:#aaa;margin-bottom:8px}}
</style></head><body>
<h1>LinkedIn jobs</h1>
<p class="meta">{len(jobs)} ofertas — filtra abajo · clic en el link</p>
<input id="f" placeholder="Filtrar (titulo, empresa, ciudad...)" oninput="filter()">
<table><thead><tr><th>Fecha</th><th>Titulo</th><th>Empresa</th><th>Ubicacion</th><th>Query</th><th>Link</th></tr></thead>
<tbody id="tb">{"".join(rows)}</tbody></table>
<script>
function filter(){{
  const q=document.getElementById('f').value.toLowerCase();
  for (const tr of document.querySelectorAll('#tb tr')) {{
    tr.style.display = tr.innerText.toLowerCase().includes(q) ? '' : 'none';
  }}
}}
</script></body></html>
"""
out.write_text(html, encoding="utf-8")
print(out)
print("with_url", sum(1 for j in jobs if j.get("url")))
