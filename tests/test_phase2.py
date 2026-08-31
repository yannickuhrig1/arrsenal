"""Tests des ajouts de la phase 2 : second client de telechargement et Lidarr."""

from __future__ import annotations

import base64
import hashlib

import pytest

from arrsenal import catalog, seed
from arrsenal.downloadclients import ARR_FIELD_PREFIX, ARR_ROUTING, profile_for
from arrsenal.layout import CONTAINER_PATHS
from arrsenal.models import ServiceInstance, StackConfig
from arrsenal.wiring import ROOT_FOLDERS, SYNC_CATEGORIES, Wirer


def make_cfg(tmp_path, services):
    cfg = StackConfig(config_root=str(tmp_path / "c"), data_root=str(tmp_path / "d"))
    for sid in catalog.resolve_dependencies(list(services)):
        spec = catalog.get(sid)
        cfg.services[sid] = ServiceInstance(
            spec_id=sid,
            host_port=spec.default_host_port,
            api_key=seed.generate_api_key() if spec.api_family == "arr" else None,
            username="arrsenal",
            password="pw",
        )
    return cfg


# ------------------------------------------------------------------- catalogue


def test_every_managed_arr_has_routing_and_sync_categories():
    """Ajouter un *arr sans son routage produirait un KeyError au cablage."""
    for arr_id in catalog.MANAGED_ARRS:
        assert arr_id in ARR_FIELD_PREFIX, arr_id
        assert arr_id in ARR_ROUTING, arr_id
        assert arr_id in SYNC_CATEGORIES, arr_id
        assert arr_id in ROOT_FOLDERS, arr_id


def test_every_download_client_has_a_profile():
    for dl_id in catalog.DOWNLOAD_CLIENTS:
        assert profile_for(dl_id).service_id == dl_id


def test_lidarr_uses_api_v1_unlike_sonarr_and_radarr():
    assert catalog.get("lidarr").api_version == "v1"
    assert catalog.get("sonarr").api_version == "v3"
    assert catalog.get("radarr").api_version == "v3"


def test_routing_paths_all_live_under_the_single_data_mount():
    for _category, path in ARR_ROUTING.values():
        assert path.startswith("/data/")


# ------------------------------------------------------- profils de download


def test_transmission_routes_by_directory_and_clears_the_category():
    """Poser les deux fait echouer la validation des *arr."""
    values = profile_for("transmission").arr_values(
        host="transmission", port=9091, username="u", password="p", arr_id="sonarr"
    )
    assert values["tvDirectory"] == CONTAINER_PATHS["torrents_tv"]
    assert values["tvCategory"] == ""


def test_qbittorrent_routes_by_category_and_clears_the_directory():
    values = profile_for("qbittorrent").arr_values(
        host="qbittorrent", port=8080, username="u", password="p", arr_id="radarr"
    )
    assert values["movieCategory"] == "movies"
    assert values["movieDirectory"] == ""


def test_only_the_relevant_prefix_is_sent(tmp_path):
    """Envoyer movieDirectory a Sonarr generait un avertissement a chaque passage."""
    values = profile_for("qbittorrent").arr_values(
        host="h", port=1, username="u", password="p", arr_id="lidarr"
    )
    assert {k for k in values if k.endswith(("Category", "Directory"))} == {
        "musicCategory",
        "musicDirectory",
    }


def test_only_transmission_gets_a_url_base():
    common = {"host": "h", "port": 1, "username": "u", "password": "p"}
    assert "urlBase" in profile_for("transmission").prowlarr_values(**common)
    assert "urlBase" not in profile_for("qbittorrent").prowlarr_values(**common)


# ------------------------------------------------------------- pre-semis qbt


