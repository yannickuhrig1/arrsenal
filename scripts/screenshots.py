"""Genere les captures SVG de l'assistant pour le README.

Tourne sans terminal et sans Docker : le harnais de test de Textual pilote
l'application en memoire et exporte chaque ecran en SVG.

    python scripts/screenshots.py

Les fichiers sont regeneres a l'identique a chaque execution, ce qui permet de
les versionner et de voir les regressions visuelles dans une pull request.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from textual.widgets import Label, ListItem, ListView, Static

from arrsenal.clients.prowlarr import IndexerDefinition
from arrsenal.tui.app import ArrsenalApp
from arrsenal.tui.indexers import IndexersScreen
from arrsenal.tui.screens import (
    InstallScreen,
    PathsScreen,
    ReportScreen,
    ServicesScreen,
    SummaryScreen,
    TemplatesScreen,
)
from arrsenal.wiring import StepResult

OUT = ROOT / "docs" / "screenshots"
SIZE = (104, 34)


#: Resultats fictifs pour illustrer l'ecran de rapport sans rien demarrer.
FAKE_STEPS = [
    StepResult("sonarr: dossier racine /data/media/tv", True, "cree", created=True),
    StepResult("radarr: dossier racine /data/media/movies", True, "cree", created=True),
    StepResult("qbittorrent: categories avec chemin de sauvegarde", True, "creees: tv, movies"),
    StepResult("sonarr: client de telechargement qBittorrent", True, "cree (id=1), test OK"),
    StepResult("radarr: client de telechargement qBittorrent", True, "cree (id=1), test OK"),
    StepResult("prowlarr -> sonarr (Application, fullSync)", True, "cree (id=1), test OK"),
    StepResult("prowlarr -> radarr (Application, fullSync)", True, "cree (id=2), test OK"),
    StepResult("jellyfin: assistant + bibliotheques", True, "Films, Series"),
]


#: Definition fictive : arrsenal ne nomme et ne recommande aucun indexeur reel.
FAKE_DEFINITION = IndexerDefinition(
    name="Votre indexeur",
    implementation="Torznab",
    privacy="private",
    protocol="torrent",
    language="fr-FR",
    description="La liste vient de votre Prowlarr. arrsenal n'en fournit aucun.",
    raw={
        "indexerUrls": ["https://exemple.invalid/"],
        "fields": [
            {"name": "baseUrl", "type": "select", "label": "Url", "value": None},
            {"name": "apiKey", "type": "textbox", "label": "API Key", "privacy": "apiKey"},
        ],
    },
)


async def capture() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    async def shot(app: ArrsenalApp, pilot, name: str) -> None:
        path = OUT / f"{name}.svg"
        path.write_text(app.export_screenshot(), encoding="utf-8")
        print(f"  {path.relative_to(ROOT)}")

    app = ArrsenalApp(project_dir=ROOT)
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        await shot(app, pilot, "1-accueil")

        app.push_screen(ServicesScreen())
        await pilot.pause()
        await shot(app, pilot, "2-services")

        app.selection = ["prowlarr", "sonarr", "radarr", "qbittorrent", "jellyfin"]
        app.push_screen(PathsScreen())
        await pilot.pause()
        await shot(app, pilot, "3-chemins")

        app.data_root, app.config_root = "/srv/data", "/opt/arrsenal/config"
        app.selection = [*app.selection, "recyclarr"]
        app.push_screen(TemplatesScreen())
        # La liste des templates arrive d'un worker : capturer trop tot montrerait
        # « Chargement… » au lieu de l'ecran reel.
        for _ in range(40):
            await pilot.pause(0.25)
            if str(app.screen.query_one("#tpl-choices-sonarr", Static).content):
                break
        await shot(app, pilot, "4-profils")

        app.push_screen(SummaryScreen())
        await pilot.pause()
        await shot(app, pilot, "5-recapitulatif")

        # L'ecran d'installation lance un worker : on le rend inerte pour la
        # capture, puis on injecte des lignes representatives.
        InstallScreen.run_install = lambda self: None  # type: ignore[method-assign]
        app.stack_config = app.build_config()
        app.push_screen(InstallScreen())
        await pilot.pause()
        screen = app.screen
        screen._phase("cablage : 8/8 liens etablis")
        for step in FAKE_STEPS:
            screen._log(f"  [green]OK[/green]  {step.name} - {step.detail}")
        await pilot.pause()
        await shot(app, pilot, "6-installation")

        # Etape indexeurs : rendue hors ligne. Le chargement des definitions est
        # neutralise, on injecte des exemples representatifs de ce que Prowlarr
        # renvoie. Aucun indexeur reel n'est nomme : arrsenal n'en recommande aucun.
        IndexersScreen.load_definitions = lambda self: None  # type: ignore[method-assign]
        app.push_screen(IndexersScreen())
        await pilot.pause()
        screen = app.screen
        screen._set_status("[dim]626 definitions fournies par votre Prowlarr[/dim]")
        screen._matches = [FAKE_DEFINITION]
        results = screen.query_one("#indexer-results", ListView)
        results.append(ListItem(Label("Votre indexeur  [dim]prive - torrent[/dim]")))
        screen._render_form(FAKE_DEFINITION)
        # mount() est asynchrone : sans ces passes, la capture part avant que les
        # champs du formulaire soient rendus.
        for _ in range(4):
            await pilot.pause()
        await shot(app, pilot, "7-indexeurs")

        app.results = FAKE_STEPS
        app.push_screen(ReportScreen())
        await pilot.pause()
        await shot(app, pilot, "8-rapport")


if __name__ == "__main__":
    print("Generation des captures :")
    asyncio.run(capture())
