"""La langue des interfaces se choisit une fois et s'applique partout.

Demande a l'usage : « on pourrait aussi demander la langue voulue dans les
applications et les passer directement en fr ».

La demande a mis au jour une incoherence deja presente : arrsenal imposait le
francais a Jellyfin — code EN DUR dans la signature de son client — et laissait
Sonarr, Radarr et Prowlarr en anglais. Personne n'avait choisi ce melange.

Chaque application exprime la meme idee differemment, et le piege est la :

- Sonarr et Radarr veulent un ENTIER (`2` pour le francais) ;
- Prowlarr veut le CODE (`'fr'`) — poser l'entier donne « The JSON value could
  not be converted to System.String » ;
- Jellyfin veut une culture et un pays ;
- Silo veut un code par BIBLIOTHEQUE.
"""

from __future__ import annotations

import pytest

from arrsenal import langues, orchestrator
from arrsenal.clients.arr import ArrClient
from arrsenal.wiring import Wirer

# ------------------------------------------------------------------- table


def test_la_table_vient_d_une_instance_reelle():
    """Relevee en posant chaque valeur de 1 a 29 sur un Sonarr 4.0.19 et en
    relisant `/localization/language`. Aucune documentation ne la publie.

    Le meme numerotage a ensuite ete confirme service par service, chacun
    interroge en vrai :

        Sonarr   4.0.19.2979  entier  2 -> fr-FR
        Radarr   6.3.0.10514  entier  2 -> fr-FR
        Lidarr   3.1.0        entier  2 -> « Cle API », « A propos »
        Prowlarr 2.5.2.5491   CHAINE  'fr'

    Lidarr n'expose pas `/localization/language` : la verification y est passee
    par `/localization`, dont les chaines rendues sont francaises.
    """
    assert langues.arr_ui_language("fr") == 2
    assert langues.arr_ui_language("en") == 1


def test_le_19_est_absent():
    """Refuse par l'application : le trou est reel, pas un oubli de saisie."""
    assert 19 not in langues.ARR_UI_LANGUAGE.values()


def test_une_langue_inconnue_ne_donne_aucune_valeur():
    assert langues.arr_ui_language("klingon") is None


def test_toutes_les_langues_proposees_sont_connues_des_arr():
    """Proposer dans l'assistant une langue que les *arr refusent serait une
    promesse en l'air."""
    for lang in langues.PROPOSEES:
        assert langues.arr_ui_language(lang.code) is not None, lang.code


def test_le_pays_retombe_sur_le_code():
    """Jellyfin veut les deux. `fr` donne `FR`, ce qui est vrai bien plus
    souvent que faux et n'est jamais bloquant."""
    assert langues.resoudre("fr").pays == "FR"
    assert langues.resoudre("xx").pays == "XX"


# ----------------------------------------------------- le type depend de l'app


class _FauxArr(ArrClient):
    """Journalise les appels au lieu de les emettre."""

    def __init__(self, ui):
        self.name = "faux"
        self._ui = dict(ui)
        self.ecrits: list[dict] = []

    def get(self, resource):
        assert resource == "config/ui"
        return dict(self._ui)

    def put(self, resource, payload):
        self.ecrits.append(payload)
        self._ui = dict(payload)


def test_un_arr_a_entier_recoit_un_entier():
    client = _FauxArr({"id": 1, "uiLanguage": 1, "theme": "auto"})

    assert client.set_ui_language("fr", 2) is True
    assert client.ecrits[0]["uiLanguage"] == 2


def test_un_arr_a_chaine_recoit_une_chaine():
    """Prowlarr. Lui poser l'entier renvoie 400 : « The JSON value could not be
    converted to System.String »."""
    client = _FauxArr({"id": 1, "uiLanguage": "en", "theme": "auto"})

    assert client.set_ui_language("fr", 2) is True
    assert client.ecrits[0]["uiLanguage"] == "fr"


def test_le_reste_de_la_configuration_survit():
    """N'ecrire que ce champ effacerait le format de date, le theme et le reste."""
    client = _FauxArr({"id": 1, "uiLanguage": 1, "theme": "dark", "timeFormat": "HH:mm"})

    client.set_ui_language("fr", 2)

    assert client.ecrits[0]["theme"] == "dark"
    assert client.ecrits[0]["timeFormat"] == "HH:mm"


@pytest.mark.parametrize("actuel", [2, "fr"])
def test_une_langue_deja_posee_n_est_pas_reecrite(actuel):
    client = _FauxArr({"id": 1, "uiLanguage": actuel})

    assert client.set_ui_language("fr", 2) is False
    assert client.ecrits == []


# ------------------------------------------------------------- le cablage


def _cfg(langue, services=("sonarr", "prowlarr")):
    cfg = orchestrator.build_config(
        services=list(services), config_root="/c", data_root="/d", language=langue
    )
    return cfg


def test_une_etape_par_arr_quand_la_langue_est_connue():
    etapes = [e.name for e in Wirer(_cfg("fr")).build_plan() if e.name.endswith("/langue")]

    assert sorted(etapes) == ["prowlarr/langue", "sonarr/langue"]


def test_aucune_etape_quand_la_langue_est_inconnue():
    """Mieux vaut ne rien poser que poser n'importe quoi."""
    etapes = [e.name for e in Wirer(_cfg("klingon")).build_plan() if e.name.endswith("/langue")]

    assert etapes == []


def test_la_langue_atteint_la_configuration():
    assert _cfg("es").language == "es"


def test_le_defaut_reste_l_anglais_en_ligne_de_commande():
    """C'est le defaut des applications elles-memes. L'assistant, lui, propose
    le francais : il est en francais, qui le lit le comprend."""
    assert orchestrator.build_config(
        services=["sonarr"], config_root="/c", data_root="/d"
    ).language == "en"


# ------------------------------------------------------------- Jellyfin


def test_jellyfin_n_impose_plus_le_francais():
    """Le defaut etait code en dur dans la signature du client."""
    import inspect

    from arrsenal.clients.jellyfin import JellyfinClient

    signature = inspect.signature(JellyfinClient.run_startup_wizard)
    assert signature.parameters["ui_culture"].default == "en"
    assert signature.parameters["country"].default == "US"
    assert signature.parameters["metadata_language"].default == "en"
