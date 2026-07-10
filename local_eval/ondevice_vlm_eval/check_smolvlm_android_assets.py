"""SmolVLM-500M Android 패키징 후보 자산 점검(존재/크기/조합 합계/권장).

모델 자산은 /data/models/SmolVLM-500M-Instruct 기준. 결과를 콘솔 + SMOLVLM_ANDROID_ASSET_CHECK.md 로.
조합:
  A(권장) = decoder_q4 + vision_int8 + embed_int8
  B       = decoder_q4 + vision_q4  + embed_int8
  C       = decoder_q4 + vision_int8 + embed_q4f16
공통 tokenizer/config 세트 포함.
"""

from __future__ import annotations

from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
MODEL_DIR = Path("/data/models/SmolVLM-500M-Instruct")
ONNX = MODEL_DIR / "onnx"
OUT = THIS_DIR / "SMOLVLM_ANDROID_ASSET_CHECK.md"

DECODER = {"q4": ONNX / "decoder_model_merged_q4.onnx"}
VISION = {"int8": ONNX / "vision_encoder_int8.onnx", "q4": ONNX / "vision_encoder_q4.onnx"}
EMBED = {"int8": ONNX / "embed_tokens_int8.onnx", "q4f16": ONNX / "embed_tokens_q4f16.onnx"}
COMMON = [MODEL_DIR / f for f in (
    "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt",
    "config.json", "preprocessor_config.json", "processor_config.json")]

OPTIONS = {
    "A (recommended)": [DECODER["q4"], VISION["int8"], EMBED["int8"]],
    "B": [DECODER["q4"], VISION["q4"], EMBED["int8"]],
    "C": [DECODER["q4"], VISION["int8"], EMBED["q4f16"]],
}


def _mb(p: Path) -> float:
    return round(p.stat().st_size / (1024 * 1024), 1) if p.exists() else 0.0


def main() -> None:
    all_files = [DECODER["q4"], VISION["int8"], VISION["q4"], EMBED["int8"], EMBED["q4f16"], *COMMON]
    present, missing = [], []
    L = ["# SMOLVLM Android asset check", "", f"- model dir: `{MODEL_DIR}`",
         f"- dir exists: {MODEL_DIR.exists()}", "", "## 파일 존재/크기", "",
         "| file | exists | size(MB) |", "|---|---|---|"]
    print(f"[check] model dir={MODEL_DIR} exists={MODEL_DIR.exists()}")
    for p in all_files:
        ex = p.exists(); sz = _mb(p)
        (present if ex else missing).append(p)
        rel = str(p).replace(str(MODEL_DIR) + "/", "")
        L.append(f"| {rel} | {'✅' if ex else '❌ MISSING'} | {sz if ex else '-'} |")
        print(f"  {'OK ' if ex else 'MISS'} {sz if ex else 0:>7} MB  {rel}")

    common_mb = round(sum(_mb(p) for p in COMMON if p.exists()), 1)
    rt_mb = 20.0  # ONNX Runtime Mobile(.aar arm64) 대략치
    L += ["", f"- tokenizer/config 합계: {common_mb} MB", f"- ONNX Runtime Mobile(.aar, 추정): ~{rt_mb} MB",
          "", "## 조합별 합계(모델 3모듈 + tokenizer/config + 런타임)", "",
          "| option | modules | model(MB) | +tok/cfg | +runtime(pkg 추정) |", "|---|---|---|---|---|"]
    print("\n[options]")
    opt_totals = {}
    for name, mods in OPTIONS.items():
        mods_ok = all(p.exists() for p in mods)
        model_mb = round(sum(_mb(p) for p in mods), 1)
        with_common = round(model_mb + common_mb, 1)
        with_rt = round(with_common + rt_mb, 1)
        opt_totals[name] = with_rt if mods_ok else None
        modnames = "+".join(p.name.replace(".onnx", "").replace("_model_merged", "").replace("_encoder", "").replace("_tokens", "") for p in mods)
        status = "" if mods_ok else " (missing module!)"
        L.append(f"| {name} | {modnames} | {model_mb} | {with_common} | **{with_rt}**{status} |")
        print(f"  {name:16} model={model_mb}MB  +tok/cfg={with_common}MB  +runtime≈{with_rt}MB{status}")

    rec = "A (recommended)"
    rec_ok = OPTIONS[rec] and all(p.exists() for p in OPTIONS[rec]) and not [p for p in COMMON[:6] if not p.exists()]
    L += ["", "## 권장", f"- **{rec}** = decoder_q4 + vision_int8 + embed_int8 "
          f"(vision int8 로 빈컵/물 시각 디테일 보존 → FP 안전). "
          f"패키지 추정 ≈ **{opt_totals.get(rec)} MB**." if opt_totals.get(rec) else
          f"- 권장 A 산정 불가(모듈 누락).",
          f"- 상태: {'✅ 준비됨' if rec_ok else '⚠️ 일부 파일 누락 — 아래 missing 확인'}"]
    if missing:
        L += ["", "## MISSING", *[f"- {p}" for p in missing]]
    else:
        L += ["", "## MISSING", "- 없음(모든 후보 파일 존재)"]
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"\n[recommended] {rec} ≈ {opt_totals.get(rec)} MB  ready={rec_ok}")
    print(f"[missing] {len(missing)}")
    print(f"[out] {OUT}")


if __name__ == "__main__":
    main()
