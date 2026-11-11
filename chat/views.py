from __future__ import annotations

import json
import logging
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from . import limits
from .models import Conversation, Site
from .services.bot import record_exchange

log = logging.getLogger(__name__)
WIDGET_PATH = Path(__file__).resolve().parent / "static" / "chat" / "widget.js"


# ---- cross-origin handling ---------------------------------------------------------------
# The widget runs on the customer's website and calls this server, so every API response needs
# CORS headers. No cookies are used: a conversation is identified by an unguessable id that the
# widget keeps in the visitor's browser, which is why these endpoints are exempt from CSRF.

def _origin_ok(request: HttpRequest, site: Site) -> bool:
    origin = request.headers.get("Origin")
    if not origin:
        return True  # same-origin navigation or a server-side call; rate limits still apply
    own = f"{request.scheme}://{request.get_host()}"
    return origin.rstrip("/") == own or site.origin_allowed(origin)


def _cors(request: HttpRequest, response: HttpResponse) -> HttpResponse:
    origin = request.headers.get("Origin")
    if origin:
        response["Access-Control-Allow-Origin"] = origin
        response["Vary"] = "Origin"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        response["Access-Control-Max-Age"] = "600"
    return response


def _json(request: HttpRequest, data: dict, status: int = 200) -> HttpResponse:
    return _cors(request, JsonResponse(data, status=status))


def _error(request: HttpRequest, message: str, status: int = 400) -> HttpResponse:
    return _json(request, {"error": message}, status)


def _serialize(conversation: Conversation) -> dict:
    return {
        "id": str(conversation.id),
        "status": conversation.status,
        "status_label": conversation.get_status_display(),
        "lead": {"name": conversation.lead_name, "email": conversation.lead_email, "note": conversation.lead_note},
        "messages": [{"role": m.role, "text": m.text} for m in conversation.messages.all()],
    }


def purge_old() -> int:
    cutoff = timezone.now() - timedelta(days=settings.SITECHAT["RETENTION_DAYS"])
    return Conversation.objects.filter(updated_at__lt=cutoff).delete()[0]


# ---- pages -------------------------------------------------------------------------------
@require_GET
def home(request: HttpRequest):
    return render(
        request,
        "chat/home.html",
        {
            "base_url": f"{request.scheme}://{request.get_host()}",
            "repo_url": settings.SITECHAT["REPO_URL"],
            "ai_enabled": bool(settings.ANTHROPIC_API_KEY),
            "retention_days": settings.SITECHAT["RETENTION_DAYS"],
        },
    )


@require_GET
def widget_js(request: HttpRequest):
    """Stable, cache-friendly address for the embed script: <script src=".../widget.js">."""
    response = HttpResponse(WIDGET_PATH.read_text(encoding="utf-8"), content_type="application/javascript; charset=utf-8")
    response["Cache-Control"] = "public, max-age=600"
    response["Access-Control-Allow-Origin"] = "*"
    response["Cross-Origin-Resource-Policy"] = "cross-origin"
    return response


@require_GET
def healthz(request: HttpRequest):
    return JsonResponse({"ok": True, "ai": bool(settings.ANTHROPIC_API_KEY)})


# ---- widget API --------------------------------------------------------------------------
@csrf_exempt
def site_config(request: HttpRequest, slug: str):
    if request.method == "OPTIONS":
        return _cors(request, HttpResponse(status=204))
    site = get_object_or_404(Site, slug=slug)
    if not _origin_ok(request, site):
        return _error(request, "This website is not allowed to use this chat widget.", 403)
    return _json(request, {"name": site.name, "greeting": site.greeting, "accent": site.accent})


@csrf_exempt
def messages(request: HttpRequest, slug: str):
    if request.method == "OPTIONS":
        return _cors(request, HttpResponse(status=204))
    if request.method != "POST":
        return _error(request, "Use POST.", 405)
    site = get_object_or_404(Site, slug=slug)
    if not _origin_ok(request, site):
        return _error(request, "This website is not allowed to use this chat widget.", 403)

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _error(request, "Send the message as JSON.")
    text = str(payload.get("text", "")).strip()
    cfg = settings.SITECHAT
    if not text:
        return _error(request, "Type a message first.")
    if len(text) > cfg["MAX_MESSAGE_CHARS"]:
        return _error(request, f"Keep messages under {cfg['MAX_MESSAGE_CHARS']} characters.")
    if not limits.allow("msg", limits.client_ip(request), cfg["MESSAGES_PER_IP_PER_DAY"]):
        return _error(request, "You have reached today's message limit. Please try again tomorrow.", 429)
    if not limits.allow("msg-total", "everyone", cfg["MESSAGES_PER_DAY_TOTAL"]):
        return _error(request, "The chat has reached its daily limit. Please try again tomorrow.", 429)

    conversation = None
    conversation_id = payload.get("conversation")
    if conversation_id:
        try:
            conversation = Conversation.objects.filter(pk=uuid.UUID(str(conversation_id)), site=site).first()
        except ValueError:
            conversation = None
    if conversation is None:
        purge_old()
        conversation = Conversation.objects.create(site=site, page_url=str(payload.get("page", ""))[:500])
    if conversation.messages.count() >= cfg["MAX_MESSAGES_PER_CONVERSATION"]:
        return _error(request, "This conversation has reached its length limit. Start a new chat to continue.", 429)

    reply = record_exchange(conversation, text)
    return _json(
        request,
        {
            "conversation": str(conversation.id),
            "reply": reply.text,
            "lead_saved": reply.lead_saved,
            "needs_human": reply.needs_human,
            "mode": reply.mode,
        },
    )


@csrf_exempt
def conversation_detail(request: HttpRequest, pk: uuid.UUID):
    """Lets the widget restore a chat after a page reload. The id is a random UUID known only to that browser."""
    if request.method == "OPTIONS":
        return _cors(request, HttpResponse(status=204))
    conversation = get_object_or_404(Conversation, pk=pk)
    if not _origin_ok(request, conversation.site):
        return _error(request, "Not allowed.", 403)
    return _json(request, _serialize(conversation))
