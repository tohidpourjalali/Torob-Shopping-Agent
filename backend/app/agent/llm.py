"""لایهٔ مدل زبانی — آداپتورهای provider برای حلقهٔ ایجنت.

پشتیبانی:
  * `openai`      — OpenAI Chat Completions با tool calling
  * `openrouter`  — سازگار با OpenAI (مدل‌های مختلف)
  * `groq`        — سازگار با OpenAI
  * `ollama`      — اجرای محلی، سازگار با OpenAI (`/v1`)
  * `anthropic`   — Messages API با tool use
  * `none`        — بدون مدل؛ برنامه‌ریز قاعده‌محور (`planner.py`) کار می‌کند

هیچ کلیدی در کد نیست: همه از env خوانده می‌شود. اگر کلید نبود، `available`
برمی‌گردد False و حلقهٔ ایجنت به برنامه‌ریز قطعی می‌افتد — یعنی برنامه هرگز
به خاطر نبود شبکه یا کلید از کار نمی‌افتد.

این ماژول عمداً بدون SDK رسمی نوشته شده (فقط httpx) تا نصب سبک بماند و
بتوان با یک endpoint سازگارِ دلخواه (vLLM، LM Studio، Azure، …) هم کار کرد.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

import httpx

log = logging.getLogger("agent.llm")

# پیش‌فرض‌های هر provider: base_url و مدل
PROVIDER_DEFAULTS: Dict[str, Dict[str, str]] = {
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o-mini"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "ollama": {"base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5:7b-instruct"},
    "anthropic": {"base_url": "https://api.anthropic.com/v1", "model": "claude-3-5-sonnet-latest"},
}

OPENAI_COMPATIBLE = {"openai", "openrouter", "groq", "ollama"}


class LLMError(RuntimeError):
    """خطای فراخوانی مدل — حلقهٔ ایجنت این را می‌گیرد و به برنامه‌ریز قطعی می‌افتد."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AssistantTurn:
    """یک نوبت مدل: یا متن نهایی، یا درخواست اجرای ابزار (یا هر دو)."""

    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


@dataclass
class LLMConfig:
    provider: str = "none"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.2
    timeout: float = 45.0

    @property
    def available(self) -> bool:
        if self.provider in {"", "none"}:
            return False
        if self.provider in OPENAI_COMPATIBLE:
            # ollama محلی کلید نمی‌خواهد
            return self.provider == "ollama" or bool(self.api_key)
        return bool(self.api_key)

    @property
    def label(self) -> str:
        if not self.available:
            return "بدون مدل (برنامه‌ریز قطعی)"
        return f"{self.provider}/{self.model}"


def load_config() -> LLMConfig:
    provider = (os.getenv("LLM_PROVIDER") or "none").strip().lower()
    defaults = PROVIDER_DEFAULTS.get(provider, {})
    return LLMConfig(
        provider=provider,
        api_key=(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip() or None,
        base_url=(os.getenv("LLM_BASE_URL") or defaults.get("base_url") or "").strip() or None,
        model=(os.getenv("LLM_MODEL") or defaults.get("model") or "").strip() or None,
        temperature=float(os.getenv("LLM_TEMPERATURE") or 0.2),
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS") or 45.0),
    )


class ChatModel(Protocol):
    """قرارداد مشترک همهٔ providerها."""

    config: LLMConfig

    def complete(
        self, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> AssistantTurn: ...


# --------------------------------------------------------------------------- #
# سازگار با OpenAI: /chat/completions + tools
# --------------------------------------------------------------------------- #
class OpenAICompatibleModel:
    def __init__(self, config: LLMConfig):
        self.config = config

    def complete(
        self, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> AssistantTurn:
        url = f"{(self.config.base_url or '').rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        if self.config.provider == "openrouter":
            # این دو هدر برای رتبه‌بندی OpenRouter توصیه می‌شود
            headers["HTTP-Referer"] = os.getenv("PUBLIC_BASE_URL", "http://localhost")
            headers["X-Title"] = "Torob In-Person Shopping Agent"

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            with httpx.Client(timeout=self.config.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"تماس با مدل ناموفق بود: {exc}") from exc

        try:
            choice = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("پاسخ مدل ساختار مورد انتظار را نداشت") from exc

        calls: List[ToolCall] = []
        for i, raw in enumerate(choice.get("tool_calls") or []):
            fn = raw.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args or "{}")
                except json.JSONDecodeError:
                    args = {}
            calls.append(
                ToolCall(
                    id=raw.get("id") or f"call_{i}",
                    name=fn.get("name") or "",
                    arguments=args if isinstance(args, dict) else {},
                )
            )
        return AssistantTurn(content=(choice.get("content") or "").strip(), tool_calls=calls)


# --------------------------------------------------------------------------- #
# Anthropic: /messages + tool use
# --------------------------------------------------------------------------- #
class AnthropicModel:
    def __init__(self, config: LLMConfig):
        self.config = config

    def complete(
        self, system: str, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> AssistantTurn:
        url = f"{(self.config.base_url or '').rstrip('/')}/messages"
        payload = {
            "model": self.config.model,
            "max_tokens": 1024,
            "temperature": self.config.temperature,
            "system": system,
            "messages": [_to_anthropic_message(m) for m in messages],
        }
        if tools:
            payload["tools"] = [_to_anthropic_tool(t) for t in tools]

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key or "",
            "anthropic-version": "2023-06-01",
        }
        try:
            with httpx.Client(timeout=self.config.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"تماس با مدل ناموفق بود: {exc}") from exc

        text_parts: List[str] = []
        calls: List[ToolCall] = []
        for block in data.get("content") or []:
            if block.get("type") == "text":
                text_parts.append(block.get("text") or "")
            elif block.get("type") == "tool_use":
                calls.append(
                    ToolCall(
                        id=block.get("id") or f"call_{len(calls)}",
                        name=block.get("name") or "",
                        arguments=block.get("input") or {},
                    )
                )
        return AssistantTurn(content="".join(text_parts).strip(), tool_calls=calls)


def _to_anthropic_tool(tool: Dict[str, Any]) -> Dict[str, Any]:
    fn = tool.get("function") or {}
    return {
        "name": fn.get("name"),
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
    }


def _to_anthropic_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """پیام‌های سبک OpenAI را به سبک Anthropic تبدیل می‌کند."""
    role = message.get("role")
    if role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message.get("tool_call_id"),
                    "content": message.get("content") or "",
                }
            ],
        }
    if role == "assistant" and message.get("tool_calls"):
        content: List[Dict[str, Any]] = []
        if message.get("content"):
            content.append({"type": "text", "text": message["content"]})
        for call in message["tool_calls"]:
            fn = call.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args or "{}")
                except json.JSONDecodeError:
                    args = {}
            content.append(
                {"type": "tool_use", "id": call.get("id"), "name": fn.get("name"), "input": args}
            )
        return {"role": "assistant", "content": content}
    return {"role": role, "content": message.get("content") or ""}


def build_model(config: Optional[LLMConfig] = None) -> Optional[ChatModel]:
    """مدل را می‌سازد یا None برمی‌گرداند (یعنی مسیر قطعی)."""
    cfg = config or load_config()
    if not cfg.available:
        return None
    if cfg.provider == "anthropic":
        return AnthropicModel(cfg)
    if cfg.provider in OPENAI_COMPATIBLE:
        return OpenAICompatibleModel(cfg)
    log.warning("LLM_PROVIDER ناشناخته: %s — مسیر قطعی فعال می‌شود", cfg.provider)
    return None
