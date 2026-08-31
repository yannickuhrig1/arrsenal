## Ce que fait cette PR

<!-- Une intention par PR. -->

## Pourquoi

<!-- Le "quoi" se lit dans le diff. Le "pourquoi" non. -->

## Verifie comment

<!--
Cochez ce qui s'applique. "Ca compile" n'est pas une verification.
-->

- [ ] `ruff check src tests scripts` et `pytest -q` au vert
- [ ] Verifie contre une instance reelle (precisez la version ci-dessous)
- [ ] `python scripts/screenshots.py` relance et captures commitees, si l'interface a change
- [ ] `scripts/audit_indexers.py` toujours vert, si l'heuristique des identifiants a bouge

Versions testees :

## Rappels

- [ ] Aucun endpoint, tag d'image, port ou nom de champ **devine**. Ce qui n'a pas pu
      etre verifie est marque `TODO(verify)` et signale ici.
- [ ] Aucun secret dans le diff, y compris dans les fixtures et les captures
- [ ] Aucun indexeur, tracker ou contenu ajoute ou recommande (voir DISCLAIMER.md)
- [ ] Si un comportement a ete verifie contre une instance reelle, il est consigne dans
      `docs/COMPATIBILITY.md` avec sa version et son code de retour
