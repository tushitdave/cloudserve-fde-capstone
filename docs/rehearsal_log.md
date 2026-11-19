# Clean Git clone rehearsal

Run on 16 November 2026 in `/private/tmp/cloudserve-clone.Lgcpad`, cloned from local commit `b47779d`. Host: macOS 26.6.2, build 25G83; Python 3.14.6 from the existing cached project environment; Node 25.9.0; npm 11.12.1; Apple Git 2.50.1. This verifies a fresh **source checkout** and installed frontend lockfile, but not a fresh Python dependency install or live server binding.

```bash
git clone --quiet . /private/tmp/cloudserve-clone.Lgcpad
npm --prefix /private/tmp/cloudserve-clone.Lgcpad/frontend ci --offline
CLOUDSERVE_PYTHON=/Users/tushitdave/.cache/uv/archive-v0/UtijoMQKFJEH9SXm7bVGR/bin/python /private/tmp/cloudserve-clone.Lgcpad/scripts/test.sh
CLOUDSERVE_PYTHON=/Users/tushitdave/.cache/uv/archive-v0/UtijoMQKFJEH9SXm7bVGR/bin/python /private/tmp/cloudserve-clone.Lgcpad/scripts/batch.sh /private/tmp/cloudserve-clone.Lgcpad/data/supplied/validation_tickets.json /private/tmp/cloudserve-clone.Lgcpad/evaluation/reports/clean-clone
```

Results: npm installed 69 packages with zero reported vulnerabilities; architecture and source credential checks passed; 43 Python tests passed; React TypeScript/Vite production build passed; 80-ticket batch produced 3 sent and 77 escalated results with 80/80 terminal and decision IDs reconciled. Git working tree in the clone remained clean; generated runtime and report files were ignored.

Remaining A1/A12 rehearsal: create a new Python environment and install pinned dependencies on an independent network-enabled machine, run `scripts/dev.sh` and inspect `http://localhost:5173` in a browser, then run the same commands again. The managed shell denied an offline `uv` cache initialization, localhost port binding and Docker socket access. The existing cached Python interpreter proves application compatibility, not clean dependency resolution.

After aligning `requirements.txt` with the tested dependency versions, the source-clone exercise was repeated from commit `b2876ed` in `/private/tmp/cloudserve-clone-final.U8IYJX`: offline `npm ci`, 43 Python tests, architecture/secret checks, React build and the 80-ticket batch all passed again. The same cached Python 3.14.6 interpreter was reused. This supersedes the earlier source-copy result but leaves the fresh Python install gate open.

## Container and evaluator-browser rehearsal — 18 November 2026

The final rehearsal used clean container layers rather than the host Python environment. The backend image was built from `python:3.12-slim`; its fresh dependency installation completed and the service reached application startup. The frontend image was built from Node 22 and served through Nginx. From inside the web container, `GET /api/health` returned `{"status":"ok","service":"cloudserve-api"}` and the authenticated diagnostics route reported Chroma `ready`, 145 passages and the active 384-dimensional local embedding index. This validates the web-proxy-to-API path. The host-side managed shell could not reach the forwarded port because of its network namespace, so the internal proxy check is the recorded container proof.

The React production build passed. Browser rehearsal captured the overview, four-channel Ticket Lab behavior, evidence answer, prompt-injection guardrail, HITL queue, knowledge graph, source lineage, dense/lexical/hybrid retrieval comparison, fallback/trace diagnostics, per-agent latency, outbox/dead-letter state, drift, offline evaluation and token/cost panels. Five sampled frames from the technical walkthrough were visually inspected at 1280×800.

The Docker Compose plugin was unavailable, so equivalent explicit network/container commands were used. `npm ci` reported four high-severity dependency advisories in the frontend dependency tree; they are recorded for remediation rather than hidden or auto-fixed with a potentially breaking major upgrade. The images remain available for another rehearsal; the named rehearsal containers and network are removed after evidence capture.
