#!/bin/bash
# idle-stop.sh
# Stoppt Container nach IDLE_SECONDS ohne eingehenden Netzwerktraffic.
# Läuft alle 5 Minuten via Cron.

IDLE_SECONDS=7200  # 2 Stunden
STATE_DIR=/var/lib/idle-stop
CONTAINERS=(
    "heykarl-pgadmin"
    "heykarl-phpmyadmin"
    "heykarl-redis-commander"
    "heykarl-openwebui"
)

mkdir -p "$STATE_DIR"
NOW=$(date +%s)

for container in "${CONTAINERS[@]}"; do
    STATE_FILE="${STATE_DIR}/${container}"

    # Nicht laufende Container überspringen, State aufräumen
    if ! docker ps --format "{{.Names}}" 2>/dev/null | grep -q "^${container}$"; then
        rm -f "$STATE_FILE"
        continue
    fi

    # Eingehende Bytes des Containers (erster Wert von NetIO = received)
    CURRENT_NET=$(docker stats --no-stream --format "{{.NetIO}}" "$container" 2>/dev/null | awk '{print $1}')

    if [ -z "$CURRENT_NET" ]; then
        continue
    fi

    if [ -f "$STATE_FILE" ]; then
        LAST_NET=$(sed -n '1p' "$STATE_FILE")
        LAST_ACTIVE=$(sed -n '2p' "$STATE_FILE")

        if [ "$CURRENT_NET" != "$LAST_NET" ]; then
            # Neuer Traffic — last active aktualisieren
            printf '%s\n%s\n' "$CURRENT_NET" "$NOW" > "$STATE_FILE"
        else
            IDLE_TIME=$((NOW - LAST_ACTIVE))
            if [ "$IDLE_TIME" -ge "$IDLE_SECONDS" ]; then
                echo "[idle-stop] $(date '+%Y-%m-%d %H:%M:%S') Stopping $container (idle ${IDLE_TIME}s)"
                docker stop "$container" 2>/dev/null
                rm -f "$STATE_FILE"
            fi
        fi
    else
        # Erster Check für diesen Container
        printf '%s\n%s\n' "$CURRENT_NET" "$NOW" > "$STATE_FILE"
    fi
done
