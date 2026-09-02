"""Filtre geographique accepte par Gluetun, fournisseur par fournisseur.

Les donnees viennent de l'IMAGE epinglee elle-meme, pas du depot amont :
`scripts/vpn_countries.py` demande a `gluetun-entrypoint format-servers` ce
qu'il connait, dans la version exacte que le compose deploie. Le depot avance ;
une valeur proposee par la liste amont mais absente de la version epinglee
serait refusee au demarrage, sans que rien ne l'explique a l'utilisateur.

**Tous les fournisseurs ne se filtrent pas par pays**, et c'est le piege que ce
module existe pour eviter. Cinq d'entre eux n'exposent AUCUN pays dans les
donnees de Gluetun :

- Windscribe, VyprVPN, Giganews et Private Internet Access classent par REGION ;
- Perfect Privacy ne connait que des VILLES.

Leur poser `SERVER_COUNTRIES` ne filtre rien du tout. Chaque fournisseur porte
donc le nom de la variable qu'il faut reellement lui donner.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).parent / "data" / "vpn_countries.json"

#: Variable posee quand le fournisseur est inconnu du fichier — `custom`, ou un
#: fournisseur ajoute par une version plus recente de Gluetun.
DEFAULT_ENV = "SERVER_COUNTRIES"


@lru_cache(maxsize=1)
def _tables() -> tuple[str, dict[str, dict]]:
    contenu = json.loads(DATA.read_text(encoding="utf-8"))
    return contenu["gluetun"], contenu["providers"]


def gluetun_version() -> str:
    """Version de Gluetun d'ou proviennent ces listes."""
    return _tables()[0]


def filter_env(provider: str) -> str:
    """Variable d'environnement a poser pour filtrer ce fournisseur."""
    return _tables()[1].get(provider.strip().lower(), {}).get("env", DEFAULT_ENV)


def choices(provider: str) -> list[str]:
    """Valeurs acceptees par ce fournisseur. Vide = saisie libre.

    Vide n'est pas une erreur : `custom` n'a par construction aucune liste, et un
    fournisseur inconnu du fichier doit rester utilisable — la saisie libre passe
    alors telle quelle a Gluetun, qui la validera lui-meme.
    """
    return list(_tables()[1].get(provider.strip().lower(), {}).get("values", []))


def label(provider: str) -> str:
    """Libelle du filtre, pour l'ecran de saisie."""
    return {
        "SERVER_COUNTRIES": "Pays souhaites",
        "SERVER_REGIONS": "Regions souhaitees",
        "SERVER_CITIES": "Villes souhaitees",
    }.get(filter_env(provider), "Pays souhaites")
