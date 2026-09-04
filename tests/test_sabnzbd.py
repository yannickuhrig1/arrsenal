"""SABnzbd : l'Usenet a cote des torrents, et quatre pieges enchaines.

Demande a l'usage : « il faut trouver un remplacant pour DroppedNeedle ». La
premisse meritait d'etre corrigee — DroppedNeedle n'est pas un mauvais choix, il
est bloque par son client de telechargement, et tous les chemins vers
l'acquisition automatisee de musique passent par slskd ou SABnzbd. Ajouter le
client debloque DroppedNeedle sans le remplacer, et sert toute la pile au
passage : Sonarr, Radarr et Lidarr y gagnent l'Usenet a cote des torrents.

Quatre pieges, chacun trouve en essayant pour de vrai, et chacun muet.

**La liste blanche d'hotes.** SABnzbd refuse toute requete dont l'en-tete `Host`
n'y figure pas, et n'y met par defaut QUE l'identifiant de son conteneur. Sonarr
appelant `http://sabnzbd:8080` recoit « Access denied - Hostname verification
failed », message qui ne nomme ni l'appelant ni le reglage.

**Sa cle API n'etait pas generee.** SABnzbd n'a ni identifiant ni mot de passe :
sa cle tient lieu des deux, et rien dans PlugArr ne lui en attribuait. Le
pre-semis ecrivait une cle vide, SABnzbd en generait une a lui, et tout le
cablage repondait « API Key Required ».

**Le pre-semis ne tournait pas.** `seeded_services` listait trois familles
d'API ; la sienne n'y etait pas. La cle generee n'atteignait donc jamais le
fichier.

**Les categories d'usine ont un repertoire VIDE.** `movies`, `tv`, `audio`,
`software` existent des l'installation. Se contenter de les creer si absentes
les laisse inutilisables : le nom existe, Sonarr l'accepte, et tout atterrit
dans le repertoire par defaut.

Et Prowlarr refuse de se declarer si SA categorie n'existe pas cote client :
« The category you entered doesn't exist in Sabnzbd. »
"""

from __future__ import annotations

import pytest

from plugarr import catalog, compose, orchestrator, seed
from plugarr.clients.sabnzbd import SabnzbdClient
from plugarr.downloadclients import profile_for
from plugarr.layout import CONTAINER_PATHS, DATA_SUBDIRS
from plugarr.wiring import Wirer


def _cfg(*services: str):
    return orchestrator.build_config(
        services=list(services or ("sabnzbd",)), config_root="/c", data_root="/d"
    )


# ------------------------------------------------------------------ catalogue


def test_le_service_est_choisissable():
    assert "sabnzbd" in {s.id for s in catalog.selectable()}


def test_l_image_est_epinglee_au_digest():
    assert "@sha256:" in catalog.get("sabnzbd").image


def test_il_compte_comme_client_de_telechargement():
    """Il est declare aux *arr, attendu au demarrage et protege par le VPN
    exactement comme les clients torrent."""
    assert "sabnzbd" in catalog.DOWNLOAD_CLIENTS
    assert catalog.get("sabnzbd").category is catalog.Category.DOWNLOAD


def test_son_port_hote_ne_heurte_pas_qbittorrent():
    """Les deux ecoutent sur 8080 dans leur conteneur. C'est cote hote qu'il
    faut decaler, sinon `compose up` echoue pour la pile entiere."""
    assert catalog.get("sabnzbd").internal_port == 8080
    assert catalog.get("sabnzbd").default_host_port != catalog.get("qbittorrent").default_host_port


def test_il_parle_usenet_et_non_torrent():
    """Les *arr rangent leurs clients par protocole et ne proposent un client
    Usenet que pour les publications Usenet."""
    assert profile_for("sabnzbd").protocol == "usenet"
    assert profile_for("qbittorrent").protocol == "torrent"


# ------------------------------------------------------------------ identifiants


def test_sa_cle_api_est_generee():
    """Sans elle, le pre-semis ecrit une cle vide, SABnzbd en genere une a lui,
    et tout le cablage repond « API Key Required »."""
    inst = _cfg().services["sabnzbd"]

    assert inst.api_key
    assert len(inst.api_key) == 32


def test_la_cle_sert_aussi_de_mot_de_passe():
    """Il n'a ni identifiant ni mot de passe : sa cle tient lieu des deux. Le
    champ `password` la publie dans le .env et la repose dans `apiKey`."""
    inst = _cfg().services["sabnzbd"]

    assert inst.password == inst.api_key


def test_il_est_pre_seme():
    """`seeded_services` ne listait pas sa famille d'API : la cle generee
    n'atteignait donc jamais son fichier."""
    assert "sabnzbd" in orchestrator.seeded_services(_cfg("sabnzbd", "sonarr"))


def test_les_arr_recoivent_la_cle_et_non_un_mot_de_passe():
    """Poser un identifiant et un mot de passe ferait echouer le test de
    connexion : son interface n'en demande pas."""
    valeurs = profile_for("sabnzbd").arr_values(
        host="sabnzbd", port=8080, username="plugarr", password="LA-CLE", arr_id="sonarr"
    )

    assert valeurs["apiKey"] == "LA-CLE"
    assert valeurs["username"] == ""
    assert valeurs["password"] == ""


# ------------------------------------------------------------------ pre-semis


