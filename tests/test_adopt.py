"""Tests de la detection et de la reprise d'une stack existante.

Aucun appel a Docker : `scan` est alimente par des `Found` construits a la main,
dont la forme reproduit ce qu'a renvoye `docker inspect` en conditions reelles.
"""

from __future__ import annotations

import pytest
import yaml

from arrsenal import adopt, catalog, discovery
from arrsenal.discovery import Found
from arrsenal.models import StackConfig


def found(service_id="sonarr", container="mon-sonarr", port=8991, key="a" * 32, **kw):
    return Found(
        service_id=service_id,
        container=container,
        image=kw.get("image", f"lscr.io/linuxserver/{service_id}:latest"),
        host_port=port,
        config_dir=kw.get("config_dir", "/opt/appdata/sonarr"),
        api_key=key,
        url_base=kw.get("url_base", ""),
        problems=kw.get("problems", []),
    )


# ------------------------------------------------------- reconnaissance d'image


@pytest.mark.parametrize(
    ("image", "expected"),
    [
        ("lscr.io/linuxserver/sonarr:4.0.19", "sonarr"),
        ("ghcr.io/onedr0p/sonarr:4", "sonarr"),
        ("hotio/radarr", "radarr"),
        ("linuxserver/prowlarr", "prowlarr"),
        ("lscr.io/linuxserver/qbittorrent:5.2.3", "qbittorrent"),
        # Les pieges : ces images contiennent "arr" mais n'en sont pas.
        ("ghcr.io/onedr0p/exportarr:v2", None),
        ("recyclarr/recyclarr:latest", None),
        ("ghcr.io/raydak-labs/configarr", None),
        # Et ceux qui n'ont rien a voir.
        ("alpine:3.21", None),
        ("seerr/seerr:v3.4.1", None),
        ("", None),
    ],
)
def test_image_identification(image, expected):
    assert discovery.identify(image) == expected


def test_identification_ignores_the_registry_and_the_tag():
    """Comparer la chaine entiere ferait passer `ghcr.io/x/exportarr` pour un *arr."""
    assert discovery.identify("un.registre.prive/equipe/sonarr:v4.0.19-custom") == "sonarr"


# --------------------------------------------------------------- utilisabilite


def test_an_arr_without_an_api_key_is_not_usable():
    assert not found(key=None).usable


def test_a_service_without_a_published_port_is_not_usable():
    """Sans port publie, arrsenal ne peut pas le joindre depuis l'hote."""
    assert not found(port=None).usable


def test_a_download_client_needs_no_api_key():
    assert found(service_id="qbittorrent", key=None, port=8080).usable


# ------------------------------------------------------------------- doublons


def test_two_sonarr_are_reported_as_ambiguous():
    """Cas courant et legitime : un Sonarr pour les series, un pour l'animation.
    arrsenal ne peut pas deviner lequel recevra les indexeurs."""
    entries = [found(container="sonarr"), found(container="sonarr-anime", port=8992)]
    assert set(discovery.duplicates(entries)) == {"sonarr"}

    plan = adopt.build_plan(entries)
    assert not plan.ready
    assert "sonarr" in plan.ambiguous
    assert plan.chosen == {}


def test_a_pick_lifts_the_ambiguity():
    entries = [found(container="sonarr"), found(container="sonarr-anime", port=8992)]
    plan = adopt.build_plan(entries, {"sonarr": "sonarr-anime"})
    assert plan.ready
    assert plan.chosen["sonarr"].container == "sonarr-anime"
    assert [c.container for c, _ in plan.skipped] == ["sonarr"]


def test_a_pick_naming_an_unknown_container_stays_ambiguous():
    """Se tromper de nom ne doit pas cabler silencieusement le mauvais service."""
    entries = [found(container="sonarr"), found(container="sonarr-anime", port=8992)]
    plan = adopt.build_plan(entries, {"sonarr": "sonarr-inexistant"})
    assert not plan.ready


def test_a_single_instance_needs_no_pick():
    assert adopt.build_plan([found()]).ready


# ---------------------------------------------------------------- exclusions


def test_arrsenal_does_not_adopt_its_own_containers():
    """Inutile de proposer d'adopter la stack qu'on vient d'installer."""
    mine = found(container="arrsenal-sonarr")
    mine.managed_by_us = True
    assert discovery.looks_like_arrsenal(mine)
    plan = adopt.build_plan([mine])
    assert plan.chosen == {}
    assert plan.skipped[0][1] == "deja gere par arrsenal"


@pytest.mark.parametrize("name", ["mon-sonarr", "media-sonarr", "sonarr", "arrsenal-sonarr"])
def test_a_foreign_container_is_never_mistaken_for_ours(name):
    """Un nom ne prouve rien. Une heuristique de nom sautait "mon-sonarr" en
    silence : arrsenal ignorait un conteneur qui ne lui appartenait pas."""
    assert not discovery.looks_like_arrsenal(found(container=name))


