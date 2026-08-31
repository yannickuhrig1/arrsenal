"""Tests de l'ecran indexeurs. Aucun reseau : le chargement est neutralise."""

from __future__ import annotations

import pytest
from textual.widgets import Button, Input, Static

from arrsenal.clients.prowlarr import IndexerDefinition
from arrsenal.tui.app import ArrsenalApp
from arrsenal.tui.indexers import IndexersScreen
from arrsenal.tui.screens import ReportScreen

DEFINITION = IndexerDefinition(
    name="Exemple",
    implementation="Torznab",
    privacy="private",
    protocol="torrent",
    language="fr-FR",
    description="Definition fictive.",
    raw={
        "indexerUrls": ["https://un.invalid/", "https://deux.invalid/"],
        "fields": [
            {"name": "baseUrl", "type": "select", "label": "Url", "value": None},
            {"name": "apiKey", "type": "textbox", "label": "API Key", "privacy": "apiKey"},
            {"name": "baseSettings.queryLimit", "type": "number", "label": "Limite"},
            {"name": "info_help", "type": "info", "label": "Aide"},
        ],
    },
)


@pytest.fixture
def screen_app(tmp_path, monkeypatch):
    monkeypatch.setattr(IndexersScreen, "load_definitions", lambda self: None)
    app = ArrsenalApp(project_dir=tmp_path)
    app.selection = ["prowlarr"]
    app.stack_config = app.build_config()
    return app


@pytest.mark.asyncio
async def test_intro_states_that_arrsenal_provides_no_indexer(screen_app):
    """La position juridique du projet doit etre lisible a l'ecran, pas seulement
    dans le README."""
    async with screen_app.run_test() as pilot:
        pilot.app.push_screen(IndexersScreen())
        await pilot.pause()
        intro = str(pilot.app.screen.query_one("#indexers-intro", Static).content)
        assert "aucun" in intro.lower()
        assert "votre propre Prowlarr" in intro


@pytest.mark.asyncio
async def test_intro_warns_that_adding_contacts_the_indexer(screen_app):
    """Prowlarr contacte l'indexeur pour valider : l'utilisateur doit le savoir
    avant de cliquer."""
    async with screen_app.run_test() as pilot:
        pilot.app.push_screen(IndexersScreen())
        await pilot.pause()
        intro = str(pilot.app.screen.query_one("#indexers-intro", Static).content)
        assert "contacte" in intro


@pytest.mark.asyncio
async def test_the_step_can_be_skipped(screen_app):
    async with screen_app.run_test() as pilot:
        pilot.app.push_screen(IndexersScreen())
        await pilot.pause()
        pilot.app.results = []
        pilot.app.screen.query_one("#skip", Button).press()
        await pilot.pause()
        assert isinstance(pilot.app.screen, ReportScreen)


@pytest.mark.asyncio
async def test_add_is_disabled_until_an_indexer_is_chosen(screen_app):
    async with screen_app.run_test() as pilot:
        pilot.app.push_screen(IndexersScreen())
        await pilot.pause()
        assert pilot.app.screen.query_one("#add", Button).disabled is True


@pytest.mark.asyncio
async def test_form_shows_credentials_and_hides_tuning_fields(screen_app):
    async with screen_app.run_test() as pilot:
        pilot.app.push_screen(IndexersScreen())
        await pilot.pause()
        screen = pilot.app.screen
        screen._render_form(DEFINITION)
        await pilot.pause()

        names = {inp.id for inp in screen.query(".indexer-field").results(Input)}
        assert names == {"fld-baseUrl", "fld-apiKey"}
        assert screen.query_one("#add", Button).disabled is False


@pytest.mark.asyncio
async def test_secret_fields_are_masked_on_screen(screen_app):
    async with screen_app.run_test() as pilot:
        pilot.app.push_screen(IndexersScreen())
        await pilot.pause()
        screen = pilot.app.screen
        screen._render_form(DEFINITION)
        await pilot.pause()
        masked = {inp.id: inp.password for inp in screen.query(".indexer-field").results(Input)}
        assert masked == {"fld-baseUrl": False, "fld-apiKey": True}


@pytest.mark.asyncio
async def test_base_url_is_prefilled_from_the_definition(screen_app):
    """Sans cela l'utilisateur devrait deviner l'adresse du tracker."""
    async with screen_app.run_test() as pilot:
        pilot.app.push_screen(IndexersScreen())
        await pilot.pause()
        screen = pilot.app.screen
        screen._render_form(DEFINITION)
        await pilot.pause()
        url = screen.query_one("#fld-baseUrl", Input)
        assert url.value == "https://un.invalid/"


@pytest.mark.asyncio
async def test_rendering_a_second_indexer_replaces_the_first_form(screen_app):
    """Sinon les champs du precedent resteraient a l'ecran et seraient envoyes."""
    other = IndexerDefinition(
        name="Autre",
        implementation="X",
        privacy="public",
        protocol="usenet",
        language="en",
        description="",
        raw={"indexerUrls": [], "fields": [{"name": "cookie", "type": "textbox"}]},
    )
    async with screen_app.run_test() as pilot:
        pilot.app.push_screen(IndexersScreen())
        await pilot.pause()
        screen = pilot.app.screen
        screen._render_form(DEFINITION)
        await pilot.pause()
        screen._render_form(other)
        await pilot.pause()
        names = {inp.id for inp in screen.query(".indexer-field").results(Input)}
        assert names == {"fld-cookie"}
