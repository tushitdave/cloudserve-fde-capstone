# PR-05 triage-v2-deterministic (Triage Agent)

Triggered only when calibrated intent confidence is below the policy threshold (currently 0.90). It records the top three intent interpretations with their confidences in the `triage_reviewed` event and the escalation packet's "Unknown" list. It always recommends escalation, so it cannot lower a threshold, override a rule or send.

Deferred experiment: an o3-mini adjudication prompt. It needs labelled ambiguous tickets to show incremental gain (P5-06).
