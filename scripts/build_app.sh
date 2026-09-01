#!/bin/bash
# Génère scripts/ComptesApp.app (non versionné) à partir du template versionné,
# en y injectant le chemin réel du repo sur cette machine.
set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP="$REPO_DIR/scripts/ComptesApp.app"

rm -rf "$APP"
cp -R "$REPO_DIR/scripts/ComptesApp.app.template" "$APP"
sed -i '' "s|__REPO_PATH__|$REPO_DIR|" "$APP/Contents/MacOS/ComptesApp"

echo "App générée : $APP"
echo "Pour l'installer : cp -R \"$APP\" /Applications/"
