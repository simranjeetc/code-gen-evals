# Tasks

## 1. Anchor the judge

- [x] 1.1 Rewrite the judge prompt in `scoring/semantic.py` to include the requirement, the **reference solution** and the candidate, framed as a comparison; verify a rendered prompt contains all three and is byte-identical across two calls
- [x] 1.2 Add a worked score ladder (concrete 1.0 / 0.5 / 0.0 examples) to the prompt; verify all three bands are present and the ladder is stable across calls
- [x] 1.3 Add an explicit warning against rewarding superficial similarity to the reference; verify it appears in the prompt
- [x] 1.4 Thread the reference solution from `pipeline.py` into the judge call; verify a scored result was produced with the reference present in the prompt
- [x] 1.5 Verify the reference is still never sent to the **subject** model: run the prompt-isolation tests and confirm no subject prompt contains reference source

## 2. Unblend semantic from the composite

- [x] 2.1 Change composite weights to `execution` 0.5, `edge` 0.3, `style` 0.2; verify `config.DEFAULT_WEIGHTS` sums to 1.0 over objective dimensions only
- [x] 2.2 Update `aggregate.composite` to iterate objective dimensions only; verify changing a semantic score leaves the composite unchanged
- [x] 2.3 Verify semantic is still aggregated, still counted for abstentions, and still present in results
- [x] 2.4 Update `DimensionScores` / `EvalResult` serialisation so semantic is flagged as judge-derived; verify the flag round-trips through JSON

## 3. Judge agreement

- [x] 3.1 Implement `judge-agreement` as a CLI operation over the reference solutions, using two judge models; verify it runs and emits exact-match rate plus mean absolute difference — measured live: 20/20 references, exact-match 1.00, MAD 0.000 (glm-5.3-flash vs deepseek-v4.1-flash)
- [x] 3.2 Record the agreement figure in run metadata when known; verify it appears in the saved results file
- [x] 3.3 Verify the report renders the figure next to the semantic column when known, and states plainly that agreement is unmeasured when not

## 4. Reporting

- [x] 4.1 Render semantic as its own clearly labelled opinion column, separate from the composite; verify the composite column is unaffected by semantic values
- [x] 4.2 State in the report what the composite now excludes; verify the text is present in a generated report
- [x] 4.3 State that two-judge agreement measures stability, not correctness; verify the wording is present
- [x] 4.4 Mark historical results as produced under the previous judge design; verify the report footer distinguishes them
- [x] 4.5 Regenerate the reports and confirm semantic scores, the composite, and the ranking all still render correctly — `reports/results-live20-v3.{json,md}` generated; semantic opinion column, objective composite and ranking all render, agreement figure embedded, reference baseline row present

## 5. Reference baseline row

- [x] 5.1 Add a reference row to the report: the reference solutions scored on `execution`, `edge` and `style`, with semantic omitted or clearly marked as judge-derived
- [x] 5.2 Verify the reference scores 1.0 on `execution` and `edge` for all 20 specs, and record what it scores on `style` — execution and edge `1.0` for all 20; mean `style` **0.60** (none of the 20 reaches 0.99)
- [x] 5.3 If the reference's `style` score is materially below 1.0, record that as a finding about the style dimension rather than silently accepting it — recorded in `docs/scoring.md`; reference-quality composite ceiling is ~0.92, not 1.0

## 6. Validation against the previous design

- [x] 6.1 Re-run the four-model bank over the full corpus under the new judge and composite; verify the run completes and is not marked inconclusive — completed, 80/80 scored, not inconclusive, not unreliable; objective spread 0.063
- [x] 6.2 Compare per-spec semantic scores before and after; verify the direction and size of the change is documented, including the case where it is worse — mean fell 1.000 → 0.967 over 61 comparable pairs (5 lower, 56 unchanged, none higher, max drop −0.50). Recorded in `docs/scoring.md`. Composite intentionally not compared (different dimensions).
- [x] 6.3 Confirm the abstention count does not rise materially; verify it is reported — **it rose**: 8/80 → 13/80. Investigated before reporting: probing the judge with the same prompt gave a timeout on one call and 1.0 on the next, so the rise is judge provider timeouts, not the longer rubric. Documented with the probe.
- [x] 6.4 Update `docs/scoring.md` to describe reference-anchored judging, the objective-only composite, and the stability-not-correctness caveat; verify every formula in the doc matches the implementation
