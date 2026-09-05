"""PlugArr sait-il qu'une version plus recente de LUI-MEME existe ?

Signale a l'usage : « je viens de lancer la 0.6 et elle ne detecte pas la 0.7
pour se mettre a jour ».

C'etait juste, et le trou etait beant. La 0.6.0 a livre `plugarr upgrade`, qui
aligne les IMAGES des services sur le catalogue **du binaire en cours**. Elle
supposait donc qu'on avait deja telecharge le binaire du jour — et rien, nulle
part, ne le disait : `__version__` n'etait qu'affiche.

La verification est un CONFORT. PlugArr marche parfaitement hors ligne, et un
NAS derriere un pare-feu ne doit pas voir une erreur parce qu'il ne joint pas
GitHub. Tout echec rend « on ne sait pas », jamais « pas de mise a jour ».
"""

from __future__ import annotations

import httpx
import pytest

from plugarr import autoupdate


def _reponse(monkeypatch, *, statut=200, corps=None, leve=None):
    def faux_get(url, **kw):
        if leve is not None:
            raise leve
        return httpx.Response(
            statut,
            json=corps if corps is not None else {},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(autoupdate.httpx, "get", faux_get)


def _publiee(tag):
    return {"tag_name": tag, "html_url": f"https://exemple.invalid/{tag}"}


# ------------------------------------------------------------------ detection


def test_une_version_plus_recente_est_signalee(monkeypatch):
    """LE cas signale a l'usage."""
    monkeypatch.setattr(autoupdate, "__version__", "0.6.0")
    _reponse(monkeypatch, corps=_publiee("v0.7.0"))

    sortie = autoupdate.derniere()

    assert sortie.disponible == "0.7.0"
    assert sortie.url.endswith("v0.7.0")


def test_a_jour_ne_signale_rien(monkeypatch):
    monkeypatch.setattr(autoupdate, "__version__", "0.7.0")
    _reponse(monkeypatch, corps=_publiee("v0.7.0"))

    sortie = autoupdate.derniere()

    assert sortie.disponible is None
    assert sortie.a_jour is True


def test_on_ne_redescend_jamais(monkeypatch):
    """Quelqu'un qui construit depuis les sources peut avoir plus recent que la
    derniere release. Lui proposer de « mettre a jour » vers le passe serait
    faux."""
    monkeypatch.setattr(autoupdate, "__version__", "9.9.9")
    _reponse(monkeypatch, corps=_publiee("v0.7.0"))

    assert autoupdate.derniere().disponible is None


def test_la_comparaison_se_fait_sur_des_nombres(monkeypatch):
    """`0.10.0` est plus recent que `0.9.0`, ce que l'ordre alphabetique
    inverse."""
    monkeypatch.setattr(autoupdate, "__version__", "0.9.0")
    _reponse(monkeypatch, corps=_publiee("v0.10.0"))

    assert autoupdate.derniere().disponible == "0.10.0"


# ------------------------------------------------------ les echecs sont muets


@pytest.mark.parametrize(
    "cas",
    [
        {"leve": httpx.ConnectError("pas de reseau")},
        {"statut": 403},
        {"statut": 500},
        {"corps": {"pas_de_tag": True}},
    ],
)
def test_un_echec_ne_leve_jamais(monkeypatch, cas):
    """Une verification de confort qui fait tomber `upgrade` serait pire que
    pas de verification du tout."""
    monkeypatch.setattr(autoupdate, "__version__", "0.6.0")
    _reponse(monkeypatch, **cas)

    sortie = autoupdate.derniere()

    assert sortie.disponible is None
    assert sortie.probleme, "un echec doit se DIRE, pas se taire"


def test_un_echec_ne_se_lit_pas_comme_a_jour(monkeypatch):
    """C'est la nuance qui compte : « on ne sait pas » n'est pas « rien de
    neuf ». Les confondre laisserait quelqu'un sur une version perimee en
    croyant etre a jour."""
    monkeypatch.setattr(autoupdate, "__version__", "0.6.0")
    _reponse(monkeypatch, statut=403)

    assert autoupdate.derniere().a_jour is False


def test_le_quota_epuise_a_son_propre_message(monkeypatch):
    """403 sur l'API publique de GitHub veut presque toujours dire « 60
    requetes par heure atteintes », pas « interdit »."""
    monkeypatch.setattr(autoupdate, "__version__", "0.6.0")
    _reponse(monkeypatch, statut=403)

    assert "quota" in autoupdate.derniere().probleme


# ------------------------------------------------------------- les points d'usage


@pytest.mark.parametrize("commande", ["upgrade", "doctor"])
def test_les_commandes_de_maintenance_le_disent(commande):
    """Ce sont celles ou quelqu'un se demande « suis-je a jour ? »."""
    import inspect

    from plugarr import cli

    source = inspect.getsource(getattr(cli, commande))

    assert "_annoncer_nouvelle_version" in source


def test_upgrade_le_dit_AVANT_de_parler_des_images():
    """Aligner les services sur le catalogue d'un binaire perime n'a qu'un
    interet limite : l'utilisateur doit le savoir avant de lire le reste."""
    import inspect

    from plugarr import cli

    source = inspect.getsource(cli.upgrade)

    assert source.index("_annoncer_nouvelle_version") < source.index("pack.ecarts")


def test_la_console_verifie_aussi_plugarr(monkeypatch):
    """Le bouton « chercher les mises a jour » ne regardait que les images des
    services : on pouvait tout avoir a jour sauf l'outil qui le dit."""
    from plugarr import admin, orchestrator

    monkeypatch.setattr(autoupdate, "__version__", "0.6.0")
    _reponse(monkeypatch, corps=_publiee("v0.7.0"))
    monkeypatch.setattr(admin.updates, "check", lambda cfg: [])

    cfg = orchestrator.build_config(services=["sonarr"], config_root="/c", data_root="/d")
    charge = admin.updates_payload(cfg)

    assert charge["plugarr"]["available"] is True
    assert charge["plugarr"]["latest"] == "0.7.0"
    assert charge["plugarr"]["current"] == "0.6.0"


def test_la_release_visee_est_la_bonne():
    """`/releases/latest` ignore d'office brouillons et preversions : on ne
    pousse personne vers une version d'essai."""
    assert autoupdate.LATEST.endswith("/releases/latest")
    assert "yannickuhrig1/plugarr" in autoupdate.LATEST


def test_le_numero_affiche_est_celui_qui_a_ete_COMPARE(capsys, monkeypatch):
    """Le message annoncait « vous avez la 0.7.0 » a quelqu'un en 0.6.0.

    `cli` et `autoupdate` lisaient chacun leur propre `__version__` : deux
    lectures separees qui peuvent diverger. Le resultat porte desormais la
    version a laquelle la comparaison a ete faite, et c'est elle qu'on affiche.

    Trouve en lisant le message produit, pas en relisant le code.
    """
    from plugarr import cli

    monkeypatch.setattr(autoupdate, "__version__", "0.6.0")
    _reponse(monkeypatch, corps=_publiee("v0.7.0"))

    cli._annoncer_nouvelle_version()

    sortie = capsys.readouterr().out
    assert "0.7.0" in sortie
    assert "0.6.0" in sortie, "la version de l'utilisateur doit etre la sienne"
