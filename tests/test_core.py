"""Tests du coeur : ils tournent sans Docker et sans reseau."""

from __future__ import annotations

import json
from xml.etree import ElementTree as ET

import pytest
import yaml

from arrsenal import catalog, compose, seed
from arrsenal.clients.arr import ArrClient
from arrsenal.layout import hardlink_supported
from arrsenal.models import PlatformProfile, ServiceInstance, StackConfig


def make_cfg(tmp_path, services=("prowlarr", "sonarr", "radarr", "transmission", "jellyfin")):
    cfg = StackConfig(
        config_root=str(tmp_path / "config"),
        data_root=str(tmp_path / "data"),
        platform=PlatformProfile.GENERIC_LINUX,
    )
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


def test_dependencies_pull_in_transmission_for_flood():
    assert catalog.resolve_dependencies(["flood"]) == ["transmission", "flood"]


def test_startup_order_places_prowlarr_after_the_arrs():
    order = catalog.STARTUP_ORDER
    assert order.index("prowlarr") > order.index("sonarr")
    assert order.index("prowlarr") > order.index("radarr")


def test_every_image_tag_is_pinned():
    """Un tag flottant rend le cablage non reproductible."""
    for spec in catalog.CATALOG.values():
        tag = spec.image.rsplit(":", 1)[-1]
        assert tag not in ("latest", "develop", "nightly"), spec.id


def test_unknown_service_error_lists_known_ones():
    with pytest.raises(KeyError, match="sonarr"):
        catalog.get("sonaar")


# ---------------------------------------------------------------------- seeding


def test_arr_config_enforces_forms_auth():
    """Verifie contre Sonarr 4.0.19.2979 : Forms + Enabled protege l'UI web."""
    xml = ET.fromstring(
        seed.render_arr_config(
            api_key="a" * 32, port=8989, instance_name="Sonarr", username="u", password="p"
        )
    )
    assert xml.findtext("AuthenticationMethod") == "Forms"
    assert xml.findtext("AuthenticationRequired") == "Enabled"
    assert xml.findtext("ApiKey") == "a" * 32


def test_seed_arr_is_idempotent_and_adopts_existing_key(tmp_path):
    d = tmp_path / "sonarr"
    first, written = seed.seed_arr(
        d, api_key="b" * 32, port=8989, instance_name="Sonarr", username="u", password="p"
    )
    assert written and first == "b" * 32

    second, written_again = seed.seed_arr(
        d, api_key="c" * 32, port=8989, instance_name="Sonarr", username="u", password="p"
    )
    # La cle existante fait autorite : on ne l'ecrase jamais.
    assert not written_again
    assert second == "b" * 32


def test_transmission_settings_allow_container_to_container_rpc():
    s = seed.render_transmission_settings(rpc_username="u", rpc_password="p")
    # Sans ces deux reglages, Sonarr/Radarr sont refuses par Transmission.
    assert s["rpc-whitelist-enabled"] is False
    assert s["rpc-host-whitelist-enabled"] is False
    assert s["download-dir"].startswith("/data/")
    assert s["incomplete-dir"].startswith("/data/")


def test_seed_transmission_does_not_overwrite(tmp_path):
    d = tmp_path / "transmission"
    d.mkdir()
    (d / "settings.json").write_text(json.dumps({"custom": True}))
    written, _ = seed.seed_transmission(d, rpc_username="u", rpc_password="p")
    assert not written
    assert json.loads((d / "settings.json").read_text()) == {"custom": True}


# ---------------------------------------------------------------------- compose


def test_all_services_share_one_data_mount(tmp_path):
    """LE point critique : un seul montage /data, sinon les hardlinks echouent."""
    doc = compose.build_compose(make_cfg(tmp_path))
    for sid, block in doc["services"].items():
        mounts = [v.split(":")[-1] for v in block["volumes"]]
        assert "/data" in mounts, f"{sid} n'a pas le montage /data"
        assert not any(m.startswith("/downloads") or m == "/media" for m in mounts), sid


def test_compose_is_valid_yaml_and_pins_images(tmp_path):
    doc = yaml.safe_load(compose.render_compose(make_cfg(tmp_path)))
    assert set(doc["services"]) == {"transmission", "sonarr", "radarr", "prowlarr", "jellyfin"}
    for block in doc["services"].values():
        assert ":" in block["image"]


def test_vpn_moves_torrent_client_into_gluetun_network(tmp_path):
    cfg = make_cfg(tmp_path)
    cfg.vpn_enabled = True
    block = compose.build_compose(cfg)["services"]["transmission"]
    # Avec VPN, le client perd son reseau et ses ports publies.
    assert block["network_mode"] == "service:gluetun"
    assert "ports" not in block
    assert "networks" not in block
    # Les autres services ne bougent pas.
    assert "ports" in compose.build_compose(cfg)["services"]["sonarr"]


