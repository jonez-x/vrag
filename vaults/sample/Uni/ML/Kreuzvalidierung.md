---
tags: [ml, uni]
---

# Kreuzvalidierung
Bei k-facher Kreuzvalidierung wird der Datensatz in k gleich große Teile geteilt. Jeder Teil ist einmal Validierungsmenge, der Rest Training.

## Wann sinnvoll
Bei kleinen Datensätzen, wenn ein einzelner Train/Test-Split zu zufällig wäre. Typisch k = 5 oder 10.

## Stolperfallen
Bei Zeitreihen keine zufällige Aufteilung – sonst sieht das Modell die Zukunft (Data Leakage).
Hyperparameter nie auf dem finalen Testset tunen.
