import os
import json
from dotenv import load_dotenv
from pr_review_agent.logging_utils import log_action

load_dotenv()

# Google / Gemini is the only supported provider for this project.
# The actual model is configured here and used by the REST client below.

AI_STUDIO_KEY = os.getenv("AI_STUDIO_API_KEY")
AI_STUDIO_MODEL = os.getenv("AI_STUDIO_MODEL", "models/gemini-3.1-flash-lite")


class SimpleResponse:
    def __init__(self, text: str):
        self.content = text


class GeminiClient:
    """Very small client for Google Generative API using REST.

    Provides an `invoke(messages)` method to remain compatible with
    the rest of the codebase which calls `model.invoke([HumanMessage(...)])`.
    """

    def __init__(self, api_key: str, model: str = AI_STUDIO_MODEL, timeout: int = 45):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        try:
            import requests
        except Exception:  # pragma: no cover - runtime environment
            raise
        self._requests = requests

    def _choose_text_from_response(self, data: dict) -> str:
        if not data:
            return ""

        if "error" in data:
            return json.dumps(data)

        if "candidates" in data and isinstance(data["candidates"], list) and data["candidates"]:
            cand = data["candidates"][0]
            content = cand.get("content", {})
            parts = content.get("parts", [])
            if parts:
                texts = []
                for part in parts:
                    if isinstance(part, dict) and "text" in part:
                        texts.append(part["text"])
                    elif isinstance(part, str):
                        texts.append(part)
                if texts:
                    return "".join(texts)
            return json.dumps(cand)

        for key in ("output", "content", "text"):
            if key in data:
                return data[key]
        return json.dumps(data)

    def invoke(self, messages):
        parts = []
        for m in messages:
            if isinstance(m, str):
                parts.append(m)
                continue
            text = None
            if hasattr(m, "content"):
                text = getattr(m, "content")
            elif isinstance(m, dict) and "content" in m:
                text = m["content"]
            elif isinstance(m, dict) and "text" in m:
                text = m["text"]
            if text is not None:
                parts.append(text)

        prompt = "\n\n".join(parts)
        model_name = self.model.replace("models/", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
        body = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        log_action("tool", "LLM API call", f"model={self.model} url={url}")

        resp = self._requests.post(url, json=body, timeout=self.timeout)
        try:
            data = resp.json()
        except Exception:
            data = {"error": resp.text}
        log_action("tool", "LLM API response", f"status={getattr(resp, 'status_code', 'unknown')} payload_keys={list(data.keys())[:10] if isinstance(data, dict) else type(data).__name__}")

        text = self._choose_text_from_response(data)
        return SimpleResponse(text)


# Try to instantiate the best available client
model = None
if AI_STUDIO_KEY:
    try:
        model = GeminiClient(api_key=AI_STUDIO_KEY, model=AI_STUDIO_MODEL)
    except Exception:
        model = None

if model is None:
    # final fallback: simple echoing shim for local testing
    class EchoModel:
        def invoke(self, messages):
            parts = []
            for m in messages:
                if isinstance(m, str):
                    parts.append(m)
                elif hasattr(m, "content"):
                    parts.append(m.content)
                elif isinstance(m, dict) and "content" in m:
                    parts.append(m["content"])
            return SimpleResponse("\n\n".join(parts))

    model = EchoModel()
