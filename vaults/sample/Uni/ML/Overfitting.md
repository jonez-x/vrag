---
tags: [ml, uni]
---

# Overfitting
Das Modell lernt die Trainingsdaten auswendig inklusive Rauschen und generalisiert schlecht auf neue Daten.

## Erkennen
Trainingsfehler sinkt weiter, Validierungsfehler steigt wieder an. Deshalb immer einen separaten Validierungsdatensatz nutzen, siehe [[Kreuzvalidierung]].

## Gegenmaßnahmen
Mehr Daten, Data Augmentation, Early Stopping, kleineres Modell und [[Regularisierung]].
Gegenteil: Underfitting – Modell ist zu einfach für die Struktur der Daten.
