"""Narrow Azure OpenAI chat adapter with bounded request time."""

import json
import urllib.parse
import urllib.request
import urllib.error
import threading

from cloudserve.config import setting


class ModelUnavailable(RuntimeError):
    pass


_USAGE_LOCK = threading.Lock()
_USAGE: dict[str, dict[str, float]] = {}


def _price(model: str, kind: str) -> float:
    names = {
        ("gpt-4o", "input"): "CLOUDSERVE_GPT4O_INPUT_USD_PER_M",
        ("gpt-4o", "output"): "CLOUDSERVE_GPT4O_OUTPUT_USD_PER_M",
        ("o3-mini", "input"): "CLOUDSERVE_O3MINI_INPUT_USD_PER_M",
        ("o3-mini", "output"): "CLOUDSERVE_O3MINI_OUTPUT_USD_PER_M",
        ("text-embedding-ada-002", "input"): "CLOUDSERVE_ADA002_INPUT_USD_PER_M",
    }
    try:
        return float(setting(names.get((model, kind), ""), "0") or 0)
    except ValueError:
        return 0.0


def _record_usage(model: str, usage: dict | None) -> None:
    if not usage:
        return
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    estimated = prompt * _price(model, "input") / 1_000_000 + completion * _price(model, "output") / 1_000_000
    with _USAGE_LOCK:
        row = _USAGE.setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_usd": 0.0})
        row["calls"] += 1
        row["input_tokens"] += prompt
        row["output_tokens"] += completion
        row["total_tokens"] += total
        row["estimated_usd"] = round(row["estimated_usd"] + estimated, 8)


def usage_snapshot() -> dict:
    """Process-local provider usage. Cost stays zero until explicit price settings are configured."""
    with _USAGE_LOCK:
        models = {name: dict(values) for name, values in _USAGE.items()}
    return {
        "models": models,
        "total_calls": int(sum(row["calls"] for row in models.values())),
        "total_tokens": int(sum(row["total_tokens"] for row in models.values())),
        "estimated_usd": round(sum(row["estimated_usd"] for row in models.values()), 8),
        "cost_status": "configured_estimate" if any(_price(name, "input") or _price(name, "output") for name in models) else "price_not_configured",
        "scope": "current_api_process",
    }


def embed(texts: list[str], timeout: int = 20) -> list[list[float]]:
    """Call the configured Azure ada-002 deployment; never persist credentials."""
    endpoint = setting("embedding_endpoint_url")
    key = setting("embedding_api_key")
    deployment = setting("embedding_model_name", "text-embedding-ada-002")
    version = setting("embedding_api_version")
    if not all((endpoint, key, deployment, version)):
        raise ModelUnavailable("embedding deployment is not configured")
    url = f"{endpoint.rstrip('/')}/openai/deployments/{urllib.parse.quote(deployment)}/embeddings?api-version={version}"
    request = urllib.request.Request(url, json.dumps({"input": texts}).encode(), {"Content-Type": "application/json", "api-key": key})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        _record_usage("text-embedding-ada-002", data.get("usage"))
        ordered = sorted(data["data"], key=lambda item: item["index"])
        vectors = [item["embedding"] for item in ordered]
        if len(vectors) != len(texts) or any(len(vector) != 1536 for vector in vectors):
            raise ModelUnavailable("embedding response shape mismatch")
        return vectors
    except Exception as error:
        raise ModelUnavailable(f"embedding request failed: {type(error).__name__}") from error


def chat(messages: list[dict], model: str = "gpt-4o", timeout: int = 12) -> str:
    prefix = "AZURE_GPT_4o" if model == "gpt-4o" else "AZURE_O3_mini"
    endpoint = setting(f"{prefix}_ENDPOINT")
    key = setting(f"{prefix}_API_KEY")
    deployment = setting("AZURE_DEPLOYMENT_GPT_4o" if model == "gpt-4o" else "AZURE_O3_mini_DEPLOYMENT_NAME")
    version = setting("AZURE_GPT_4o_API_VERSION" if model == "gpt-4o" else "AZURE_O3_mini_VERSION")
    if not all((endpoint, key, deployment, version)):
        raise ModelUnavailable(f"{model} is not configured")
    url = f"{endpoint.rstrip('/')}/openai/deployments/{urllib.parse.quote(deployment)}/chat/completions?api-version={version}"
    payload = {"messages": messages, "max_completion_tokens": 500}
    request = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json", "api-key": key})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        _record_usage(model, data.get("usage"))
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ModelUnavailable(f"{model} returned empty content")
        return content.strip()
    except Exception as error:
        raise ModelUnavailable(f"{model} request failed: {type(error).__name__}") from error
