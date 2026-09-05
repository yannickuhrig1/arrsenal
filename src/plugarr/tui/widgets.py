"""Widgets Textual qui traduisent leur libelle en passant.

Il y a deux facons de traduire une interface, et la premiere ne tient pas.

**Envelopper chaque phrase a la main** — `Button(t("Continuer"))` — oblige a
penser a `t()` a chaque ligne ecrite. Sur les cent-cinquante phrases de
l'assistant, la question n'est pas de savoir si on en oubliera, mais combien.
Et une phrase oubliee ne casse rien : elle s'affiche simplement en francais a
quelqu'un qui a demande l'anglais, sans erreur ni avertissement.

**Traduire au passage**, ici. Les ecrans continuent d'ecrire leurs phrases en
francais, en clair, exactement comme avant ; c'est le widget qui les fait
passer par le catalogue au moment de les afficher. Rien a oublier, et le diff
sur les ecrans se reduit a une ligne d'import.

`scripts/audit_traductions.py` releve les litteraux passes a ces widgets aussi
bien que les appels directs a `t()`, et echoue s'il en manque un au catalogue.

Ce qui reste hors de portee, et c'est assume : les f-strings. `f"[red]{exc}
[/red]"` ne peut pas etre une cle, sa valeur change a chaque appel. Les
morceaux fixes de ces messages passent par `t()` explicitement dans les
ecrans.
"""

from __future__ import annotations

from typing import Any

from textual import widgets as _tx

from ..i18n import t


def _traduit(valeur: Any) -> Any:
    """Traduit une chaine, laisse passer tout le reste.

    Textual accepte aussi bien un `str` qu'un `RichRenderable` : ce qui n'est
    pas une chaine ne nous concerne pas et doit arriver intact.
    """
    return t(valeur) if isinstance(valeur, str) else valeur


class Button(_tx.Button):
    def __init__(self, label: Any = "", *args: Any, **kw: Any) -> None:
        super().__init__(_traduit(label), *args, **kw)


class Label(_tx.Label):
    def __init__(self, renderable: Any = "", *args: Any, **kw: Any) -> None:
        super().__init__(_traduit(renderable), *args, **kw)

    def update(self, renderable: Any = "") -> None:
        super().update(_traduit(renderable))


class Static(_tx.Static):
    def __init__(self, renderable: Any = "", *args: Any, **kw: Any) -> None:
        super().__init__(_traduit(renderable), *args, **kw)

    def update(self, renderable: Any = "") -> None:
        # `update` compte autant que le constructeur : la moitie des phrases de
        # l'assistant sont posees apres coup, en reponse a une action.
        super().update(_traduit(renderable))


class Checkbox(_tx.Checkbox):
    def __init__(self, label: Any = "", *args: Any, **kw: Any) -> None:
        super().__init__(_traduit(label), *args, **kw)


class RadioButton(_tx.RadioButton):
    def __init__(self, label: Any = "", *args: Any, **kw: Any) -> None:
        super().__init__(_traduit(label), *args, **kw)


class Input(_tx.Input):
    def __init__(self, *args: Any, **kw: Any) -> None:
        # Seul le texte d'invite est une phrase ; la valeur est une donnee de
        # l'utilisateur et ne doit surtout pas etre touchee.
        if isinstance(kw.get("placeholder"), str):
            kw["placeholder"] = t(kw["placeholder"])
        super().__init__(*args, **kw)


class DataTable(_tx.DataTable):
    def add_columns(self, *labels: Any) -> list[Any]:
        return super().add_columns(*(_traduit(libelle) for libelle in labels))
