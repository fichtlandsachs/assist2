#!/bin/bash
# start-tool.sh
# Startet einen Tool-Container on demand.
# Verwendung: ./start-tool.sh [pgadmin|phpmyadmin|redis|openwebui]

COMPOSE_FILE="/opt/assist2/infra/docker-compose.yml"

case "$1" in
    pgadmin)
        docker compose -f "$COMPOSE_FILE" --profile tools up -d pgadmin
        ;;
    phpmyadmin)
        docker compose -f "$COMPOSE_FILE" --profile tools up -d phpmyadmin
        ;;
    redis|redis-commander)
        docker compose -f "$COMPOSE_FILE" --profile tools up -d redis-commander
        ;;
    openwebui)
        docker compose -f "$COMPOSE_FILE" --profile optional up -d openwebui
        ;;
    tools)
        docker compose -f "$COMPOSE_FILE" --profile tools up -d
        ;;
    all)
        docker compose -f "$COMPOSE_FILE" --profile tools --profile optional up -d
        ;;
    *)
        echo "Verwendung: $0 [pgadmin|phpmyadmin|redis|openwebui|tools|all]"
        echo ""
        echo "Verfügbare Tool-Container:"
        echo "  pgadmin     - PostgreSQL Admin UI"
        echo "  phpmyadmin  - MariaDB Admin UI (Nextcloud DB)"
        echo "  redis       - Redis Commander"
        echo "  openwebui   - Open WebUI (LiteLLM Chat)"
        echo "  tools       - Alle DB/Redis Admin Tools"
        echo "  all         - Alle optionalen Services"
        exit 1
        ;;
esac
