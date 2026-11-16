# Evidence Agent query rewrite diagnostic

The Evidence Agent emits a versioned `QueryPlan` and `EvidenceBundle`, restricts retrieval to the approved predicted document, and performs at most two searches. When the first Resolution passage is strong enough it stops after one search. Otherwise it adds the predicted intent to the query and retains the stronger result. Weak evidence or a tool error leads to a human escalation through the deterministic route/failure gate.

`evaluation/query_rewrite_eval.py` compared the initial and rewritten queries with supplied expected-document labels. On 500 development tickets, 410 had an approved-document plan, 179 invoked the second search, first-query document hits were 184, rewritten-query hits were 215, candidate gain was 31, candidate harm was 0 and bounded-search violations were 0. On 80 visible validation tickets, 65 had an approved-document plan, 25 invoked rewrite, first-query hits were 30, rewritten-query hits were 33, gain was 3, harm was 0 and budget violations were 0.

These are **document-label diagnostics**, not passage Recall@k. The development set trained the intent/document predictors; visible validation labels informed earlier tuning. A zero harm count here does not prove that adding terms cannot hurt on unseen language or human-adjudicated passages. The final selected evidence is constrained to the authorized doc and the higher-score candidate. Passage-level review and no-answer specificity remain open under P4-04/P4-05.

```bash
PYTHONPATH=src:. .venv/bin/python -m evaluation.query_rewrite_eval --input data/supplied/development_tickets.json --output evaluation/reports/query-rewrite-dev.json
PYTHONPATH=src:. .venv/bin/python -m evaluation.query_rewrite_eval --input data/supplied/validation_tickets.json --output evaluation/reports/query-rewrite-validation.json
```
