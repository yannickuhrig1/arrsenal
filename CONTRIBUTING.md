# Contribuer

Merci d'y jeter un œil. Ce projet a une règle qui prime sur toutes les autres, et il
vaut mieux la connaître avant d'écrire du code.

## La règle : ne devinez rien

**Ne devinez aucun endpoint d'API, aucun tag d'image, aucun numéro de port, aucun nom de
champ, aucune version.** Vérifiez contre la documentation officielle ou, mieux, contre
une instance réelle.

Ce n'est pas une posture. Pendant la seule phase 1, cinq hypothèses parfaitement
raisonnables se sont révélées fausses au premier contact avec un vrai conteneur :

| Ce qui semblait évident | Ce qui est vrai |
|---|---|
| Radarr est en 5.x | 6.3.0 |
| `AuthenticationMethod=External` suffit | il laisse les interfaces web **sans login** |
| On peut poser Category *et* Directory | ils sont exclusifs, et une catégorie par défaut est déjà remplie |
| La notification Jellyfin prend host + port | elle exige une clé API, à créer d'abord |
| `forceSave=true` saute la validation | il ne saute rien, l'indexeur est contacté quoi qu'il arrive |

Chacune aurait produit du code plausible et cassé. Toutes sont consignées avec leurs
codes HTTP dans [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

Quand un fait n'est pas vérifiable dans votre environnement, écrivez `TODO(verify)` et
dites-le dans la pull request. Une lacune signalée vaut mieux qu'une invention.

## Mettre en place l'environnement

```bash
git clone <votre-fork>
cd plugarr
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

```bash
ruff check src tests scripts
pytest -q
```

La suite complète tourne **sans Docker et sans réseau**. Si un test que vous ajoutez a
besoin de l'un ou de l'autre, c'est qu'il appartient au job d'intégration.

## Comment le projet est découpé

```
core     catalog, models, layout, seed, compose, wiring, orchestrator, dashboard
         → aucune dépendance à Typer ni à Textual, testable sans Docker
cli      traduit des options en appels, rend les événements
tui      même chose au clavier
```

**La CLI et l'assistant ne doivent jamais contenir de logique métier.** Ils appellent
`orchestrator.py`. C'est ce qui garantit qu'ils ne divergeront pas.

## Ajouter un service

Dans la plupart des cas, une entrée dans `catalog.py` suffit : l'assistant, la CLI, la
page d'accès et le récapitulatif le découvrent tout seuls. Vous n'avez à toucher au TUI
que si le service demande une interaction d'un genre nouveau.

Si le service a besoin d'un câblage particulier, ajoutez une étape dans `wiring.py`.
Une étape doit être :

- **idempotente** — vérifier l'existence avant de créer, ne jamais écraser un réglage
  manuel ;
- **vérifiée** — se faire valider par le bouton *Test* de l'application cible, pas par
  le code de retour du POST ;
- **pilotée par le schéma** — demander son gabarit à l'application plutôt que coder un
  JSON en dur, et signaler les champs qu'une version n'expose pas au lieu de les perdre.

Épinglez le tag d'image. Un tag flottant rend le câblage non reproductible ; un test
échoue si vous l'oubliez.

## Écrire les tests

Un test doit dire **pourquoi** il existe, pas seulement ce qu'il vérifie. Comparez :

```python
def test_download_dir():
    assert s["rpc-whitelist-enabled"] is False
```

```python
def test_transmission_settings_allow_container_to_container_rpc():
    # Sans ces deux reglages, Sonarr/Radarr sont refuses par Transmission.
    assert s["rpc-whitelist-enabled"] is False
    assert s["rpc-host-whitelist-enabled"] is False
```

Le second survit à une relecture dans six mois.

## Les captures du README

Elles sont **générées**, pas prises à la main :

```bash
python scripts/screenshots.py
```

Le script tourne sans terminal ni Docker et produit des fichiers identiques d'une
exécution à l'autre. La CI échoue si le README affiche une version périmée de
l'interface : régénérez et commitez.

## L'audit des indexeurs

Prowlarr embarque plus de 600 définitions dont la forme change à chaque version.
`scripts/audit_indexers.py` confronte l'heuristique de détection des identifiants à
toutes, et **échoue si une définition expose un champ d'une forme non prévue**.

Il tourne en CI. Si vous le voyez signaler un cas nouveau : examinez-le, puis ajoutez-le
aux listes `REVIEWED_*` du script s'il est correct, ou étendez l'heuristique s'il ne
l'est pas. Ne le faites pas taire sans regarder.

## Secrets

Aucune clé, aucun mot de passe, aucun jeton dans le dépôt — y compris dans les fixtures
de test et les captures. `.env`, `stack.yml`, `docker-compose.yml` et la page d'accès
sont générés et ignorés par git ; ne les commitez pas.

Dans les journaux, les secrets passent par `mask()`. Masquez sur le **nom** de la
variable, jamais sur la forme de la valeur : un jeton JWT ne ressemble pas à une clé
hexadécimale, et un masquage par motif le laisse passer.

## Indexeurs et contenu

`plugarr` ne fournit, n'héberge et ne recommande **aucun indexeur, aucun tracker, aucun
contenu**. La liste que voit l'utilisateur vient de son propre Prowlarr.

Les pull requests qui ajouteraient une liste d'indexeurs, un tracker préconfiguré ou une
recommandation seront refusées. Ce n'est pas négociable : c'est ce qui protège le projet
et ses utilisateurs. Voir [DISCLAIMER.md](DISCLAIMER.md).

## Pull requests

- une intention par pull request ;
- `ruff check` et `pytest` au vert ;
- le message de commit explique **pourquoi**, pas seulement quoi ;
- si vous avez vérifié un comportement contre une instance réelle, ajoutez-le à
  `docs/COMPATIBILITY.md` avec sa version et son code de retour. C'est le document le
  plus utile du dépôt.

## Langue

Le code, les commentaires et la documentation sont en français. Les identifiants Python
restent en anglais, par convention du langage. Une pull request en anglais sera lue et
acceptée — nous traduirons.
