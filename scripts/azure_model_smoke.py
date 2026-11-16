"""Minimal Azure OpenAI connectivity check; run from the project root."""
import json, urllib.parse, urllib.request
from pathlib import Path

cfg = dict(line.split('=', 1) for line in Path(__file__).resolve().parents[1].joinpath('.env').read_text().splitlines() if '=' in line and not line.lstrip().startswith('#'))
cfg = {k.strip(): v.strip().strip('"\'') for k, v in cfg.items()}
failed = False
def check(label, endpoint, deployment, version, key, path, payload):
    global failed
    url = f"{cfg[endpoint].rstrip('/')}/openai/deployments/{urllib.parse.quote(cfg[deployment])}/{path}?api-version={cfg[version]}"
    req = urllib.request.Request(url, json.dumps(payload).encode(), {'Content-Type': 'application/json', 'api-key': cfg[key]})
    try:
        with urllib.request.urlopen(req, timeout=30) as res: data = json.load(res)
        print(f"{label}: OK ({'dimensions=' + str(len(data['data'][0]['embedding'])) if path == 'embeddings' else 'response=' + repr(data['choices'][0]['message'].get('content'))})")
    except Exception as exc:
        failed = True
        print(f"{label}: FAILED ({type(exc).__name__}: {getattr(exc, 'code', str(exc))})")
for label, e, d, v, k in [('GPT-4o', 'AZURE_GPT_4o_ENDPOINT', 'AZURE_DEPLOYMENT_GPT_4o', 'AZURE_GPT_4o_API_VERSION', 'AZURE_GPT_4o_API_KEY'), ('o3-mini', 'AZURE_O3_mini_ENDPOINT', 'AZURE_O3_mini_DEPLOYMENT_NAME', 'AZURE_O3_mini_VERSION', 'AZURE_O3_mini_API_KEY')]:
    check(label, e, d, v, k, 'chat/completions', {'messages': [{'role': 'user', 'content': 'Reply with exactly OK.'}], 'max_completion_tokens': 300})
check('text-embedding-ada-002', 'embedding_endpoint_url', 'embedding_model_name', 'embedding_api_version', 'embedding_api_key', 'embeddings', {'input': 'CloudServe smoke test'})
raise SystemExit(1 if failed else 0)
