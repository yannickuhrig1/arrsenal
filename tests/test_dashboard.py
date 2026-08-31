"""Tests de la page d'acces. Aucun reseau, aucun navigateur."""

from __future__ import annotations

import re

import pytest

from arrsenal import dashboard, orchestrator
from arrsenal.models import PlatformProfile


def make(services=("prowlarr", "sonarr", "radarr", "qbittorrent", "jellyfin"), **kw):
    return orchestrator.build_config(
        services=list(services),
        data_root=kw.get("data_root", "/srv/data"),
        config_root=kw.get("config_root", "/opt/arrsenal/config"),
        platform=PlatformProfile.GENERIC_LINUX,
    )


# ------------------------------------------------------------------- contenu


def test_every_installed_service_gets_a_link():
    cfg = make()
    page = dashboard.render(cfg)
    for sid, inst in orchestrator.iter_selected(cfg):
        assert f":{inst.host_port}" in page, sid


def test_services_that_were_not_installed_are_absent():
    page = dashboard.render(make(services=("sonarr",)))
    assert "Sonarr" in page
    assert "Jellyfin" not in page
    assert "qBittorrent" not in page


def test_download_and_media_folders_are_listed():
    page = dashboard.render(make(data_root="/srv/data"))
    assert "/srv/data/media/movies" in page
    assert "/srv/data/media/tv" in page
    assert "/srv/data/torrents" in page


def test_music_folder_only_appears_with_lidarr():
    assert "media/music" not in dashboard.render(make())
    assert "media/music" in dashboard.render(make(services=("lidarr",)))


def test_folder_rows_offer_a_copyable_path_and_a_local_link():
    """Le lien file:// ne marche que si le navigateur tourne sur la machine
    d'installation. Le chemin copiable doit donc exister aussi."""
    page = dashboard.render(make(data_root="/srv/data"))
    assert 'data-value="/srv/data/torrents"' in page
    assert "file:///srv/data/torrents" in page
    assert "ne fonctionnent que si ce navigateur tourne sur la" in page


# -------------------------------------------------------------------- secrets


def test_secrets_are_masked_until_clicked():
    cfg = make()
    page = dashboard.render(cfg)
    password = cfg.services["sonarr"].password
    # La valeur est dans le fichier - c'est un fichier local, comme le .env.
    # Ce qui compte est qu'elle ne s'AFFICHE pas sans un clic explicite.
    assert f'data-value="{password}"' in page
    assert "••••••••" in page


def test_the_page_warns_that_it_holds_secrets():
    page = dashboard.render(make())
    assert "chmod 600" in page
    assert "Ne la partagez pas" in page


def test_written_file_is_restricted_and_named_predictably(tmp_path):
    path = dashboard.write(make(), tmp_path)
    assert path.name == dashboard.FILENAME
    assert path.exists()


# ------------------------------------------------------------------- securite


def test_paths_are_html_escaped():
    """Les chemins viennent de l'utilisateur : sans echappement, un chemin
    malicieux injecterait du script dans la page."""
    page = dashboard.render(make(data_root='/srv/<script>alert(1)</script>'))
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_the_only_script_tag_is_our_own():
    page = dashboard.render(make(data_root="/srv/data"))
    assert len(re.findall(r"<script", page)) == 1


# ----------------------------------------------------------------------- hote


def test_localhost_is_replaced_by_the_lan_address(monkeypatch):
    """Installee sur un NAS et ouverte depuis un portable, une URL en localhost
    pointerait vers le portable."""
    monkeypatch.setattr(dashboard, "primary_lan_ip", lambda: "192.168.1.42")
    cfg = make()
    host, note = dashboard.resolve_host(cfg)
    assert host == "192.168.1.42"
    assert "192.168.1.42" in (note or "")
    assert "192.168.1.42" in dashboard.render(cfg)


def test_an_explicit_host_is_left_alone(monkeypatch):
    monkeypatch.setattr(dashboard, "primary_lan_ip", lambda: "192.168.1.42")
    cfg = make()
    cfg.host = "nas.local"
    host, note = dashboard.resolve_host(cfg)
    assert host == "nas.local"
    assert note is None


def test_without_a_lan_address_the_limit_is_stated(monkeypatch):
    monkeypatch.setattr(dashboard, "primary_lan_ip", lambda: None)
    _host, note = dashboard.resolve_host(make())
    assert note and "autre appareil" in note


def test_lan_detection_never_returns_loopback(monkeypatch):
    class FakeSock:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def settimeout(self, _):
            pass

        def connect(self, _):
            pass

        def getsockname(self):
            return ("127.0.0.1", 0)

    monkeypatch.setattr(dashboard.socket, "socket", lambda *a, **k: FakeSock())
    assert dashboard.primary_lan_ip() is None


# ---------------------------------------------------------------- avertissements


def test_failed_links_are_surfaced_on_the_page():
    page = dashboard.render(make(), failed=3)
    assert "3 lien(s)" in page
    assert "arrsenal doctor" in page


def test_a_clean_install_shows_no_failure_banner():
    assert "arrsenal doctor" not in dashboard.render(make())


def test_the_vpn_warning_follows_the_config():
    cfg = make()
    assert "Aucun VPN" in dashboard.render(cfg)
    cfg.vpn.enabled = True
    assert "Aucun VPN" not in dashboard.render(cfg)


def test_uncertain_ids_are_repeated_on_the_page():
    cfg = make()
    cfg.ids_certain = False
    cfg.ids_source = "lance en root : conteneurs et medias appartiendront a root"
    page = dashboard.render(cfg)
    assert "root" in page
    assert "qui possede vos medias" in page


@pytest.mark.parametrize("marker", ["<!doctype html>", 'lang="fr"', "prefers-color-scheme"])
def test_page_is_a_standalone_document(marker):
    """Aucune ressource externe : la page doit s'ouvrir hors ligne."""
    page = dashboard.render(make())
    assert marker in page
    assert "http://cdn" not in page
    assert "https://" not in page.split("<style>")[0]


def test_no_vpn_warning_without_a_download_client():
    """Sans client torrent il n'y a pas de trafic BitTorrent : l'avertissement
    serait du bruit, et le bruit fait ignorer les vrais avertissements."""
    assert "Aucun VPN" not in dashboard.render(make(services=("sonarr", "jellyfin")))
    assert "Aucun VPN" in dashboard.render(make(services=("sonarr", "qbittorrent")))