def test_qbittorrent_hash_is_valid_pbkdf2_sha512():
    """Verifie contre qBittorrent 5.2.3 : sans ce format, la WebUI genere un
    mot de passe temporaire aleatoire et le cablage devient impossible."""
    raw = seed.qbittorrent_password_hash("hunter2")
    assert raw.startswith("@ByteArray(") and raw.endswith(")")
    salt_b64, hash_b64 = raw[len("@ByteArray(") : -1].split(":")
    salt, digest = base64.b64decode(salt_b64), base64.b64decode(hash_b64)
    assert len(salt) == 16 and len(digest) == 64
    assert hashlib.pbkdf2_hmac("sha512", b"hunter2", salt, 100000, dklen=64) == digest


def test_qbittorrent_hash_is_salted_differently_each_time():
    assert seed.qbittorrent_password_hash("x") != seed.qbittorrent_password_hash("x")


def test_qbittorrent_conf_disables_host_header_validation():
    """Sans ce reglage, qBittorrent rejette Sonarr et Radarr, qui l'appellent
    par son nom de conteneur et non par une adresse IP."""
    conf = seed.render_qbittorrent_conf(username="u", password="p")
    assert r"WebUI\HostHeaderValidation=false" in conf
    assert r"Downloads\SavePath=/data/torrents/" in conf


def test_seed_qbittorrent_writes_to_the_linuxserver_path(tmp_path):
    written, _ = seed.seed_qbittorrent(tmp_path, username="u", password="p")
    assert written
    assert (tmp_path / "qBittorrent" / "qBittorrent.conf").exists()


def test_seed_qbittorrent_never_overwrites(tmp_path):
    seed.seed_qbittorrent(tmp_path, username="u", password="p")
    before = (tmp_path / "qBittorrent" / "qBittorrent.conf").read_text()
    written, _ = seed.seed_qbittorrent(tmp_path, username="u", password="other")
    assert not written
    assert (tmp_path / "qBittorrent" / "qBittorrent.conf").read_text() == before


# -------------------------------------------------------------------- plan


def test_plan_scales_with_the_selection(tmp_path):
    names = [s.name for s in Wirer(make_cfg(tmp_path, ["prowlarr", "sonarr"])).build_plan()]
    assert "prowlarr/application/sonarr" in names
    assert not any("lidarr" in n for n in names)

    full = [
        s.name
        for s in Wirer(
            make_cfg(tmp_path, ["prowlarr", "sonarr", "radarr", "lidarr", "qbittorrent", "jellyfin"])
        ).build_plan()
    ]
    assert "lidarr/downloadclient/qbittorrent" in full
    assert "qbittorrent/categories" in full


def test_categories_are_created_before_any_arr_points_at_them(tmp_path):
    """Sinon qBittorrent les cree lui-meme, sans chemin de sauvegarde."""
    names = [
        s.name
        for s in Wirer(make_cfg(tmp_path, ["prowlarr", "sonarr", "qbittorrent"])).build_plan()
    ]
    assert names.index("qbittorrent/categories") < names.index("sonarr/downloadclient/qbittorrent")
    assert names.index("qbittorrent/categories") < names.index(
        "prowlarr/downloadclient/qbittorrent"
    )


def test_lidarr_gets_no_jellyfin_notification(tmp_path):
    """L'implementation MediaBrowser n'existe pas dans Lidarr."""
    names = [
        s.name for s in Wirer(make_cfg(tmp_path, ["lidarr", "sonarr", "jellyfin"])).build_plan()
    ]
    assert "sonarr/notification/jellyfin" in names
    assert "lidarr/notification/jellyfin" not in names


def test_two_download_clients_produce_two_sets_of_links(tmp_path):
    names = [
        s.name
        for s in Wirer(
            make_cfg(tmp_path, ["sonarr", "transmission", "qbittorrent"])
        ).build_plan()
    ]
    assert "sonarr/downloadclient/transmission" in names
    assert "sonarr/downloadclient/qbittorrent" in names


def test_unknown_download_client_raises_a_readable_error():
    with pytest.raises(KeyError, match="qbittorrent"):
        profile_for("deluge")
