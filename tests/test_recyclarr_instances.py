"""Deux fichiers pour un meme service : une panne totale, et muette.

Recyclarr groupe ses instances par `base_url` et **ecarte tout groupe qui en
compte plus d'une** — c'est `SplitInstancesFilter`, lu dans son code source.
plugarr ecrit toujours la meme URL interne pour un service donne : deux
fichiers visant Sonarr sont donc deux instances sur la meme URL, et Recyclarr
n'en synchronise AUCUNE. Pas « la derniere gagne » : plus rien.

Constate sur une stack reelle, ou deux installations successives avec des
profils differents avaient laisse quatre fichiers :

    [DBG] Split instances: [{"BaseUrl":"http://sonarr:8989",
                             "InstanceNames":["web-1080p","web-2160p"]}]
    [INF] Found 0 config files with 0 Radarr and 0 Sonarr instances

Recyclarr sortait en code 0, plugarr annoncait « synchronise », et aucun profil
TRaSH n'etait pose.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugarr.clients import recyclarr

MODELE = "sonarr:\n  {nom}:\n    base_url: http://sonarr:8989\n    api_key: {cle}\n"


def ecrire(dossier: Path, nom: str, service: str = "sonarr") -> Path:
    configs = dossier / "configs"
    configs.mkdir(parents=True, exist_ok=True)
    path = configs / f"{nom}.yml"
    path.write_text(
        MODELE.replace("sonarr", service).format(nom=nom, cle="0" * 32), encoding="utf-8"
    )
    return path


# ------------------------------------------------------------------ detection


def test_un_seul_fichier_par_service_ne_pose_pas_de_probleme(tmp_path):
    ecrire(tmp_path, "web-1080p")
    ecrire(tmp_path, "hd-bluray-web", service="radarr")

    assert recyclarr.split_instances(tmp_path) == {}


def test_deux_fichiers_pour_sonarr_sont_reperes(tmp_path):
    a = ecrire(tmp_path, "web-1080p")
    b = ecrire(tmp_path, "web-2160p")

    trouve = recyclarr.split_instances(tmp_path)

    assert set(trouve) == {"sonarr"}
    assert sorted(trouve["sonarr"]) == sorted([a, b])


def test_le_service_est_lu_dans_le_yaml_pas_dans_le_nom(tmp_path):
    """Le nom de fichier n'est qu'un titre de template."""
    ecrire(tmp_path, "un-nom-qui-ne-dit-rien", service="radarr")
    ecrire(tmp_path, "un-autre", service="radarr")

    assert set(recyclarr.split_instances(tmp_path)) == {"radarr"}


def test_un_dossier_absent_ne_leve_pas(tmp_path):
    assert recyclarr.split_instances(tmp_path / "nulle-part") == {}


# ---------------------------------------------------------------- reparation


def test_le_template_choisi_est_conserve(tmp_path):
    ecrire(tmp_path, "web-1080p")
    garde = ecrire(tmp_path, "web-2160p")

    ecartes = recyclarr.resolve_split_instances(tmp_path, {"sonarr": "web-2160p"})

    assert [p.name for p, _s in ecartes] == ["web-1080p.yml"]
    assert garde.exists()
    assert recyclarr.split_instances(tmp_path) == {}


def test_sans_choix_le_plus_recent_gagne(tmp_path):
    """C'est le dernier choix de l'utilisateur."""
    vieux = ecrire(tmp_path, "web-1080p")
    recent = ecrire(tmp_path, "web-2160p")
    import os

    os.utime(vieux, (1, 1))

    recyclarr.resolve_split_instances(tmp_path, {})

    assert recent.exists()
    assert not vieux.exists()


def test_le_fichier_ecarte_est_renomme_jamais_efface(tmp_path):
    """Il a pu etre ajuste a la main : le rendre actif ne doit demander qu'un
    changement d'extension."""
    ecarte = ecrire(tmp_path, "web-1080p")
    ecrire(tmp_path, "web-2160p")

    recyclarr.resolve_split_instances(tmp_path, {"sonarr": "web-2160p"})

    voisin = ecarte.with_suffix("").with_suffix(recyclarr.DISABLED_SUFFIX)
    assert voisin.exists(), "le contenu doit survivre"
    assert "base_url" in voisin.read_text(encoding="utf-8")
    # Recyclarr ne charge que les `.yml` : l'extension suffit a le neutraliser.
    assert not voisin.name.endswith(".yml")


def test_chaque_service_est_traite_separement(tmp_path):
    ecrire(tmp_path, "web-1080p")
    ecrire(tmp_path, "web-2160p")
    ecrire(tmp_path, "hd-bluray-web", service="radarr")
    ecrire(tmp_path, "french-multi", service="radarr")

    ecartes = recyclarr.resolve_split_instances(
        tmp_path, {"sonarr": "web-2160p", "radarr": "french-multi"}
    )

    assert sorted(s for _p, s in ecartes) == ["radarr", "sonarr"]
    assert recyclarr.split_instances(tmp_path) == {}
    restants = sorted(p.stem for p in (tmp_path / "configs").glob("*.yml"))
    assert restants == ["french-multi", "web-2160p"]


def test_rien_a_faire_quand_tout_va_bien(tmp_path):
    ecrire(tmp_path, "web-1080p")

    assert recyclarr.resolve_split_instances(tmp_path, {}) == []


@pytest.mark.parametrize("choix", [{}, {"sonarr": "inexistant"}])
def test_un_choix_introuvable_ne_supprime_pas_tout(tmp_path, choix):
    """Meme quand le template retenu n'est plus la, il doit rester UN fichier."""
    ecrire(tmp_path, "web-1080p")
    ecrire(tmp_path, "web-2160p")

    recyclarr.resolve_split_instances(tmp_path, choix)

    assert len(list((tmp_path / "configs").glob("*.yml"))) == 1
