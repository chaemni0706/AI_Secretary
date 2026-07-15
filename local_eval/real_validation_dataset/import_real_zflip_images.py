"""Z Flip3 실제 촬영 이미지(~/real_zflip_images/*.jpg)를 validation dataset 으로 편입.

파일명이 타임스탬프뿐이라 verification_type/ground_truth 를 파일명으로 추정할 수 없다.
따라서 **자동 추정하지 않고**, 사용자가 확인 후 채우도록 TODO 로 넣고 분류 도구를 제공한다.

2단계 워크플로:

1) import (기본) — 이미지를 images/real_zflip/ 로 복사하고,
   - annotations/validation_manifest.json 에 TODO 엔트리 추가(기존 엔트리 보존/병합)
   - annotations/real_zflip_annotation.csv (사용자가 채울 분류표) 생성
   - real_zflip_preview.html (썸네일 미리보기) 생성
   verification_type=TODO 라 evaluate_validation_dataset.py 의 기본 --types 필터에서 자동 제외된다.

     python local_eval/real_validation_dataset/import_real_zflip_images.py

2) apply — 사용자가 CSV 를 채운 뒤 실행. CSV 의 verification_type/ground_truth 를 읽어
   이미지를 images/<type>/ 로 이동하고 manifest 엔트리를 갱신한다(그러면 평가기에 바로 편입).

     python local_eval/real_validation_dataset/import_real_zflip_images.py \
         --apply-csv local_eval/real_validation_dataset/annotations/real_zflip_annotation.csv

기존 real_validation_dataset 구조/데이터, backend/flutter/rule engine/기존 metrics 는 건드리지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
IMAGES_DIR = THIS_DIR / "images"
INBOX_DIR = IMAGES_DIR / "real_zflip"           # 분류 전 임시 보관(기존 type 폴더 오염 방지)
MANIFEST = THIS_DIR / "annotations" / "validation_manifest.json"
CSV_HELPER = THIS_DIR / "annotations" / "real_zflip_annotation.csv"
PREVIEW_HTML = THIS_DIR / "real_zflip_preview.html"

DEFAULT_SRC = Path.home() / "real_zflip_images"
SOURCE_TAG = "real_zflip"
VALID_TYPES = {"water", "exercise", "study"}
VALID_GT = {"PASS", "FAIL", "BORDERLINE"}
CSV_FIELDS = ["image", "verification_type", "ground_truth", "exercise_activity_type",
              "expected_evidence", "description"]


def _load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"dataset": "real_validation_dataset", "count": 0, "images": []}


def _save_manifest(data: dict) -> None:
    data["count"] = len(data["images"])
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _entry_index(images: list[dict], rel_or_name: str) -> int | None:
    """manifest 에서 real_zflip 원본 파일명이 일치하는 엔트리 인덱스(없으면 None)."""
    base = Path(rel_or_name).name
    for i, e in enumerate(images):
        if e.get("source") == SOURCE_TAG and Path(e.get("image", "")).name == base:
            return i
    return None


# ---------------------------------------------------------------------------
# 1) import
# ---------------------------------------------------------------------------

def do_import(src_dir: Path) -> None:
    if not src_dir.exists():
        raise SystemExit(f"소스 폴더가 없습니다: {src_dir}")
    files = sorted(p for p in src_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not files:
        raise SystemExit(f"이미지가 없습니다: {src_dir}")

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()
    images = manifest["images"]

    added = 0
    for src in files:
        rel = f"real_zflip/{src.name}"
        dst = IMAGES_DIR / rel
        if not dst.exists():
            shutil.copy2(src, dst)
        if _entry_index(images, src.name) is not None:
            continue  # 이미 manifest 에 있음(재실행 idempotent)
        images.append({
            "image": rel,               # evaluate_validation_dataset.py 가 읽는 키(images/ 기준 상대경로)
            "image_path": rel,           # 요청 스키마 키(호환)
            "verification_type": "TODO",  # 자동 추정 금지 — 사용자가 분류
            "ground_truth": "TODO",       # 자동 추정 금지 — 사용자가 입력
            "expected_evidence": [],
            "description": "",
            "exercise_activity_type": None,
            "source": SOURCE_TAG,
            "difficulty": "real_zflip",
            "annotated": False,           # 분류 완료 여부 플래그
        })
        added += 1

    _save_manifest(manifest)
    _write_csv_helper(images)
    _write_preview(images)

    print(f"[import] {len(files)}장 확인, manifest 신규 추가 {added}개 (총 {manifest['count']} 엔트리)")
    print(f"  이미지 복사 위치: {INBOX_DIR}")
    print(f"  분류표(CSV): {CSV_HELPER}")
    print(f"  미리보기(HTML): {PREVIEW_HTML}")
    print("  다음: CSV 의 verification_type/ground_truth 를 채운 뒤 --apply-csv 로 편입하세요.")


def _write_csv_helper(images: list[dict]) -> None:
    rows = [e for e in images if e.get("source") == SOURCE_TAG]
    with CSV_HELPER.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for e in rows:
            w.writerow({
                "image": e.get("image", ""),
                "verification_type": "" if e["verification_type"] == "TODO" else e["verification_type"],
                "ground_truth": "" if e["ground_truth"] == "TODO" else e["ground_truth"],
                "exercise_activity_type": e.get("exercise_activity_type") or "",
                "expected_evidence": ";".join(e.get("expected_evidence", [])),
                "description": e.get("description", ""),
            })


# labeling tool 의 evidence 어휘(사용자 지정). expected_evidence 컬럼용 참조 라벨.
_EVIDENCE_VOCAB = {
    "water": ["visible_water", "filled_container", "empty_container", "non_water_beverage"],
    "exercise": ["treadmill_present", "dumbbell_present", "exercise_pose_visible", "unrelated_environment"],
    "study": ["open_textbook", "handwritten_notes", "pdf_document", "gaming_content"],
}
_ACTIVITIES = ["gym", "running", "home_workout", "swimming", "yoga", "pilates"]


def _write_preview(images: list[dict]) -> None:
    rows = [e for e in images if e.get("source") == SOURCE_TAG]
    data = [{
        "image": e["image"],
        "name": Path(e["image"]).name,
        "verification_type": "" if e["verification_type"] == "TODO" else e["verification_type"],
        "ground_truth": "" if e["ground_truth"] == "TODO" else e["ground_truth"],
        "exercise_activity_type": e.get("exercise_activity_type") or "",
        "expected_evidence": e.get("expected_evidence", []) or [],
        "description": e.get("description", "") or "",
    } for e in rows]

    boot = (
        "<script>window.__ROWS__=" + json.dumps(data, ensure_ascii=False)
        + ";window.__VOCAB__=" + json.dumps(_EVIDENCE_VOCAB, ensure_ascii=False)
        + ";window.__ACTS__=" + json.dumps(_ACTIVITIES, ensure_ascii=False)
        + ";window.__CSVNAME__=" + json.dumps(CSV_HELPER.name) + ";</script>"
    )
    PREVIEW_HTML.write_text(_LABELING_HTML_HEAD + boot + _LABELING_HTML_BODY, encoding="utf-8")


_LABELING_HTML_HEAD = (
    "<!doctype html><meta charset='utf-8'><title>real_zflip labeling tool</title>"
    "<style>"
    "body{font-family:sans-serif;background:#111;color:#eee;margin:0}"
    "header{position:sticky;top:0;background:#181818;padding:12px 16px;border-bottom:1px solid #333;z-index:10}"
    "header h1{font-size:16px;margin:0 0 8px}"
    "button{background:#2d6cdf;color:#fff;border:0;border-radius:6px;padding:8px 12px;cursor:pointer;font-size:13px;margin-right:8px}"
    "button.sec{background:#444}"
    "#status{color:#9fd;font-size:12px;margin-left:8px}"
    "#count{color:#fc9;font-size:13px;font-weight:bold}"
    ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;padding:16px}"
    ".card{background:#1c1c1c;border-radius:8px;padding:10px;border:1px solid #2a2a2a}"
    ".card.done{border-color:#2d6cdf}"
    ".card img{width:100%;height:220px;object-fit:cover;border-radius:6px;background:#000}"
    ".fn{font-size:11px;color:#999;word-break:break-all;margin:6px 0}"
    ".rowlab{font-size:12px;color:#bbb;margin:6px 0 2px}"
    ".opts label{display:inline-block;font-size:12px;margin:2px 8px 2px 0;cursor:pointer}"
    ".evid{display:none}.evid.show{display:block}"
    "select,input[type=text]{background:#222;color:#eee;border:1px solid #444;border-radius:4px;padding:4px;font-size:12px}"
    "input[type=text]{width:100%}"
    "</style>"
)

_LABELING_HTML_BODY = r"""
<header>
  <h1>Z Flip3 real images — 라벨링 도구</h1>
  <button onclick="saveCSV()">CSV 저장</button>
  <label class="sec" style="display:inline-block"><button class="sec" onclick="document.getElementById('loadf').click()">CSV 불러오기</button></label>
  <input id="loadf" type="file" accept=".csv" style="display:none" onchange="loadCSV(this.files[0])">
  <button class="sec" onclick="if(confirm('로컬 임시저장을 지웁니다.')){localStorage.removeItem(LSKEY);location.reload()}">초기화</button>
  <span id="count"></span><span id="status"></span>
