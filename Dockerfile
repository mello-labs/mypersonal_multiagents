FROM python:3.12-slim

WORKDIR /app
ENV PIP_ROOT_USER_ACTION=ignore

# Instala dependências do sistema + Docker CLI via repositório da distro
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o projeto
COPY . .

# Cria diretórios de runtime e troca para usuário sem privilégios
RUN mkdir -p logs reports \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Variáveis de ambiente padrão
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV WEB_HOST=0.0.0.0

EXPOSE 8000

CMD ["sh", "-c", "uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
