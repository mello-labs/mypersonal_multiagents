"""
agents/ecosystem_monitor.py — Fase 1: Órbita externa do kernel

Observa o ecossistema externo de NEØ MELLØ e produz sinais acionáveis:
  - GitHub: atividade por org, repos estagnados, issues abertas
  - Railway: health check de serviços via HTTP
  - On-chain: NEOFLW via DexScreener

Saídas:
  - health_check()   → dict com status de cada camada
  - daily_report()   → string formatada para leitura humana
  - run()            → executa tudo e persiste no Redis

Não faz:
  - alterar agenda íntima automaticamente
  - publicar nada diretamente
  - chamar focus_guard ou life_guard
"""

from __future__ import annotations

import time
import json
import datetime
import requests
import redis
from typing import Any

from config import GITHUB_TOKEN, RAILWAY_TOKEN, RAILWAY_WORKSPACE_ID
from core import memory, notifier

AGENT_NAME = "ecosystem_monitor"

GITHUB_ORGS = [
    "NEO-PROTOCOL",
    "NEO-FlowOFF",
    "flowpay-system",
    "neo-smart-factory",
    "FluxxDAO",
    "wodxpro",
]

# Repos prioritários para monitorar dentro de cada org
PRIORITY_REPOS = {
    "NEO-PROTOCOL": [
        "neobot",
        "neo-dashboard",
        "neo-mello-eth",
        "mio-system",
        "neoflw-base-landing",
    ],
    "NEO-FlowOFF": [
        "neo-control-plane",
        "neo-content-dashboard",
        "neo-content-accounts-api",
    ],
    "flowpay-system": ["flowpay-api", "flowpay-app"],
    "neo-smart-factory": ["smart-core", "smart-nft", "smart-cli"],
    "FluxxDAO": ["fluxx-backend", "fluxx-landing"],
    "wodxpro": ["wod-protocol", "wod-eth", "wod-x-pro"],
}

# Serviços Railway: nome → URL de health check
RAILWAY_SERVICES: dict[str, dict[str, str]] = {
    "neo-dashboard": {
        "url": "https://mypersonal-multiagents.up.railway.app/health",
        "priority": "P0",
    },
    "neo-mello-eth": {
        "url": "https://neomelloeth.up.railway.app/",
        "priority": "P0",
    },
    "neo-mello-eth-redis": {
        "url": "https://redis-neomello.up.railway.app/",
        "priority": "P0",
    },
    "mio-system": {
        "url": "https://mio-system-production.up.railway.app/health",
        "priority": "P1",
    },
    "neo-nexus": {
        "url": "https://neo-nexus-production.up.railway.app/health",
        "priority": "P1",
    },
    "neobot": {
        "url": "https://neobot-production.up.railway.app/health",
        "priority": "P0",
    },
}

# NEOFLW on Base
NEOFLW_CONTRACT = "0x41F4ff3d45DED9C1332e4908F637B75fe83F5d6B"
NEOFLW_CHAIN = "base"

# Thresholds
STALE_HOURS = 72  # repo sem push → sinalizar
ISSUE_WARN = 20  # issues abertas → warn
PRICE_DROP_PCT = 15  # queda de preço → alert
LIQUIDITY_MIN = 1000  # liquidez mínima USD
VOLUME_MIN = 500  # volume 24h mínimo USD

# Redis TTL
REDIS_TTL_SECONDS = 86400  # 24h


# ─── Helpers HTTP ──────────────────


def _get(
    url: str, headers: dict | None = None, timeout: int = 8
) -> dict | None:
    try:
        resp = requests.get(url, headers=headers or {}, timeout=timeout)
        if resp.ok:
            try:
                return resp.json()
            except ValueError:
                return {"_raw_status": resp.status_code, "_ok": True}
        return {"_error": resp.status_code}
    except requests.exceptions.RequestException as exc:
        return {"_exception": str(exc)}


def _github_headers() -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h


# ─── GitHub ──────────────────────────────────────────────────────────────────


def _hours_since(iso_str: str | None) -> float | None:
    if not iso_str:
        return None
    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        return (now - dt).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


