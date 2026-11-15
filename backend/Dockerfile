FROM python:3.11-slim

# Evitar escritura de .pyc y habilitar salida sin buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SPHEREX_PORT=8000 \
    SPHEREX_HOST=0.0.0.0

WORKDIR /app

# Instalar dependencias del sistema y utilitarios para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Crear usuario sin privilegios por seguridad y preparar directorio de caché
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data/cache/frames /app/data/cache/metadata /app/data/cache/fits && \
    chown -R appuser:appuser /app

# Copiar el código de la aplicación
COPY --chown=appuser:appuser app/ ./app/

# Declarar volumen persistente para la caché de disco
VOLUME ["/app/data/cache"]

# Cambiar a usuario sin privilegios
USER appuser

EXPOSE 8000

# Verificación periódica de salud
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
