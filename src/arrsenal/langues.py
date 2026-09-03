"""Langue de l'interface, service par service.

Chaque application exprime la meme idee differemment, et aucune ne le fait
comme sa voisine :

- les *arr veulent un ENTIER, `config/ui.uiLanguage`. La table ci-dessous a ete
  relevee en interrogeant un Sonarr reel — on lui a pose chaque valeur de 1 a
  29 et relu ce que `/localization/language` repondait. Aucune documentation
  amont ne la publie ;
- Jellyfin veut une culture (`fr`) et un pays (`FR`), poses a son assistant ;
- Silo veut un code de langue par BIBLIOTHEQUE, `metadata_language` ;
- qBittorrent veut un `locale` dans ses preferences.

Avant, arrsenal imposait le francais a Jellyfin — en dur, dans la signature du
client — et laissait tout le reste en anglais. Le resultat etait incoherent
sans que personne l'ait decide.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Correspondance `uiLanguage` des *arr, relevee contre Sonarr 4.0.19 en
#: essayant chaque valeur. Le 19 est absent : refuse par l'application.
ARR_UI_LANGUAGE = {
    "en": 1, "fr": 2, "es": 3, "de": 4, "it": 5, "da": 6, "nl": 7, "ja": 8,
    "is": 9, "zh": 10, "ru": 11, "pl": 12, "vi": 13, "sv": 14, "no": 15,
    "fi": 16, "tr": 17, "pt": 18, "el": 20, "ko": 21, "hu": 22, "he": 23,
    "lt": 24, "cs": 25, "ar": 26, "hi": 27, "bg": 28, "ml": 29,
}


@dataclass(frozen=True)
class Langue:
    code: str
    nom: str
    #: Pays associe, pour les services qui veulent les deux (Jellyfin).
    pays: str


#: Ce qu'on PROPOSE. Volontairement court : les *arr en acceptent 28, mais une
#: liste de 28 entrees dans un assistant se parcourt mal, et les absentes
#: restent accessibles par `--langue`.
PROPOSEES = (
    Langue("fr", "Francais", "FR"),
    Langue("en", "English", "US"),
    Langue("es", "Espanol", "ES"),
    Langue("de", "Deutsch", "DE"),
    Langue("it", "Italiano", "IT"),
    Langue("pt", "Portugues", "PT"),
    Langue("nl", "Nederlands", "NL"),
)

_PAR_CODE = {lang.code: lang for lang in PROPOSEES}


def connue(code: str) -> bool:
    """Cette langue est-elle utilisable par au moins un service ?"""
    return code.strip().lower() in ARR_UI_LANGUAGE


def resoudre(code: str) -> Langue:
    """Langue complete a partir d'un code. Le pays retombe sur le code en
    majuscules quand on ne le connait pas — `fr` donne `FR`, ce qui est vrai
    bien plus souvent que faux et n'est jamais bloquant."""
    code = code.strip().lower()
    if code in _PAR_CODE:
        return _PAR_CODE[code]
    return Langue(code, code, code.upper())


def arr_ui_language(code: str) -> int | None:
    """Valeur de `config/ui.uiLanguage`. None si l'application ne connait pas."""
    return ARR_UI_LANGUAGE.get(code.strip().lower())
