# Scripts

Add one-command batch runs, index builds, schema generation, migrations and evaluation commands here as the implementation grows. Scripts should call application use cases, not duplicate business policy.

`azure_model_smoke.py` checks the three configured Azure deployments from a private `.env` in the application root. It prints model responses/dimensions and never prints keys.
