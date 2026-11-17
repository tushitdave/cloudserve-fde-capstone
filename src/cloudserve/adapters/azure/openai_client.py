"""Narrow Azure OpenAI chat adapter with bounded request time."""

import json
import urllib.parse
import urllib.request
import urllib.error

from cloudserve.config import setting


class ModelUnavailable(RuntimeError):
    pass


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
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ModelUnavailable(f"{model} returned empty content")
        return content.strip()
    except Exception as error:
        raise ModelUnavailable(f"{model} request failed: {type(error).__name__}") from error
