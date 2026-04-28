#!/usr/bin/env bash
# =============================================================================
# install_launchd.sh — Instala o Focus Guard como serviço launchd no macOS
# =============================================================================
# Uso: bash scripts/install_launchd.sh
# Para desinstalar: bash scripts/install_launchd.sh --uninstall

set -euo pipefail

LABEL="com.multiagentes.focusguard"
PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/${LABEL}.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT/.venv/bin/python3"

# ---- Desinstalação ----
if [[ "${1:-}" == "--uninstall" ]]; then
    echo "Desinstalando Focus Guard..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    rm -f "$PLIST_DEST"
    echo "Removido: $PLIST_DEST"
    echo "Focus Guard desinstalado."
    exit 0
fi

# ---- Pré-requisitos ----
if [[ ! -f "$PYTHON" ]]; then
    echo "ERRO: Python não encontrado em $PYTHON"
    echo "Execute 'make install' antes de instalar o serviço."
    exit 1
fi

if [[ ! -f "$PROJECT/scripts/focus_guard_service.py" ]]; then
    echo "ERRO: scripts/focus_guard_service.py não encontrado em $PROJECT"
    exit 1
fi

# ---- Geração do plist final ----
mkdir -p "$HOME/Library/LaunchAgents"

sed \
    -e "s|__PYTHON__|$PYTHON|g" \
    -e "s|__PROJECT__|$PROJECT|g" \
    "$PLIST_SRC" > "$PLIST_DEST"

echo "Plist gerado: $PLIST_DEST"

# ---- Carrega o serviço ----
# Se já estava carregado, descarrega primeiro
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo ""
echo "Focus Guard instalado e iniciado."
echo ""
echo "Comandos úteis:"
echo "  Status:      launchctl list | grep focusguard"
echo "  Logs:        tail -f /tmp/focusguard.log"
echo "  Erros:       tail -f /tmp/focusguard.err"
echo "  Parar:       launchctl unload $PLIST_DEST"
echo "  Desinstalar: bash scripts/install_launchd.sh --uninstall"
