"""manifest_unlabeled.json → labeling_page.html (사용자 검수/라벨링 도구) 생성.

기능: 이미지별로 (1) 사진 여부/내용 확인, (2) task 지정(intake/UNLABELED 용), (3) ground_truth 확정
(UNLABELED/PASS/FAIL/BORDERLINE), (4) AI/illustration 의심 시 exclude(include_in_eval=N), (5) notes 편집.
저장: File System Access API 로 manifest_unlabeled.csv 에 직접 저장(미지원 시 다운로드). localStorage 자동저장.

주의: ground_truth 기본은 UNLABELED. 사용자가 직접 확정한다(원칙 7).
"""

from __future__ import annotations

import json
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
MANIFEST = THIS_DIR / "manifest_unlabeled.json"
OUT = THIS_DIR / "labeling_page.html"
FIELDS = ["image_id", "filepath", "task", "ground_truth", "suggested_ground_truth",
          "evidence_hint", "source_type", "source_site", "source_url", "author",
          "license_or_usage_note", "include_in_eval", "exclude_reason", "notes",
          "needs_user_review", "batch"]

HEAD = (
    "<!doctype html><meta charset='utf-8'><title>150 candidate labeling</title><style>"
    "body{font-family:sans-serif;background:#111;color:#eee;margin:0}"
    "header{position:sticky;top:0;background:#181818;padding:10px 14px;border-bottom:1px solid #333;z-index:9}"
    "button{background:#2d6cdf;color:#fff;border:0;border-radius:6px;padding:7px 11px;cursor:pointer;margin-right:6px}"
    "button.sec{background:#444}#status{color:#9fd;font-size:12px}#count{color:#fc9;font-weight:bold;font-size:13px}"
    ".filters{margin-top:6px;font-size:12px;color:#bbb}.filters label{margin-right:10px}"
    ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;padding:12px}"
    ".card{background:#1c1c1c;border:1px solid #2a2a2a;border-radius:8px;padding:8px}.card.excl{opacity:.45}"
    ".card img{width:100%;height:200px;object-fit:contain;background:#000;border-radius:6px}"
    ".meta{font-size:11px;color:#9aa;word-break:break-all;margin:4px 0}.meta a{color:#8bf}"
    ".row{margin:4px 0;font-size:12px}select,input{background:#222;color:#eee;border:1px solid #444;border-radius:4px;padding:3px;font-size:12px}"
    "input.notes{width:100%}</style>"
)