def test_env_contains_secrets_and_compose_does_not(tmp_path):
    cfg = make_cfg(tmp_path)
    env = compose.render_env(cfg)
    key = cfg.services["sonarr"].api_key
    assert f"SONARR_API_KEY={key}" in env
    assert key not in compose.render_compose(cfg)


def test_write_artifacts_roundtrips_stack_yml(tmp_path):
    cfg = make_cfg(tmp_path)
    compose.write_artifacts(cfg, tmp_path / "proj")
    reloaded = StackConfig.model_validate(
        yaml.safe_load((tmp_path / "proj" / "stack.yml").read_text(encoding="utf-8"))
    )
    assert reloaded.services.keys() == cfg.services.keys()
    assert reloaded.services["sonarr"].api_key == cfg.services["sonarr"].api_key


# ----------------------------------------------------------------- schema fill


SCHEMA = {
    "implementation": "Transmission",
    "configContract": "TransmissionSettings",
    "fields": [
        {"name": "host", "value": ""},
        {"name": "port", "value": 9091},
        {"name": "tvDirectory", "value": ""},
    ],
}


def test_fill_applies_known_fields_and_reports_unknown_ones():
    filled, applied, skipped = ArrClient.fill(
        SCHEMA, {"host": "transmission", "tvDirectory": "/data/torrents/tv", "movieDirectory": "/x"}
    )
    by_name = {f["name"]: f["value"] for f in filled["fields"]}
    assert by_name["host"] == "transmission"
    assert by_name["tvDirectory"] == "/data/torrents/tv"
    assert sorted(applied) == ["host", "tvDirectory"]
    # movieDirectory n'existe pas dans CE gabarit : signale, pas perdu en silence.
    assert skipped == ["movieDirectory"]


def test_fill_does_not_mutate_the_source_schema():
    ArrClient.fill(SCHEMA, {"host": "x"})
    assert SCHEMA["fields"][0]["value"] == ""


# -------------------------------------------------------------------- hardlink


def test_hardlink_probe_actually_runs(tmp_path):
    ok, detail = hardlink_supported(tmp_path)
    assert isinstance(ok, bool) and detail
    # Aucun fichier temporaire ne doit survivre au test.
    assert not list((tmp_path / "torrents").glob(".arrsenal-*"))
    assert not list((tmp_path / "media").glob(".arrsenal-*"))


# ------------------------------------------------------------------ validation


def test_bad_umask_is_rejected_with_a_readable_message(tmp_path):
    with pytest.raises(ValueError, match="umask"):
        StackConfig(config_root=str(tmp_path), data_root=str(tmp_path), umask="99")


# ------------------------------------------------------- identifiants systeme


def test_unraid_uses_the_platform_constant_not_detection():
    """Unraid fait tourner ses conteneurs en nobody:users a l'echelle de la
    plateforme : detecter l'utilisateur courant y serait faux."""
    from arrsenal.layout import PROFILE_DEFAULTS, resolve_ids

    uid, gid, source, certain = resolve_ids(PlatformProfile.UNRAID)
    assert (uid, gid) == (99, 100)
    assert certain
    assert "Unraid" in source
    assert not PROFILE_DEFAULTS[PlatformProfile.UNRAID].prefer_detection


def test_synology_detects_because_dsm_uids_vary():
    """Sur DSM l'UID depend de l'ordre de creation des utilisateurs : une
    constante serait fausse par conception."""
    from arrsenal.layout import PROFILE_DEFAULTS

    assert PROFILE_DEFAULTS[PlatformProfile.SYNOLOGY].prefer_detection


def test_detection_returns_none_rather_than_inventing_a_value(monkeypatch):
    """Renvoyer 1000:1000 en silence empecherait d'avertir l'utilisateur."""
    import os as _os

    from arrsenal.layout import detect_ids

    monkeypatch.delattr(_os, "getuid", raising=False)
    monkeypatch.delattr(_os, "getgid", raising=False)
    assert detect_ids() is None


def test_undetectable_ids_are_flagged_as_uncertain(monkeypatch):
    import os as _os

    from arrsenal.layout import resolve_ids

    monkeypatch.delattr(_os, "getuid", raising=False)
    monkeypatch.delattr(_os, "getgid", raising=False)
    _uid, _gid, source, certain = resolve_ids(PlatformProfile.GENERIC_LINUX)
    assert not certain
    assert "detection impossible" in source


def test_config_records_where_the_ids_came_from(tmp_path):
    from arrsenal import orchestrator

    cfg = orchestrator.build_config(services=["sonarr"], data_root=str(tmp_path))
    assert cfg.ids_source and cfg.ids_source != "non renseigne"
