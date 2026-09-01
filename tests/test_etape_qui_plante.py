"""Une etape qui plante ne doit pas emporter tout le cablage.

Constate en integration : une erreur de programmation a l'avant-derniere etape
a fait echouer l'installation APRES 40 etapes reussies. Ni rapport, ni page
d'acces, ni trace de ce qui avait pourtant marche — alors que la stack etait
entierement cablee et fonctionnelle. Le message se resumait a
`AttributeError : 'NoneType' object has no attribute 'status_code'`.

`execute` n'attrapait que `WiringError`, c'est-a-dire les pannes prevues.
Un defaut d'arrsenal lui-meme passait au travers.
"""

from __future__ import annotations

from arrsenal.clients.base import WiringError
from arrsenal.models import StackConfig
from arrsenal.wiring import StepResult, Wirer, WiringStep


def _wirer(steps: list[WiringStep]) -> Wirer:
    cfg = StackConfig(config_root="/c", data_root="/d")
    wirer = Wirer(cfg)
    wirer.build_plan = lambda: steps  # type: ignore[method-assign]
    return wirer


def test_les_etapes_suivantes_tournent_quand_meme():
    passees = []

    def plante() -> StepResult:
        raise AttributeError("'NoneType' object has no attribute 'status_code'")

    def marche() -> StepResult:
        passees.append("apres")
        return StepResult("apres", ok=True, detail="")

    results = _wirer(
        [
            WiringStep("avant", lambda: StepResult("avant", ok=True, detail="")),
            WiringStep("plante", plante),
            WiringStep("apres", marche),
        ]
    ).execute()

    assert passees == ["apres"], "l'etape suivante n'a jamais tourne"
    assert [r.ok for r in results] == [True, False, True]


def test_le_rapport_nomme_l_etape_et_le_type_d_erreur():
    """Sans cela, l'utilisateur ne peut ni comprendre ni rapporter la panne."""

    def plante() -> StepResult:
        raise AttributeError("pas de status_code")

    result = _wirer([WiringStep("jellyfin/bibliotheques", plante)]).execute()[0]

    assert result.name == "jellyfin/bibliotheques"
    assert "AttributeError" in result.detail
    assert "pas de status_code" in result.detail


def test_la_faute_est_attribuee_a_arrsenal():
    """Une erreur inattendue vient d'arrsenal, pas de la machine de qui l'utilise.
    Le dire evite d'envoyer quelqu'un chercher une panne qui n'existe pas."""

    def plante() -> StepResult:
        raise KeyError("champ")

    result = _wirer([WiringStep("x", plante)]).execute()[0]

    assert any("defaut d'arrsenal" in w for w in result.warnings)


def test_une_panne_prevue_garde_son_message():
    """`WiringError` porte un diagnostic ecrit pour l'utilisateur : il ne doit
    pas etre remplace par le texte generique des erreurs inattendues."""

    def refuse() -> StepResult:
        raise WiringError("sonarr: acces refuse", "HTTP 401", "verifiez la cle")

    result = _wirer([WiringStep("sonarr/x", refuse)]).execute()[0]

    assert "acces refuse" in result.detail
    assert "erreur inattendue" not in result.detail
