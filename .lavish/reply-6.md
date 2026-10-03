**Cut, not grown: 921 → 506 lines.** You were right — it was becoming a changelog.

## What I did instead of appending

| before | after |
| --- | --- |
| 12 sections, 921 lines | **9 sections, 506 lines** (−45%) |
| 4 near-duplicate "why" sections | merged into one header block |
| Q&A replies baked into sections | **removed** — they live in the side chat where they belong |
| "What we actually built" + "Tomorrow" + "Publishing" + "Building in public" | collapsed into **one "next" section** |
| 11-row jargon table | **inline badges, ~4 lines** |
| "The cardboard robot" card + "broader bank" card + two "trying a robot" cards | → one line of prose, one callout |

Three things became `<details>` foldouts rather than more prose: the two-suites question, the broader-bank explanation, and the commercial framing. Same knowledge, collapsed by default.

## Updated with what actually happened

- **20 puzzles** (was 15), **5 robots** (was 4) — adding **Claude Code**, which is now a real provider
- **208 tests**, **40 checks all pass**, **3 commits** — the "not committed" warning is gone, that's fixed
- Results table is now **real Claude Code output**, judged by haiku, not the old OpenCode run
- New weakness stated plainly: **robots still tie**, and sonnet cleared the five puzzles I wrote specifically to separate models

## Kept out of the HTML

Per your instruction, all the knowledge-base Q&A — why tests are hidden, whether the judge is the same model, can you create a model, is it publishable — is **not** in the artifact. Only what a reader needs to understand the thing in five minutes.

The one exception: the *single most asked* question ("why two test sets, and who judges?") is a one-line folded `<details>` under the four grades, because a reader will hit that wall immediately. Everything else stays in chat.

## Honest note on the new results

Sonnet scored **1.00 execution and 1.00 edge on all five hard puzzles**, including the ones designed as separators. That's a real finding, and mildly disappointing for the corpus: the tie isn't fixed by 5 more hard specs either. The artifact says so rather than burying it.

Which strengthens the case for the **broaden-the-bank** control experiment — it's now the top row of "do next", above pass@k and contamination.
