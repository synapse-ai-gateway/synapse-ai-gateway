"""
GET /admin/models — fetch available models from the configured LLM backend.
Works with both Ollama (/v1/models OpenAI-compatible) and vLLM.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from auth import require_role
from config import settings
from state import gateway_settings

router = APIRouter()


@router.get("/models")
async def list_models(current_user=Depends(require_role("analyst"))) -> dict:
    """
    Proxy the model list from the configured vllm_url.
    Returns a list of model id strings.
    Raises 502 with a descriptive message if the LLM backend is unreachable.
    """
    base_url = gateway_settings.get("vllm_url", settings.VLLM_URL).rstrip("/")
    try:
        async with httpx.AsyncClient(
            timeout=settings.MODELS_FETCH_TIMEOUT_SEC, trust_env=False, follow_redirects=True
        ) as client:
            resp = await client.get(f"{base_url}/models")
            resp.raise_for_status()
            data = resp.json()
            # OpenAI-compatible format: {"object": "list", "data": [{"id": "..."}]}
            models = [m["id"] for m in data.get("data", [])]
            return {"models": models}
    except httpx.ConnectError:
        raise HTTPException(
            status_code=502,
            detail=f"Cannot connect to LLM backend at {base_url}. "
                   "Make sure Ollama/vLLM is running ('ollama serve').",
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail=f"LLM backend at {base_url} did not respond within "
                   f"{settings.MODELS_FETCH_TIMEOUT_SEC} seconds.",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"LLM backend returned HTTP {e.response.status_code}: {e.response.text[:200]}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Unexpected error fetching models: {e}",
        )
