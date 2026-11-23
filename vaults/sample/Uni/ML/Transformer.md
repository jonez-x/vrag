---
tags: [ml, uni]
---

# Transformer
Architektur aus dem Paper "Attention Is All You Need" (2017). Ersetzt Rekurrenz komplett durch [[Self-Attention]].

## Aufbau
Encoder- und Decoder-Stapel aus Blöcken: Multi-Head-Attention, Feed-Forward-Netz, Residualverbindungen und Layer-Norm.
Weil es keine Reihenfolge gibt, braucht man eine Positionskodierung (Sinus/Cosinus oder gelernt).

## Warum so erfolgreich
Alle Tokens werden parallel verarbeitet, das skaliert auf GPUs viel besser als RNNs.
Grundlage für BERT, GPT und moderne [[Embeddings]].
