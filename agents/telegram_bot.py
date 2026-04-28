# =============================================================================
# agents/telegram_bot.py — Inbound do segundo cérebro via Telegram
# =============================================================================
# Implementação long-poll usando HTTP puro (sem dependência nova):
#   - getUpdates com offset persistido no Redis
#   - sendMessage com parseMode HTML
#   - comandos curtos para forçar categoria ou apenas deixar o classificador decidir
#
# Deploy: roda como SERVICE separado no Railway (Procfile.worker).
# Entry point: `python -m agents.telegram_bot` (bloqueia no loop de long-poll).
# =============================================================================

from __future__ import annotations

import os
import sys
import time
from typing import Any, Optional

import requests


from config import (  # noqa: E402
    TELEGRAM_ALLOWED_CHAT_IDS,
    TELEGRAM_BOT_TOKEN,
)
from core import memory, notifier  # noqa: E402

AGENT_NAME = "telegram_bot"
_API_BASE = "https://api.telegram.org"
_OFFSET_KEY = "telegram:last_update_id"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _api(method: str, **params: Any) -> dict:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não configurada.")
    url = f"{_API_BASE}/bot{TELEGRAM_BOT_TOKEN}/{method}"
    resp = requests.post(url, json=params, timeout=65)
    if not resp.ok:
        raise RuntimeError(f"Telegram {resp.status_code}: {resp.text[:300]}")
    payload = resp.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error: {payload}")
    return payload["result"]


def _send(chat_id: int, text: str, reply_to: Optional[int] = None) -> None:
    try:
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text[:4000],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_to is not None:
            params["reply_to_message_id"] = reply_to
        _api("sendMessage", **params)
    except Exception as exc:
        notifier.warning(f"Falha ao enviar msg Telegram: {exc}", AGENT_NAME)


# ---------------------------------------------------------------------------
# Autorização
# ---------------------------------------------------------------------------


def _is_authorized(chat_id: int) -> bool:
    if not TELEGRAM_ALLOWED_CHAT_IDS:
        return True  # sem whitelist = libera
    return chat_id in TELEGRAM_ALLOWED_CHAT_IDS


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------

_FORCED_ACTION = {
    "/log": "capture_log",
    "/task": "capture_task",
    "/t": "capture_task",
    "/decidir": "capture_decision",
    "/decide": "capture_decision",
    "/proj": "capture_project",
    "/project": "capture_project",
    "/int": "capture_integration",
    "/integration": "capture_integration",
}

_HELP = (
    "<b>NEØ Capture Bot</b>\n\n"
    "Mande qualquer texto que eu classifico e salvo no lugar certo.\n\n"
    "<b>Atalhos p/ forçar categoria:</b>\n"
    "• /log &lt;texto&gt; → 📝 Work Log\n"
    "• /task &lt;texto&gt; → ✅ Tarefas\n"
    "• /decidir &lt;texto&gt; → 🧠 Decisões\n"
    "• /proj &lt;texto&gt; → 📁 Projetos\n"
    "• /int &lt;texto&gt; → 📋 Integrations\n\n"
    "<b>Utilitários:</b>\n"
    "• /status → estado do sistema\n"
    "• /whoami → seu chat_id (p/ liberar no allowlist)\n"
    "• /help → esta mensagem"
)


def _handle_command(cmd: str, rest: str, chat_id: int, message_id: int) -> None:
    cmd_lower = cmd.lower().split("@", 1)[0]  # remove @botname

    if cmd_lower in ("/start", "/help"):
        _send(chat_id, _HELP, reply_to=message_id)
        return

    if cmd_lower == "/whoami":
        _send(chat_id, f"<code>chat_id = {chat_id}</code>", reply_to=message_id)
        return

    if cmd_lower == "/status":
        try:
            from core.openai_utils import describe_chain
            chain = ", ".join(describe_chain())
        except Exception as exc:
            chain = f"(erro: {exc})"
        _send(
            chat_id,
            f"<b>NEØ status</b>\nLLM: <code>{chain}</code>\nCapture: on",
            reply_to=message_id,
        )
        return

    if cmd_lower in _FORCED_ACTION:
        if not rest.strip():
            _send(chat_id, f"Uso: <code>{cmd_lower} &lt;texto&gt;</code>", reply_to=message_id)
            return
        _run_capture(rest, chat_id, message_id, forced_action=_FORCED_ACTION[cmd_lower])
        return

    _send(chat_id, f"Comando desconhecido: <code>{cmd_lower}</code>\n{_HELP}", reply_to=message_id)


