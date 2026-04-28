# =============================================================================
# agents/github_projects.py — GitHub Projects v2 → Notion (Command Center TASK)
# =============================================================================
# - discover: lê manifests locais (neomello/<org>/manifests) e compara com config
# - sync: GraphQL → cria/atualiza páginas em NOTION_DB_TAREFAS; mapa issue↔Notion em Redis
#
# Direção única: GitHub → Notion. Idempotência por owner/repo#number.

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

import requests


from config import (  # noqa: E402
    GITHUB_NOTION_PRIORITY_DEFAULT,
    GITHUB_NOTION_STATUS_CLOSED,
    GITHUB_NOTION_STATUS_OPEN,
    GITHUB_PROJECTS,
    GITHUB_TOKEN,
    NEOMELLO_WORKSPACES_ROOT,
    NOTION_API_BASE,
    NOTION_API_VERSION,
    NOTION_DB_TAREFAS,
    NOTION_TOKEN,
)
from core import memory, notifier  # noqa: E402

AGENT_NAME = "github_projects"

GITHUB_GRAPHQL = "https://api.github.com/graphql"

STATE_MAP_KEY = "github_projects:issue_notion_map"

# Selects do DB "Tarefas & Ações" (NEØ Command Center) — ajuste via env se o Notion mudar
_STATUS_OPEN = GITHUB_NOTION_STATUS_OPEN
_STATUS_CLOSED = GITHUB_NOTION_STATUS_CLOSED
_PRIORITY_DEFAULT = GITHUB_NOTION_PRIORITY_DEFAULT

# Raiz dos workspaces locais (manifests). Vazio = discover não escaneia disco.

_URL_PROJECT = re.compile(
    r"github\.com/orgs/([^/]+)/projects/(\d+)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# GraphQL GitHub
# ---------------------------------------------------------------------------


def _graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN não configurada.")
    r = requests.post(
        GITHUB_GRAPHQL,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"query": query, "variables": variables},
        timeout=60,
    )
    data = r.json()
    if r.status_code != 200:
        raise RuntimeError(f"GraphQL HTTP {r.status_code}: {data}")
    if data.get("errors"):
        raise RuntimeError(f"GraphQL: {data['errors']}")
    return data.get("data") or {}


PROJECT_ITEMS_QUERY = """
query ProjectItems($org: String!, $num: Int!, $cursor: String) {
  organization(login: $org) {
    projectV2(number: $num) {
      title
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          content {
            __typename
            ... on Issue {
              number
              title
              url
              state
              body
              repository { nameWithOwner }
            }
            ... on PullRequest {
              number
              title
              url
              state
              body
              repository { nameWithOwner }
            }
          }
        }
      }
    }
  }
}
"""


def fetch_project_items(org: str, project_number: int) -> list[dict[str, Any]]:
    """Retorna lista de dicts normalizados: issue_key, title, url, state, body, repo."""
    out: list[dict[str, Any]] = []
    cursor: Optional[str] = None
    while True:
        data = _graphql(
            PROJECT_ITEMS_QUERY,
            {"org": org, "num": project_number, "cursor": cursor},
        )
        org_data = data.get("organization") or {}
        pv = org_data.get("projectV2")
        if not pv:
            notifier.warning(
                f"Sem projectV2 para org={org!r} number={project_number} "
                "(org inexistente, token sem escopo, ou número errado).",
                AGENT_NAME,
            )
            return out
        items = pv.get("items") or {}
        for node in items.get("nodes") or []:
            content = node.get("content")
            if not content:
                continue
            tn = content.get("__typename")
            if tn not in ("Issue", "PullRequest"):
                continue
            repo = (content.get("repository") or {}).get("nameWithOwner")
            num = content.get("number")
            if not repo or num is None:
                continue
            key = f"{repo}#{num}"
            out.append(
                {
                    "issue_key": key,
                    "title": content.get("title") or "",
                    "url": content.get("url") or "",
                    "state": (content.get("state") or "").upper(),
                    "body": content.get("body") or "",
                    "repo": repo,
                    "typename": tn,
                    "project_title": pv.get("title") or "",
                }
            )
        pi = items.get("pageInfo") or {}
        if not pi.get("hasNextPage"):
            break
        cursor = pi.get("endCursor")
    return out


# ---------------------------------------------------------------------------
# Discover manifests locais
# ---------------------------------------------------------------------------


