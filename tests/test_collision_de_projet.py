"""Deux installations qui partagent un nom de projet partagent leurs conteneurs.

Panne reelle, provoquee en installant une pile d'essai a cote d'une pile en
service. Les deux portaient le nom par defaut `arrsenal` :

    docker compose -p arrsenal up   depuis C:/tmp/essai
    -> les six conteneurs de C:/arrsenal sont RECREES, pointant vers C:/tmp/essai

Docker identifie une pile par un LABEL de projet, jamais par le repertoire d'ou
elle est lancee. Les fichiers de la premiere installation restent intacts, mais
ses services repartent sur la configuration de la seconde, et rien ne le dit.

Pire, le preflight rassurait : « port 8090 occupe par votre propre pile
arrsenal ». C'etait vrai du nom et faux de l'installation.
"""

from __future__ import annotations

from pathlib import Path

from arrsenal import orchestrator


def _cfg():
    return orchestrator.build_config(services=["sonarr"], config_root="/c", data_root="/d")


def test_une_pile_ailleurs_est_signalee(monkeypatch):
    monkeypatch.setattr(orchestrator, "running_project_dir", lambda nom: "C:/arrsenal")

    check = orchestrator.check_project_collision(_cfg(), Path("C:/tmp/essai"))

    assert check is not None
    assert not check.ok
    assert "C:/arrsenal" in check.detail or "C:\arrsenal" in check.detail


def test_se_reinstaller_soi_meme_ne_dit_rien(monkeypatch):
    """Le cas normal : rejouer une installation sur sa propre pile."""
    monkeypatch.setattr(orchestrator, "running_project_dir", lambda nom: "C:/arrsenal")

    assert orchestrator.check_project_collision(_cfg(), Path("C:/arrsenal")) is None


def test_aucune_pile_en_marche_ne_dit_rien(monkeypatch):
    monkeypatch.setattr(orchestrator, "running_project_dir", lambda nom: None)

    assert orchestrator.check_project_collision(_cfg(), Path("C:/arrsenal")) is None


def test_l_avertissement_ne_bloque_pas(monkeypatch):
    """Ecraser sa propre pile est parfois voulu. On previent, on n'interdit pas."""
    monkeypatch.setattr(orchestrator, "running_project_dir", lambda nom: "C:/ailleurs")

    check = orchestrator.check_project_collision(_cfg(), Path("C:/ici"))

    assert check is not None and not check.blocking


def test_le_preflight_le_porte(monkeypatch):
    """Le controle doit atteindre l'utilisateur, pas seulement exister."""
    monkeypatch.setattr(orchestrator, "running_project_dir", lambda nom: "C:/ailleurs")
    monkeypatch.setattr(orchestrator, "check_docker", list)
    monkeypatch.setattr(orchestrator, "our_published_ports", lambda cfg, d: set())

    noms = [c.name for c in orchestrator.preflight(_cfg(), Path("C:/ici"))]

    assert "nom de projet" in noms


def test_le_nom_de_la_pile_se_choisit():
    """Sans cette option, deux piles sur une machine etaient impossibles : le
    nom etait fige a `arrsenal`, et la seconde installation emportait la
    premiere. C'est ce qui est arrive."""
    from arrsenal import orchestrator as o

    cfg = o.build_config(
        services=["sonarr"], config_root="/c", data_root="/d", project_name="arrsenal-essai"
    )

    assert cfg.project_name == "arrsenal-essai"


def test_les_conteneurs_portent_ce_nom():
    """Le nom doit atteindre les conteneurs, sinon il ne protege de rien."""
    from arrsenal import compose
    from arrsenal import orchestrator as o

    cfg = o.build_config(
        services=["sonarr"], config_root="/c", data_root="/d", project_name="arrsenal-essai"
    )
    doc = compose.build_compose(cfg)

    assert doc["name"] == "arrsenal-essai"
    assert doc["services"]["sonarr"]["container_name"] == "arrsenal-essai-sonarr"