def check_github() -> dict:
    """Verifica atividade GitHub em todas as orgs."""
    result: dict[str, Any] = {}
    headers = _github_headers()

    for org in GITHUB_ORGS:
        org_result: dict[str, Any] = {
            "status": "ok",
            "repos_active_24h": 0,
            "repos_stale": [],
            "open_issues": 0,
            "repos": {},
        }

        # Busca repos da org
        repos_data = _get(
            f"https://api.github.com/orgs/{org}/repos?per_page=30&sort=pushed",
            headers=headers,
        )

        if (
            not repos_data
            or "_error" in repos_data
            or "_exception" in repos_data
        ):
            org_result["status"] = "error"
            org_result["error"] = str(repos_data)
            result[org] = org_result
            continue

        if not isinstance(repos_data, list):
            org_result["status"] = "error"
            result[org] = org_result
            continue

        for repo in repos_data:
            name = repo.get("name", "")
            pushed = repo.get("pushed_at")
            issues = repo.get("open_issues_count", 0)
            hours = _hours_since(pushed)

            org_result["open_issues"] += issues

            repo_info = {
                "pushed_at": pushed,
                "hours_since_push": round(hours, 1) if hours is not None else None,
                "open_issues": issues,
                "stale": (hours is not None and hours > STALE_HOURS),
                "priority": name in PRIORITY_REPOS.get(org, []),
            }
            org_result["repos"][name] = repo_info

            if hours is not None and hours <= 24:
                org_result["repos_active_24h"] += 1

            if (
                hours is not None
                and hours > STALE_HOURS
                and name in PRIORITY_REPOS.get(org, [])
            ):
                org_result["repos_stale"].append(name)

        if org_result["repos_stale"]:
            org_result["status"] = "warn"
        if org_result["open_issues"] >= ISSUE_WARN:
            org_result["status"] = "warn"

        result[org] = org_result

    return result


# ─── Railway ─────────────────────────────────────────────────────────────────


def check_railway() -> dict:
    """Verifica saúde dos serviços Railway via HTTP health check."""
    result: dict[str, Any] = {}

    for service, cfg in RAILWAY_SERVICES.items():
        url = cfg["url"]
        priority = cfg.get("priority", "P2")
        start = time.time()

        try:
            resp = requests.get(url, timeout=8, allow_redirects=True)
            elapsed_ms = round((time.time() - start) * 1000)
            status_code = resp.status_code

            if status_code == 200:
                status = "ok"
                try:
                    body = resp.json()
                    svc_status = body.get("status", "ok")
                    if str(svc_status).lower() not in (
                        "ok",
                        "up",
                        "healthy",
                        "true",
                    ):
                        status = "warn"
                except ValueError:
                    pass
            elif status_code in (301, 302, 307, 308):
                status = "ok"  # redirect = vivo
            elif status_code == 404:
                status = "warn"  # existe mas endpoint não encontrado
            elif status_code >= 500:
                status = "fail"
            else:
                status = "warn"

            result[service] = {
                "status": status,
                "http_code": status_code,
                "response_ms": elapsed_ms,
                "priority": priority,
                "url": url,
            }

        except requests.exceptions.Timeout:
            result[service] = {
                "status": "fail",
                "error": "timeout",
                "priority": priority,
                "url": url,
            }
        except Exception as exc:
            result[service] = {
                "status": "fail",
                "error": str(exc),
                "priority": priority,
                "url": url,
            }

    return result


# ─── On-chain / DexScreener ───────────────────────────────────────────────────


