---
tags: [ml, uni]
---

# Regularisierung
Techniken, die die Modellkomplexität bestrafen, um [[Overfitting]] zu reduzieren.

## L2 (Weight Decay)
Bestraft große Gewichte quadratisch. Gewichte werden klein, aber selten exakt null.

## L1 (Lasso)
Bestraft den Betrag der Gewichte, erzeugt dünnbesetzte Modelle – praktisch für Feature-Selektion.

## Dropout
Während des Trainings werden zufällig Neuronen deaktiviert (z. B. p = 0.5). Das Netz kann sich nicht auf einzelne Pfade verlassen.
Beim Inferenzschritt ist Dropout aus.
