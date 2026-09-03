"""Le conseil de fin doit parler de ce qui est INSTALLE.

arrsenal terminait chaque installation par « ajoutez vos indexeurs dans
Prowlarr. Ils descendront automatiquement vers Sonarr et Radarr », quelle que
soit la selection. Constate en installant Silo seul depuis l'executable : le
conseil citait trois applications dont aucune n'existait, et envoyait chercher
un ecran qui n'etait nulle part.

Un conseil faux coute plus cher qu'un conseil absent : il est suivi.
"""

from __future__ import annotations

import re

from arrsenal import dashboard, orchestrator


def _cfg(*services: str, data_root: str = "/d"):
    return orchestrator.build_config(
        services=list(services), config_root="/c", data_root=data_root
    )


def test_prowlarr_absent_n_est_jamais_cite():
    texte = " ".join(orchestrator.prochaine_etape(_cfg("silo")))

    assert "Prowlarr" not in texte


def test_une_selection_media_seule_parle_des_medias():
    lignes = orchestrator.prochaine_etape(_cfg("silo", data_root="D:/medias"))

    assert "D:/medias" in lignes[0]
    assert "Silo" in " ".join(lignes)


def test_seules_les_applications_installees_sont_citees():
    texte = " ".join(orchestrator.prochaine_etape(_cfg("sonarr", "prowlarr")))

    assert "Sonarr" in texte
    assert "Radarr" not in texte
    assert "Lidarr" not in texte


def test_sans_prowlarr_le_conseil_change_de_cible():
    """Sans lui, chaque application reste a alimenter une par une : le dire
    evite d'attendre une distribution automatique qui n'arrivera pas."""
    texte = " ".join(orchestrator.prochaine_etape(_cfg("sonarr", "radarr")))

    assert "Sonarr, Radarr" in texte
    assert "il n'est pas installe" in texte


def test_il_y_a_toujours_un_conseil():
    """Meme une selection qui ne rentre dans aucun cas repond quelque chose."""
    for selection in (("qbittorrent",), ("transmission", "flood")):
        lignes = orchestrator.prochaine_etape(_cfg(*selection))
        assert lignes and lignes[0].startswith("Prochaine etape")


def test_la_page_d_acces_dit_la_meme_chose():
    """Trois interfaces affichaient ce conseil, chacune avec son propre texte
    en dur. Elles lisent desormais la meme source."""
    page = dashboard.render(_cfg("silo", data_root="D:/medias"))
    trouve = re.search(r"<p><strong>(Prochaine[^<]*)</strong></p>", page)

    assert trouve is not None
    assert "Prowlarr" not in trouve.group(1)
