"""Tests de l'ecran de choix des profils de qualite.

Aucun de ces tests ne touche au reseau : le manifeste est simule. C'est la forme
reelle du fichier `templates.json` publie par Recyclarr qui est reproduite.
"""

from __future__ import annotations

import pytest
from textual.widgets import Button, Input, Static

from arrsenal.clients import recyclarr
from arrsenal.tui.app import ArrsenalApp
from arrsenal.tui.screens import PathsScreen, SummaryScreen, TemplatesScreen

AVAILABLE = {
    "sonarr": ["sonarr-german-hd-bluray-web", "web-1080p", "web-2160p"],
    "radarr": ["french-multi-vf-hd-bluray-web", "hd-bluray-web"],
}


@pytest.fixture
def app(tmp_path):
    return ArrsenalApp(project_dir=tmp_path)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """L'assistant ne doit jamais dependre de GitHub pendant les tests."""
    monkeypatch.setattr(recyclarr, "fetch_manifest", lambda **kw: (dict(AVAILABLE), None))


async def _goto_templates(pilot, selection) -> TemplatesScreen:
    pilot.app.selection = selection
    pilot.app.push_screen(TemplatesScreen())
    await pilot.pause()
    await pilot.pause()
    return pilot.app.screen


@pytest.mark.asyncio
async def test_les_defauts_sont_preremplis(app):
    async with app.run_test() as pilot:
        screen = await _goto_templates(pilot, ["sonarr", "radarr", "recyclarr"])

        assert screen.query_one("#tpl-sonarr", Input).value == "web-1080p"
        assert screen.query_one("#tpl-radarr", Input).value == "hd-bluray-web"
        assert screen.choices() == recyclarr.DEFAULT_TEMPLATES


@pytest.mark.asyncio
async def test_seuls_les_services_installes_sont_proposes(app):
    """Sans Radarr, lui demander un profil n'a aucun sens."""
    async with app.run_test() as pilot:
        screen = await _goto_templates(pilot, ["sonarr", "recyclarr"])

        assert screen.query_one("#tpl-sonarr", Input) is not None
        assert not screen.query("#tpl-radarr")
        assert list(screen.choices()) == ["sonarr"]


@pytest.mark.asyncio
async def test_un_nom_inconnu_est_signale_avant_l_installation(app):
    """Recyclarr ne refuserait le nom qu'a la fin du cablage, stack demarree.

    Le dire ici coute une comparaison ; le decouvrir la-bas coute une
    installation.
    """
    async with app.run_test() as pilot:
        screen = await _goto_templates(pilot, ["sonarr", "radarr", "recyclarr"])
        screen.query_one("#tpl-sonarr", Input).value = "web-9999p"
        await pilot.pause()

        assert screen.query_one("#next", Button).disabled is True
        assert "inconnu" in str(screen.query_one("#templates-status", Static).content)

        screen.query_one("#tpl-sonarr", Input).value = "web-2160p"
        await pilot.pause()

        assert screen.query_one("#next", Button).disabled is False


@pytest.mark.asyncio
async def test_passer_laisse_les_defauts_au_cablage(app):
    """« Passer » ne doit pas signifier « aucun profil »."""
    async with app.run_test() as pilot:
        screen = await _goto_templates(pilot, ["sonarr", "radarr", "recyclarr"])
        screen.query_one("#skip", Button).press()
        await pilot.pause()

        assert pilot.app.recyclarr_templates == {}
        # Le cablage retombe alors sur les defauts du module, pas sur rien.
        cfg = pilot.app.build_config()
        assert cfg.recyclarr_templates == {}
        assert recyclarr.DEFAULT_TEMPLATES["sonarr"] == "web-1080p"


@pytest.mark.asyncio
async def test_un_choix_atteint_la_configuration(app):
    async with app.run_test() as pilot:
        screen = await _goto_templates(pilot, ["sonarr", "radarr", "recyclarr"])
        screen.query_one("#tpl-radarr", Input).value = "french-multi-vf-hd-bluray-web"
        await pilot.pause()
        screen.query_one("#next", Button).press()
        await pilot.pause()

        cfg = pilot.app.build_config()
        assert cfg.recyclarr_templates["radarr"] == "french-multi-vf-hd-bluray-web"


@pytest.mark.asyncio
async def test_un_manifeste_injoignable_n_empeche_pas_de_continuer(app, monkeypatch):
    """Sans reseau, on ne peut pas verifier les noms. Ce n'est pas une raison
    pour bloquer quelqu'un qui sait ce qu'il veut."""
    monkeypatch.setattr(recyclarr, "fetch_manifest", lambda **kw: ({}, "depot injoignable"))

    async with app.run_test() as pilot:
        screen = await _goto_templates(pilot, ["sonarr", "recyclarr"])

        assert screen.query_one("#next", Button).disabled is False
        assert "injoignable" in str(screen.query_one("#templates-status", Static).content)


@pytest.mark.asyncio
async def test_l_ecran_est_saute_sans_recyclarr(app):
    """L'etape ne doit pas apparaitre pour une stack qui n'en a pas l'usage."""
    async with app.run_test() as pilot:
        pilot.app.selection = ["sonarr", "radarr"]
        pilot.app.push_screen(PathsScreen())
        await pilot.pause()
        pilot.app.screen.query_one("#next", Button).press()
        await pilot.pause()

        assert isinstance(pilot.app.screen, SummaryScreen)


@pytest.mark.asyncio
async def test_l_ecran_apparait_avec_recyclarr(app):
    async with app.run_test() as pilot:
        pilot.app.selection = ["sonarr", "recyclarr"]
        pilot.app.push_screen(PathsScreen())
        await pilot.pause()
        pilot.app.screen.query_one("#next", Button).press()
        await pilot.pause()

        assert isinstance(pilot.app.screen, TemplatesScreen)


@pytest.mark.asyncio
async def test_recyclarr_seul_ne_declenche_pas_l_ecran(app):
    """Sans Sonarr ni Radarr, Recyclarr n'a rien a configurer."""
    async with app.run_test() as pilot:
        pilot.app.selection = ["recyclarr", "jellyfin"]
        pilot.app.push_screen(PathsScreen())
        await pilot.pause()
        pilot.app.screen.query_one("#next", Button).press()
        await pilot.pause()

        assert isinstance(pilot.app.screen, SummaryScreen)
