"""Tests de la reinstallation sur une configuration existante.

Signale a l'usage. Relancer `install` en visant un `config_root` deja utilise
donnait une stack ou RIEN ne fonctionnait, avec des messages incomprehensibles :
« reponse illisible sur les categories », « HTTP 401 », « l'API d'autobrr a
peut-etre change de forme ».

La cause tenait en une phrase : arrsenal gardait les configurations existantes
mais generait de nouveaux mots de passe, qu'il annoncait dans son rapport. Les
services refusaient donc les identifiants affiches a l'utilisateur.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

from arrsenal import orchestrator, seed


def _conf_qbittorrent(chemin: Path, mot_de_passe: str, extra: str = "") -> Path:
    dossier = chemin / "qBittorrent"
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / "qBittorrent.conf"
    fichier.write_text(
        seed.render_qbittorrent_conf(username="ancien", password=mot_de_passe) + extra,
        encoding="utf-8",
    )
    return fichier


def _hash_correspond(fichier: Path, mot_de_passe: str) -> bool:
    brut = re.search(r"WebUI.Password_PBKDF2=(.*)", fichier.read_text(encoding="utf-8"))
    sel_b64, empreinte_b64 = brut.group(1).strip()[len("@ByteArray(") : -1].split(":")
    recalcul = hashlib.pbkdf2_hmac(
        "sha512", mot_de_passe.encode(), base64.b64decode(sel_b64), 100000, dklen=64
    )
    return recalcul == base64.b64decode(empreinte_b64)


# ------------------------------------------------------------- qBittorrent


def test_le_mot_de_passe_annonce_devient_le_vrai(tmp_path):
    fichier = _conf_qbittorrent(tmp_path, "AncienMotDePasse1!")
    assert _hash_correspond(fichier, "AncienMotDePasse1!")

    _ecrit, message = seed.seed_qbittorrent(tmp_path, username="arrsenal", password="Nouveau2@")

    assert "mis a jour" in message
    assert _hash_correspond(fichier, "Nouveau2@")
    assert not _hash_correspond(fichier, "AncienMotDePasse1!")


def test_les_autres_reglages_sont_preserves(tmp_path):
    """L'utilisateur a pu regler des dizaines d'options : on ne touche qu'aux deux
    lignes d'identification."""
    marqueur = "Preferences\\Downloads\\SavePath=D:/a-moi\n"
    fichier = _conf_qbittorrent(tmp_path, "Ancien1!", extra=marqueur)

    seed.seed_qbittorrent(tmp_path, username="arrsenal", password="Nouveau2@")
    apres = fichier.read_text(encoding="utf-8")

    assert marqueur.strip() in apres
    assert "WebUI\\Username=arrsenal" in apres


def test_un_fichier_sans_ligne_de_mot_de_passe_recoit_la_cle(tmp_path):
    dossier = tmp_path / "qBittorrent"
    dossier.mkdir(parents=True)
    (dossier / "qBittorrent.conf").write_text("[Preferences]\nAutre=1\n", encoding="utf-8")

    seed.seed_qbittorrent(tmp_path, username="arrsenal", password="Nouveau2@")

    assert _hash_correspond(dossier / "qBittorrent.conf", "Nouveau2@")


# ------------------------------------------------------------- Transmission


def test_les_identifiants_rpc_sont_mis_a_jour(tmp_path):
    """Transmission stocke le mot de passe hache apres son premier demarrage.
    Le reecrire en clair est la facon prevue de le changer."""
    fichier = tmp_path / "settings.json"
    fichier.write_text(
        json.dumps({"rpc-username": "ancien", "rpc-password": "{HACHE", "download-dir": "/a-moi"}),
        encoding="utf-8",
    )

    _ecrit, message = seed.seed_transmission(
        tmp_path, rpc_username="arrsenal", rpc_password="Nouveau2@"
    )
    reglages = json.loads(fichier.read_text(encoding="utf-8"))

    assert "mis a jour" in message
    assert reglages["rpc-username"] == "arrsenal"
    assert reglages["rpc-password"] == "Nouveau2@"
    assert reglages["rpc-authentication-required"] is True
    # Le reste du fichier appartient a l'utilisateur.
    assert reglages["download-dir"] == "/a-moi"


def test_un_settings_illisible_est_laisse_tranquille(tmp_path):
    fichier = tmp_path / "settings.json"
    fichier.write_text("{pas du json", encoding="utf-8")

    ecrit, message = seed.seed_transmission(tmp_path, rpc_username="a", rpc_password="b")

    assert not ecrit and "illisible" in message
    assert fichier.read_text(encoding="utf-8") == "{pas du json"


# ------------------------------------------------------------------ preflight


def _cfg(tmp_path, services):
    return orchestrator.build_config(
        services=services,
        config_root=str(tmp_path / "config"),
        data_root=str(tmp_path / "data"),
    )


def test_une_installation_neuve_ne_declenche_aucun_avertissement(tmp_path):
    controle = orchestrator.check_existing_config(_cfg(tmp_path, ["sonarr", "jellyfin"]))

    assert controle.ok
    assert "neuve" in controle.detail


def test_une_configuration_a_mot_de_passe_hache_est_signalee(tmp_path):
    """Jellyfin, autobrr et qui ne peuvent pas etre repris : leur mot de passe
    n'existe que hache, et aucune API ne permet de le reinitialiser sans lui."""
    cfg = _cfg(tmp_path, ["sonarr", "jellyfin"])
    dossier = Path(cfg.config_path("jellyfin"))
    dossier.mkdir(parents=True)
    (dossier / "data.db").write_text("x", encoding="utf-8")

    controle = orchestrator.check_existing_config(cfg)

    assert not controle.ok
    assert "jellyfin" in controle.detail
    assert "--project-dir" in controle.detail
    # Non bloquant : c'est un avertissement, pas un refus d'installer.
    assert not controle.blocking


def test_une_configuration_arr_seule_ne_bloque_pas(tmp_path):
    """La cle API d'un *arr est relue dans son config.xml : ce cas-la est gere."""
    cfg = _cfg(tmp_path, ["sonarr"])
    dossier = Path(cfg.config_path("sonarr"))
    dossier.mkdir(parents=True)
    (dossier / "config.xml").write_text("<Config/>", encoding="utf-8")

    controle = orchestrator.check_existing_config(cfg)

    assert controle.ok
    assert "sonarr" in controle.detail


def test_un_dossier_vide_ne_compte_pas(tmp_path):
    cfg = _cfg(tmp_path, ["jellyfin"])
    Path(cfg.config_path("jellyfin")).mkdir(parents=True)

    assert orchestrator.check_existing_config(cfg).ok
