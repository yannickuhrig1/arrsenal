"""PlugArr sait-il qu'une version plus recente de LUI-MEME existe ?

Signale a l'usage, et c'est un trou que la 0.6.0 avait laisse beant : « je
viens de lancer la 0.6 et elle ne detecte pas la 0.7 pour se mettre a jour ».

La 0.6.0 a livre `plugarr upgrade`, qui aligne les IMAGES des services sur le
catalogue **du binaire en cours**. Elle supposait donc que l'utilisateur avait
deja telecharge le binaire du jour — et rien, nulle part, ne le lui disait.
`__version__` n'etait qu'affiche.

**Une seule requete, et elle peut echouer sans consequence.** La verification
est un CONFORT : PlugArr fonctionne parfaitement hors ligne, et un NAS derriere
un pare-feu ne doit pas voir une erreur rouge parce qu'il ne joint pas GitHub.
Tout echec rend « on ne sait pas », jamais « pas de mise a jour ».

L'API publique de GitHub autorise 60 requetes par heure et par adresse sans
authentification. On en fait une, a la demande, jamais en boucle.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from . import __version__
from .i18n import t
from .updates import parse_version

#: La release la plus recente du depot. `/releases/latest` ignore d'office les
#: brouillons et les preversions, ce qui est exactement ce qu'on veut : on ne
#: pousse personne vers une version d'essai.
LATEST = "https://api.github.com/repos/yannickuhrig1/plugarr/releases/latest"

#: Court : c'est un confort en debut de commande, pas une etape. Mieux vaut ne
#: pas savoir que faire attendre.
TIMEOUT = 6.0


@dataclass
class Sortie:
    """Ce que la verification a appris. `disponible` est None quand on ne sait
    pas — hors ligne, quota epuise, reponse illisible."""

    disponible: str | None = None
    url: str = ""
    probleme: str = ""
    #: La version a laquelle la comparaison a ete faite. Portee par le
    #: resultat plutot que relue par chaque appelant : deux lectures separees
    #: de `__version__` pourraient diverger, et la console afficherait alors
    #: deux numeros incoherents.
    #:
    #: `field(default_factory=...)` et non `= __version__` : la seconde forme
    #: fige la valeur au CHARGEMENT du module, ce qui rend le champ
    #: intestable — un test qui remplace `__version__` n'aurait aucun effet.
    courante: str = field(default_factory=lambda: __version__)

    @property
    def a_jour(self) -> bool:
        return self.disponible is None and not self.probleme


def derniere(*, timeout: float = TIMEOUT) -> Sortie:
    """Version publiee la plus recente, si elle est plus recente que la notre.

    Ne leve jamais. Une verification de confort qui fait tomber `upgrade`
    serait pire que pas de verification.
    """
    try:
        reponse = httpx.get(
            LATEST,
            timeout=timeout,
            follow_redirects=True,
            headers={"Accept": "application/vnd.github+json"},
        )
    except httpx.HTTPError as exc:
        return Sortie(probleme=t("GitHub injoignable : {erreur}", erreur=exc))

    if reponse.status_code == 403:
        # Quota horaire epuise. Le dire plutot que de laisser croire qu'il n'y
        # a pas de mise a jour.
        return Sortie(probleme=t("quota de l'API GitHub epuise, reessayez plus tard"))
    if reponse.status_code != 200:
        return Sortie(probleme=t("GitHub a repondu HTTP {code}", code=reponse.status_code))

    try:
        donnees = reponse.json()
        tag = str(donnees["tag_name"])
        url = str(donnees.get("html_url", ""))
    except (ValueError, KeyError, TypeError):
        return Sortie(probleme=t("reponse illisible de GitHub"))

    publiee = parse_version(tag)
    courante = parse_version(__version__)
    if publiee is None or courante is None:
        return Sortie(probleme=t("versions incomparables : {tag} et {courante}",
                                 tag=tag, courante=__version__))
    if publiee <= courante:
        return Sortie()
    return Sortie(disponible=tag.lstrip("v"), url=url)
