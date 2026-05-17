import re
from types import SimpleNamespace
import subprocess


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_notify_outputs_expected_line(capsys):
    from core import notifier

    notifier.notify("Mensagem ok", notifier.NotifLevel.SUCCESS, agent="tester", also_log=False)

    output = _strip_ansi(capsys.readouterr().out)
    assert "Mensagem ok" in output
    assert "[OK]" in output
    assert "(tester)" in output


def test_print_table_renders_headers_and_rows(capsys):
    from core import notifier

    notifier.print_table(["Coluna A", "Coluna B"], [["A1", "B1"]], title="Resumo")

    output = _strip_ansi(capsys.readouterr().out)
    assert "Resumo" in output
    assert "Coluna A" in output
    assert "A1" in output


def test_chat_completions_fallback(monkeypatch):
    from core import openai_utils

    class FakeProvider:
        def __init__(self, side_effects):
            self.side_effects = list(side_effects)
            self.calls = []

        def complete(self, model=None, **kwargs):
            self.calls.append({"model": model, **kwargs})
            result = self.side_effects.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
    )
    fake_cloud = FakeProvider([RuntimeError("primary failed"), response])

    warnings: list[str] = []
    errors: list[str] = []

    # Cria uma chain de teste (API: cloud_primary / cloud_fallback)
    test_chain = openai_utils.LLMChain(
        azure=None,
        cloud=fake_cloud,
        cloud_primary="primary",
        cloud_fallback="fallback",
        local=None,
    )

    monkeypatch.setattr(openai_utils, "_chain", test_chain)
    monkeypatch.setattr(
        openai_utils.notifier, "warning", lambda msg, *_: warnings.append(msg)
    )
    monkeypatch.setattr(
        openai_utils.notifier, "error", lambda msg, *_: errors.append(msg)
    )

    result = openai_utils.chat_completions(messages=[{"role": "user", "content": "Oi"}])

    assert result.choices[0].message.content == "ok"
    assert fake_cloud.calls[0]["model"] == "primary"
    assert fake_cloud.calls[1]["model"] == "fallback"
    assert len(warnings) == 1
    assert errors == []


def test_mac_push_warns_outside_macos(monkeypatch):
    from core import notifier

    warnings: list[str] = []
    monkeypatch.setattr(notifier.sys, "platform", "linux")
    monkeypatch.setattr(notifier, "warning", lambda msg, *_: warnings.append(msg))

    notifier.mac_push("Teste", "Mensagem")

    assert warnings == ["mac_push ignorado: notificações nativas só funcionam em macOS."]


def test_mac_push_warns_when_osascript_fails(monkeypatch):
    from core import notifier

    warnings: list[str] = []
    monkeypatch.setattr(notifier.sys, "platform", "darwin")
    monkeypatch.setattr(notifier, "warning", lambda msg, *_: warnings.append(msg))

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stderr=b"boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    notifier.mac_push("Teste", "Mensagem")

    assert warnings == ["mac_push falhou via osascript (code=1): boom"]


def test_alexa_announce_warns_without_provider(monkeypatch):
    from core import notifier

    warnings: list[str] = []
    monkeypatch.delenv("VOICE_MONKEY_TOKEN", raising=False)
    monkeypatch.setattr(notifier, "warning", lambda msg, *_: warnings.append(msg))

    notifier.alexa_announce("Mensagem")

    assert warnings == [
        "Alexa indisponível: configure VOICE_MONKEY_TOKEN no ambiente."
    ]