def test_an_unusable_service_is_skipped_with_its_reason():
    entry = found(key=None, problems=["le volume /config n'est pas monte"])
    plan = adopt.build_plan([entry])
    assert plan.chosen == {}
    assert "config" in plan.skipped[0][1]


# ------------------------------------------------------------------ config


def test_adopted_services_are_marked_as_such():
    cfg = adopt.config_from_plan(
        adopt.build_plan([found()]), data_root="/srv/d", config_root="/opt/c"
    )
    inst = cfg.services["sonarr"]
    assert inst.adopted
    assert inst.container == "mon-sonarr"
    assert inst.api_key == "a" * 32


def test_the_real_published_port_is_kept_not_the_catalog_default():
    """Une stack existante n'utilise pas forcement les ports par defaut."""
    cfg = adopt.config_from_plan(
        adopt.build_plan([found(port=18989)]), data_root="/srv/d", config_root="/opt/c"
    )
    assert cfg.services["sonarr"].host_port == 18989


def test_a_url_base_is_carried_over():
    """Derriere un reverse proxy, le service n'est pas servi a la racine."""
    cfg = adopt.config_from_plan(
        adopt.build_plan([found(url_base="sonarr")]), data_root="/srv/d", config_root="/opt/c"
    )
    assert cfg.services["sonarr"].url("nas") == "http://nas:8991/sonarr"


# --------------------------------------------------- URL vues d'un conteneur


def test_an_adopted_service_is_reached_through_the_host():
    """Les conteneurs existants vivent sur leurs propres reseaux : le nom de
    service compose n'y resout pas. Verifie en conditions reelles - Prowlarr
    repondait "cannot connect to Sonarr" sur une URL en nom de service."""
    cfg = adopt.config_from_plan(
        adopt.build_plan([found()]), data_root="/srv/d", config_root="/opt/c", host="192.168.1.10"
    )
    spec = catalog.get("sonarr")
    assert cfg.services["sonarr"].internal_url(spec, cfg.host) == "http://192.168.1.10:8991"


def test_a_managed_service_keeps_the_compose_service_name():
    from arrsenal import orchestrator

    cfg = orchestrator.build_config(services=["sonarr"], data_root="/d", config_root="/c")
    spec = catalog.get("sonarr")
    assert cfg.services["sonarr"].internal_url(spec, cfg.host) == "http://sonarr:8989"


# --------------------------------------------------------------- persistance


def test_adopting_writes_stack_yml_but_never_a_compose_file(tmp_path):
    """Generer un docker-compose.yml donnerait a `uninstall` le pouvoir de
    detruire une stack qui n'appartient pas a arrsenal."""
    cfg = adopt.config_from_plan(
        adopt.build_plan([found()]), data_root="/srv/d", config_root="/opt/c"
    )
    adopt.write_stack(cfg, tmp_path)
    assert (tmp_path / "stack.yml").exists()
    assert not (tmp_path / "docker-compose.yml").exists()
    assert not (tmp_path / ".env").exists()


def test_the_written_stack_says_it_is_adopted(tmp_path):
    cfg = adopt.config_from_plan(
        adopt.build_plan([found()]), data_root="/srv/d", config_root="/opt/c"
    )
    path = adopt.write_stack(cfg, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "ADOPTEE" in text
    reloaded = StackConfig.model_validate(yaml.safe_load(text))
    assert reloaded.services["sonarr"].adopted


# ------------------------------------------------------------- diagnostics


def test_a_stack_without_a_download_client_is_flagged():
    cfg = adopt.config_from_plan(
        adopt.build_plan([found()]), data_root="/srv/d", config_root="/opt/c"
    )
    notes = adopt.missing_for_wiring(cfg)
    assert any("client de telechargement" in n for n in notes)


def test_prowlarr_alone_is_flagged():
    entry = found(service_id="prowlarr", container="prowlarr", port=9696)
    cfg = adopt.config_from_plan(
        adopt.build_plan([entry]), data_root="/srv/d", config_root="/opt/c"
    )
    assert any("Prowlarr est seul" in n for n in adopt.missing_for_wiring(cfg))


def test_a_complete_stack_raises_no_note():
    entries = [
        found(),
        found(service_id="prowlarr", container="prowlarr", port=9696),
        found(service_id="qbittorrent", container="qbit", port=8080, key=None),
    ]
    cfg = adopt.config_from_plan(
        adopt.build_plan(entries), data_root="/srv/d", config_root="/opt/c"
    )
    assert adopt.missing_for_wiring(cfg) == []


def test_keys_are_masked_for_display():
    assert discovery.mask_key("0123456789abcdef") == "0123…cdef"
    assert discovery.mask_key(None) == "-"
