#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
#  Crée un raccourci "IPN Hébergement" sur le Bureau (macOS)
#  À exécuter une seule fois depuis le terminal :
#    chmod +x create_shortcut.sh && ./create_shortcut.sh
# ─────────────────────────────────────────────────────────────────────

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP="$HOME/Desktop"
SHORTCUT="$DESKTOP/IPN Hébergement.command"

# Rendre les scripts du projet exécutables
chmod +x "$PROJECT_DIR/launch.command"
chmod +x "$PROJECT_DIR/ipn.sh"

# ── Générer un raccourci qui encode le chemin absolu du projet ────────
# (ne PAS copier launch.command : il s'exécuterait depuis le Bureau)
cat > "$SHORTCUT" << SHORTCUT_EOF
#!/bin/bash
# Raccourci IPN Hébergement — généré par create_shortcut.sh
# Chemin projet encodé à la création : ne pas déplacer sans régénérer.
cd "$PROJECT_DIR"
exec bash launch.command
SHORTCUT_EOF

chmod +x "$SHORTCUT"

echo ""
echo "  ✓ Raccourci créé : $SHORTCUT"
echo "  ✓ Projet         : $PROJECT_DIR"
echo ""
echo "  Double-cliquez sur « IPN Hébergement » sur votre Bureau."
echo ""

open "$DESKTOP"