# ---------------------------------------------------------------------------
# Captura
# ---------------------------------------------------------------------------


def _run_capture(text: str, chat_id: int, message_id: int, forced_action: Optional[str] = None) -> None:
    from agents import capture_agent

    payload: dict[str, Any] = {"text": text, "source": f"telegram:{chat_id}"}
    if forced_action:
        payload["action"] = forced_action
    else:
        payload["action"] = "capture"

    try:
        resp = capture_agent.handle_handoff(payload)
    except Exception as exc:
        _send(chat_id, f"❌ Erro interno: <code>{exc}</code>", reply_to=message_id)
        return

    if resp.get("status") != "success":
        err = resp.get("result")
        _send(chat_id, f"❌ Falhou: <code>{err}</code>", reply_to=message_id)
        return

    r = resp["result"]
    title = r.get("title", "(sem título)")
    dest = r.get("destination", r.get("category", "?"))
    url = r.get("notion_url", "")
    msg = f"✅ <b>{dest}</b>\n<i>{title}</i>"
    if url:
        msg += f'\n<a href="{url}">abrir no Notion →</a>'
    _send(chat_id, msg, reply_to=message_id)


# ---------------------------------------------------------------------------
# Loop de long-poll
# ---------------------------------------------------------------------------


def _process_update(update: dict) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return

    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    message_id = msg.get("message_id")
    text = msg.get("text") or msg.get("caption") or ""

    if chat_id is None or not text:
        return

    if not _is_authorized(chat_id):
        _send(chat_id, "⛔ Não autorizado. Peça liberação no allowlist.", reply_to=message_id)
        notifier.warning(f"Rejeitado chat_id {chat_id}", AGENT_NAME)
        return

    if text.startswith("/"):
        parts = text.split(None, 1)
        cmd = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        _handle_command(cmd, rest, chat_id, message_id)
        return

    # Texto livre → classifier
    _run_capture(text, chat_id, message_id)


def _get_offset() -> int:
    try:
        raw = memory.get_state(_OFFSET_KEY, 0)
        return int(raw or 0)
    except Exception:
        return 0


def _set_offset(offset: int) -> None:
    try:
        memory.set_state(_OFFSET_KEY, offset)
    except Exception as exc:
        notifier.warning(f"Falha ao persistir offset: {exc}", AGENT_NAME)


def run() -> None:
    if not TELEGRAM_BOT_TOKEN:
        notifier.error("TELEGRAM_BOT_TOKEN não configurada — bot não inicia.", AGENT_NAME)
        raise SystemExit(1)

    try:
        me = _api("getMe")
        notifier.success(f"Bot online: @{me.get('username')}", AGENT_NAME)
    except Exception as exc:
        notifier.error(f"getMe falhou: {exc}", AGENT_NAME)

    offset = _get_offset()
    while True:
        try:
            updates = _api(
                "getUpdates",
                offset=offset + 1 if offset else None,
                timeout=50,
                allowed_updates=["message", "edited_message"],
            )
        except Exception as exc:
            notifier.warning(f"getUpdates falhou ({exc}) — retry em 5s", AGENT_NAME)
            time.sleep(5)
            continue

        if not isinstance(updates, list):
            time.sleep(1)
            continue

        for update in updates:
            try:
                _process_update(update)
            except Exception as exc:
                notifier.error(f"Erro ao processar update: {exc}", AGENT_NAME)
            update_id = update.get("update_id", 0)
            if update_id > offset:
                offset = update_id
                _set_offset(offset)


if __name__ == "__main__":
    run()
