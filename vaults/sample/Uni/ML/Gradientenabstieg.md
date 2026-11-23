---
tags: [ml, uni]
---

# Gradientenabstieg
Parameter werden schrittweise entgegen dem Gradienten der Verlustfunktion verschoben.

## Lernrate
Zu groß: das Training divergiert oder springt hin und her. Zu klein: extrem langsame Konvergenz.
Lernraten-Schedules (Warmup, Cosine Decay) helfen.

## Varianten
- Batch, Mini-Batch, stochastisch (SGD)
- Momentum glättet die Richtung
- Adam kombiniert Momentum mit adaptiver Lernrate pro Parameter
Verwandt: [[Overfitting]], [[Regularisierung]].
