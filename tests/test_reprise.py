"""Reinstaller par-dessus une installation existante sans tout perdre.

Demande a l'usage : « quand on installe PlugArr par-dessus une ancienne
installation, il faudrait proposer de garder les parametres deja existants ».

En regardant, c'etait pire que « pas propose ». `install` construisait sa
configuration de zero et **ne lisait jamais le `stack.yml` deja present**.
Mesure sur une installation d'essai :

    identifiant          yannick        -> plugarr
    VPN                  mullvad + cle  -> DESACTIVE
    profils Recyclarr    choisis        -> vides
    mot de passe console pose           -> perdu

Le VPN est le cas grave : il disparaissait **en silence**, et l'installation
affichait « Aucun VPN n'est configure ». Quelqu'un qui reinstalle pour reparer
autre chose se retrouvait avec son trafic torrent en clair.
"""

from __future__ import annotations

import yaml

from plugarr import orchestrator, reprise
from plugarr.models import VpnConfig


def _ancienne(tmp_path, **extra):
    cfg = orchestrator.build_config(
        services=["sonarr", "qbittorrent"],
        config_root=str(tmp_path / "config"),
        data_root=str(tmp_path / "data"),
        username="yannick",
    )
    cfg.vpn = VpnConfig(
        enabled=True,
        provider="mullvad",
        vpn_type="wireguard",
        wireguard_private_key="MA-CLE-A-MOI",
        countries="Switzerland",
    )
    cfg.recyclarr_templates = {"sonarr": "french-multi-vf-bluray-web-1080p"}
    cfg.admin_password_hash = "pbkdf2:empreinte"
    for champ, valeur in extra.items():
        setattr(cfg, champ, valeur)
    (tmp_path / "stack.yml").write_text(
        yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
    )
    return cfg


def _neuve(tmp_path):
    return orchestrator.build_config(
        services=["sonarr", "qbittorrent"],
        config_root=str(tmp_path / "config"),
        data_root=str(tmp_path / "data"),
    )


# ----------------------------------------------------------------- la lecture


def test_sans_installation_precedente_il_n_y_a_rien_a_reprendre(tmp_path):
    assert reprise.precedente(tmp_path) is None


def test_un_stack_illisible_n_arrete_pas_une_installation_neuve(tmp_path):
    """Repartir de zero est exactement ce que l'utilisateur a demande."""
    (tmp_path / "stack.yml").write_text("ceci n'est pas du yaml valide : [", encoding="utf-8")

    assert reprise.precedente(tmp_path) is None


def test_un_stack_venu_du_futur_remonte(tmp_path):
    """Celui-la ne doit PAS etre avale : le refuser est tout l'interet du
    garde-fou de `migrations`."""
    import pytest

    from plugarr import migrations

    cfg = _ancienne(tmp_path)
    donnees = cfg.model_dump(mode="json")
    donnees["version"] = migrations.VERSION_COURANTE + 1
    (tmp_path / "stack.yml").write_text(yaml.safe_dump(donnees), encoding="utf-8")

    with pytest.raises(migrations.VersionFuture):
        reprise.precedente(tmp_path)


# --------------------------------------------------------------- les reglages


def test_le_vpn_survit_a_une_reinstallation(tmp_path):
    """LE cas grave. Sans cette reprise, le tunnel disparait en silence et le
    trafic torrent sort en clair."""
    ancienne = _ancienne(tmp_path)
    neuve = _neuve(tmp_path)
    assert neuve.vpn.enabled is False

    reprise.appliquer(neuve, ancienne)

    assert neuve.vpn.enabled is True
    assert neuve.vpn.provider == "mullvad"
    assert neuve.vpn.wireguard_private_key == "MA-CLE-A-MOI"
    assert neuve.vpn.countries == "Switzerland"


def test_le_vpn_se_reprend_EN_BLOC(tmp_path):
    """Reprendre le fournisseur sans la cle donnerait une configuration
    incomplete, que Gluetun refuserait au demarrage."""
    ancienne = _ancienne(tmp_path)
    neuve = _neuve(tmp_path)

    reprise.appliquer(neuve, ancienne)

    assert neuve.vpn.missing() == []


def test_les_reglages_choisis_sont_repris(tmp_path):
    ancienne = _ancienne(tmp_path)
    neuve = _neuve(tmp_path)

    rapport = reprise.appliquer(neuve, ancienne)

    assert neuve.username == "yannick"
    assert neuve.admin_password_hash == "pbkdf2:empreinte"
    assert neuve.recyclarr_templates == {"sonarr": "french-multi-vf-bluray-web-1080p"}
    assert rapport.reglages, "la reprise doit se dire, pas se faire en silence"


