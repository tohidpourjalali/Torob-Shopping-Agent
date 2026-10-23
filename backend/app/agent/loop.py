"""حلقهٔ ایجنت — یک `Runtime` برای هر دو موتور تصمیم.

مسیر ۱ (مدل زبانی): حلقهٔ استاندارد tool calling.
    system prompt + تاریخچه → مدل → tool_calls → اجرای ابزار → observation → مدل → …
مسیر ۲ (بدون مدل): همان حلقه با `planner.next_action`.

در هر دو مسیر:
  * هر فراخوانی ابزار در پاسخ برگردانده می‌شود (`tool_calls`) تا کاربر ببیند
    ایجنت واقعاً چه کاری انجام داده — نه یک متن آمادهٔ از پیش نوشته‌شده.
  * نشست در `agent_sessions` ذخیره می‌شود، پس گفت‌وگو بین نوبت‌ها ادامه دارد.
  * اگر مدل خطا داد (شبکه/کلید/سهمیه)، بی‌سروصدا به مسیر قطعی می‌افتد و
    این را در `notes` می‌گوید.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.agent import planner
from app.agent.llm import LLMError, build_model, load_config
from app.agent.prompts import SYSTEM_PROMPT
from app.core.text import content_tokens
from app.agent.tools import TOOL_SCHEMAS, TOOL_TITLES, ToolContext, ToolResult, run_tool
from app.db.models import AgentSession
from app.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    AgentStep,
    ProductSummary,
    PurchasePlanOut,
    StoreOffer,
    ToolCallTrace,
)
from app.services import search as search_service

log = logging.getLogger("agent.runtime")

MAX_STEPS = 8
MAX_HISTORY = 24


# --------------------------------------------------------------------------- #
# نشست
# --------------------------------------------------------------------------- #
def new_session_id() -> str:
    return f"s-{uuid.uuid4().hex[:12]}"


def load_state(db: Session, session_id: str) -> Dict[str, Any]:
    row = db.get(AgentSession, session_id)
    if not row or not row.state:
        return {}
    try:
        data = json.loads(row.state)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(db: Session, session_id: str, state: Dict[str, Any]) -> None:
    from datetime import datetime

    payload = json.dumps(state, ensure_ascii=False, default=str)
    row = db.get(AgentSession, session_id)
    now = datetime.utcnow()
    if row is None:
        db.add(AgentSession(session_id=session_id, state=payload, step=state.get("stage", ""),
                            created_at=now, updated_at=now))
    else:
        row.state = payload
        row.step = state.get("stage", "")
        row.updated_at = now
    db.commit()


# --------------------------------------------------------------------------- #
# Runtime
# --------------------------------------------------------------------------- #
class AgentRuntime:
    def __init__(self, db: Session, model=None):
        self.db = db
        self.config = load_config()
        self.model = model if model is not None else build_model(self.config)

    # ------------------------------------------------------------------ #
    def chat(self, request: AgentChatRequest) -> AgentChatResponse:
        session_id = (request.session_id or "").strip() or new_session_id()
        state = load_state(self.db, session_id) if request.session_id else {}
        state.setdefault("facts", {})
        state.setdefault("artifacts", {})
        state.setdefault("selection", {})
        state.setdefault("messages", [])
        state["tool_calls"] = _coerce_traces(state.get("tool_calls"))
        state.setdefault("stage", "need")

        self._absorb_request(state, request)

        fallback_note: Optional[str] = None
        if self.model is not None:
            try:
                return self._run_with_model(session_id, state, request)
            except LLMError as exc:
                log.warning("LLM failed, falling back to deterministic: %s", exc)
                fallback_note = f"مدل زبانی پاسخ نداد ({type(exc).__name__})؛ با برنامه‌ریز قطعی ادامه دادم."
                state["tool_calls"] = []
        return self._run_deterministic(session_id, state, request, fallback_note)

    # ------------------------------------------------------------------ #
    def _absorb_request(self, state: Dict[str, Any], request: AgentChatRequest) -> None:
        """واقعیت‌های تازه از درخواست را در نشست بریز (موقعیت، انتخاب صریح، متن)."""
        facts = state["facts"]
        before_fp = _search_fingerprint(state)

        if request.lat is not None and request.lon is not None:
            ctx = ToolContext(self.db, facts, state["artifacts"])
            # وقتی مختصات داریم، برچسب را نفرست: برچسب مشتق‌شده («نزدیک X»)
            # نام محلهٔ دیتاست نیست و ابزار را بی‌دلیل به خطا می‌اندازد.
            res = run_tool(ctx, "set_location", {"lat": request.lat, "lon": request.lon})
            facts.update(ctx.facts)
            state["tool_calls"].append(_to_trace(0, "set_location", {}, res, 0))
        elif request.location_label:
            ctx = ToolContext(self.db, facts, state["artifacts"])
            res = run_tool(ctx, "set_location", {"label": request.location_label})
            facts.update(ctx.facts)
            state["tool_calls"].append(_to_trace(0, "set_location", {}, res, 0))

        message = (request.message or "").strip()
        existing_products = state["artifacts"].get("products") or []
        # آیا این پیام «انتخاب محصول» است؟ (شناسه یا شماره/عنوان از فهرست قبلی)
        picked = planner.pick_product_from_message(message, existing_products) if message else None

        if message and message not in {"__start__", "start"}:
            # شناسهٔ محصول رقم دارد؛ استخراج بودجه/عبارت از آن، واقعیت‌ها را خراب می‌کند
            if picked is None:
                fresh = {k: v for k, v in planner.extract_facts(message).items() if v is not None}
                facts.update(fresh)
                # «سلام» یا «؟؟؟» نباید به‌عنوان عبارت جست‌وجو استفاده شود:
                # فقط وقتی عبارت می‌سازیم که توکن معنادار داشته باشد.
                if not facts.get("query") and content_tokens(message):
                    facts["query"] = message
                facts["last_message"] = message
            state["messages"].append({"role": "user", "content": message})

        if request.product_id:
            state["selection"]["product_id"] = request.product_id
            state["facts"].pop("query", None)
        if request.offer_id:
            state["selection"]["offer_id"] = request.offer_id

        # انتخاب محصول از میان پیشنهادهای همین نشست (کلیک یا شماره)
        if picked and not request.product_id:
            state["selection"]["product_id"] = picked

        # تغییر بودجه یا عبارت ⇒ نتیجهٔ جست‌وجوی قبلی بی‌اعتبار است
        # (انتخاب صریح محصول، عبارت را پاک می‌کند و نباید انتخاب را باطل کند)
        if not request.product_id and not picked and _search_fingerprint(state) != before_fp:
            state["tried"] = []
            state["artifacts"].pop("products", None)
            state["selection"].pop("product_id", None)
            state["attempts"] = {}

        # اگر محصول عوض شد، مشاهدات قبلی فروشگاه بی‌اعتبار می‌شوند
        if state["selection"].get("product_id") != state["artifacts"].get("_stores_for"):
            state["artifacts"].pop("stores", None)
            state["tried"] = []
            state["attempts"] = {}

    # ------------------------------------------------------------------ #
    def _run_deterministic(self, session_id: str, state: Dict[str, Any],
                           request: AgentChatRequest, fallback_note: Optional[str]) -> AgentChatResponse:
        ctx = ToolContext(self.db, state["facts"], state["artifacts"])
        traces: List[ToolCallTrace] = _coerce_traces(state.get("tool_calls"))
        tried: List[str] = list(state.get("tried") or [])
        attempts: Dict[str, int] = dict(state.get("attempts") or {})
        action = planner.Action(kind="answer", stage=state.get("stage", "need"))

        for _ in range(MAX_STEPS):
            action = planner.next_action({**state, "tried": tried, "attempts": attempts}, ctx)
            if action.kind != "tool":
                break
            t0 = time.perf_counter()
            result = run_tool(ctx, action.tool, action.arguments)
            ms = int((time.perf_counter() - t0) * 1000)
            traces.append(_to_trace(len(traces), action.tool, action.arguments, result, ms))
            tried.append(action.tool)
            attempts[action.tool] = attempts.get(action.tool, 0) + 1
            state["facts"].update(ctx.facts)
            state["artifacts"] = ctx.artifacts

        state["tried"] = tried
        state["attempts"] = attempts
        state["tool_calls"] = traces
        return self._finish(session_id, state, action, traces,
                            fallback_note=fallback_note, llm=False)

    # ------------------------------------------------------------------ #
    def _run_with_model(self, session_id: str, state: Dict[str, Any],
                        request: AgentChatRequest) -> AgentChatResponse:
        ctx = ToolContext(self.db, state["facts"], state["artifacts"])
        traces: List[ToolCallTrace] = _coerce_traces(state.get("tool_calls"))
        messages: List[Dict[str, Any]] = list(state.get("messages") or [])
        if not messages:
            messages = [{"role": "user", "content": request.message or "شروع"}]

        final_text = ""
        for _ in range(MAX_STEPS):
            turn = self.model.complete(SYSTEM_PROMPT, messages, TOOL_SCHEMAS)  # type: ignore[union-attr]
            if not turn.wants_tools:
                final_text = turn.content or ""
                messages.append({"role": "assistant", "content": final_text})
                break

            messages.append({
                "role": "assistant",
                "content": turn.content or "",
                "tool_calls": [
                    {"id": c.id, "type": "function",
                     "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)}}
                    for c in turn.tool_calls
                ],
            })
            for call in turn.tool_calls:
                t0 = time.perf_counter()
                result = run_tool(ctx, call.name, call.arguments)
                ms = int((time.perf_counter() - t0) * 1000)
                traces.append(_to_trace(len(traces), call.name, call.arguments, result, ms))
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": result.observation(),
                })
            state["facts"].update(ctx.facts)
            state["artifacts"] = ctx.artifacts
        else:
            final_text = ""

        state["messages"] = messages[-MAX_HISTORY:]
        state["tool_calls"] = traces

        stage = _infer_stage(ctx.artifacts, state["selection"])
        action = planner.Action(kind="answer", stage=stage, message=final_text)
        return self._finish(session_id, state, action, traces, fallback_note=None, llm=True)

    # ------------------------------------------------------------------ #
    def _finish(self, session_id: str, state: Dict[str, Any], action,
                traces: List[ToolCallTrace], fallback_note: Optional[str],
                llm: bool) -> AgentChatResponse:
        artifacts = state.get("artifacts") or {}
        selection = state.get("selection") or {}
        stage = action.stage or _infer_stage(artifacts, selection)

        products = [p for p in (artifacts.get("products") or [])][:8]
        stores = artifacts.get("stores") or []
        guide = artifacts.get("guide")

        reply = action.message or _build_reply(stage, artifacts, state, action)
        if fallback_note:
            reply = f"{reply}\n\n{fallback_note}" if reply else fallback_note

        notes = _notes_for(stage, artifacts)
        state["stage"] = stage
        state["artifacts"] = _trim_artifacts(artifacts)
        save_state(self.db, session_id, state)

        model_label = self.config.label if llm else "بدون مدل (برنامه‌ریز قطعی)"

        return AgentChatResponse(
            session_id=session_id,
            stage=stage,
            reply=reply,
            question=action.question,
            quick_replies=action.quick_replies,
            products=[_as_product(p) for p in products],
            stores=[_as_store(s) for s in stores if isinstance(s, dict)],
            guide=PurchasePlanOut(**guide) if guide else None,
            suggested_categories=artifacts.get("suggested_categories") or [],
            collected=_public_facts(state.get("facts") or {}),
            tool_calls=traces,
            agent_trace=_agent_trace(stage, traces, artifacts),
            reasoning_engine="llm" if llm else "deterministic",
            model_label=model_label,
            llm_enabled=llm,
            notes=notes,
        )


# --------------------------------------------------------------------------- #
# کمکی‌ها
# --------------------------------------------------------------------------- #
def _coerce_traces(raw: Any) -> List[ToolCallTrace]:
    """ردیابی‌های ذخیره‌شده در نشست JSON هستند؛ به مدل تبدیل می‌شوند."""
    out: List[ToolCallTrace] = []
    for item in raw or []:
        if isinstance(item, ToolCallTrace):
            out.append(item)
        elif isinstance(item, dict):
            try:
                out.append(ToolCallTrace(**item))
            except Exception:  # noqa: BLE001 - رکورد ناسازگار نباید گفت‌وگو را بشکند
                continue
    return out


def _to_trace(index: int, tool: str, arguments: Dict[str, Any], result: ToolResult, ms: int) -> ToolCallTrace:
    return ToolCallTrace(
        index=index,
        tool=tool,
        title=TOOL_TITLES.get(tool, tool),
        arguments={k: v for k, v in (arguments or {}).items() if v is not None},
        ok=result.ok,
        summary=result.summary,
        duration_ms=ms,
    )


def _search_fingerprint(state: Dict[str, Any]) -> str:
    facts = state.get("facts") or {}
    return "|".join(str(facts.get(k) or "") for k in ("query", "product_type", "budget_max"))


def _infer_stage(artifacts: Dict[str, Any], selection: Dict[str, Any]) -> str:
    if artifacts.get("guide"):
        return "guide"
    if artifacts.get("stores"):
        return "stores"
    if selection.get("product_id"):
        return "stores"
    if artifacts.get("products"):
        return "product"
    return "need"


def _build_reply(stage: str, artifacts: Dict[str, Any], state: Dict[str, Any], action) -> str:
    products = artifacts.get("products") or []
    stores = artifacts.get("stores") or []
    guide = artifacts.get("guide") or {}

    if stage == "guide" and guide:
        if guide.get("dataset_status") == "no_nearby_store":
            return (
                "این محصول در دیتاست هست اما در شعاع انتخابی فروشگاهی با آفر واقعی نبود. "
                "نقشهٔ خرید حضوری و چک‌لیست را آوردم؛ شعاع یا محله را هم می‌توانید عوض کنید."
            )
        if guide.get("dataset_status") == "not_in_dataset":
            return (
                "این کالا در دیتاست ترب نبود، پس فروشگاه یا قیمتی برایش نمی‌سازم. "
                "به‌جایش نقشهٔ خرید حضوری‌اش را چیدم: چطور استعلام بگیرید، چه بپرسید و چه چیزی را چک کنید."
            )
        shop = (guide.get("shop") or {}).get("name")
        return (
            f"{shop} بهترین گزینه از نظر قیمت/فاصله/ساعت است. "
            "نقشهٔ خرید حضوری را پایین ببینید — از تماس قبل از حرکت تا بازرسی کالا و فاکتور."
        )
    if stage == "stores" and stores:
        return f"{len(stores)} فروشگاه با آفر واقعی پیدا شد."
    if stage == "product" and products:
        return f"{len(products)} محصول مطابق پیدا شد؛ کدام را می‌خواهید؟"
    return "می‌توانم محصول را پیدا کنم، فروشگاه‌های حضوری‌اش را با قیمت و فاصله بیاورم، و راهنمای خرید حضوری بدهم."


def _notes_for(stage: str, artifacts: Dict[str, Any]) -> List[str]:
    notes: List[str] = []
    if stage == "guide" and (artifacts.get("guide") or {}).get("dataset_status") == "no_nearby_store":
        notes.append("برای این محصول در شعاع انتخابی آفری نبود؛ آدرس/قیمت ساختگی ساخته نشد.")
    if stage == "guide" and (artifacts.get("guide") or {}).get("dataset_status") == "not_in_dataset":
        notes.append("این کالا در دیتاست نیست؛ برایش فروشگاه/قیمت ساختگی ساخته نشد.")
    if artifacts.get("stores"):
        notes.append("قیمت‌ها snapshot دیتاست هستند و تأییدنشده‌اند.")
    return notes


def _agent_trace(stage: str, traces: List[ToolCallTrace], artifacts: Dict[str, Any]) -> List[AgentStep]:
    steps: List[AgentStep] = []
    by_tool = {t.tool: t for t in traces}
    order = [
        ("need", "کشف نیاز", ["search_products", "dataset_coverage"]),
        ("product", "انتخاب محصول", ["get_product"]),
        ("stores", "یافتن فروشگاه حضوری", ["find_stores", "compare_offers"]),
        ("verify", "تأیید قیمت/موجودی", ["request_verification"]),
        ("guide", "راهنمای خرید حضوری", ["build_purchase_guide"]),
    ]
    active_found = False
    for key, title, tools in order:
        hit = next((by_tool[t] for t in tools if t in by_tool), None)
        if hit:
            steps.append(AgentStep(step=key, title=title, detail=hit.summary, status="done"))
        elif not active_found:
            steps.append(AgentStep(step=key, title=title, detail="در انتظار", status="active"))
            active_found = True
        else:
            steps.append(AgentStep(step=key, title=title, detail="در انتظار", status="pending"))
    return steps


def _public_facts(facts: Dict[str, Any]) -> Dict[str, Any]:
    keep = {"query", "product_type", "budget_max", "budget_min", "location", "category", "brand"}
    return {k: v for k, v in facts.items() if k in keep and v not in (None, "", [], {})}


def _trim_artifacts(artifacts: Dict[str, Any]) -> Dict[str, Any]:
    """آرتیفکت‌های بزرگ را برای ذخیره در نشست کوتاه می‌کند."""
    out: Dict[str, Any] = {}
    if artifacts.get("products"):
        out["products"] = artifacts["products"][:8]
        out["_stores_for"] = (artifacts.get("selected_product") or {}).get("product_id")
    if artifacts.get("suggested_categories"):
        out["suggested_categories"] = artifacts["suggested_categories"][:6]
    if artifacts.get("stores"):
        out["stores"] = artifacts["stores"][:12]
    if artifacts.get("guide"):
        out["guide"] = artifacts["guide"]
    if artifacts.get("coverage"):
        out["coverage"] = artifacts["coverage"]
    if artifacts.get("selected_product"):
        out["selected_product"] = {
            k: artifacts["selected_product"].get(k) for k in ("product_id", "persian_title")
        }
    return out


def _as_product(p: Dict[str, Any]) -> ProductSummary:
    allowed = set(ProductSummary.model_fields)
    return ProductSummary(**{k: v for k, v in p.items() if k in allowed})


def _as_store(s: Dict[str, Any]) -> StoreOffer:
    allowed = set(StoreOffer.model_fields)
    return StoreOffer(**{k: v for k, v in s.items() if k in allowed})


# --------------------------------------------------------------------------- #
# قابلیت‌ها (برای صفحهٔ شفافیت)
# --------------------------------------------------------------------------- #
def capabilities() -> Dict[str, Any]:
    cfg = load_config()
    return {
        "llm_enabled": cfg.available,
        "provider": cfg.provider,
        "model": cfg.model,
        "model_label": cfg.label,
        "tools": [{"name": t["function"]["name"], "title": TOOL_TITLES.get(t["function"]["name"], ""),
                   "description": t["function"].get("description", "")} for t in TOOL_SCHEMAS],
        "note": (
            "مدل زبانی پیکربندی شده است و حلقهٔ tool calling با آن اجرا می‌شود."
            if cfg.available
            else "هیچ کلید مدلی در env نیست؛ ایجنت با برنامه‌ریز قطعی همان ابزارها را صدا می‌زند. "
                 "برای فعال‌کردن مدل: LLM_PROVIDER و LLM_API_KEY را در .env بگذارید."
        ),
    }
