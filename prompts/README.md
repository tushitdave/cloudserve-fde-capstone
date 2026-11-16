# Versioned prompt library

`registry.json` lists every prompt or deterministic template with its version, agent, model, inputs, outputs, the requirement IDs it serves and a change log. Model prompts are plain-text files loaded at runtime by `src/cloudserve/agents.py`, so the file is the single source of truth. The version string is written into every decision record (`prompt_version`). Agent outputs cannot publish knowledge or release customer responses; the deterministic release gate does that.
