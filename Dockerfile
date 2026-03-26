FROM python:3.12-slim

WORKDIR /app

# Instala dependências do sistema (necessário para google-auth e outras)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o projeto
COPY . .

# Cria diretório de logs
RUN mkdir -p logs reports

# Variáveis de ambiente padrão
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV WEB_HOST=0.0.0.0

EXPOSE 8000

CMD uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-8000}
