#!/usr/bin/env python3
"""Generate task-specific SmolVLM prompt token ids for the Android diagnostics bridge.

The on-device bridge (SmolVlmBridge.kt) has no tokenizer, so per-task prompt token
ids are encoded here offline and pasted as Kotlin constants. Structure kept identical
to the SmolVLM processor output (do_image_splitting=false):

    <|im_start|>User:<fake_token_around_image><global-img> [64x <image>] <fake_token_around_image> {QUESTION} <end_of_utterance>\nAssistant:

Only the QUESTION differs per task. The earlier single prompt asked about "the drink",
which biased study/exercise generations toward beverages; per-task questions fix that.

Usage:
    python tools/gen_smol_prompts.py [--model /data/models/SmolVLM-500M-Instruct]

Requires the `tokenizers` package and the model's tokenizer.json (a model asset — not
committed). Emits Kotlin `longArrayOf(...)` lines + validation (image_token count==64).
"""
from __future__ import annotations

import argparse

# <|im_start|>User:<fake_token_around_image><global-img>
PREFIX = [1, 11126, 42, 49189, 49152]
FAKE = 49189                       # <fake_token_around_image>
TAIL = [49279, 198, 9519, 9531, 42]  # <end_of_utterance>\nAssistant:
IMG_TOKEN_ID = 49190
N_IMG = 64

# Short NEUTRAL descriptive questions (best of three styles tested on-device):
#  - option-enumerating ("... or empty?")  -> model copies the last option ("Empty.") -> wrong
#  - object-naming imperative ("Name visible ... items") -> short garbage/partial ("TMC") -> worse
#  - neutral descriptive ("Describe the ... briefly.") -> coherent scene, no beverage bias -> chosen
# Only the task noun differs. SmolVLM-500M at single-512 won't be prompted into reliable
# object-noun extraction (caption granularity limit); descriptive is the safe choice.
QUESTIONS = {
    "water": "Describe the drink briefly.",
    "study": "Describe the scene briefly.",
    "exercise": "Describe the activity briefly.",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="/data/models/SmolVLM-500M-Instruct")
    args = ap.parse_args()

    from tokenizers import Tokenizer  # local import so the file imports without the dep
    tk = Tokenizer.from_file(f"{args.model}/tokenizer.json")

    def enc(s: str) -> list[int]:
        return tk.encode(s, add_special_tokens=False).ids

    for task, q in QUESTIONS.items():
        q_ids = enc(q)
        ids = PREFIX + [IMG_TOKEN_ID] * N_IMG + [FAKE] + q_ids + TAIL
        n_img = ids.count(IMG_TOKEN_ID)
        start = ids.index(IMG_TOKEN_ID)
        assert n_img == N_IMG, f"{task}: image_token count {n_img} != {N_IMG}"
        print(f"// [{task}] seq_len={len(ids)} q_tok={len(q_ids)} image@{start}..{start + N_IMG - 1}  Q={q!r}")
        # Kotlin: only the question tokens are needed (bridge builds prefix+64img+fake+q+tail).
        print(f"private val Q_{task.upper()} = longArrayOf(" + ", ".join(f"{x}L" for x in q_ids) + ")")
        print()


if __name__ == "__main__":
    main()