def _extract_urls_from_json(obj: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            urls.extend(_extract_urls_from_json(v))
    elif isinstance(obj, list):
        for v in obj:
            urls.extend(_extract_urls_from_json(v))
    elif isinstance(obj, str) and "github.com/orgs/" in obj:
        urls.append(obj)
    return urls


def discover_manifest_project_urls(root: Path) -> list[dict[str, Any]]:
    """
    Percorre root/<org>/manifests/{workspace,integrations}.json e extrai URLs
    de GitHub Org Projects (projects/N).
    """
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows

    for org_dir in sorted(root.iterdir()):
        if not org_dir.is_dir():
            continue
        manifests = org_dir / "manifests"
        if not manifests.is_dir():
            continue
        for name in ("workspace.json", "integrations.json"):
            p = manifests / name
            if not p.is_file():
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for url in _extract_urls_from_json(data):
                m = _URL_PROJECT.search(url)
                if not m:
                    continue
                gh_org, num_s = m.group(1), m.group(2)
                rows.append(
                    {
                        "path": str(p),
                        "manifest_org_dir": org_dir.name,
                        "github_org": gh_org,
                        "project_number": int(num_s),
                        "url": url,
                    }
                )
    return rows


def discover_compare_with_config(root_override: Optional[Path] = None) -> str:
    """Retorna texto formatado: manifest vs GITHUB_PROJECTS em config."""
    root = root_override or Path(NEOMELLO_WORKSPACES_ROOT.strip() or "")
    lines: list[str] = []
    if not root.is_dir():
        lines.append(
            f"NEOMELLO_WORKSPACES_ROOT não é diretório válido: {root}\n"
            "Defina NEOMELLO_WORKSPACES_ROOT ou deixe vazio para pular discover.\n"
        )
        lines.append("── Config (GITHUB_PROJECTS) ──")
        for o, n in GITHUB_PROJECTS.items():
            lines.append(f"  {o} → project {n}")
        return "\n".join(lines)

    found = discover_manifest_project_urls(root)
    lines.append(f"Manifest roots scanned: {root} ({len(found)} URL(s) com projects/)\n")

    by_org: dict[str, set[int]] = {}
    for row in found:
        go = row["github_org"]
        by_org.setdefault(go, set()).add(row["project_number"])

    lines.append("── Manifests (GitHub org → números vistos) ──")
    for o in sorted(by_org.keys()):
        nums = ", ".join(str(x) for x in sorted(by_org[o]))
        lines.append(f"  {o} → {nums}")

    lines.append("── Config (GITHUB_PROJECTS / env) ──")
    mismatches = 0
    for o, n in sorted(GITHUB_PROJECTS.items()):
        manifest_nums = by_org.get(o, set())
        mark = ""
        if manifest_nums and n not in manifest_nums:
            mark = "  [!] mismatch vs manifests"
            mismatches += 1
        elif not manifest_nums:
            mark = "  (sem manifest para esta org)"
        lines.append(f"  {o} → project {n}{mark}")

    if mismatches:
        lines.append(
            "\nAjuste GH_PROJECT_* no .env para bater com o board real, "
            "ou atualize os manifests."
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Notion — Command Center Tarefas (igual capture_agent.create_task)
# ---------------------------------------------------------------------------


def _notion_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


def _normalize_notion_db_id(raw: str) -> str:
    s = raw.replace("-", "").strip()
    if len(s) == 32:
        return f"{s[0:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:32]}"
    return raw.strip()


def notion_tarefas_diagnostic() -> str:
    """
    Lê schema + amostra de páginas de NOTION_DB_TAREFAS e tamanho do mapa Redis.
    Use para confirmar integration, nomes de propriedades e se há linhas criadas.
    """
    lines: list[str] = []
    if not NOTION_TOKEN or not NOTION_DB_TAREFAS:
        return "NOTION_TOKEN ou NOTION_DB_TAREFAS vazio no config.\n"

    db_id = _normalize_notion_db_id(NOTION_DB_TAREFAS)

    url = f"{NOTION_API_BASE}/databases/{db_id}"
    r = requests.get(url, headers=_notion_headers(), timeout=20)
    if not r.ok:
        lines.append(
            f"GET database falhou ({r.status_code}): {r.text[:500]}\n"
            "→ Confirma que a integration tem acesso ao database (Share → invite)."
        )
        return "\n".join(lines)

    data = r.json()
    title_arr = data.get("title", [])
    db_title = ""
    if title_arr and isinstance(title_arr[0], dict):
        db_title = title_arr[0].get("plain_text", "") or ""
    lines.append(f"Database OK: {db_title or '(sem título)'}")
    lines.append(f"ID usado na API: {db_id}")

    props = data.get("properties", {})
    lines.append("\nPropriedades no Notion (sync espera: Tarefa, Descrição, Status, Prioridade):")
    for name, meta in sorted(props.items()):
        lines.append(f"  - {name!r} → {meta.get('type', '?')}")

    required = [
        ("Tarefa", "title"),
        ("Descrição", "rich_text"),
        ("Status", "select"),
        ("Prioridade", "select"),
    ]
    for name, want in required:
        if name not in props:
            lines.append(f"\n[!] Falta {name!r} — POST do sync falha 400.")
        elif props[name].get("type") != want:
            lines.append(
                f"\n[!] {name!r} é tipo {props[name].get('type')!r} (esperado {want!r})."
            )

    q = requests.post(
        f"{NOTION_API_BASE}/databases/{db_id}/query",
        headers=_notion_headers(),
        json={"page_size": 15},
        timeout=30,
    )
    if not q.ok:
        lines.append(f"\nQuery falhou ({q.status_code}): {q.text[:400]}")
        return "\n".join(lines)

    results = q.json().get("results", [])
    lines.append(f"\nPáginas neste database (amostra até 15): {len(results)}")
    for page in results:
        pid = page.get("id", "")
        pprops = page.get("properties", {})
        row_title = ""
        for _key, pv in pprops.items():
            if pv.get("type") == "title":
                t = pv.get("title") or []
                if t and isinstance(t[0], dict):
                    row_title = t[0].get("plain_text", "") or ""
                break
        if not row_title:
            row_title = "(sem title)"
        ell = "…" if len(row_title) > 78 else ""
        lines.append(f"  · {row_title[:78]}{ell}  id={pid[:8]}…")

    m = _get_issue_map()
    lines.append(f"\nMapa Redis github↔Notion: {len(m)} chaves.")
    return "\n".join(lines)


def _p_title(text: str) -> dict:
    return {"title": [{"text": {"content": text[:2000]}}]}


def _p_rich(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text[:2000]}}]}


