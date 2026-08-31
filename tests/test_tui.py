"""Tests de l'assistant, pilotes sans terminal via le harnais Textual.

Aucun de ces tests ne demarre Docker : ils s'arretent avant le recapitulatif, qui
est la derniere etape ou rien n'est encore ecrit.
"""

from __future__ import annotations

import pytest
from textual.widgets import Button, Checkbox, Input, RadioButton, Static

from arrsenal import catalog
from arrsenal.models import PlatformProfile
from arrsenal.tui.app import ArrsenalApp
from arrsenal.tui.screens import PathsScreen, ServicesScreen, SummaryScreen


@pytest.fixture
def app(tmp_path):
    return ArrsenalApp(project_dir=tmp_path)


async def _goto_services(pilot) -> ServicesScreen:
    """Force le passage a l'ecran de selection sans dependre de Docker."""
    pilot.app.push_screen(ServicesScreen())
    await pilot.pause()
    return pilot.app.screen


@pytest.mark.asyncio
async def test_welcome_blocks_until_docker_answers(app):
    """Le bouton Commencer reste desactive tant que Docker n'a pas repondu."""
    async with app.run_test() as pilot:
        assert pilot.app.screen.query_one("#start", Button).disabled is True


@pytest.mark.asyncio
async def test_every_catalog_service_has_a_checkbox(app):
    async with app.run_test() as pilot:
        screen = await _goto_services(pilot)
        ids = {box.id for box in screen.query(Checkbox)}
        assert ids == {f"svc-{sid}" for sid in catalog.CATALOG}


@pytest.mark.asyncio
async def test_default_selection_is_prechecked(app):
    async with app.run_test() as pilot:
        screen = await _goto_services(pilot)
        assert set(screen.selection()) == set(catalog.DEFAULT_SELECTION)


@pytest.mark.asyncio
async def test_summary_counts_the_links_that_will_be_wired(app):
    async with app.run_test() as pilot:
        screen = await _goto_services(pilot)
        text = str(screen.query_one("#selection-summary", Static).content)
        assert "liens" in text
        assert "18 liens" not in text  # selection par defaut, pas le catalogue entier


@pytest.mark.asyncio
async def test_checking_flood_pulls_in_a_download_client(app):
    """La dependance est resolue et ANNONCEE, pas silencieuse.

    Flood pilote qBittorrent OU Transmission : seul le premier est ajoute."""
    async with app.run_test() as pilot:
        screen = await _goto_services(pilot)
        for box in screen.query(Checkbox):
            box.value = box.id == "svc-flood"
        await pilot.pause()
        text = str(screen.query_one("#selection-summary", Static).content)
        assert "qBittorrent" in text
        assert "Transmission" not in text
        assert "prerequis" in text


@pytest.mark.asyncio
async def test_empty_selection_blocks_the_next_button(app):
    async with app.run_test() as pilot:
        screen = await _goto_services(pilot)
        for box in screen.query(Checkbox):
            box.value = False
        await pilot.pause()
        assert screen.query_one("#next", Button).disabled is True


@pytest.mark.asyncio
async def test_selection_is_carried_to_the_app_state(app):
    async with app.run_test() as pilot:
        screen = await _goto_services(pilot)
        for box in screen.query(Checkbox):
            box.value = box.id in ("svc-sonarr", "svc-prowlarr")
        await pilot.pause()
        screen.query_one("#next", Button).press()
        await pilot.pause()
        assert set(pilot.app.selection) == {"sonarr", "prowlarr"}


@pytest.mark.asyncio
async def test_switching_platform_rewrites_the_default_paths(app):
    async with app.run_test() as pilot:
        pilot.app.push_screen(PathsScreen())
        await pilot.pause()
        screen = pilot.app.screen
        assert screen.query_one("#data-root", Input).value == "/srv/data"

        screen.query_one("#plat-synology", RadioButton).value = True
        await pilot.pause()
        assert screen.query_one("#data-root", Input).value.startswith("/volume1")


@pytest.mark.asyncio
async def test_platform_note_states_where_the_ids_come_from(app):
    """Des PUID/PGID faux cassent les permissions de toute la stack :
    l'utilisateur doit voir d'ou viennent les valeurs proposees."""
    async with app.run_test() as pilot:
        pilot.app.push_screen(PathsScreen())
        await pilot.pause()
        screen = pilot.app.screen
        screen.query_one("#plat-unraid", RadioButton).value = True
        await pilot.pause()
        note = str(screen.query_one("#platform-note", Static).content)
        # Unraid impose nobody:users a l'echelle de la plateforme : c'est une
        # constante, pas une detection.
        assert "99:100" in note


@pytest.mark.asyncio
async def test_path_check_actually_creates_a_hardlink(app, tmp_path):
    async with app.run_test() as pilot:
        pilot.app.push_screen(PathsScreen())
        await pilot.pause()
        screen = pilot.app.screen
        screen.query_one("#data-root", Input).value = str(tmp_path / "data")
        screen.query_one("#check", Button).press()
        await pilot.pause()
        assert "hardlink" in str(screen.query_one("#paths-check", Static).content)


@pytest.mark.asyncio
async def test_summary_warns_about_the_absent_vpn(app):
    """L'avertissement VPN doit apparaitre AVANT toute ecriture."""
    async with app.run_test() as pilot:
        pilot.app.selection = ["sonarr", "transmission"]
        pilot.app.data_root = "/tmp/x"
        pilot.app.config_root = "/tmp/y"
        pilot.app.push_screen(SummaryScreen())
        await pilot.pause()
        text = str(pilot.app.screen.query_one("#summary-warnings", Static).content)
        assert "VPN" in text


@pytest.mark.asyncio
async def test_summary_shows_the_single_data_mount(app):
    async with app.run_test() as pilot:
        pilot.app.selection = ["sonarr"]
        pilot.app.data_root = "/srv/data"
        pilot.app.config_root = "/opt/c"
        pilot.app.push_screen(SummaryScreen())
        await pilot.pause()
        text = str(pilot.app.screen.query_one("#summary-paths", Static).content)
        assert "/data dans tous les conteneurs" in text


def test_app_build_config_matches_the_collected_state(tmp_path):
    """Le TUI ne doit pas reimplementer la construction de config."""
    app = ArrsenalApp(project_dir=tmp_path)
    app.selection = ["sonarr", "qbittorrent"]
    app.config_root, app.data_root = "/c", "/d"
    app.timezone = "Europe/Paris"
    app.platform = PlatformProfile.GENERIC_LINUX
    cfg = app.build_config()
    assert set(cfg.services) == {"sonarr", "qbittorrent"}
    assert cfg.timezone == "Europe/Paris"
    assert cfg.services["sonarr"].api_key
