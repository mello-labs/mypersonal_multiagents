"""
conftest.py — Fixtures compartilhadas entre todos os testes.
Usa fakeredis para isolar cada teste sem depender de um Redis real.
"""
import sys
import os
import pytest
import fakeredis

# Garante que o projeto raiz está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def mem():
    """
    Fornece o módulo `memory` usando um FakeRedis isolado.
    Cada teste recebe um banco limpo e vazio — sem Redis real necessário.
    """
    import core.memory as memory

    fake = fakeredis.FakeRedis(decode_responses=True)

    # Injeta o cliente fake no singleton do módulo
    memory._redis_client = fake

    # Inicializa (apenas confirma ping — fakeredis sempre responde)
    memory.init_db()

    yield memory

    # Limpa tudo após o teste
    fake.flushall()
    memory._redis_client = None