BODY = r"""
<header>
  <button onclick="save()">CSV 저장</button>
  <button class="sec" onclick="document.getElementById('lf').click()">CSV 불러오기</button>
  <input id="lf" type="file" accept=".csv" style="display:none" onchange="load(this.files[0])">
  <button class="sec" onclick="if(confirm('로컬 임시저장 삭제?')){localStorage.removeItem(LSKEY);location.reload()}">초기화</button>
  <span id="count"></span> <span id="status"></span>
  <div class="filters">
    task 필터: <label><input type=radio name=ftask value=all checked onchange=render()> all</label>
    <label><input type=radio name=ftask value=water onchange=render()> water</label>
    <label><input type=radio name=ftask value=exercise onchange=render()> exercise</label>
    <label><input type=radio name=ftask value=study onchange=render()> study</label>
    <label><input type=radio name=ftask value=UNLABELED onchange=render()> intake(UNLABELED)</label>
    &nbsp;|&nbsp; batch:
    <label><input type=radio name=fbatch value=all checked onchange=render()> all</label>
    <label><input type=radio name=fbatch value=gap_fill_02 onchange=render()> gap_fill_02</label>
    <label><input type=radio name=fbatch value=initial onchange=render()> initial</label>
    <span style="margin-left:12px">규칙: 실제 사진만. AI/그림/렌더/아이콘 의심 → include=N(exclude).</span>
  </div>
</header>
<div id="grid" class="grid"></div>
<script>
const ROWS=window.__ROWS__, FIELDS=window.__FIELDS__, LSKEY="cand150_v1";
const st={};
function init(){ROWS.forEach(r=>st[r.image_id]={...r});
  try{const s=JSON.parse(localStorage.getItem(LSKEY)||"{}");Object.keys(s).forEach(k=>{if(st[k])st[k]={...st[k],...s[k]}})}catch(e){}}
function persist(){localStorage.setItem(LSKEY,JSON.stringify(st));count()}
function count(){const done=Object.values(st).filter(r=>r.ground_truth&&r.ground_truth!=="UNLABELED"||r.include_in_eval==="N").length;
  document.getElementById("count").textContent=done+" / "+ROWS.length+" 검수";}
function setStatus(t){const s=document.getElementById("status");s.textContent=t;setTimeout(()=>{if(s.textContent===t)s.textContent=""},4000)}
function ftask(){return document.querySelector("input[name=ftask]:checked").value}
function fbatch(){return document.querySelector("input[name=fbatch]:checked").value}
function opt(v,cur){return `<option ${v===cur?"selected":""}>${v}</option>`}
function card(r){const s=st[r.image_id];const ex=s.include_in_eval==="N";
 return `<div class="card ${ex?'excl':''}" id="c_${r.image_id}">
  <img src="${r.filepath}" loading="lazy">
  <div class="meta"><b>${r.image_id}</b> [${r.source_type}] · ${r.source_site||''} · <b>${s.batch||'initial'}</b>
   ${r.source_url?`· <a href="${r.source_url}" target="_blank">source</a>`:''}<br>author: ${r.author||'-'} · lic: ${r.license_or_usage_note||''}</div>
  <div class="row">task <select onchange="upd('${r.image_id}','task',this.value)">
    ${["UNLABELED","water","exercise","study"].map(v=>opt(v,s.task)).join("")}</select>
   gt <select onchange="upd('${r.image_id}','ground_truth',this.value)">
    ${["UNLABELED","PASS","FAIL","BORDERLINE"].map(v=>opt(v,s.ground_truth)).join("")}</select></div>
  <div class="row">suggested <select onchange="upd('${r.image_id}','suggested_ground_truth',this.value)">
    ${["","PASS","FAIL","BORDERLINE"].map(v=>opt(v,s.suggested_ground_truth)).join("")}</select>
   <label><input type=checkbox ${ex?"":"checked"} onchange="upd('${r.image_id}','include_in_eval',this.checked?'Y':'N')"> include</label></div>
  <div class="row">exclude reason <select onchange="upd('${r.image_id}','exclude_reason',this.value)">
    ${["","ai_or_generated","illustration_render","irrelevant","historical_document","landscape_or_object","duplicate","low_quality","other"].map(v=>opt(v,s.exclude_reason)).join("")}</select></div>
  <div class="row"><input class="notes" placeholder="notes" value="${(s.notes||'').replace(/"/g,'&quot;')}"
    oninput="upd('${r.image_id}','notes',this.value)"></div></div>`}
function render(){const f=ftask(),b=fbatch();
  const rows=ROWS.filter(r=>(f==="all"||st[r.image_id].task===f)&&(b==="all"||(st[r.image_id].batch||"initial")===b));
  document.getElementById("grid").innerHTML=rows.map(card).join("");count()}
function upd(id,k,v){st[id][k]=v;
  if(k==="exclude_reason"&&v){st[id].include_in_eval="N"}
  if(k==="include_in_eval"&&v==="Y"){st[id].exclude_reason=""}
  st[id].needs_user_review="N";
  const c=document.getElementById("c_"+id); if(c)c.classList.toggle("excl",st[id].include_in_eval==="N");
  persist()}
function q(v){v=(v==null?"":String(v));return /[",\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v}
function buildCSV(){const L=[FIELDS.join(",")];ROWS.forEach(r=>{const s=st[r.image_id];L.push(FIELDS.map(k=>q(s[k])).join(","))});return L.join("\n")+"\n"}
async function save(){const t=buildCSV();
  if(window.showSaveFilePicker){try{const h=await showSaveFilePicker({suggestedName:"manifest_unlabeled.csv",types:[{description:"CSV",accept:{"text/csv":[".csv"]}}]});
    const w=await h.createWritable();await w.write(t);await w.close();setStatus("저장 완료");return}catch(e){if(e&&e.name==="AbortError")return}}
  const b=new Blob([t],{type:"text/csv"}),a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="manifest_unlabeled.csv";a.click();setStatus("다운로드됨")}
function parseCSV(t){const rows=[];let i=0,f="",row=[],inq=false;while(i<t.length){const c=t[i];
  if(inq){if(c==='"'){if(t[i+1]==='"'){f+='"';i+=2;continue}inq=false;i++;continue}f+=c;i++;continue}
  if(c==='"'){inq=true;i++;continue}if(c===','){row.push(f);f="";i++;continue}
  if(c==='\n'||c==='\r'){if(c==='\r'&&t[i+1]==='\n')i++;row.push(f);rows.push(row);row=[];f="";i++;continue}f+=c;i++}
  if(f.length||row.length){row.push(f);rows.push(row)}return rows.filter(r=>r.length>1)}
function load(file){if(!file)return;const rd=new FileReader();rd.onload=()=>{const rs=parseCSV(rd.result);const h=rs[0];
  rs.slice(1).forEach(r=>{const o={};h.forEach((k,i)=>o[k]=r[i]);if(o.image_id&&st[o.image_id])st[o.image_id]={...st[o.image_id],...o}});
  persist();render();setStatus("불러옴")};rd.readAsText(file)}
init();render();
</script>
"""


def main() -> None:
    rows = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []
    boot = ("<script>window.__ROWS__=" + json.dumps(rows, ensure_ascii=False)
            + ";window.__FIELDS__=" + json.dumps(FIELDS) + ";</script>")
    OUT.write_text(HEAD + boot + BODY, encoding="utf-8")
    print(f"[labeling-page] {OUT}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