def test_le_pre_semis_pose_les_noms_d_hote(tmp_path):
    """Sans eux : « Access denied - Hostname verification failed »."""
    seed.seed_sabnzbd(
        tmp_path, api_key="CLE", port=8080,
        hotes_autorises=["sabnzbd", "plugarr-sabnzbd", "localhost"],
        incomplet="/data/usenet/.incomplete", complet="/data/usenet",
    )
    texte = (tmp_path / "sabnzbd.ini").read_text(encoding="utf-8")

    for hote in ("sabnzbd", "plugarr-sabnzbd", "localhost"):
        assert hote in texte


def test_le_pre_semis_met_les_telechargements_sous_data(tmp_path):
    """Par defaut ils sont sous /config : les liens physiques deviennent
    impossibles et chaque import recopie le fichier."""
    seed.seed_sabnzbd(
        tmp_path, api_key="CLE", port=8080, hotes_autorises=["sabnzbd"],
        incomplet="/data/usenet/.incomplete", complet="/data/usenet",
    )
    texte = (tmp_path / "sabnzbd.ini").read_text(encoding="utf-8")

    assert "/data/usenet/.incomplete" in texte
    assert "/data/usenet" in texte


def test_un_fichier_existant_fait_autorite(tmp_path):
    """Quelqu'un a pu regler son serveur Usenet et ses categories. On n'AJOUTE
    que les hotes manquants."""
    seed.seed_sabnzbd(
        tmp_path, api_key="PREMIERE", port=8080, hotes_autorises=["sabnzbd"],
        incomplet="/a", complet="/b",
    )
    ecrit, message = seed.seed_sabnzbd(
        tmp_path, api_key="SECONDE", port=9999, hotes_autorises=["sabnzbd", "autre-nom"],
        incomplet="/x", complet="/y",
    )
    texte = (tmp_path / "sabnzbd.ini").read_text(encoding="utf-8")

    assert ecrit is False
    assert "PREMIERE" in texte, "la cle existante a ete ecrasee"
    assert "autre-nom" in texte, "le nouvel hote n'a pas ete ajoute"
    assert "autre-nom" in message


# ------------------------------------------------------------------ arborescence


def test_l_usenet_a_son_propre_arbre():
    """Torrent et Usenet ont des durees de vie differentes : un torrent doit
    rester en partage apres l'import, un NZB non. Melanger les deux fait
    effacer par l'un ce que l'autre partage encore."""
    assert "usenet/.incomplete" in DATA_SUBDIRS
    assert "usenet/tv" in DATA_SUBDIRS
    assert "torrents/tv" in DATA_SUBDIRS


def test_les_deux_arbres_partagent_le_point_de_montage():
    """Condition des liens physiques."""
    assert CONTAINER_PATHS["usenet_root"].startswith("/data/")
    assert CONTAINER_PATHS["torrents_root"].startswith("/data/")


def test_il_voit_data_en_entier():
    """Monter seulement /data/usenet obligerait chaque import a recopier."""
    volumes = compose.build_compose(_cfg())["services"]["sabnzbd"]["volumes"]

    assert "${DATA_ROOT}:/data" in volumes


# ------------------------------------------------------------------ categories


class _Faux(SabnzbdClient):
    """Journalise, et reproduit les categories d'usine."""

    def __init__(self, categories=None):
        self.name = "faux"
        self._cats = dict(categories if categories is not None else {"movies": "", "tv": ""})
        self.poses: list[tuple[str, str]] = []

    def categories(self):
        return dict(self._cats)

    def _call(self, mode, **params):
        if mode == "set_config":
            self._cats[params["keyword"]] = params["dir"]
            self.poses.append((params["keyword"], params["dir"]))
        return {}


def test_une_categorie_d_usine_vide_est_remplie():
    """Le piege : le nom existe deja, mais son repertoire est vide. Se
    contenter de tester la presence laisse tout atterrir au mauvais endroit."""
    faux = _Faux({"tv": ""})

    assert faux.ensure_category("tv", "/data/usenet/tv") is True
    assert faux.categories()["tv"] == "/data/usenet/tv"


def test_une_categorie_deja_reglee_n_est_pas_ecrasee():
    """Un repertoire vide est un defaut d'usine ; un repertoire renseigne est
    une decision."""
    faux = _Faux({"tv": "/mon/chemin/a/moi"})

    assert faux.ensure_category("tv", "/data/usenet/tv") is False
    assert faux.categories()["tv"] == "/mon/chemin/a/moi"


def test_une_categorie_absente_est_creee():
    faux = _Faux({})

    assert faux.ensure_category("anime", "/data/usenet/anime") is True


def test_prowlarr_recoit_sa_categorie():
    """Il REFUSE de se declarer sans elle : « The category you entered doesn't
    exist in Sabnzbd. »"""
    import inspect

    source = inspect.getsource(Wirer.step_sabnzbd_categories)

    assert '"prowlarr"' in source


def test_les_categories_precedent_la_declaration():
    """Les *arr n'envoient qu'un NOM de categorie : elle doit deja porter son
    repertoire quand ils la citent."""
    noms = [e.name for e in Wirer(_cfg("sabnzbd", "sonarr")).build_plan()]

    assert noms.index("sabnzbd/categories") < noms.index("sonarr/downloadclient/sabnzbd")


@pytest.mark.parametrize("arr_id", ["sonarr", "radarr", "lidarr"])
def test_chaque_arr_le_declare(arr_id):
    noms = [e.name for e in Wirer(_cfg("sabnzbd", arr_id)).build_plan()]

    assert f"{arr_id}/downloadclient/sabnzbd" in noms
