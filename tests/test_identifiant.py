"""Tests du choix de l'identifiant.

Demande a l'usage : « pas tout le monde veut mettre plugarr comme username ».

Ce nom traverse cinq applications differentes — un XML, un INI, un JSON, un
formulaire de connexion et une ligne de commande de conteneur — et ne peut plus
etre change sans tout reinstaller. D'ou une forme contrainte, mais contrainte
sur ce qui est REELLEMENT risque.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from plugarr import seed
from plugarr.models import StackConfig
from plugarr.orchestrator import build_config


def _cfg(tmp_path, **kw):
    return build_config(
        services=["sonarr", "qbittorrent", "transmission", "jellyfin"],
        config_root=str(tmp_path / "c"),
        data_root=str(tmp_path / "d"),
        **kw,
    )


def test_le_defaut_reste_plugarr(tmp_path):
    cfg = _cfg(tmp_path)
    assert cfg.username == "plugarr"
    assert all(inst.username == "plugarr" for inst in cfg.services.values())


def test_le_choix_atteint_tous_les_services(tmp_path):
    """Un seul identifiant pour toute la stack : c'est ce qui rend la page
    d'acces lisible."""
    cfg = _cfg(tmp_path, username="yannick")

    assert cfg.username == "yannick"
    assert {inst.username for inst in cfg.services.values()} == {"yannick"}


@pytest.mark.parametrize("nom", ["y", "ab", "yannick", "jean.dupont", "jean-d", "jean_d", "a" * 32])
def test_les_identifiants_raisonnables_passent(nom):
    """Deux caracteres suffisent : verifie contre qBittorrent 5.2.3, qui accepte
    « ab » et repond 204 a la connexion. Imposer trois aurait ete arbitraire."""
    assert StackConfig(config_root="c", data_root="d", username=nom).username == nom


@pytest.mark.parametrize(
    "nom",
    ["", "   ", "jean dupont", "jean@maison", "jean/dupont", "a" * 33, "jean\ttab", "élise"],
)
def test_les_identifiants_risques_sont_refuses(nom):
    with pytest.raises(ValidationError):
        StackConfig(config_root="c", data_root="d", username=nom)


def test_le_message_d_erreur_dit_quoi_faire():
    with pytest.raises(ValidationError) as exc:
        StackConfig(config_root="c", data_root="d", username="jean dupont")

    message = str(exc.value)
    assert "lettres, chiffres" in message
    assert "sans espace" in message


def test_les_espaces_autour_sont_retirees():
    assert StackConfig(config_root="c", data_root="d", username="  yannick ").username == "yannick"


# --------------------------------------------------- jusque dans les fichiers


def test_l_identifiant_choisi_arrive_dans_le_config_xml(tmp_path):
    xml = seed.render_arr_config(
        api_key="a" * 32,
        port=8989,
        instance_name="Sonarr",
        username="yannick",
        password="MotDePasse1!",
    )
    assert "<Username>yannick</Username>" in xml


def test_l_identifiant_choisi_arrive_dans_qbittorrent(tmp_path):
    seed.seed_qbittorrent(tmp_path, username="yannick", password="MotDePasse1!")
    conf = (tmp_path / "qBittorrent" / "qBittorrent.conf").read_text(encoding="utf-8")

    assert r"WebUI\Username=yannick" in conf


def test_l_identifiant_choisi_arrive_dans_le_env(tmp_path):
    from plugarr import compose

    env = compose.render_env(_cfg(tmp_path, username="yannick"))

    assert "SONARR_USER='yannick'" in env
    assert "QBITTORRENT_USER='yannick'" in env


def test_il_survit_a_un_aller_retour_par_stack_yml(tmp_path):
    """`wire` relit stack.yml : un identifiant perdu la casserait le cablage."""
    import yaml

    from plugarr import compose

    cfg = _cfg(tmp_path, username="yannick")
    compose.write_artifacts(cfg, tmp_path)
    relu = StackConfig.model_validate(
        yaml.safe_load((tmp_path / "stack.yml").read_text(encoding="utf-8"))
    )

    assert relu.username == "yannick"
    assert relu.services["sonarr"].username == "yannick"
