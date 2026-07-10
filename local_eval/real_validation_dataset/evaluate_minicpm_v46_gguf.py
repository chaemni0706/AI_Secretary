"""MiniCPM-V-4.6 GGUF batch validation (llama.cpp / llama-mtmd-cli).

파이프라인: image → llama-mtmd-cli(MiniCPM-V-4.6, 서술형 evidence) → 보수적 파서 → VisionAnalysis
          → backend Rule Engine(evaluate_image_verification) → verified/rejected/retake_required.

원칙(프로젝트 규칙):
- VLM 은 PASS/FAIL 을 결정하지 않는다. 시각 evidence 서술만 한다(프롬프트가 판정 금지).
- 최종 판정은 backend Rule Engine. FP=0 최우선.
- Flutter/backend API/Rule Engine core/기존 SmolVLM·Qwen 어댑터/Qwen fallback/기존 metrics 구조는 건드리지 않는다.
  (이 스크립트는 신규 파일이며 backend 스키마/Rule Engine 을 read-only 로 import 만 한다.)

파서 특이사항(MiniCPM-V-4.6 대응):
- MiniCPM 은 "There is no visible liquid, study materials, handwriting..." 처럼 **부정 나열**을 자주 낸다.
  단순 substring 파서는 'handwriting' 등을 오탐(FP) 한다. → **부정 문장을 제거한 뒤** positive 매칭한다.
- 보수적 규칙: 용기 '이름'만(water bottle/cup)으로 visible_water 금지, book/laptop 단독으로 study positive 금지,
  자세는 '적극적 운동 동작' 표현일 때만 exercise_pose_visible.

실행: 하단 --help 또는 프로젝트 지시의 smoke/full 명령 참고.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database.schema.image_verification_schema import (  # noqa: E402
    ImageVerificationContext,
    VisionAnalysis,
)
from backend.services.image_verification_rule_engine import (  # noqa: E402
    evaluate_image_verification,
)

# ---------------------------------------------------------------------------
# 프롬프트 (판정 금지, 시각 evidence 서술만) — 프로젝트 지시문 그대로
# ---------------------------------------------------------------------------
PROMPTS = {
    "water": (
        "Describe visible evidence for water verification only. Mention: "
        "visible water or clear liquid; cup, glass, bottle, tumbler, or container; "
        "water surface, water level, or liquid inside a transparent container; "
        "empty container or no liquid visible; coffee, tea, juice, soda, or non-water beverage. "
        "Do not infer water from a bottle/cup/container name alone. Do not decide PASS or FAIL."
    ),
    "study": (
        "Describe visible evidence for study verification only. Mention: "
        "open textbook, notebook, worksheet, printed learning material; "
        "handwritten notes, highlighted text, problem solving; "
        "PDF document, lecture screen, coding screen; "
        "game, SNS, movie, entertainment, unrelated work screen. "
        "Do not infer studying from a desk, book, or laptop alone. Do not decide PASS or FAIL."
    ),
    "exercise": (
        "Describe visible evidence for exercise verification only. Mention: "
        "gym environment; treadmill, dumbbell, barbell, weight machine, exercise bike; "
        "exercise mat, home workout environment; active exercise pose or movement; "
        "shoes-only, water bottle-only, food, office, bedroom, unrelated environment. "
        "Do not infer exercise from shoes, clothes, or a person standing alone. Do not decide PASS or FAIL."
    ),
}

# ---------------------------------------------------------------------------
# 부정 처리: 부정 문장을 제거한 텍스트(=positive 매칭용)와 원문(=empty 감지용) 분리
# ---------------------------------------------------------------------------
_NEG_CUES = (
    "no visible", "there is no", "there are no", "not visible", "without",
    "no water", "no liquid", "no study", "no exercise", "no handwriting",
    "cannot see", "can't see", "doesn't show", "does not show", "no sign of",
    "absence of", "absent", "lack of", "no other items", "not engaged",
    "no active", "no equipment", "no gym", "no physical activity", "rather than",
    "n't ", " no ",
)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?\n;]", text.lower()) if s.strip()]


def _positive_text(text: str) -> str:
    """부정 cue 가 있는 문장을 제거한 나머지(=긍정 서술만) 반환."""
    keep = [s for s in _sentences(text) if not any(c in (" " + s + " ") for c in _NEG_CUES)]
    return " . ".join(keep)


def _has(text: str, phrases) -> bool:
    return any(p in text for p in phrases)


# ---------------------------------------------------------------------------
# 파서 (보수적, schema enum 만 생성). insufficient_* 는 빈 evidence 로 표현.
# ---------------------------------------------------------------------------
_CONTAINER_WORDS = {"glass": "glass", "tumbler": "tumbler", "mug": "cup",
                    "water bottle": "water_bottle", "bottle": "water_bottle", "cup": "cup"}


def _water_container_object(pos: str):
    for word, label in _CONTAINER_WORDS.items():
        if word in pos:
            return [{"label": label, "confidence": 0.6, "evidence": None}]
    return []


def parse_water(raw: str) -> dict:
    pos = _positive_text(raw)
    # 'non-empty'/'not empty' 는 '비어있지 않음'(=참) → empty 오탐 방지 위해 제거 후 empty 감지.
    full = re.sub(r"\bnon[\s-]?empty\b|\bnot (a |an )?empty\b|\bnon[\s-]?empty\b", " ", raw.lower())
    ev: list[str] = []
    # 실제 물/액체 '존재' 표현만 positive (용기 이름 단독 금지)
    water_pos = ("water in ", "water inside", "glass of water", "cup of water",
                 "bottle of water", "filled with water", "water level", "water surface",
                 "holding water", "pouring water", "drinking water", "visible water",
                 "water is visible", "full of water", "half full of water")
    clear_pos = ("clear liquid", "transparent liquid")
    if _has(pos, water_pos):
        ev += ["visible_water", "filled_container"]
    elif _has(pos, clear_pos) and "water" in pos:
        ev += ["visible_clear_liquid", "filled_container"]
    # 비음료(coffee/tea/...)는 '적극적' 표현일 때만. 프롬프트가 음료 목록을 나열하므로 MiniCPM 이
    # 'a non-coffee, tea, juice, or soda beverage'(=물) 처럼 echo/부정하는 것을 오탐하지 않도록 한정.
    bev_pos = ("cup of coffee", "coffee is", "contains coffee", "a coffee", "cup of tea",
               "glass of tea", "tea is", "glass of juice", "cup of juice", "juice is",
               "can of soda", "soda is", "cola is", "latte", "iced coffee", "milk tea")
    if _has(pos, bev_pos):
        ev.append("non_water_beverage")
    # empty: 명시적 empty 또는 물/액체 부정 → empty_container
    empty_cue = ("empty", "appears empty", "looks empty", "nothing inside", "no liquid",
                 "no water", "no visible liquid", "without water", "no beverage")
    if _has(full, empty_cue):
        ev.append("empty_container")
    ev = _dedupe(ev)
    objs = _water_container_object(pos) if ("visible_water" in ev or "visible_clear_liquid" in ev) else []
    return _va_dict(objs, water=ev)


def parse_exercise(raw: str) -> dict:
    pos = _positive_text(raw)
    ev: list[str] = []
    table = [
        (("treadmill",), "treadmill_present"),
        (("dumbbell",), "dumbbell_present"),
        (("barbell", "weight plate"), "barbell_present"),
        (("weight machine", "cable machine", "lat pulldown", "weight-machine"), "weight_machine_present"),
        (("exercise bike", "stationary bike", "spin bike"), "exercise_bike_present"),
        (("exercise mat", "yoga mat", "workout mat", "fitness mat"), "exercise_mat_present"),
        (("gym", "fitness center", "weight room"), "gym_environment"),
        (("home workout", "home gym", "living room workout"), "home_workout_environment"),
    ]
    for phrases, tok in table:
        if _has(pos, phrases):
            ev.append(tok)
    # 자세: 적극적 운동 동작 표현일 때만 (standing/person 단독 금지)
    pose_pos = ("doing a squat", "doing a push-up", "doing a pushup", "doing a plank",
                "doing a lunge", "stretching", "actively exercising", "exercising",
                "lifting weights", "mid-exercise", "in a workout pose", "performing an exercise",
                "doing exercise", "working out")
    if _has(pos, pose_pos):
        ev.append("exercise_pose_visible")
    # 무관 환경 (긍정 근거가 전혀 없을 때만)
    if not ev and _has(pos, ("office", "desk", "laptop", "computer", "bedroom", "bed ",
                             "food", "meal", "dining", "kitchen", "restaurant", "sofa", "couch")):
        ev.append("unrelated_environment")
    ev = _dedupe(ev)
    return _va_dict([], exercise=ev)


def parse_study(raw: str) -> dict:
    pos = _positive_text(raw)
    ev: list[str] = []
    table = [
        (("open textbook", "textbook", "open book", "textbook page", "open workbook", "workbook"), "open_textbook"),
        (("handwritten", "handwriting", "written notes", "handwritten notes", "taking notes", "note-taking"), "handwritten_notes"),
        (("highlighted", "highlighter"), "highlighted_text"),
        (("worksheet", "math problem", "practice problem", "problem solving", "solving problems",
          "problem set", "problems on paper"), "problem_solving_material"),
        (("pdf", "printed learning material", "study document", "printed material",
          "printed worksheet", "educational document"), "educational_document"),
        (("lecture", "online class", "video lecture", "lecture video"), "lecture_video"),
        (("code editor", "coding", "source code", "programming", "writing code"), "code_editor"),
        (("study app", "study screen", "learning content on screen", "educational content on screen",
          "study content"), "study_content_on_screen"),
        # 부정 콘텐츠 (긍정 서술에 나타나면 그대로 부정 evidence)
        (("video game", "gaming", "playing a game", "game screen"), "gaming_content"),
        (("instagram", "social media", "facebook", "twitter", "tiktok", "messenger feed"), "social_media"),
        (("youtube", "movie", "netflix", "tv show", "entertainment"), "entertainment_video"),
    ]
    for phrases, tok in table:
        if _has(pos, phrases):
            ev.append(tok)
    ev = _dedupe(ev)
    paper = {"open_textbook", "handwritten_notes", "highlighted_text",
             "problem_solving_material", "educational_document"} & set(ev)
    screen = {"study_content_on_screen", "lecture_video", "code_editor"} & set(ev)
    objs = []
    if paper:
        objs += [{"label": "notebook", "confidence": 0.6, "evidence": None},
                 {"label": "pen", "confidence": 0.6, "evidence": None},
                 {"label": "desk", "confidence": 0.6, "evidence": None}]
    if screen:
        objs += [{"label": "laptop", "confidence": 0.6, "evidence": None},
                 {"label": "monitor", "confidence": 0.6, "evidence": None}]
    return _va_dict(objs, study=ev)


def _dedupe(items):
    seen, out = set(), []
    for it in items:
        if it not in seen:
            seen.add(it); out.append(it)
    return out


def _va_dict(objects, water=None, study=None, exercise=None) -> dict:
    return {
        "quality": {"brightness": "normal", "blur": "low", "usable": True, "issues": []},
        "scene": None, "objects": objects, "visible_text": [], "visual_evidence": [],
        "water_visual_evidence": water or [],
        "study_visual_evidence": study or [],
        "exercise_visual_evidence": exercise or [],
    }


_PARSERS = {"water": parse_water, "exercise": parse_exercise, "study": parse_study}


def parse_raw(raw: str, vtype: str) -> dict:
    return _PARSERS[vtype](raw or "")


# ---------------------------------------------------------------------------
# llama-mtmd-cli 호출
# ---------------------------------------------------------------------------

def run_llama(llama_bin: str, model: str, mmproj: str, image: Path, prompt: str,
              timeout_sec: int, max_new_tokens: int = 96) -> tuple[str, str]:
    """(raw_text, error). error 비어있으면 성공."""
    cmd = [llama_bin, "-m", model, "--mmproj", mmproj, "--image", str(image),
           "-p", prompt, "-ngl", "99", "-n", str(max_new_tokens), "--temp", "0"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return "", f"timeout>{timeout_sec}s"
    except Exception as exc:  # noqa: BLE001
        return "", f"subprocess_error: {type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        return "", f"exit_{proc.returncode}: {proc.stderr.strip()[-200:]}"
    return proc.stdout.strip(), ""


# ---------------------------------------------------------------------------
# manifest 필터
# ---------------------------------------------------------------------------

def load_items(manifest_path: Path, types, source, include_real_zflip, gt_filter=None):
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    allowed_sources = {source}
    if include_real_zflip:
        allowed_sources.add("real_zflip")
    items = []
    for e in data.get("images", []):
        if e.get("source") == "synthetic":
            continue  # 항상 제외
        if e.get("source") not in allowed_sources:
            continue
        vt = e.get("verification_type")
        gt = e.get("ground_truth")
        if vt == "TODO" or gt == "TODO":
            continue  # 미분류 제외
        if vt not in types:
            continue
        if gt_filter and gt not in gt_filter:
            continue  # FP-trap 등에서 특정 ground_truth 만
        items.append(e)
    return items


def _percentile(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return round(s[k], 1)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--images-dir", required=True)
    ap.add_argument("--llama-bin", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--mmproj", required=True)
    ap.add_argument("--types", default="water,exercise,study")
    ap.add_argument("--source", default="real")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--timeout-sec", type=int, default=180)
    ap.add_argument("--max-new-tokens", type=int, default=96)
    ap.add_argument("--include-real-zflip", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model-name", default="MiniCPM-V-4.6-GGUF",
                    help="metrics_summary 에 기록할 모델 이름(GGUF VLM 재사용용). 기본은 MiniCPM.")
    ap.add_argument("--gt", default=None,
                    help="특정 ground_truth 만 평가(콤마). 예: FAIL,BORDERLINE (FP-trap).")
    args = ap.parse_args()

    types = {t.strip() for t in args.types.split(",") if t.strip()}
    gt_filter = {g.strip() for g in args.gt.split(",")} if args.gt else None
    manifest = Path(args.manifest)
    images_dir = Path(args.images_dir)
    out_dir = Path(args.output_dir)
    items = load_items(manifest, types, args.source, args.include_real_zflip, gt_filter)
    if args.limit:
        items = items[: args.limit]

    from collections import Counter
    plan = Counter((i["verification_type"], i["ground_truth"]) for i in items)
    print(f"[plan] {len(items)} images | sources={{{args.source}}}"
          f"{'+real_zflip' if args.include_real_zflip else ''} | types={sorted(types)}")
    for vt in sorted(types):
        row = {gt: plan[(vt, gt)] for gt in ("PASS", "FAIL", "BORDERLINE") if plan[(vt, gt)]}
        if row:
            print(f"       {vt}: {row}")
    if args.dry_run:
        print("[dry-run] 모델 호출 없이 종료.")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    results, raws, per_image, parse_failures = [], [], [], []
    latencies, lat_by_type = [], {}

    for idx, item in enumerate(items, 1):
        vt = item["verification_type"]
        gt = item["ground_truth"]
        rel = item.get("image") or item.get("image_path")
        img = images_dir / rel
        prompt = PROMPTS[vt]
        t0 = time.perf_counter()
        raw, err = run_llama(args.llama_bin, args.model, args.mmproj, img, prompt,
                             args.timeout_sec, args.max_new_tokens)
        dt = round((time.perf_counter() - t0) * 1000, 1)
        latencies.append(dt); lat_by_type.setdefault(vt, []).append(dt)
        raws.append({"image": rel, "verification_type": vt, "raw_output": raw, "error": err})

        rec = {"image": rel, "verification_type": vt, "ground_truth": gt,
               "source": item.get("source"), "latency_ms": dt, "error": err}
        if err or not raw:
            parse_failures.append({"image": rel, "reason": err or "empty_output", "raw": raw})
            rec.update({"pred_result": "error", "pred_label": "ERROR", "score": 0,
                        "mandatory_passed": False, "got_evidence": [], "rule_evidence": [],
                        "is_false_positive": False, "is_false_negative": (gt == "PASS"), "correct": False})
            results.append(rec); per_image.append(rec)
            print(f"  [{idx}/{len(items)}] {rel:34} gt={gt:9} ERR={err}")
            continue

        va_dict = parse_raw(raw, vt)
        try:
            va = VisionAnalysis(**va_dict)
            ctx = ImageVerificationContext(exercise_activity_type=item.get("exercise_activity_type"))
            data = evaluate_image_verification(vt, va, ctx)
            got = list(getattr(va, f"{vt}_visual_evidence"))
            gt_pass = gt == "PASS"
            pred_pass = data.result == "verified"
            rec.update({
                "pred_result": data.result,
                "pred_label": {"verified": "PASS", "rejected": "FAIL",
                               "retake_required": "BORDERLINE"}.get(data.result, data.result),
                "score": data.score, "mandatory_passed": data.mandatory_passed,
                "got_evidence": got, "rule_evidence": [e.code for e in data.rule_evidence],
                "is_false_positive": (not gt_pass) and pred_pass,
                "is_false_negative": gt_pass and (not pred_pass),
                "correct": gt_pass == pred_pass,
            })
        except Exception as exc:  # noqa: BLE001 - 파싱→스키마 실패는 parse_failure 로
            parse_failures.append({"image": rel, "reason": f"parse/schema: {type(exc).__name__}: {exc}",
                                   "raw": raw})
            rec.update({"pred_result": "error", "pred_label": "ERROR", "score": 0,
                        "mandatory_passed": False, "got_evidence": [], "rule_evidence": [],
                        "is_false_positive": False, "is_false_negative": (gt == "PASS"), "correct": False})
        results.append(rec); per_image.append(rec)
        flag = "FP!" if rec.get("is_false_positive") else ("FN" if rec.get("is_false_negative") else
               ("ok" if rec.get("correct") else ""))
        print(f"  [{idx}/{len(items)}] {rel:34} gt={gt:9} pred={rec['pred_label']:9} {flag} "
              f"{dt:.0f}ms ev={rec.get('got_evidence')}")

    # ---- metrics ----
    def confusion(rows):
        tp = fp = tn = fn = 0
        for r in rows:
            if r["pred_result"] == "error":
                if r["ground_truth"] == "PASS":
                    fn += 1
                else:
                    tn += 1
                continue
            gp = r["ground_truth"] == "PASS"; pp = r["pred_result"] == "verified"
            tp += gp and pp; fp += (not gp) and pp; tn += (not gp) and (not pp); fn += gp and (not pp)
        n = len(rows)
        acc = (tp + tn) / n if n else 0.0
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec_ = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec_ / (prec + rec_) if (prec + rec_) else 0.0
        return {"n": n, "tp": tp, "tn": tn, "fp": fp, "fn": fn,
                "accuracy": round(acc, 3), "precision": round(prec, 3),
                "recall": round(rec_, 3), "f1": round(f1, 3)}

    metrics = {"ALL": confusion(results)}
    for vt in sorted(types):
        sub = [r for r in results if r["verification_type"] == vt]
        if sub:
            metrics[vt] = confusion(sub)

    latency_summary = {
        "overall": {"count": len(latencies), "avg_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
                    "p50_ms": _percentile(latencies, 50), "p95_ms": _percentile(latencies, 95),
                    "max_ms": round(max(latencies), 1) if latencies else 0},
        "by_type": {vt: {"count": len(v), "avg_ms": round(sum(v) / len(v), 1)} for vt, v in lat_by_type.items()},
    }
    fps = [r for r in results if r.get("is_false_positive")]
    fns = [r for r in results if r.get("is_false_negative")]

    # ---- save ----
    (out_dir / "results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n", encoding="utf-8")
    (out_dir / "raw_outputs.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in raws) + "\n", encoding="utf-8")
    (out_dir / "metrics_summary.json").write_text(
        json.dumps({"model": args.model_name, "generated_at": datetime.now(timezone.utc).isoformat(),
                    "metrics": metrics}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "false_positive_cases.json").write_text(json.dumps(fps, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "false_negative_cases.json").write_text(json.dumps(fns, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "latency_summary.json").write_text(json.dumps(latency_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "parse_failures.json").write_text(json.dumps(parse_failures, ensure_ascii=False, indent=2), encoding="utf-8")
    cols = ["image", "verification_type", "ground_truth", "pred_label", "pred_result", "score",
            "mandatory_passed", "got_evidence", "rule_evidence", "is_false_positive",
            "is_false_negative", "correct", "latency_ms", "source", "error"]
    with (out_dir / "per_image.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in per_image:
            row = dict(r)
            for k in ("got_evidence", "rule_evidence"):
                row[k] = ";".join(map(str, row.get(k, []) or []))
            w.writerow({k: row.get(k, "") for k in cols})

    print(f"\n[done] {len(results)} images → {out_dir}")
    for vt in ("ALL", *sorted(types)):
        if vt in metrics:
            m = metrics[vt]
            print(f"  {vt:9} acc={m['accuracy']:.3f} P={m['precision']:.3f} R={m['recall']:.3f} "
                  f"F1={m['f1']:.3f} FP={m['fp']} FN={m['fn']} (n={m['n']})")
    print(f"  false_positives={len(fps)} false_negatives={len(fns)} parse_failures={len(parse_failures)}")
    print(f"  latency avg={latency_summary['overall']['avg_ms']}ms p95={latency_summary['overall']['p95_ms']}ms")


if __name__ == "__main__":
    main()
