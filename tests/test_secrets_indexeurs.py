"""Une cle d'indexeur ne doit ni s'afficher en clair, ni finir au journal.

Prowlarr RENVOIE l'URL complete de son appel echoue, parametres compris. Sur un
tracker reel, l'ajout d'un indexeur avec une mauvaise cle produit :

    HTTP request failed: [401:Unauthorized] [GET] at
    [https://exemple.org/api/torznab?apikey=<la cle>&t=search&l

Cette cle est celle que l'utilisateur vient de taper. plugarr ne la stocke
jamais, donc le masquage par valeur connue ne pouvait rien pour elle : elle
s'affichait a l'ecran et partait dans le fichier qu'on demande aux gens de
joindre a un rapport de bug.
"""

from __future__ import annotations

import pytest

from plugarr import journal
from plugarr.clients.prowlarr import IndexerDefinition, is_secret, redact

CLE = "71e0869061f6f8452024f6fc2d8c35ca"
MESSAGE = (
    "Unable to connect: to indexer. HTTP request failed: [401:Unauthorized] [GET] at "
    f"[https://exemple.org/api/torznab?apikey={CLE}&t=search&cat=100"
)


# ------------------------------------------------------------------ affichage


def test_la_cle_disparait_du_message_affiche():
    caviarde = redact(MESSAGE)

    assert CLE not in caviarde
    assert "apikey=..." in caviarde
    # Le reste du diagnostic doit survivre : sans lui le message ne sert a rien.
    assert "401:Unauthorized" in caviarde
    assert "exemple.org" in caviarde


@pytest.mark.parametrize(
    "parametre", ["apikey", "api_key", "passkey", "rsskey", "authkey", "token", "digest"]
)
def test_les_autres_noms_de_parametre_sont_couverts(parametre):
    assert CLE not in redact(f"at [https://x/api?{parametre}={CLE}&t=search")


def test_une_url_sans_secret_reste_intacte():
    """Caviarder plus que necessaire rendrait le diagnostic illisible."""
    url = "at [https://exemple.org/api/torznab?t=search&cat=100&limit=20"

    assert redact(url) == url


# -------------------------------------------------------------------- journal


def test_la_cle_disparait_du_journal(tmp_path):
    journal.start(tmp_path, "test")
    journal.LOGGER.error("ajout impossible : %s", MESSAGE)
    for handler in journal.LOGGER.handlers:
        handler.flush()

    contenu = (tmp_path / journal.FILENAME).read_text(encoding="utf-8")
    assert CLE not in contenu
    assert "<masque>" in contenu


def test_la_cle_disparait_aussi_de_la_TRACE(tmp_path):
    """Un filtre de `logging` ne voit que le message. La trace est mise en forme
    plus tard et echappait entierement au masquage — alors que c'est justement
    la qu'atterrit le texte d'erreur d'un service tiers."""
    journal.start(tmp_path, "test")
    try:
        raise RuntimeError(MESSAGE)
    except RuntimeError:
        journal.LOGGER.exception("ajout de l'indexeur %s", "C411")
    for handler in journal.LOGGER.handlers:
        handler.flush()

    contenu = (tmp_path / journal.FILENAME).read_text(encoding="utf-8")
    assert "Traceback" in contenu, "la trace doit bien etre ecrite"
    assert CLE not in contenu


def test_le_masquage_par_valeur_connue_fonctionne_toujours(tmp_path):
    """La regle de forme complete le masquage exact, elle ne le remplace pas."""
    journal.start(tmp_path, "test")
    journal._MASKER.remember("cle-api-sonarr", "abcdef0123456789")
    journal.LOGGER.info("cle utilisee : abcdef0123456789")
    for handler in journal.LOGGER.handlers:
        handler.flush()

    contenu = (tmp_path / journal.FILENAME).read_text(encoding="utf-8")
    assert "abcdef0123456789" not in contenu
    assert "<cle-api-sonarr>" in contenu


# ---------------------------------------------------------------- saisie a l'ecran


def test_un_champ_apikey_non_marque_est_quand_meme_masque():
    """C411 expose `apikey` en `type: textbox` sans `privacy` : la cle se
    tapait EN CLAIR a l'ecran, visible de quiconque passait derriere."""
    assert is_secret({"name": "apikey", "type": "textbox"}) is True
    assert is_secret({"name": "passkey", "type": "textbox"}) is True
    assert is_secret({"name": "cookie", "type": "textbox"}) is True


def test_un_champ_ordinaire_reste_visible():
    """Masquer l'URL de base n'aurait aucun sens et generait la saisie."""
    assert is_secret({"name": "baseUrl", "type": "select"}) is False
    assert is_secret({"name": "username", "type": "textbox"}) is False


def test_le_marqueur_de_prowlarr_reste_prioritaire():
    assert is_secret({"name": "quoi", "type": "password"}) is True
    assert is_secret({"name": "quoi", "privacy": "apiKey"}) is True


def test_la_definition_reelle_de_c411_masque_sa_cle():
    """Forme exacte relevee dans le Prowlarr 2.5.2 de l'utilisateur."""
    c411 = IndexerDefinition(
        name="C411",
        implementation="Cardigann",
        privacy="private",
        protocol="torrent",
        language="fr-FR",
        description="",
        raw={
            "indexerUrls": ["https://c411.org/"],
            "fields": [
                {"name": "baseUrl", "type": "select", "label": "Base Url", "value": None},
                {"name": "apikey", "type": "textbox", "label": "API Key"},
            ],
        },
    )
    champs = {c.name: c.secret for c in c411.editable_fields()}

    assert champs == {"baseUrl": False, "apikey": True}


@pytest.fixture(autouse=True)
def _journal_propre():
    yield
    for handler in list(journal.LOGGER.handlers):
        handler.close()
    journal.LOGGER.handlers.clear()
    journal._MASKER._secrets.clear()
