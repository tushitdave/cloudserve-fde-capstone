# Clean Git clone rehearsal

Run on 16 November 2026 in `/private/tmp/cloudserve-clone.Lgcpad`, cloned from local commit `5c423f0`. Host: macOS 26.6.2, build 25G83; Python 3.14.6 from the existing cached project environment; Node 25.9.0; npm 11.12.1; Apple Git 2.50.1. This verifies a fresh **source checkout** and installed frontend lockfile, but not a fresh Python dependency install or live server binding.

```bash
git clone --quiet . /private/tmp/cloudserve-clone.Lgcpad
npm --prefix /private/tmp/cloudserve-clone.Lgcpad/frontend ci --offline
CLOUDSERVE_PYTHON=/Users/tushitdave/.cache/uv/archive-v0/UtijoMQKFJEH9SXm7bVGR/bin/python /private/tmp/cloudserve-clone.Lgcpad/scripts/test.sh
CLOUDSERVE_PYTHON=/Users/tushitdave/.cache/uv/archive-v0/UtijoMQKFJEH9SXm7bVGR/bin/python /private/tmp/cloudserve-clone.Lgcpad/scripts/batch.sh /private/tmp/cloudserve-clone.Lgcpad/data/supplied/validation_tickets.json /private/tmp/cloudserve-clone.Lgcpad/evaluation/reports/clean-clone
```

Results: npm installed 69 packages with zero reported vulnerabilities; architecture and source credential checks passed; 43 Python tests passed; React TypeScript/Vite production build passed; 80-ticket batch produced 3 sent and 77 escalated results with 80/80 terminal and decision IDs reconciled. Git working tree in the clone remained clean; generated runtime and report files were ignored.

Remaining A1/A12 rehearsal: create a new Python environment and install pinned dependencies on an independent network-enabled machine, run `scripts/dev.sh` and inspect `http://localhost:5173` in a browser, then run the same commands again. The managed shell denied an offline `uv` cache initialization, localhost port binding and Docker socket access. The existing cached Python interpreter proves application compatibility, not clean dependency resolution.

After aligning `requirements.txt` with the tested dependency versions, the source-clone exercise was repeated from commit `39a0d75` in `/private/tmp/cloudserve-clone-final.U8IYJX`: offline `npm ci`, 43 Python tests, architecture/secret checks, React build and the 80-ticket batch all passed again. The same cached Python 3.14.6 interpreter was reused. This supersedes the earlier source-copy result but leaves the fresh Python install gate open.