def _p_select(name: str) -> dict:
    return {"select": {"name": name}}


def _issue_status_to_notion(state: str) -> str:
    s = (state or "").upper()
    if s in ("CLOSED", "MERGED"):
        return _STATUS_CLOSED
    return _STATUS_OPEN


def _description_block(
    body: str, url: str, org: str, project_title: str, typename: str
) -> str:
    excerpt = (body or "").strip()[:1500]
    parts = [
        excerpt if excerpt else "(sem descrição na issue/PR)",
        "",
        "---",
        url,
        f"GitHub {typename} · org workspace: {org} · project: {project_title}",
    ]
    return "\n".join(parts)


def _get_issue_map() -> dict[str, str]:
    raw = memory.get_state(STATE_MAP_KEY, default=None)
    if not raw or not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def _set_issue_map(m: dict[str, str]) -> None:
    memory.set_state(STATE_MAP_KEY, m)


def clear_issue_notion_map() -> None:
    """
    Apaga o mapa issue→página no Redis (`state:github_projects:issue_notion_map`).
    O próximo `sync` fará POST de novo para cada item (criadas>0).

    Nota: páginas antigas no Notion não são apagadas — podes ficar com
    duplicados se não limpares o DB manualmente.
    """
    memory.set_state(STATE_MAP_KEY, {})


def sync_org_to_notion(
    org: str,
    *,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Importa itens do Project v2 da org para NOTION_DB_TAREFAS.
    Retorna (criadas, atualizadas).
    """
    if not NOTION_TOKEN or not NOTION_DB_TAREFAS:
        raise RuntimeError("NOTION_TOKEN e NOTION_DB_TAREFAS são obrigatórios para sync.")

    num = GITHUB_PROJECTS.get(org)
    if num is None:
        raise RuntimeError(f"Org {org!r} não está em config GITHUB_PROJECTS.")

    items = fetch_project_items(org, num)
    issue_map = _get_issue_map()
    created = updated = 0

    for it in items:
        ikey = it["issue_key"]
        short = ikey.rsplit("/", 1)[-1]
        title = f"{short}: {it['title']}"
        desc = _description_block(
            it["body"],
            it["url"],
            org,
            it.get("project_title") or "",
            it.get("typename") or "Issue",
        )
        status = _issue_status_to_notion(it["state"])
        props: dict[str, Any] = {
            "Tarefa": _p_title(title),
            "Descrição": _p_rich(desc),
            "Status": _p_select(status),
            "Prioridade": _p_select(_PRIORITY_DEFAULT),
        }

        page_id = issue_map.get(ikey)

        if dry_run:
            action = "UPDATE" if page_id else "CREATE"
            notifier.info(f"[dry-run] {action} {ikey} → {status}", AGENT_NAME)
            continue

        if page_id:
            url = f"{NOTION_API_BASE}/pages/{page_id}"
            r = requests.patch(
                url,
                headers=_notion_headers(),
                json={"properties": props},
                timeout=30,
            )
            if not r.ok:
                notifier.warning(
                    f"PATCH falhou {ikey} ({r.status_code}): {r.text[:300]}",
                    AGENT_NAME,
                )
                continue
            updated += 1
        else:
            r = requests.post(
                f"{NOTION_API_BASE}/pages",
                headers=_notion_headers(),
                json={
                    "parent": {"database_id": _normalize_notion_db_id(NOTION_DB_TAREFAS)},
                    "properties": props,
                },
                timeout=30,
            )
            if not r.ok:
                notifier.warning(
                    f"POST falhou {ikey} ({r.status_code}): {r.text[:300]}",
                    AGENT_NAME,
                )
                continue
            new_id = r.json().get("id")
            if new_id:
                issue_map[ikey] = new_id
                created += 1

    if not dry_run:
        _set_issue_map(issue_map)

    return created, updated


def sync_all_orgs(*, dry_run: bool = False) -> dict[str, tuple[int, int]]:
    results: dict[str, tuple[int, int]] = {}
    for org in GITHUB_PROJECTS:
        try:
            c, u = sync_org_to_notion(org, dry_run=dry_run)
            results[org] = (c, u)
        except Exception as exc:
            notifier.error(f"{org}: {exc}", AGENT_NAME)
            results[org] = (0, 0)
    return results