def check_onchain() -> dict:
    """Verifica NEOFLW via DexScreener."""
    result: dict[str, Any] = {
        "NEOFLW": {
            "status": "unknown",
            "contract": NEOFLW_CONTRACT,
            "chain": NEOFLW_CHAIN,
        }
    }

    # Tenta endpoint de pairs por contrato
    data = _get(
        f"https://api.dexscreener.com/latest/dex/tokens/{NEOFLW_CONTRACT}",
        timeout=10,
    )

    pairs = None
    if data and isinstance(data.get("pairs"), list) and data["pairs"]:
        pairs = data["pairs"]
    else:
        # Tenta endpoint alternativo
        data2 = _get(
            f"https://api.dexscreener.com/token-pairs/v1/{NEOFLW_CHAIN}/{NEOFLW_CONTRACT}",
            timeout=10,
        )
        if data2 and isinstance(data2, list) and data2:
            pairs = data2

    if not pairs:
        result["NEOFLW"]["status"] = "no_data"
        result["NEOFLW"][
            "note"
        ] = "Token sem liquidez ativa ou não indexado no DexScreener"
        return result

    # Usa o par com maior liquidez
    pairs_sorted = sorted(
        pairs,
        key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0),
        reverse=True,
    )
    pair = pairs_sorted[0]

    price_usd = pair.get("priceUsd")
    liquidity_usd = pair.get("liquidity", {}).get("usd", 0) or 0
    volume_24h = pair.get("volume", {}).get("h24", 0) or 0
    price_change_24h = pair.get("priceChange", {}).get("h24", 0) or 0
    dex_id = pair.get("dexId", "")
    pair_address = pair.get("pairAddress", "")

    # Avaliar status
    status = "ok"
    alerts = []

    if float(liquidity_usd) < LIQUIDITY_MIN:
        status = "warn"
        alerts.append(f"liquidez baixa: ${liquidity_usd:.0f}")

    if float(volume_24h) < VOLUME_MIN:
        alerts.append(f"volume 24h baixo: ${volume_24h:.0f}")

    if float(price_change_24h) <= -PRICE_DROP_PCT:
        status = "fail"
        alerts.append(f"queda de preço 24h: {price_change_24h:.1f}%")

    result["NEOFLW"] = {
        "status": status,
        "price_usd": price_usd,
        "liquidity_usd": round(float(liquidity_usd), 2),
        "volume_24h_usd": round(float(volume_24h), 2),
        "price_change_24h_pct": round(float(price_change_24h), 2),
        "dex": dex_id,
        "pair_address": pair_address,
        "contract": NEOFLW_CONTRACT,
        "chain": NEOFLW_CHAIN,
        "alerts": alerts,
    }

    return result


# ─── Health Check ─────────────────────────────────────────────────────────────


