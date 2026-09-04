"""Lancement automatique de la console, sur l'hote.

Pas dans un conteneur, et ce n'est pas un detail de mise en oeuvre. La console
doit creer, demarrer et recreer des conteneurs — soit `POST /containers/create`
puis `/start`. Or un conteneur qu'on cree peut monter la racine de l'hote et
tourner en root : un proxy de socket qui autorise ces deux appels n'enferme
rien, et sans eux la console ne sert plus a rien.

Sur l'hote, elle tourne sous le compte de l'utilisateur, ecoute sur 127.0.0.1
et reste hors du reseau Docker. Le confort recherche est le meme.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugarr import autostart

# ------------------------------------------------------------------ commande


def test_la_commande_vise_le_bon_repertoire(tmp_path):
    ligne = autostart.commande(tmp_path, host="127.0.0.1", port=7373)

    assert str(tmp_path.resolve()) in ligne
    assert "serve" in ligne


def test_la_commande_n_ouvre_pas_de_navigateur(tmp_path):
    """Ouvrir un navigateur a chaque ouverture de session serait insupportable."""
    assert "--no-open" in autostart.commande(tmp_path, host="127.0.0.1", port=7373)


def test_la_commande_reprend_l_interpreteur_courant(tmp_path):
    """Quelqu'un qui a double-clique un executable n'a pas `plugarr` dans son
    PATH : lui dire « lancez plugarr serve » ne l'avance a rien."""
    import sys

    assert str(Path(sys.executable).resolve()) in autostart.commande(
        tmp_path, host="127.0.0.1", port=7373
    )


def test_l_adresse_et_le_port_sont_repris(tmp_path):
    ligne = autostart.commande(tmp_path, host="0.0.0.0", port=9999)

    assert "--host 0.0.0.0" in ligne
    assert "--port 9999" in ligne


def test_un_chemin_avec_espaces_est_protege(tmp_path):
    """« Arr auto install » contient des espaces : sans guillemets, la commande
    se coupe en deux au demarrage."""
    dossier = tmp_path / "un dossier avec espaces"
    dossier.mkdir()

    ligne = autostart.commande(dossier, host="127.0.0.1", port=7373)

    assert f'"{dossier.resolve()}"' in ligne


# ------------------------------------------------------------------- Windows


@pytest.fixture
def demarrage_windows(tmp_path, monkeypatch):
    """Simule Windows, avec un dossier Demarrage jetable."""
    monkeypatch.setattr(autostart.sys, "platform", "win32")
    dossier = tmp_path / "Startup"
    monkeypatch.setattr(autostart, "_dossier_demarrage", lambda: dossier)
    return dossier


def test_windows_pose_un_script_dans_le_dossier_demarrage(demarrage_windows, tmp_path):
    ok, message = autostart.enable(tmp_path, host="127.0.0.1", port=7373)

    cible = demarrage_windows / "plugarr-console.cmd"
    assert ok
    assert cible.is_file()
    assert str(cible) in message


def test_le_script_windows_est_lisible_et_explique_comment_le_retirer(
    demarrage_windows, tmp_path
):
    """Il atterrit dans le dossier Demarrage de quelqu'un : il doit dire d'ou il
    vient et comment s'en debarrasser."""
    autostart.enable(tmp_path, host="127.0.0.1", port=7373)
    contenu = (demarrage_windows / "plugarr-console.cmd").read_text(encoding="utf-8")

    assert "plugarr autostart" in contenu
    assert "Supprimez ce fichier" in contenu
    assert "serve" in contenu


def test_windows_signale_l_etat(demarrage_windows, tmp_path):
    assert autostart.status(tmp_path).actif is False

    autostart.enable(tmp_path, host="127.0.0.1", port=7373)

    etat = autostart.status(tmp_path)
    assert etat.actif is True
    assert etat.mecanisme == "demarrage-windows"


def test_windows_retire_le_script(demarrage_windows, tmp_path):
    autostart.enable(tmp_path, host="127.0.0.1", port=7373)

    ok, _message = autostart.disable(tmp_path)

    assert ok
    assert not (demarrage_windows / "plugarr-console.cmd").exists()
    assert autostart.status(tmp_path).actif is False


def test_retirer_ce_qui_n_existe_pas_n_est_pas_une_erreur(demarrage_windows, tmp_path):
    ok, message = autostart.disable(tmp_path)

    assert ok
    assert "aucun" in message.lower()


def test_reinstaller_ecrase_sans_broncher(demarrage_windows, tmp_path):
    autostart.enable(tmp_path, host="127.0.0.1", port=7373)
    ok, _message = autostart.enable(tmp_path, host="127.0.0.1", port=8888)

    contenu = (demarrage_windows / "plugarr-console.cmd").read_text(encoding="utf-8")
    assert ok
    assert "--port 8888" in contenu
    assert "--port 7373" not in contenu


# ------------------------------------------------------------------ systemd


def test_l_unite_systemd_a_la_forme_attendue(tmp_path):
    unite = autostart._unite_systemd("/bin/plugarr serve", tmp_path)

    assert "[Unit]" in unite and "[Service]" in unite and "[Install]" in unite
    assert "ExecStart=/bin/plugarr serve" in unite
    # Sans redemarrage, une console tombee reste tombee jusqu'a la prochaine
    # ouverture de session.
    assert "Restart=on-failure" in unite
    assert "After=docker.service" in unite


# ----------------------------------------------------- plateforme inconnue


def test_une_plateforme_inconnue_rend_la_commande_a_coller(tmp_path, monkeypatch):
    """Unraid n'a pas de systemd. Inventer un mecanisme non verifie serait pire
    que de rendre la main."""
    monkeypatch.setattr(autostart.sys, "platform", "freebsd")
    monkeypatch.setattr(autostart.shutil, "which", lambda _nom: None)

    ok, message = autostart.enable(tmp_path, host="127.0.0.1", port=7373)

    assert ok is False
    assert "serve" in message
    assert str(tmp_path.resolve()) in message


def test_une_plateforme_inconnue_ne_pretend_pas_avoir_installe(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart.sys, "platform", "freebsd")
    monkeypatch.setattr(autostart.shutil, "which", lambda _nom: None)

    assert autostart.status(tmp_path).actif is False
    assert autostart.mecanisme() == "aucun"
