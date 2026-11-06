# API Trophy (lecture seule) en conteneur. Pas de compose : image seule.
#
# Deux étapes : uv installe les dépendances figées (uv.lock) dans un venv ;
# l'image finale ne garde que Python, iODBC, le pilote HFSQL et l'application.
#
# Particularité : le client parle à HFSQL via le pilote natif PC SOFT
# (driver/wd250hfo64.so + ses .so). On embarque driver/, on règle
# LD_LIBRARY_PATH et TROPHY_DRIVER ; le pilote est chargé par chemin absolu
# (DRIVER=<.so>), donc pas besoin d'enregistrement ODBC (odbcinst.ini).

ARG UBUNTU=ubuntu:26.04

# ------------------------------------------------------------------ construction
FROM ${UBUNTU} AS construction
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 ca-certificates \
 && rm -rf /var/lib/apt/lists/*
ENV UV_PYTHON=/usr/bin/python3 \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ------------------------------------------------------------------- exécution
FROM ${UBUNTU}
# libiodbc2 : gestionnaire de pilotes attendu par le pilote HFSQL PC SOFT.
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 libiodbc2 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin trophy

WORKDIR /app
COPY --from=construction /app/.venv /app/.venv
COPY api ./api
COPY extractor ./extractor
COPY driver ./driver

# La config (identifiants HFSQL + api_key) n'est JAMAIS dans l'image :
# settings.json se monte en lecture seule dans /config au lancement.
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LD_LIBRARY_PATH=/app/driver \
    TROPHY_DRIVER=/app/driver/wd250hfo64.so \
    TROPHY_SETTINGS=/config/settings.json

USER trophy
EXPOSE 8333

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8333/health', timeout=4)"]

# UN SEUL processus : le pilote HFSQL n'autorise qu'une connexion par process
# (sur le thread principal). Jamais --workers > 1.
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8333", \
     "--no-server-header"]