def test_une_option_donnee_a_la_main_prime(tmp_path):
    """Sinon elle serait sans effet, et personne ne comprendrait pourquoi."""
    ancienne = _ancienne(tmp_path)
    neuve = _neuve(tmp_path)
    neuve.username = "bob"

    reprise.appliquer(neuve, ancienne, imposes={"username"})

    assert neuve.username == "bob"


def test_le_vpn_donne_a_la_main_prime_aussi(tmp_path):
    ancienne = _ancienne(tmp_path)
    neuve = _neuve(tmp_path)
    neuve.vpn = VpnConfig(
        enabled=True, provider="protonvpn", vpn_type="wireguard", wireguard_private_key="AUTRE"
    )

    reprise.appliquer(neuve, ancienne, imposes={"vpn"})

    assert neuve.vpn.provider == "protonvpn"


def test_ce_qui_n_est_pas_un_reglage_herite_n_est_pas_repris(tmp_path):
    """La selection de services et les racines sont les reponses de
    l'installation EN COURS, pas un heritage."""
    ancienne = _ancienne(tmp_path)
    neuve = orchestrator.build_config(
        services=["radarr"],
        config_root=str(tmp_path / "autre"),
        data_root=str(tmp_path / "autres-donnees"),
    )

    reprise.appliquer(neuve, ancienne)

    assert set(neuve.services) >= {"radarr"}
    assert "sonarr" not in neuve.services
    assert neuve.config_root == str(tmp_path / "autre")


# ------------------------------------------------------------ les identifiants


def test_les_mots_de_passe_precedents_sont_repris(tmp_path):
    """C'est ce qui repare le defaut le plus ancien du lot.

    qBittorrent, Jellyfin, autobrr et les autres ne stockent leur mot de passe
    que HACHE : PlugArr ne peut pas le relire, en generait un nouveau,
    l'annoncait, et le service le refusait. Mais quand c'est PlugArr qui a
    installe, le mot de passe est dans SON stack.yml.
    """
    ancienne = _ancienne(tmp_path)
    neuve = _neuve(tmp_path)
    assert neuve.services["qbittorrent"].password != ancienne.services["qbittorrent"].password

    reprise.appliquer(neuve, ancienne)

    assert neuve.services["qbittorrent"].password == ancienne.services["qbittorrent"].password


def test_les_cles_api_precedentes_sont_reprises(tmp_path):
    ancienne = _ancienne(tmp_path)
    neuve = _neuve(tmp_path)

    reprise.appliquer(neuve, ancienne)

    assert neuve.services["sonarr"].api_key == ancienne.services["sonarr"].api_key


def test_un_port_decale_a_la_main_est_conserve(tmp_path):
    """Quelqu'un qui a decale qBittorrent pour eviter un conflit ne veut pas le
    retrouver sur 8080."""
    ancienne = _ancienne(tmp_path)
    ancienne.services["qbittorrent"].host_port = 18080
    neuve = _neuve(tmp_path)

    reprise.appliquer(neuve, ancienne)

    assert neuve.services["qbittorrent"].host_port == 18080


def test_un_service_absent_de_l_ancienne_garde_ses_valeurs_neuves(tmp_path):
    ancienne = _ancienne(tmp_path)
    neuve = orchestrator.build_config(
        services=["sonarr", "radarr"],
        config_root=str(tmp_path / "config"),
        data_root=str(tmp_path / "data"),
    )
    radarr_avant = neuve.services["radarr"].api_key

    rapport = reprise.appliquer(neuve, ancienne)

    assert neuve.services["radarr"].api_key == radarr_avant
    assert "radarr" not in rapport.services


# ----------------------------------------------------------------- la commande


def test_la_reprise_est_active_par_defaut():
    """Perdre un VPN en silence est pire que reprendre sans demander, et le
    projet conserve deja par defaut ailleurs."""
    import inspect

    from plugarr import cli

    signature = inspect.signature(cli.install)

    assert signature.parameters["reprendre"].default.default is True


def test_la_reprise_precede_le_recapitulatif():
    """Le recapitulatif doit montrer ce qui sera REELLEMENT pose. Reprendre
    apres reviendrait a annoncer une chose et a en ecrire une autre."""
    import inspect

    from plugarr import cli

    source = inspect.getsource(cli.install)

    assert source.index("reprise_mod.appliquer") < source.index("print_summary")