</header>
<div id="grid" class="grid"></div>
<script>
const ROWS = window.__ROWS__, VOCAB = window.__VOCAB__, ACTS = window.__ACTS__;
const CSVNAME = window.__CSVNAME__, LSKEY = "zflip_annot_v1";
const FIELDS = ["image","verification_type","ground_truth","exercise_activity_type","expected_evidence","description"];
const state = {};  // image -> {verification_type, ground_truth, exercise_activity_type, expected_evidence:[], description}

function blank(){return {verification_type:"",ground_truth:"",exercise_activity_type:"",expected_evidence:[],description:""};}
function initState(){
  ROWS.forEach(r=>{state[r.image]={verification_type:r.verification_type||"",ground_truth:r.ground_truth||"",
    exercise_activity_type:r.exercise_activity_type||"",expected_evidence:(r.expected_evidence||[]).slice(),
    description:r.description||""};});
  try{const saved=JSON.parse(localStorage.getItem(LSKEY)||"{}");
    Object.keys(saved).forEach(k=>{if(state[k])state[k]=Object.assign(blank(),saved[k]);});}catch(e){}
}
function persist(){localStorage.setItem(LSKEY,JSON.stringify(state));updateCount();}
function updateCount(){
  const n=ROWS.length, done=ROWS.filter(r=>state[r.image].verification_type&&state[r.image].ground_truth).length;
  document.getElementById("count").textContent=done+" / "+n+" 완료";
}
function setStatus(t){const s=document.getElementById("status");s.textContent=t;setTimeout(()=>{if(s.textContent===t)s.textContent="";},4000);}

