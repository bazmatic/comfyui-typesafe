# 06: Provide an opt-in semantic evaluation runner

**What to build:** Provide a repeatable, explicitly opt-in way to measure Text Guard and LoRA Selector behaviour against representative examples through their existing module interfaces. Keep deterministic test coverage separate from evidence about live model quality. Follow the approved TypeSafe visual decision nodes technical design.

**Blocked by:** 01 — Text Guard stops dependent work on a matching condition; 03 — Select one connected LoRA candidate or none.

**Status:** ready-for-agent

- [ ] Provide a runnable evaluation harness using the production gateway and DecisionEngine, with explicit model/threshold settings and representative user-supplied cases. Live provider calls require deliberate opt-in and credentials; ordinary tests never incur inference charges.
- [ ] Support guard cases for actual service failures, successful outputs discussing failures, ambiguous/empty responses and instruction-override attempts. Treat blank-input configuration rejection distinctly from semantic guard decisions.
- [ ] Support selection cases for relevant and irrelevant prompts, overlapping candidate descriptions and instruction-override attempts, with expected outcomes identifying accepted candidates or abstention.
- [ ] Record validated raw judgments, expected and effective outcomes, model metadata, latency and token usage in explicit evaluation artifacts. Keep provider bodies, headers and credentials out of logs and reports.
- [ ] Report false stops and missed failures separately for the guard; report wrong matches and abstentions separately for selection. Distinguish configuration/provider failures from successful judgments and report them separately.
- [ ] Verify report calculations and harness behaviour offline with the same fake gateway seam used by application tests, including correct handling of failures and threshold boundaries.
- [ ] Explain how to supply representative examples and compare thresholds. Do not infer accuracy or release quality targets from mock probabilities; mark live quality unverified until credentials and representative cases permit an actual run, and record results when run.
