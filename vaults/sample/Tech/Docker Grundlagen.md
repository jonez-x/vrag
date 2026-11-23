---
tags: [tech, devops]
---

# Docker Grundlagen
## Begriffe
Image = unveränderliche Vorlage, Container = laufende Instanz eines Images, Volume = persistenter Speicher.

## Befehle
- `docker run -d -p 8080:80 nginx` startet einen Container im Hintergrund
- `docker compose up -d` startet alle Dienste aus der compose.yaml
- `docker system prune` räumt ungenutzte Images und Container auf

## Fehler
"port is already allocated" heißt: ein anderer Prozess nutzt den Port schon. Mit `lsof -i :8080` finden.
Genutzt im [[Homelab]].
