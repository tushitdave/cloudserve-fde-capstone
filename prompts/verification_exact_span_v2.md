# PR-04 verification-exact-span-v2 (Verification Agent, deterministic)

For every line containing a `[passage_id]` citation:

- Each cited ID must belong to the passages retrieved for this ticket, otherwise `missing_or_unretrieved_citation`.
- After removing list markers and normalising whitespace, the line text must be a substring of each cited passage, otherwise `unsupported_claim`.

Any failure blocks release and escalates. The deterministic guardrails (`src/cloudserve/guardrails.py`) then run independently: grounding, tone/scope, private data and instruction integrity.