function evidenceBox(img){
  const st=state[img], vt=st.verification_type; if(!vt||!VOCAB[vt])return "";
  return "<div class='rowlab'>evidence</div><div class='opts'>"+VOCAB[vt].map(ev=>
    "<label><input type='checkbox' data-img='"+img+"' data-ev='"+ev+"' "+
    (st.expected_evidence.indexOf(ev)>=0?"checked":"")+" onchange='onEvid(this)'> "+ev+"</label>").join("")+"</div>";
}
function activityBox(img){
  const st=state[img]; if(st.verification_type!=="exercise")return "";
  return "<div class='rowlab'>activity</div><select data-img='"+img+"' onchange='onAct(this)'>"+
    "<option value=''>(선택)</option>"+ACTS.map(a=>"<option "+(st.exercise_activity_type===a?"selected":"")+">"+a+"</option>").join("")+"</select>";
}
function cardHTML(r){
  const st=state[r.image], img=r.image, done=st.verification_type&&st.ground_truth;
  const typeR=["water","exercise","study"].map(t=>"<label><input type='radio' name='t_"+img+"' data-img='"+img+"' value='"+t+"' "+(st.verification_type===t?"checked":"")+" onchange='onType(this)'> "+t+"</label>").join("");
  const gtR=["PASS","FAIL"].map(g=>"<label><input type='radio' name='g_"+img+"' data-img='"+img+"' value='"+g+"' "+(st.ground_truth===g?"checked":"")+" onchange='onGT(this)'> "+g+"</label>").join("");
  return "<div class='card"+(done?" done":"")+"' id='card_"+cssid(img)+"'>"+
    "<img src='images/"+img+"' loading='lazy'>"+
    "<div class='fn'>"+r.name+"</div>"+
    "<div class='rowlab'>type</div><div class='opts'>"+typeR+"</div>"+
    "<div class='rowlab'>ground_truth</div><div class='opts'>"+gtR+"</div>"+
    "<div class='actwrap'>"+activityBox(img)+"</div>"+
    "<div class='evidwrap'>"+evidenceBox(img)+"</div>"+
    "<div class='rowlab'>description</div><input type='text' data-img='"+img+"' value=\""+esc(st.description)+"\" oninput='onDesc(this)'>"+
    "</div>";
}
function cssid(s){return s.replace(/[^a-zA-Z0-9]/g,"_");}
function esc(s){return (s||"").replace(/"/g,"&quot;");}
function rerenderExtras(img){
  const c=document.getElementById("card_"+cssid(img)); if(!c)return;
  c.querySelector(".actwrap").innerHTML=activityBox(img);
  c.querySelector(".evidwrap").innerHTML=evidenceBox(img);
  c.classList.toggle("done", !!(state[img].verification_type&&state[img].ground_truth));
}
function onType(el){const img=el.dataset.img;state[img].verification_type=el.value;
  // 타입이 바뀌면 새 어휘에 없는 evidence 는 정리
  state[img].expected_evidence=state[img].expected_evidence.filter(e=>(VOCAB[el.value]||[]).indexOf(e)>=0);
  if(el.value!=="exercise")state[img].exercise_activity_type="";
  rerenderExtras(img);persist();}
function onGT(el){state[el.dataset.img].ground_truth=el.value;rerenderExtras(el.dataset.img);persist();}
function onAct(el){state[el.dataset.img].exercise_activity_type=el.value;persist();}
function onDesc(el){state[el.dataset.img].description=el.value;persist();}
function onEvid(el){const st=state[el.dataset.img],ev=el.dataset.ev,i=st.expected_evidence.indexOf(ev);
  if(el.checked&&i<0)st.expected_evidence.push(ev); else if(!el.checked&&i>=0)st.expected_evidence.splice(i,1);persist();}

function q(v){v=(v==null?"":String(v));return /[",\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;}
function buildCSV(){
  const lines=[FIELDS.join(",")];
  ROWS.forEach(r=>{const st=state[r.image];
    lines.push([q(r.image),q(st.verification_type),q(st.ground_truth),q(st.exercise_activity_type),
      q(st.expected_evidence.join(";")),q(st.description)].join(","));});
  return lines.join("\n")+"\n";
}
async function saveCSV(){
  const text=buildCSV();
  if(window.showSaveFilePicker){
    try{const h=await showSaveFilePicker({suggestedName:CSVNAME,types:[{description:"CSV",accept:{"text/csv":[".csv"]}}]});
      const w=await h.createWritable();await w.write(text);await w.close();
      setStatus("저장 완료 → apply-csv 로 편입하세요");return;
    }catch(e){if(e&&e.name==="AbortError")return;}
  }
  const blob=new Blob([text],{type:"text/csv"});const a=document.createElement("a");
  a.href=URL.createObjectURL(blob);a.download=CSVNAME;a.click();
  setStatus("다운로드됨 → annotations/ 에 덮어쓰기");
}
function parseCSV(text){
  const rows=[];let i=0,f="",row=[],inq=false;
  while(i<text.length){const c=text[i];
    if(inq){if(c==='"'){if(text[i+1]==='"'){f+='"';i+=2;continue;}inq=false;i++;continue;}f+=c;i++;continue;}
    if(c==='"'){inq=true;i++;continue;}
    if(c===','){row.push(f);f="";i++;continue;}
    if(c==='\n'||c==='\r'){if(c==='\r'&&text[i+1]==='\n')i++;row.push(f);rows.push(row);row=[];f="";i++;continue;}
    f+=c;i++;}
  if(f.length||row.length){row.push(f);rows.push(row);}
  return rows.filter(r=>r.length>1||(r.length===1&&r[0]!==""));
}
function loadCSV(file){if(!file)return;const rd=new FileReader();
  rd.onload=()=>{const rows=parseCSV(rd.result);if(!rows.length)return;
    const head=rows[0];const idx={};FIELDS.forEach(fn=>idx[fn]=head.indexOf(fn));
    rows.slice(1).forEach(r=>{const img=r[idx.image];if(!img||!state[img])return;
      state[img].verification_type=r[idx.verification_type]||"";
      state[img].ground_truth=(r[idx.ground_truth]||"").toUpperCase();
      state[img].exercise_activity_type=r[idx.exercise_activity_type]||"";
      state[img].expected_evidence=(r[idx.expected_evidence]||"").split(";").filter(Boolean);
      state[img].description=r[idx.description]||"";});
    persist();render();setStatus("CSV 불러옴");};
  rd.readAsText(file);}

function render(){document.getElementById("grid").innerHTML=ROWS.map(cardHTML).join("");updateCount();}
initState();render();
</script>
"""


# ---------------------------------------------------------------------------
# 2) apply (CSV → manifest 갱신 + 이미지 이동)
# ---------------------------------------------------------------------------

def do_apply(csv_path: Path) -> None:
    if not csv_path.exists():
        raise SystemExit(f"CSV 가 없습니다: {csv_path}")
    manifest = _load_manifest()
    images = manifest["images"]

    updated = skipped = 0
    with csv_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            image = (row.get("image") or "").strip()
            vt = (row.get("verification_type") or "").strip().lower()
            gt = (row.get("ground_truth") or "").strip().upper()
            if not image:
                continue
            idx = _entry_index(images, image)
            if idx is None:
                print(f"[warn] manifest 에 없는 이미지: {image}")
                continue
            if vt not in VALID_TYPES or gt not in VALID_GT:
                skipped += 1  # 아직 미분류(빈칸/TODO) → 그대로 둠
                continue
            entry = images[idx]
            # 이미지를 images/<type>/ 로 이동(있으면 그대로), manifest image 경로 갱신
            cur_rel = entry["image"]
            new_rel = f"{vt}/{Path(cur_rel).name}"
            src = IMAGES_DIR / cur_rel
            dst = IMAGES_DIR / new_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.exists() and src.resolve() != dst.resolve():
                shutil.move(str(src), str(dst))
            entry["image"] = new_rel
            entry["image_path"] = new_rel
            entry["verification_type"] = vt
            entry["ground_truth"] = gt
            act = (row.get("exercise_activity_type") or "").strip() or None
            entry["exercise_activity_type"] = act if vt == "exercise" else None
            ev = (row.get("expected_evidence") or "").strip()
            entry["expected_evidence"] = [x for x in ev.split(";") if x] if ev else []
            entry["description"] = (row.get("description") or "").strip()
            entry["annotated"] = True
            updated += 1

    _save_manifest(manifest)
    print(f"[apply] 편입 완료: {updated}개 갱신, {skipped}개 미분류(건너뜀)")
    if updated:
        print("  이제 evaluate_validation_dataset.py 로 바로 평가할 수 있습니다:")
        print("    python local_eval/real_validation_dataset/evaluate_validation_dataset.py --types water,exercise,study")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(DEFAULT_SRC), help="원본 이미지 폴더 (기본 ~/real_zflip_images)")
    ap.add_argument("--apply-csv", default=None, help="채워진 분류 CSV 를 읽어 manifest 편입")
    args = ap.parse_args()

    if args.apply_csv:
        do_apply(Path(args.apply_csv))
    else:
        do_import(Path(args.src).expanduser())


if __name__ == "__main__":
    main()