def health_check() -> dict:
    """Executa health check completo do ecossistema."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    notifier.info("Iniciando health check do ecossistema...", AGENT_NAME)

    github = check_github()
    railway = check_railway()
    onchain = check_onchain()

    # Contagens de status
    gh_orgs_total = len(github)
    gh_orgs_warn = sum(1 for v in github.values() if v.get("status") != "ok")
    gh_repos_active = sum(v.get("repos_active_24h", 0) for v in github.values())
    gh_stale = [r for v in github.values() for r in v.get("repos_stale", [])]

    rw_total = len(railway)
    rw_ok = sum(1 for v in railway.values() if v.get("status") == "ok")
    rw_warn = sum(1 for v in railway.values() if v.get("status") == "warn")
    rw_fail = sum(1 for v in railway.values() if v.get("status") == "fail")

    # Status global
    global_status = "ok"
    if rw_fail > 0 or gh_orgs_warn > 0:
        global_status = "warn"
    if rw_fail >= 2:
        global_status = "fail"
    if any(
        railway.get(s, {}).get("status") == "fail"
        for s in ["neo-dashboard", "neo-mello-eth"]
    ):
        global_status = "fail"

    result = {
        "timestamp": now,
        "status": global_status,
        "summary": {
            "github": {
                "orgs_total": gh_orgs_total,
                "orgs_warn": gh_orgs_warn,
                "repos_active_24h": gh_repos_active,
                "repos_stale_priority": gh_stale,
            },
            "railway": {
                "services_total": rw_total,
                "services_ok": rw_ok,
                "services_warn": rw_warn,
                "services_fail": rw_fail,
            },
            "onchain": {
                "NEOFLW": onchain.get("NEOFLW", {}).get("status", "unknown"),
            },
        },
        "github": github,
        "railway": railway,
        "onchain": onchain,
    }

    # Persiste no Redis
    try:
        memory.set_state("ecosystem:health_check:latest", result)
        memory.set_state(f"ecosystem:health_check:{now[:10]}", result)
    except requests.exceptions.RequestException as exc:
        notifier.warning(
            f"Falha ao persistir health check no Redis: {exc}", AGENT_NAME
        )

    notifier.info(
        f"Health check concluído: {global_status.upper()} "
        f"| Railway {rw_ok}/{rw_total} ok "
        f"| GitHub {gh_repos_active} repos ativos 24h",
        AGENT_NAME,
    )

    return result


# ─── Daily Report ─────────────────────────────────────────────────────────────


def _status_icon(status: str) -> str:
    return {
        "ok": "OK  ",
        "warn": "WARN",
        "fail": "FAIL",
        "unknown": "???",
        "no_data": "----",
    }.get(status, "????")


def daily_report(data: dict | None = None) -> str:
    """Gera relatório diário legível. Usa dados do health_check se não fornecidos."""
    if data is None:
        # Tenta carregar do Redis
        try:
            r = memory.get_redis()
            raw = r.get("ecosystem:health_check:latest")
            if raw:
                data = json.loads(raw)
        except (redis.RedisError, json.JSONDecodeError):
            pass

    if data is None:
        data = health_check()

    today = data.get("timestamp", "")[:10]
    summary = data.get("summary", {})
    github = data.get("github", {})
    railway = data.get("railway", {})
    onchain = data.get("onchain", {})
    global_status = data.get("status", "?")

    lines: list[str] = []
    lines.append(f"NEØ Ecosystem — {today}")
    lines.append(f"{_status_icon(global_status)} Status global")
    lines.append("")

    # GitHub
    gh_s = summary.get("github", {})
    lines.append("GitHub")
    lines.append(f"  {gh_s.get('repos_active_24h', 0)} repos ativos (24h)")
    stale = gh_s.get("repos_stale_priority", [])
    if stale:
        lines.append(f"  WARN repos prioritários estagnados: {', '.join(stale)}")
    # Por org
    for org, info in github.items():
        active = info.get("repos_active_24h", 0)
        issues = info.get("open_issues", 0)
        status = info.get("status", "ok")
        icon = _status_icon(status)
        lines.append(f"  {icon} {org}: {active} ativos / {issues} issues abertas")

    lines.append("")

    # Railway
    rw_s = summary.get("railway", {})
    lines.append("Infra (Railway)")
    lines.append(
        f"  {rw_s.get('services_ok', 0)}/{rw_s.get('services_total', 0)} serviços ok"
    )
    for svc, info in railway.items():
        status = info.get("status", "?")
        icon = _status_icon(status)
        code = info.get("http_code", info.get("error", "?"))
        ms = info.get("response_ms", "")
        ms_str = f" ({ms}ms)" if ms else ""
        prio = info.get("priority", "")
        lines.append(f"  {icon} {svc} [{prio}]: {code}{ms_str}")

    lines.append("")

    # On-chain
    neoflw = onchain.get("NEOFLW", {})
    neoflw_status = neoflw.get("status", "unknown")
    lines.append("On-chain")
    if neoflw_status == "no_data":
        lines.append("  ---- NEOFLW: sem dados no Coingecko")
    else:
        price = neoflw.get("price_usd", "?")
        vol = neoflw.get("volume_24h_usd", "?")
        liq = neoflw.get("liquidity_usd", "?")
        chg = neoflw.get("price_change_24h_pct", "?")
        icon = _status_icon(neoflw_status)
        lines.append(
            f"  {icon} NEOFLW: ${price} | vol: ${vol} | liq: ${liq} | Δ: {chg}%"
        )
        for alert in neoflw.get("alerts", []):
            lines.append(f"       ⚠ {alert}")

    lines.append("")

    # Ações sugeridas
    actions: list[str] = []

    fail_svcs = [s for s, v in railway.items() if v.get("status") == "fail"]
    warn_svcs = [s for s, v in railway.items() if v.get("status") == "warn"]
    if fail_svcs:
        msg = f"verificar serviço(s) com falha: {', '.join(fail_svcs)}"
        actions.append(msg)
    if warn_svcs:
        actions.append(f"investigar: {', '.join(warn_svcs)}")
    if stale:
        actions.append(f"revisar repos estagnados: {', '.join(stale)}")
    if neoflw.get("alerts"):
        actions.append("monitorar NEOFLW — alertas ativos")

    if actions:
        lines.append("Ação sugerida")
        for a in actions:
            lines.append(f"  - {a}")
    else:
        lines.append("Sem ações urgentes.")

    report = "\n".join(lines)

    # Persiste relatório no Redis
    try:
        memory.set_state("ecosystem:daily_report:latest", report)
        memory.set_state(f"ecosystem:daily_report:{today}", report)
    except Exception as exc:
        notifier.warning(
            f"Falha ao persistir relatório no Redis: {exc}", AGENT_NAME
        )

    return report


# ─── Entry point ───────────────────────


def run() -> str:
    """Executa health check completo e devolve relatório."""
    data = health_check()
    report = daily_report(data)

    # Alerta imediato apenas para eventos graves
    rw = data.get("railway", {})
    p0_fail = [
        s
        for s, v in rw.items()
        if v.get("status") == "fail" and v.get("priority") == "P0"
    ]
    if p0_fail:
        msg = f"[ECOSYSTEM] Serviço P0 com falha: {', '.join(p0_fail)}"
        notifier.mac_push("NEO Ecosystem FAIL", msg, sound=True)

    return report
