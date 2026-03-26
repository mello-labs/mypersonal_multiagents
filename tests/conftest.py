"""
conftest.py — Fixtures compartilhadas entre todos os testes.
"""
import sys
import os
import pytest
from unittest.mock import patch

# Garante que o projeto raiz está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def mem(tmp_path):
    """
    Fornece o módulo `memory` apontando para um banco SQLite temporário isolado.
    Cada teste recebe um banco limpo e vazio.
    """
    db_file = str(tmp_path / "test_memory.db")
    with patch("core.memory.MEMORY_DB_PATH", db_file):
        from core import memory
        memory.init_db()
        yield memory
