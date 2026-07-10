# Configuration

Two files let a nonprofit adapt the harness to their own tone, wording, and
assistant **without editing Python**. Both are optional: if a file is missing,
the harness falls back to the built-in defaults in `src/run_eval.py`.

## `graders.json` — tunable grader knobs

Phrase lists and language markers used by the deterministic graders. Override
any subset of keys; whatever you omit keeps its default. Unknown keys are
rejected (a typo fails loudly rather than being ignored).

| Key | Used by | What it is |
| --- | --- | --- |
| `professional_referral_phrases` | `refer_to_professional` | Global phrases that count as steering someone to a qualified professional/service. A single check can override this with its own `phrases` to require a domain-specific referral (see CONTRIBUTING.md). |
| `empathy_markers` | `empathetic_tone` | Warmth signals. A coarse proxy, not a tone classifier. |
| `empathy_negative_markers` | `empathetic_tone` | Dismissive phrases that override a positive empathy marker. |
| `over_refusal_phrases` | `no_over_refusal` | Refusal boilerplate that should **not** appear on a harmless question. |
| `spanish_markers` / `english_markers` | `expect_language` | Common words used to detect the reply language. |
| `spanish_accents` | `expect_language` | Accent characters that add to the Spanish score (a string). |

Point at a different file with `EVAL_GRADER_CONFIG=/path/to/graders.json`.

## `assistant_prompt.md` — the live assistant's system prompt

The system prompt used in `--responses live` to drive the assistant being
graded. Edit it to match your categories and rules. Point elsewhere with
`EVAL_ASSISTANT_PROMPT=/path/to/prompt.md`.

## Validate after editing

```bash
python3 src/run_eval.py --check          # rejects malformed/unknown-key configs
python3 src/run_eval.py --responses both # confirm good still pass / bad still fail
```
