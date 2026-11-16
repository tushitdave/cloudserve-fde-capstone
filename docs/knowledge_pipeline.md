# Governed knowledge pipeline: local prototype

## Flow

1. The 29 supplied articles are the approved baseline. `data/manifests/source_manifest_v1.json` freezes their IDs, hashes, owner and authority. Canonical documents retain the original text, 145 section spans and 116 numbered-step spans with exact offsets.
2. The Knowledge page stages a revision of an existing document ID. Source Intake checks the JSON shape; Knowledge Steward records warnings and quarantine reasons. Unknown IDs, absent resolution sections, unsafe instructions, possible secrets and out-of-bounds text are quarantined.
3. A pending candidate needs a named human review with notes. Rejection keeps the active index unchanged. Publication requires an approved job and checks that its base version is still active. SQLite commits the active version and revision atomically.
4. Retrieval reads the current approved snapshot. The previous source remains addressable by document ID, passage ID and source version. A ticket citation links to that exact version. If the source changes before answer release, the release gate blocks the stale citation.
5. The Knowledge page shows the source catalog, active index revision, version history, passage offsets, related article IDs, citing tickets and review queue. Review and publication actions are audit events in `knowledge.sqlite`.

## API and proof

`POST /v1/knowledge/jobs` accepts an article revision. `GET /v1/knowledge/jobs` lists review states; `GET /v1/knowledge/jobs/{id}` includes events. `POST /v1/knowledge/jobs/{id}/approve`, `/reject` and `/publish` perform the lifecycle. `GET /v1/knowledge/documents/{id}/versions` lists source hashes and certification records. `GET /v1/knowledge/documents/{id}/lineage?source_version=...` returns historical passage text, offsets and ticket links. `GET /v1/knowledge/passages/{passage_id}?source_version=...` resolves an exact citation.

`tests/test_knowledge_pipeline.py` covers the publication gate, rejected and quarantined candidates, stale approvals, idempotent restaging, revision changes, source offsets and old citations. `tests/test_knowledge_api.py` covers the HTTP lifecycle and versioned lineage. The 31-test backend suite and React production build passed on 16 November 2026. The full 500 development and 80 visible validation ticket batches still reconcile to one terminal result per ticket after revisioned retrieval.

## Remaining acceptance work

- Connect reviewer and publisher actions to authenticated roles and tenant/source permissions. Typed names in the local UI are audit labels, not verified identity.
- Add safe parsers for other file formats, per-job retry/checkpoint handling, and a controlled way to introduce new document IDs with classifier intent mapping.
- Measure cross-article conflicts, duplicate content, passage relevance and dense retrieval on human-adjudicated gold. Refresh an Azure dense index after a publication; until then retrieval uses the revised lexical index.
- Run a real browser and deployment rehearsal; this session verified TypeScript/Vite compilation and ASGI behavior only.
