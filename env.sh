# Environnement d'exécution de l'extracteur Trophy (Linux, iODBC).
# Usage :  source env.sh   puis   python extractor/discover.py
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# iODBC : fichiers de configuration locaux (pas besoin de /etc ni de sudo)
export ODBCINSTINI="$HERE/odbc/odbcinst.ini"   # liste des pilotes
export ODBCINI="$HERE/odbc/odbc.ini"           # DSN (optionnel)

# le pilote HFSQL charge ses dépendances PC SOFT depuis driver/
export LD_LIBRARY_PATH="$HERE/driver:${LD_LIBRARY_PATH:-}"

# connexion (le mot de passe vient de l'extérieur, pas en dur ici)
export TROPHY_SERVER="100.79.174.114"
export TROPHY_PORT="4902"
export TROPHY_DB="Datas"
# chemin direct du .so : évite de dépendre de l'enregistrement du pilote
export TROPHY_DRIVER="$HERE/driver/wd250hfo64.so"
# export TROPHY_UID="api_lecture"
# export TROPHY_PWD="..."   # à fournir au moment du lancement

# venv
if [ -f "$HERE/.venv/bin/activate" ]; then . "$HERE/.venv/bin/activate"; fi
