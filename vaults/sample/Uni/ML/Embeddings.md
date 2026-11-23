---
tags: [ml, retrieval]
---

# Embeddings
Dichte Vektoren, die Bedeutung abbilden: ähnliche Texte liegen nah beieinander (Kosinus-Ähnlichkeit).

## Für Suche
Dokumente und Anfrage werden mit demselben Modell eingebettet, dann sucht man die nächsten Nachbarn.
Findet auch Treffer ohne gemeinsame Wörter ("Auto" ↔ "PKW"), schwächer bei exakten Namen und Zahlen.

## Modelle
Mehrsprachige Modelle wie bge-m3 funktionieren auch für deutsche Notizen. Siehe [[BM25]] für die lexikalische Alternative und [[Reciprocal Rank Fusion]] zum Kombinieren.
