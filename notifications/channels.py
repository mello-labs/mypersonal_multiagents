# =============================================================================
# notifications/channels.py — Canais de notificação externos (push, voice)
# =============================================================================
# Contém adaptadores para canais externos que enviam mensagens para o usuário
# fora do terminal: macOS Notification Center, Alexa via Voice Monkey e
# futuramente Telegram.
#
# core/notifier.py mantém apenas output de terminal e logging.
# Agentes que precisam de push importam daqui.

import os
import sys


def mac_push(title: str, message: str, sound: bool = False) -> None:
    """Envia notificação nativa macOS via AppleScript."""
    import subprocess
    from core import notifier

    if sys.platform != "darwin":
        notifier.warning(
            "mac_push ignorado: notificações nativas só funcionam em macOS.",
            "channels",
        )
        return

    sound_line = ' sound name "Sosumi"' if sound else ""
    script = f'display notification "{message}" with title "{title}"{sound_line}'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            stderr = (result.stderr or b"").decode("utf-8", errors="ignore").strip()
            notifier.warning(
                f"mac_push falhou via osascript (code={result.returncode}): "
                f"{stderr or 'sem stderr'}",
                "channels",
            )
    except Exception as exc:
        notifier.warning(f"mac_push falhou: {exc}", "channels")


def alexa_announce(message: str) -> None:
    """Dispara anúncio na Alexa exclusivamente via Voice Monkey."""
    import requests
    from core import notifier

    vm_token = os.getenv("VOICE_MONKEY_TOKEN", "")
    if vm_token:
        try:
            device = os.getenv("VOICE_MONKEY_DEVICE", "eco-room")
            response = requests.post(
                "https://api-v2.voicemonkey.io/announcement",
                headers=(
                    {"Authorization": f"Bearer {vm_token}"}
                    if not vm_token.startswith("Bearer")
                    else {"Authorization": vm_token}
                ),
                json={"device": device, "text": message},
                timeout=5,
            )
            if not response.ok:
                notifier.warning(
                    f"Voice Monkey falhou ({response.status_code}): "
                    f"{response.text[:160] or 'sem resposta'}",
                    "channels",
                )
        except Exception as exc:
            notifier.warning(f"Voice Monkey falhou: {exc}", "channels")
        return

    notifier.warning(
        "Alexa indisponível: configure VOICE_MONKEY_TOKEN no ambiente.",
        "channels",
    )
