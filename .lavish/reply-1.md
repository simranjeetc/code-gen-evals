**Two good questions — and one of them caught a real inaccuracy in my wording.**

**1. Why are some tests secret? And is the judge the same robot that wrote the code?**

No — and this is the single most important design rule in the repo. Three separate robots are involved:

- **The coder**: the robot being graded. It sees *only* the prompt ("Write a function that…"). It never sees any test.
- **The test runner**: not a robot at all. It's Python running our saved test files.
- **The judge**: a *different* model (`glm-5.3-flash`), which never writes code in this run. It only reads a pair of texts — the requirement and the candidate — and answers with a score.

The code prevents self-grading by construction: if the judge model id equals the subject model id, the judge refuses and abstains rather than scoring itself. There's a test for that.

**So why are there two test suites?**

If we only had one suite, a robot would be graded on tests, and — crucially — we would have *no way to tell* whether it generalised or simply satisfied the exact assertions we happened to write. The two suites measure different things:

- **ground truth** → "does it do the ordinary job?" (this is the `execution` score)
- **edge cases** → "does it survive inputs we never showed anyone?" (this is the `edge` score)

Only the **prompt** goes to the model. Neither suite is ever sent. So a model cannot read the tests and write code that games them. If both suites were visible, a model could special-case the exact inputs and score perfectly while being useless.

**Your question exposed a wording bug: I called the ground-truth tests "secret", and they aren't.** They're hidden *from the model*, which is a different thing. Every test in both suites is right there in the repo for a human to read. I've fixed that wording — the diagram now says "hidden from the model" rather than "secret".

**2. What does the mock do?**

The mock is a **cardboard robot**. There is no AI behind it at all.

It exists so the whole pipeline can be run with no internet, no API keys, and no cost — on any machine, in CI, deterministically. When you ask it for code, it looks up that spec's reference solution and returns a mutated copy of it, chosen by hashing the model name and the spec name:

| It returns… | Which makes… |
| --- | --- |
| the reference solution untouched | everything pass |
| the reference with labels and notes stripped | the tidy score drop |
| a do-nothing skeleton | working score collapse |
| an empty file | the import fail |

That's why a mock run produces scores that differ between "models" — and why those scores are **meaningless as a comparison**. The report prints a banner saying exactly that. It validates that the machinery works; it says nothing about any real robot.

**3. Corpus to 20, keeping the easy ones and adding harder ones.**

That's the right call, and it's the fix for the real problem: all four robots scored 1.00 on "works" and 1.00 on "survives" nearly everywhere, so the ranking rested on tidiness alone. The current 15 are already at the minimum per tier (5/5/5); going to 20 means adding 5 harder specs and keeping the existing 15 untouched.

This is a corpus change, not a cosmetic one — it changes what the benchmark measures, so I'm running it through OpenSpec as its own change rather than quietly editing the HTML. Artifact updated now; the 5 new specs land next.
