---
tags: [ml, uni]
---

# Self-Attention
Jedes Token schaut auf alle anderen Tokens derselben Sequenz und gewichtet sie.

## Query, Key, Value
Aus jedem Token werden drei Vektoren projiziert. Gewicht = softmax(Q·Kᵀ / √d_k), Ergebnis = Gewichte · V.
Die Skalierung mit √d_k verhindert, dass die Softmax bei großen Dimensionen sättigt.

## Multi-Head
Mehrere Attention-Köpfe parallel lernen unterschiedliche Beziehungen (z. B. Syntax vs. Bedeutung).
Komplexität ist quadratisch in der Sequenzlänge – deshalb sind lange Kontexte teuer.
Siehe [[Transformer]].
