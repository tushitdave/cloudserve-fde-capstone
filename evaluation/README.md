# CloudServe evaluation

The frozen [gold seed package](gold/ANNOTATION_GUIDE.md) contains 580 supplied ticket labels, a stratified 120-ticket passage/claim review queue, two independent reviewer templates and a SHA-256 manifest. The 120-review queue covers all 22 intents, four channels, both routes and both language-fluency groups. Its passage and claim fields are **pending human adjudication**. Neither development nor visible validation is an untouched holdout.

Rebuild the seed package only when intentionally creating a new version:

```bash
PYTHONPATH=src python -m evaluation.gold_builder --output evaluation/gold
```

Score a completed batch by ticket ID against the frozen source labels:

```bash
PYTHONPATH=src python -m evaluation.gold_eval --results evaluation/reports/dev-a11/results.json --output evaluation/reports/gold-dev-a11.json
PYTHONPATH=src python -m evaluation.gold_eval --results evaluation/reports/validation-a11/results.json --output evaluation/reports/gold-validation-a11.json
```

`--require-adjudicated` intentionally fails while human reviews are pending. The scorer checks frozen file hashes and exact citation IDs/source versions. It reports claim support and hallucination as `null` until adjudicated claim labels exist.

After Reviewer A and Reviewer B independently complete copies of their respective templates, compare them:

```bash
PYTHONPATH=src python -m evaluation.review_compare --reviewer-a path/to/completed_a.jsonl --reviewer-b path/to/completed_b.jsonl --output evaluation/reports/reviewer_agreement.json
```

Do not overwrite v1 templates or queue. Resolve disagreements in a new adjudicated v2 file with a new manifest. Generated reports belong in ignored `evaluation/reports/`; freeze reviewed gold files in a versioned committed directory once approved.
