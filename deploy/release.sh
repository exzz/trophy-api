#!/usr/bin/env bash
# Tague le dépôt (semver) et builde l'image Docker à cette version.
#
#   deploy/release.sh X.Y.Z
#
# Ordre : on valide, on builde trophy-api:X.Y.Z (+ :latest), puis on crée le
# tag git v X.Y.Z SEULEMENT si le build réussit (pas de tag orphelin).
set -euo pipefail

IMAGE="${IMAGE:-trophy-api}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."

V="${1:-}"
if [[ ! "$V" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Usage: deploy/release.sh X.Y.Z   (semver, ex. 1.0.0)" >&2
    last=$(git describe --tags --abbrev=0 2>/dev/null || true)
    [[ -n "$last" ]] && echo "Dernier tag : $last" >&2
    exit 2
fi
TAG="v$V"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    echo "Pas un dépôt git. Fais d'abord : git init && git add -A && git commit -m init" >&2
    exit 1
}
[[ -z "$(git status --porcelain)" ]] || { echo "Arbre de travail non propre (commit d'abord)." >&2; exit 1; }
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && { echo "Le tag $TAG existe déjà." >&2; exit 1; }

REV="$(git rev-parse --short HEAD)"
echo ">> build $IMAGE:$V (rev $REV)"
docker build \
    --label "org.opencontainers.image.version=$V" \
    --label "org.opencontainers.image.revision=$REV" \
    -t "$IMAGE:$V" -t "$IMAGE:latest" .

git tag -a "$TAG" -m "release $V"
echo ">> image $IMAGE:$V et $IMAGE:latest construites, tag git $TAG créé."
echo "   Pousser le tag :   git push origin $TAG"
