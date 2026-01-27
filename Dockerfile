# =============================================================================
# Dockerfile - Tech Watch Agent
# Image Python minimale pour VPS modeste
# =============================================================================

FROM python:3.11-slim

# Métadonnées
LABEL maintainer="Tech Watch Agent"
LABEL description="Agent de veille technologique LangGraph"

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Créer un utilisateur non-root
RUN useradd --create-home --shell /bin/bash appuser

# Répertoire de travail
WORKDIR /app

# Installer les dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copier les requirements d'abord (cache Docker)
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY src/ ./src/

# Changer le propriétaire des fichiers
RUN chown -R appuser:appuser /app

# Basculer vers l'utilisateur non-root
USER appuser

# Port exposé
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Point d'entrée
WORKDIR /app/src
CMD ["python", "main.py", "--serve", "--port", "8080"]
