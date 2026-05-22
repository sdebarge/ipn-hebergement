#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
#  Utilitaires IPN Hébergement
#  Usage : ./ipn.sh [start|stop|reload|status]
# ─────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")"
PORT=8000
PID_FILE=".uvicorn.pid"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

case "${1:-start}" in

  start)
    if lsof -ti tcp:$PORT &>/dev/null; then
        echo -e "${YELLOW}⚠ Déjà en cours sur le port $PORT${NC}"
        open "http://localhost:$PORT"
        exit 0
    fi
    source .venv/bin/activate 2>/dev/null || true
    echo -e "${GREEN}▶ Démarrage...${NC}"
    nohup python3 -m uvicorn app.main:app \
        --host 0.0.0.0 --port $PORT \
        --log-level warning > .uvicorn.log 2>&1 &
    echo $! > "$PID_FILE"
    sleep 1.2
    open "http://localhost:$PORT"
    echo -e "${GREEN}✓ Serveur démarré (PID $(cat $PID_FILE))${NC}"
    ;;

  stop)
    if [ -f "$PID_FILE" ]; then
        kill "$(cat $PID_FILE)" 2>/dev/null && rm "$PID_FILE"
        echo -e "${YELLOW}■ Serveur arrêté${NC}"
    else
        lsof -ti tcp:$PORT | xargs kill 2>/dev/null
        echo -e "${YELLOW}■ Port $PORT libéré${NC}"
    fi
    ;;

  reload)
    # Recharge les données Excel sans redémarrer
    source .venv/bin/activate 2>/dev/null || true
    RESP=$(curl -s -X POST "http://localhost:$PORT/api/reload")
    echo -e "${GREEN}✓ Données rechargées : $RESP${NC}"
    ;;

  status)
    if lsof -ti tcp:$PORT &>/dev/null; then
        PID=$(lsof -ti tcp:$PORT)
        echo -e "${GREEN}● En ligne — PID $PID — http://localhost:$PORT${NC}"
    else
        echo -e "${RED}○ Arrêté${NC}"
    fi
    ;;

  *)
    echo "Usage: ./ipn.sh [start|stop|reload|status]"
    ;;
esac
