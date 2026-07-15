"""Qwen2.5-VL-7B-Instruct server-side fallback VisionAnalyzer.

This is the ONLY analyzer in this codebase that may legitimately be called
"Qwen7B" -- it loads `Qwen/Qwen2.5-VL-7B-Instruct` directly via transformers,
distinct from `backend/services/local_vlm_analyzer.py`'s `qwen_awq` provider
key, which is Qwen2.5-VL-3B-AWQ (a different, smaller, quantized model; never
to be reported as "Qwen7B" -- see health_check()'s `model_id` field for the
honest, checkable identity).

Like every other VisionAnalyzer in this codebase, this class NEVER returns a
final verified/rejected/retake_required decision. It returns observed
evidence only (via backend/services/qwen_evidence_parser.py), full stop. The
prompt explicitly forbids the model from stating a decision, and even if the
model's raw text contains one, the parser does not extract or trust it --
only `evidence`/`blockers`/`uncertainty`/`scene_complexity` are parsed.

Hardware note (recorded here, not hidden -- discovered empirically on this
server, not assumed): the available GPU here is a Tesla P40 (Pascal, compute
capability 6.1).

ENGINE VARIANTS (Phase 12 -- `QWEN7B_ENGINE` env var, or the `engine`
constructor arg):

- `reference_fp32` (DEFAULT): `torch_dtype=float32`, `cuDNN` disabled
  (conv3d has no compiled engine for this GPU in any dtype -- fixed by
  forcing PyTorch's native conv kernel), CPU-offloaded via `device_map=
  "auto"` + an explicit `max_memory` budget (float32 7B is ~28GB > this
  P40's 24GB). **Correct output, ~300-320s/call.** This is the
  correctness/reference engine -- kept as the only DEFAULT-selectable
  engine because nothing faster has been found to also be correct on this
  GPU (see below).
- `quantized_bnb_nf4` (EXPERIMENTAL, NOT default, documented NO-GO on this
  GPU -- see `qwen_recovery/qwen7b_quantized_engine_report.md`): loads the
  SAME `Qwen/Qwen2.5-VL-7B-Instruct` checkpoint with a bitsandbytes 4-bit
  (nf4) `BitsAndBytesConfig`, fully GPU-resident (~6GB), 7-34s/call --
  dramatically faster, but produces the exact same degenerate
  repeated-"!"-token garbage output as raw float16 on this specific GPU,
  regardless of `bnb_4bit_compute_dtype` (tested both float16 and float32
  compute dtype; both fail identically). This strongly suggests the root
  cause is not "fp16 storage" per se but something about this Pascal GPU's
  fully-GPU-resident compute path for this model (the working `reference_fp32`
  engine's CPU-offloaded layers may incidentally avoid whatever the broken
  code path is -- not confirmed, noted as a hypothesis only).
  Two other candidates were ruled out before reaching bnb: official AWQ
  (`Qwen/Qwen2.5-VL-7B-Instruct-AWQ`, confirmed to exist and load, ~7GB)
  requires a Triton JIT-compiled kernel that needs Python.h (no dev headers,
  no root on this server); the precompiled alternative (`autoawq-kernels`)
  pulls in an incompatible torch version and was rejected to avoid breaking
  this environment. No official GPTQ checkpoint exists for this model.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Iterable, Optional

from backend.database.schema.image_verification_schema import VerificationType, VisionAnalysis
from backend.services import qwen_evidence_parser as parser
from backend.services.vision_analyzer import VisionAnalyzer, _unavailable_analysis

MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"
ENGINE_NAME = "qwen7b"
PARAMETER_SIZE = "7B"
MODEL_FAMILY = "Qwen2.5-VL"

# Only `reference_fp32` is selectable as the default -- `quantized_bnb_nf4` is
# experimental/NO-GO (see module docstring) and must be explicitly requested.
DEFAULT_ENGINE_VARIANT = "reference_fp32"
KNOWN_ENGINE_VARIANTS = ("reference_fp32", "quantized_bnb_nf4")

_TASK_INSTRUCTIONS = {
    "water": (
        "Look at the image. Determine whether a container (cup/glass/tumbler/bottle) is visible, "
        "and if so, whether it holds a clear liquid, is empty, or holds a colored/non-water "
        "beverage (coffee/tea/juice/milk/soda/alcohol). Report liquid fill state if visible. "
        "If a detector elsewhere flagged a region as container-like, verify independently -- do "
        "not assume it proves anything about contents.\n"
        "Choose evidence/blockers only from: visible_water, visible_clear_liquid, filled_container, "
        "sealed_water_bottle, water_stream, container_under_dispenser, receiving_water, "
        "empty_container, opaque_closed_container, non_water_beverage, uncertain_liquid."
    ),
    "study": (
        "Look at the image. Identify visible study material or study content: an open "
        "textbook/workbook, handwritten notes, a problem set, a lecture video/slide, an "
        "educational document, or a code editor. A laptop/monitor/table/person alone is NOT "
        "study evidence -- judge the actual content. If a screen shows non-study content "
        "(games/video/social media/shopping), report the corresponding blocker.\n"
        "Choose evidence/blockers only from: open_textbook, open_workbook, handwritten_notes, "
        "highlighted_text, problem_solving_material, study_content_on_screen, lecture_video, "
        "educational_document, code_editor, study_timer, gaming_content, entertainment_video, "
        "social_media, shopping_content, non_study_screen, closed_study_materials, "
        "uncertain_screen_content."
    ),
    "exercise": (
        "Look at the image. Identify whether it shows an actual exercise activity, environment, "
        "or equipment: gym environment/equipment, running/track environment, swimming pool/lane, "
        "a yoga studio or a yoga mat actually laid out, a pilates studio/reformer, or a "
        "home-workout setup (mat/resistance band/dumbbell/kettlebell/pull-up bar), or a genuinely "
        "active exercise pose. A visible person alone, sitting/resting, a selfie, or exercise "
        "clothing with no activity/equipment/environment is NOT exercise evidence.\n"
        "STRICT evidence-hygiene rules (this scene can only be ONE real place, not several):\n"
        "  - Report ONLY what is directly visible in THIS image. Never list other environments "
        "that exercise photos *could* show but this one doesn't (e.g. do not report "
        "swimming_pool_environment or yoga_studio_present just because a gym is a plausible "
        "exercise setting too -- only if you actually see a pool or a yoga studio).\n"
        "  - Do not output two mutually-exclusive environment tags together (e.g. "
        "gym_environment AND swimming_pool_environment AND yoga_studio_present all at once) unless "
        "the image genuinely, visibly shows more than one of those settings simultaneously.\n"
        "  - If uncertain which single environment this is, prefer uncertain_exercise_environment "
        "over guessing multiple.\n"
        "  - Only report an equipment tag (dumbbell_present, etc.) for an object you can actually "
        "identify in the image, not one that would be typical for a guessed environment.\n"
        "Choose evidence/blockers only from: gym_environment, treadmill_present, dumbbell_present, "
        "barbell_present, weight_machine_present, exercise_bike_present, gym_bench_present, "
        "running_track_present, treadmill_running_environment, stadium_track_present, "
        "park_running_path_present, swimming_pool_environment, swimming_lane_present, "
        "lane_rope_present, swim_cap_present, swim_goggles_present, yoga_mat_present, "
        "yoga_studio_present, yoga_pose_visible, pilates_reformer_present, "
        "pilates_equipment_present, pilates_studio_present, pilates_pose_visible, "
        "exercise_mat_present, resistance_band_present, home_dumbbell_present, kettlebell_present, "
        "pull_up_bar_present, home_exercise_pose_visible, unrelated_environment, "
        "wrong_activity_environment, insufficient_exercise_evidence, uncertain_exercise_environment."
    ),
}

_COMMON_INSTRUCTIONS = (
    "Return ONLY a single JSON object (no markdown code fence, no extra text) with exactly these "
    "keys: task (string), objects (list of {\"label\": string, \"confidence\": number 0-1} objects, "
    "see allowed object labels below), evidence (list of strings, positive findings), blockers (list "
    "of strings, contradiction/negative findings), uncertainty (one of: low, medium, high -- "
    "report \"low\" only if you are genuinely confident), scene_complexity (one of: simple, "
    "moderate, complex), parser_version (omit or empty string), model_name (this model's "
    "identifier).\n"
    "Do not include verified, rejected, retake_required, result, score, pass, fail, decision, or "
    "judgment anywhere in the response -- evidence observation only."
)


def build_prompt(task: str, allowed_labels: Optional[Iterable[str]] = None) -> str:
    task_instr = _TASK_INSTRUCTIONS.get(task)
    if task_instr is None:
        raise ValueError(f"unsupported task for Qwen7B evidence extraction: {task}")
    labels = list(allowed_labels or [])
    objects_note = (
        f"Also identify which of these specific objects are visible (list each one you see in "
        f"`objects`, each with a confidence 0-1; omit ones you don't see -- do not list objects "
        f"outside this set): {', '.join(labels)}.\n" if labels else ""
    )
    return f"Verification type: {task}.\n{task_instr}\n{objects_note}\n{_COMMON_INSTRUCTIONS}"


class Qwen7BVisionAnalyzer(VisionAnalyzer):
    """Loads Qwen2.5-VL-7B-Instruct once per process (guarded by a lock),
    exposes a real, checkable health_check(), and never returns a decision."""

    def __init__(self, model_id: str = MODEL_ID, torch_dtype: Optional[str] = None, device: str = "auto",
                 max_gpu_memory: Optional[str] = None, max_cpu_memory: Optional[str] = None,
                 no_cpu_offload: Optional[bool] = None, max_new_tokens: Optional[int] = None,
                 min_pixels: Optional[int] = None, max_pixels: Optional[int] = None,
                 engine: Optional[str] = None):
        self.model_id = model_id
        # Engine variant switch (Phase 12) -- see module docstring for what each does and why
        # `reference_fp32` is the only DEFAULT-selectable variant. Requesting the experimental
        # `quantized_bnb_nf4` variant is allowed (never deleted/hidden) but never silently chosen.
        self.engine = engine or os.environ.get("QWEN7B_ENGINE", DEFAULT_ENGINE_VARIANT)
        if self.engine not in KNOWN_ENGINE_VARIANTS:
            raise ValueError(f"unknown QWEN7B_ENGINE variant {self.engine!r}; known: {KNOWN_ENGINE_VARIANTS}")
        # float32 default: verified empirically on this server's Tesla P40 (see module docstring) --
        # float16 produced degenerate output on this specific GPU+model+op combination. The
        # quantized_bnb_nf4 engine ignores this and always dequantizes/computes in its own dtype.
        self.torch_dtype_name = torch_dtype or os.environ.get("QWEN7B_TORCH_DTYPE", "float32")
        self.device = device
        self.max_gpu_memory = max_gpu_memory or os.environ.get("QWEN7B_MAX_GPU_MEMORY", "20GiB")
        self.max_cpu_memory = max_cpu_memory or os.environ.get("QWEN7B_MAX_CPU_MEMORY", "60GiB")
        # Latency-experiment knobs (Phase 11.B) -- each independently toggleable via env var so a
        # single real measurement isolates one variable at a time. Defaults preserve the last
        # known-working configuration; nothing here silently changes behavior unless set.
        env_no_offload = os.environ.get("QWEN7B_NO_CPU_OFFLOAD", "")
        self.no_cpu_offload = no_cpu_offload if no_cpu_offload is not None else env_no_offload.lower() in ("1", "true", "yes")
        # 128 default: measured in Phase 11.B (qwen_recovery/qwen7b_latency_experiments.md) to have
        # no latency downside vs 512 on this hardware (prefill dominates, not generation length),
        # while capping worst-case output size for a response that should always be short JSON.
        self.max_new_tokens_default = max_new_tokens or int(os.environ.get("QWEN7B_MAX_NEW_TOKENS", "128"))
        self.min_pixels = min_pixels or (int(os.environ["QWEN7B_MIN_PIXELS"]) if "QWEN7B_MIN_PIXELS" in os.environ else None)
        self.max_pixels = max_pixels or (int(os.environ["QWEN7B_MAX_PIXELS"]) if "QWEN7B_MAX_PIXELS" in os.environ else None)
        self._model = None
        self._processor = None
        self._load_error: str = ""
        self._load_time_ms: float = 0.0
        self._lock = threading.Lock()
        # Candidate 7: request concurrency semaphore=1 -- this GPU cannot usefully run two
        # generate() calls at once anyway (see OOM finding); serializing avoids two requests
        # racing for the same ~20GB budget and OOMing both instead of queuing safely.
        self._generate_semaphore = threading.Semaphore(1)

    # -- loading / health -----------------------------------------------
    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        with self._lock:
            if self._model is not None:
                return True
            t0 = time.perf_counter()
            try:
                import torch
                # cuDNN has no conv3d "engine" for this GPU+op combination (verified empirically,
                # see module docstring) -- disabling it forces PyTorch's native conv kernel instead.
                torch.backends.cudnn.enabled = False
                from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

                processor_kwargs = {}
                if self.min_pixels is not None:
                    processor_kwargs["min_pixels"] = self.min_pixels
                if self.max_pixels is not None:
                    processor_kwargs["max_pixels"] = self.max_pixels
                self._processor = AutoProcessor.from_pretrained(self.model_id, **processor_kwargs)

                if self.engine == "quantized_bnb_nf4":
                    # EXPERIMENTAL / documented NO-GO on this GPU (see module docstring and
                    # qwen_recovery/qwen7b_quantized_engine_report.md) -- loads fine and is fast,
                    # but produces degenerate garbage output on this specific Pascal GPU. Kept
                    # available (not deleted) only so a different GPU can select and re-validate it.
                    from transformers import BitsAndBytesConfig
                    quant_dtype = getattr(torch, self.torch_dtype_name)
                    bnb_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_compute_dtype=quant_dtype,
                    )
                    load_kwargs = dict(quantization_config=bnb_config, device_map=self.device,
                                       attn_implementation="eager")
                    self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(self.model_id, **load_kwargs)
                else:
                    dtype = getattr(torch, self.torch_dtype_name)
                    load_kwargs = dict(torch_dtype=dtype, device_map=self.device, attn_implementation="eager")
                    if not self.no_cpu_offload:
                        load_kwargs["max_memory"] = {0: self.max_gpu_memory, "cpu": self.max_cpu_memory}
                    # no_cpu_offload=True: omit max_memory entirely, let device_map="auto" place
                    # everything on GPU 0 if it fits (candidate 2) -- will raise/OOM at load time if
                    # it doesn't, which is itself the real measurement, not something to catch here.
                    self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(self.model_id, **load_kwargs)
                self._model.eval()
                self._load_error = ""
            except Exception as exc:  # noqa: BLE001 - loading failure must never crash the service
                self._load_error = f"{type(exc).__name__}: {exc}"
                self._model = None
                self._processor = None
            self._load_time_ms = (time.perf_counter() - t0) * 1000.0
        return self._model is not None

    def available(self) -> bool:
        return self._ensure_loaded()

    def health_check(self) -> dict:
        """Real, honest status -- never fakes 'loaded' when it isn't. GPU memory figures are
        read directly from torch.cuda, never estimated."""
        loaded = self._ensure_loaded()
        device_str = "unknown"
        device_map_summary: dict = {}
        if loaded:
            try:
                device_str = str(next(self._model.parameters()).device)
            except Exception:  # noqa: BLE001
                device_str = "loaded_but_device_unknown"
            try:
                dm = getattr(self._model, "hf_device_map", {}) or {}
                devices_used = sorted({str(v) for v in dm.values()})
                device_map_summary = {
                    "devices_used": devices_used,
                    "cpu_offloaded": any(v == "cpu" for v in dm.values()),
                }
            except Exception:  # noqa: BLE001
                pass
        gpu_mem = {}
        try:
            import torch
            if torch.cuda.is_available():
                gpu_mem = {
                    "allocated_bytes": torch.cuda.memory_allocated(0),
                    "reserved_bytes": torch.cuda.memory_reserved(0),
                    "max_allocated_bytes": torch.cuda.max_memory_allocated(0),
                }
        except Exception:  # noqa: BLE001
            pass
        return {
            "model_id": self.model_id,
            "engine_name": ENGINE_NAME,
            "engine_variant": self.engine,
            "is_default_engine_variant": self.engine == DEFAULT_ENGINE_VARIANT,
            "parameter_size": PARAMETER_SIZE,
            "model_family": MODEL_FAMILY,
            "quantization": "none_fp32" if self.engine == "reference_fp32" else "bitsandbytes_nf4",
            "image_input_supported": True,
            "loaded": loaded,
            "device": device_str,
            "torch_dtype": self.torch_dtype_name,
            "load_time_ms": round(self._load_time_ms, 1),
            "error": self._load_error,
            "no_cpu_offload_requested": self.no_cpu_offload,
            "max_gpu_memory_budget": self.max_gpu_memory if not self.no_cpu_offload else None,
            "max_new_tokens_default": self.max_new_tokens_default,
            "min_pixels": self.min_pixels,
            "max_pixels": self.max_pixels,
            "device_map": device_map_summary,
            "gpu_memory": gpu_mem,
        }

    def warmup(self) -> dict:
        """Candidate 8: startup warm-up generation. Loads weights + runs one tiny real
        generation so the first REAL user request isn't also paying the cold-load /
        CUDA-kernel-JIT cost. Returns the same shape as a health_check plus warmup timing."""
        t0 = time.perf_counter()
        if not self._ensure_loaded():
            return {**self.health_check(), "warmup_ok": False, "warmup_ms": 0.0}
        try:
            import tempfile
            from PIL import Image
            with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
                Image.new("RGB", (64, 64), color=(128, 128, 128)).save(tmp.name)
                self._generate_raw(Path(tmp.name), "Describe this image in one word.", max_new_tokens=4)
            warmup_ok = True
        except Exception as exc:  # noqa: BLE001
            warmup_ok = False
            self._load_error = f"warmup_generation_failed: {type(exc).__name__}: {exc}"
        return {**self.health_check(), "warmup_ok": warmup_ok, "warmup_ms": round((time.perf_counter() - t0) * 1000, 1)}

    # -- generation -------------------------------------------------------
    def _generate_raw(self, image_path: Path, prompt: str, max_new_tokens: Optional[int] = None) -> str:
        import torch
        from qwen_vl_utils import process_vision_info

        max_new_tokens = max_new_tokens or self.max_new_tokens_default
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": f"file://{Path(image_path).resolve()}"},
                {"type": "text", "text": prompt},
            ],
        }]
        text = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self._processor(text=[text], images=image_inputs, videos=video_inputs,
                                  padding=True, return_tensors="pt")
        n_image_tokens = int(inputs.input_ids.shape[1]) if hasattr(inputs, "input_ids") else -1
        img_dims = [tuple(im.size) for im in image_inputs] if image_inputs else []
        print(f"[qwen7b] input_tokens={n_image_tokens} image_dims={img_dims} "
              f"max_new_tokens={max_new_tokens} min_pixels={self.min_pixels} max_pixels={self.max_pixels}")
        inputs = inputs.to(self._model.device)
        generated = None
        # Candidate 7: serialize generate() calls -- this GPU's memory budget cannot safely
        # support two concurrent 7B generations (see the CUDA OOM finding from Phase 10).
        with self._generate_semaphore:
            try:
                with torch.inference_mode():
                    generated = self._model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
                trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated)]
                out_text = self._processor.batch_decode(trimmed, skip_special_tokens=True,
                                                          clean_up_tokenization_spaces=False)
                return out_text[0] if out_text else ""
            finally:
                # TEMPORARY MITIGATION (Phase 11.B), not a permanent fix: on this CPU-offloaded
                # fp32 7B model on a P40, CUDA memory fragmentation accumulates across repeated
                # generate() calls in the same process until a later call OOMs even though
                # earlier ones succeeded (observed directly -- see Phase 10 report). Dropping
                # references + gc.collect() + empty_cache() after every call was measured to
                # keep 8 sequential real calls OOM-free (see qwen7b_latency_experiments.md);
                # empty_cache()'s per-call cost is the trade-off accepted for that stability.
                del inputs, generated
                import gc
                gc.collect()
                torch.cuda.empty_cache()

    def analyze(
        self,
        image_path: Path,
        verification_type: VerificationType,
        allowed_labels: Iterable[str],
    ) -> VisionAnalysis:
        return self.analyze_with_context(image_path, verification_type, allowed_labels)

    def analyze_with_context(
        self,
        image_path: Path,
        verification_type: VerificationType,
        allowed_labels: Iterable[str],
        exercise_activity_type: Optional[str] = None,
    ) -> VisionAnalysis:
        if not self._ensure_loaded():
            return _unavailable_analysis(f"Qwen7B ({self.model_id}) failed to load: {self._load_error}")

        task = str(verification_type)
        label_list = list(allowed_labels)
        prompt = build_prompt(task, label_list)
        try:
            raw = self._generate_raw(image_path, prompt)
        except Exception as exc:  # noqa: BLE001 - inference error must fail safe, never crash
            return _unavailable_analysis(f"Qwen7B inference error: {type(exc).__name__}: {exc}")

        analysis, status, diagnostics = parser.parse_qwen_response(raw, task, model_name=self.model_id)
        if analysis is None:
            # exactly one repair attempt, per this task's parser requirement
            repair_prompt = parser.build_repair_prompt(raw, task, diagnostics.get("error", "unknown"))
            try:
                raw2 = self._generate_raw(image_path, repair_prompt)
            except Exception as exc:  # noqa: BLE001
                return _unavailable_analysis(f"Qwen7B repair-attempt inference error: {type(exc).__name__}: {exc}")
            analysis, status2, diagnostics2 = parser.parse_qwen_response(raw2, task, model_name=self.model_id)
            if analysis is None:
                print(f"[qwen7b] PARSE FAILED after repair attempt: task={task} "
                      f"first_error={diagnostics.get('error')} repair_error={diagnostics2.get('error')}")
                out = _unavailable_analysis(
                    f"Qwen7B evidence JSON could not be parsed even after one repair attempt "
                    f"(first: {diagnostics.get('error')}; repair: {diagnostics2.get('error')})."
                )
                return out.model_copy(update={"parser_status": "failed", "parser_version": parser.PARSER_VERSION,
                                               "model_name": self.model_id})
            analysis = analysis.model_copy(update={"parser_status": "repaired"})
            print(f"[qwen7b] parse repaired on retry: task={task} unmapped_tags={diagnostics2.get('unmapped_tags')}")
        else:
            analysis = analysis.model_copy(update={"parser_status": "clean"})
            if diagnostics.get("unmapped_tags"):
                print(f"[qwen7b] unmapped evidence tags (kept in visual_evidence): "
                      f"task={task} tags={diagnostics['unmapped_tags']}")

        allowed = set(allowed_labels)
        analysis = analysis.model_copy(update={
            "objects": [o for o in analysis.objects if o.label in allowed] if allowed else analysis.objects,
        })
        return analysis


_LOCK = threading.Lock()
_INSTANCE: Optional[Qwen7BVisionAnalyzer] = None


def get_qwen7b_analyzer() -> Qwen7BVisionAnalyzer:
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = Qwen7BVisionAnalyzer()
        return _INSTANCE
