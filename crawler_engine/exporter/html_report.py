"""Self-contained HTML dashboard of a crawl (open it in any browser)."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from crawler_engine.analysis import KeywordAnalyzer
from crawler_engine.exceptions import ExportError
from crawler_engine.exporter.exporters import Exporter
from crawler_engine.models import CrawlResult

log = logging.getLogger(__name__)

TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Crawl Report</title>
<style>
*{box-sizing:border-box}body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f6fa;color:#1d2433}
header{background:#1f3a68;color:#fff;padding:20px 32px}header h1{margin:0;font-size:22px}
header p{margin:4px 0 0;opacity:.8;font-size:13px}main{max-width:1100px;margin:auto;padding:24px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card{background:#fff;border-radius:10px;padding:14px;box-shadow:0 1px 3px #0001}
.card b{display:block;font-size:24px;color:#1f3a68}.card span{font-size:12px;color:#667}
section{background:#fff;border-radius:10px;padding:18px;margin-top:18px;box-shadow:0 1px 3px #0001}
h2{margin:0 0 12px;font-size:16px}input{width:100%;padding:10px 12px;font-size:15px;border:1px solid #c5ccd8;border-radius:8px}
.bar{display:flex;align-items:center;margin:4px 0;font-size:13px}.bar i{width:110px;font-style:normal}
.bar div{background:#4a7bd0;height:14px;border-radius:3px}.bar em{margin-left:8px;color:#667;font-style:normal}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:8px;border-bottom:1px solid #e6e9ef;vertical-align:top}
th{background:#f0f3f9}a{color:#2a5bb8;word-break:break-all}.muted{color:#778;font-size:12px}
mark{background:#ffe58a}.hit{padding:10px 0;border-bottom:1px solid #eee}.fail{color:#b3261e}
</style></head><body>
<header><h1>Web Crawl Report</h1><p id="gen"></p></header><main>
<div class="cards" id="cards"></div>
<section><h2>Keyword search</h2><input id="q" placeholder="Type a word, e.g. love, life, python..."><div id="hits"></div></section>
<section><h2>Top keywords</h2><div id="kw"></div></section>
<section><h2>Pages crawled (<span id="n"></span>)</h2><div style="overflow-x:auto"><table id="tbl"></table></div></section>
<section id="failsec"><h2>Failed URLs</h2><div id="fails"></div></section></main>
<script>
const D=__DATA__;const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
$('gen').textContent='Generated '+D.generated;
const S=D.stats,cards=[['Pages visited',S.pages_visited],['Failures',S.failures],['Blocked by robots',S.skipped_robots],
['Duplicates avoided',S.duplicates_skipped],['URLs discovered',S.urls_discovered],['KiB downloaded',(S.bytes_downloaded/1024).toFixed(1)],
['Seconds',S.duration_seconds.toFixed(2)]];
$('cards').innerHTML=cards.map(c=>`<div class="card"><b>${c[1]}</b><span>${c[0]}</span></div>`).join('');
const max=D.keywords.length?D.keywords[0][1]:1;
$('kw').innerHTML=D.keywords.map(k=>`<div class="bar"><i>${esc(k[0])}</i><div style="width:${k[1]/max*60}%"></div><em>${k[1]}</em></div>`).join('')||'<p class="muted">No data</p>';
$('n').textContent=D.pages.length;
$('tbl').innerHTML='<tr><th>Depth</th><th>Title / URL</th><th>H1</th><th>Words</th><th>Links</th><th>Images</th></tr>'+
D.pages.map(p=>`<tr><td>${p.depth}</td><td><b>${esc(p.title||'(no title)')}</b><br><a href="${esc(p.url)}" target="_blank">${esc(p.url)}</a></td>
<td>${esc((p.headings.h1||[]).join(' | '))}</td><td>${p.word_count}</td><td>${p.links.length}</td><td>${p.images.length}</td></tr>`).join('');
if(!D.failed.length)$('failsec').style.display='none';
$('fails').innerHTML=D.failed.map(f=>`<p class="fail">${esc(f.url)} <span class="muted">(${esc(f.reason)})</span></p>`).join('');
const tok=t=>(t.toLowerCase().match(/[a-z0-9']+/g)||[]);
$('q').addEventListener('input',e=>{
  const terms=tok(e.target.value);if(!terms.length){$('hits').innerHTML='';return;}
  const res=D.pages.map(p=>{const ti=tok(p.title),he=tok(Object.values(p.headings).flat().join(' ')),bo=tok(p.text);
    const c=(a,t)=>a.filter(x=>x===t).length;let sc=0,all=true;
    terms.forEach(t=>{const n=c(ti,t)*5+c(he,t)*3+c(bo,t);sc+=n;if(!n)all=false;});
    return{p,sc,all};}).filter(r=>r.all&&r.sc).sort((a,b)=>b.sc-a.sc).slice(0,10);
  $('hits').innerHTML=res.length?res.map(r=>{const low=r.p.text.toLowerCase();
    const i=Math.max(0,Math.min(...terms.map(t=>low.indexOf(t)).filter(x=>x>=0))-80);
    let sn=esc(r.p.text.slice(i,i+220));terms.forEach(t=>{sn=sn.replace(new RegExp('('+t.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')+')','gi'),'<mark>$1</mark>')});
    return `<div class="hit"><b>${esc(r.p.title)}</b> <span class="muted">score ${r.sc}</span><br><a href="${esc(r.p.url)}" target="_blank">${esc(r.p.url)}</a><br>...${sn}...</div>`}).join('')
    :'<p class="muted">No results</p>';
});
</script></body></html>"""


class HtmlReportExporter(Exporter):
    """Writes ``report.html``: stats cards, live search, keyword chart, page table."""

    def export(self, result: CrawlResult, path: Path) -> Path:
        path = self._prepare(path)
        data = {
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stats": result.stats.to_dict(),
            "failed": [vars(f) for f in result.failed],
            "keywords": KeywordAnalyzer(result.pages).top_keywords(15),
            "pages": [p.to_dict() for p in result.pages],
        }
        payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        try:
            path.write_text(TEMPLATE.replace("__DATA__", payload), encoding="utf-8")
        except OSError as exc:
            raise ExportError(f"Cannot write {path}: {exc}") from exc
        log.info("Wrote HTML report: %s", path)
        return path
