---
tags: [tech, git]
---

# Git Rebase vs Merge
## Merge
Erzeugt einen Merge-Commit, die Historie bleibt unverändert und zeigt echte Verzweigungen.

## Rebase
Setzt die eigenen Commits auf den neuesten Stand des Zielbranches – lineare Historie.
Goldene Regel: niemals Commits rebasen, die schon gepusht und von anderen genutzt werden.

## Interaktiv
`git rebase -i HEAD~3` zum Zusammenfassen (squash) oder Umbenennen der letzten drei Commits.
Wenn es schiefgeht: `git reflog` zeigt alte Stände, `git rebase --abort` bricht ab.
