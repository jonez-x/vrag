---
tags: [retrieval]
---

# Reciprocal Rank Fusion
Methode, um mehrere Ranglisten zu kombinieren, ohne die Scores kalibrieren zu müssen.

## Formel
score(d) = Σ 1 / (k + rang_i(d)), üblich ist k = 60.
Nur die Rangposition zählt, deshalb lassen sich [[BM25]] und Vektor-Suche ([[Embeddings]]) problemlos mischen.

## Hybride Suche
Lexikalisch + semantisch fusioniert ist in Benchmarks fast immer besser als jede Methode allein.
