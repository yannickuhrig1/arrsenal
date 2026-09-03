"""Une bibliotheque, c'est trois choses qui doivent rester d'accord.

Demande a l'usage : « ajouter des repertoires pour les animes, les spectacles,
apps, ebook etc relie a qbitorrent ».

Chaque genre de contenu implique un dossier de telechargement, un dossier de
rangement, et une categorie chez le client torrent qui envoie l'un vers l'autre.
Ces trois-la vivaient dans trois listes separees — `DATA_SUBDIRS`,
`CONTAINER_PATHS`, `ARR_ROUTING` — qu'il fallait penser a tenir en phase. Elles
derivent maintenant d'une table unique.
"""

from __future__ import annotations

import pytest

from arrsenal import orchestrator
from arrsenal.layout import BIBLIOTHEQUES, CONTAINER_PATHS, DATA_SUBDIRS, create_tree
from arrsenal.wiring import ROOT_FOLDERS


def _cfg(*services):
    return orchestrator.build_config(
        services=list(services), config_root="/c", data_root="/d"
    )


@pytest.mark.parametrize("attendue", ["movies", "tv", "anime", "music", "books", "audiobooks"])
def test_la_bibliotheque_existe(attendue):
    assert attendue in {b.id for b in BIBLIOTHEQUES}


def test_chaque_bibliotheque_a_ses_deux_dossiers():
    """Un dossier de telechargement sans rangement, ou l'inverse, laisserait un
    import a mi-chemin."""
    for b in BIBLIOTHEQUES:
        assert f"torrents/{b.id}" in DATA_SUBDIRS, b.id
        if b.media:
            assert f"media/{b.id}" in DATA_SUBDIRS, b.id


def test_les_logiciels_ne_vont_pas_dans_la_mediatheque():
    """Un logiciel telecharge n'a rien a faire a cote des films."""
    assert "media/apps" not in DATA_SUBDIRS
    assert "torrents/apps" in DATA_SUBDIRS


def test_les_deux_racines_partagent_le_point_de_montage():
    """Condition des liens physiques : sans cela chaque import RECOPIE le
    fichier, et une stack de 40 Go en occupe 80."""
    for cle, chemin in CONTAINER_PATHS.items():
        assert chemin.startswith("/data/"), f"{cle} sort de /data"


def test_sonarr_recoit_un_dossier_racine_pour_l_anime():
    """Sonarr traite l'anime comme un type de serie a part, avec ses propres
    conventions de nommage. Les melanger fait renommer les series normales
    selon des regles anime — c'est la disposition des TRaSH Guides."""
    assert ROOT_FOLDERS["sonarr"] == ["/data/media/tv", "/data/media/anime"]


def test_les_autres_applications_gardent_un_seul_dossier():
    assert ROOT_FOLDERS["radarr"] == ["/data/media/movies"]
    assert ROOT_FOLDERS["lidarr"] == ["/data/media/music"]


def test_le_plan_pose_les_deux_dossiers_de_sonarr():
    from arrsenal.wiring import Wirer

    noms = [e.name for e in Wirer(_cfg("sonarr")).build_plan()]

    assert "sonarr/rootfolder/tv" in noms
    assert "sonarr/rootfolder/anime" in noms


def test_l_arborescence_est_reellement_creee(tmp_path):
    create_tree(tmp_path / "data", tmp_path / "config", ["sonarr"])

    for b in BIBLIOTHEQUES:
        assert (tmp_path / "data" / "torrents" / b.id).is_dir(), b.id
        if b.media:
            assert (tmp_path / "data" / "media" / b.id).is_dir(), b.id


def test_une_bibliotheque_sans_application_a_quand_meme_sa_categorie():
    """Elle range les telechargements manuels, et elle sera deja la le jour ou
    Audiobookshelf ou Shelfarr entrent au catalogue. Sans elle, tout finit en
    vrac a la racine des torrents."""
    sans_arr = [b for b in BIBLIOTHEQUES if b.arr is None]

    assert {b.id for b in sans_arr} >= {"books", "audiobooks", "apps"}
    for b in sans_arr:
        assert b.torrents == f"/data/torrents/{b.id}"
