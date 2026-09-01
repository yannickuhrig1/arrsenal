"""Genere les captures SVG de l'assistant pour le README.

Tourne sans terminal et sans Docker : le harnais de test de Textual pilote
l'application en memoire et exporte chaque ecran en SVG.

    python scripts/screenshots.py

Les fichiers sont regeneres a l'identique a chaque execution ET sur n'importe
quelle machine, ce qui permet de les versionner et de voir les regressions
visuelles dans une pull request. La CI le verifie.

Quatre sources de variation sont donc neutralisees ici, et il a fallu les
trouver : les identifiants Unix detectes (differents sous Windows et sous
Linux), les secrets generes (tires au hasard a chaque execution), le repertoire
du projet (le chemin personnel de qui lance le script se retrouvait dans une
capture publiee) et la liste des templates Recyclarr (elle vient du depot amont
et bouge sans nous).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from textual.widgets import Footer, Label, ListItem, ListView, Static

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

#: Repertoire affiche dans les captures. Surtout PAS celui d'ou l'on lance le
#: script : le chemin personnel de l'auteur finirait dans une image publiee.
SHOWN_PROJECT_DIR = PurePosixPath("/opt/arrsenal")

#: Secrets d'illustration. Les vrais sont tires au hasard a chaque execution :
#: sans cela, deux captures ne seraient jamais identiques.
SHOWN_API_KEY = "0123456789abcdef0123456789abcdef"
SHOWN_PASSWORD = "MotDePasseGenere42"

#: Templates figes pour l'illustration. La liste reelle vient du depot Recyclarr
#: et change quand il en publie : une capture comparee a l'octet pres ne peut pas
#: en dependre. Les noms sont vrais, seul l'instantane est fige.
SHOWN_TEMPLATES = {
    "sonarr": [
        "french-multi-vf-bluray-web-1080p",
        "french-multi-vf-bluray-web-2160p",
        "french-multi-vo-bluray-web-1080p",
        "sonarr-german-hd-bluray-web",
        "web-1080p",
        "web-2160p",
        "web-simple-1080p",
    ],
    "radarr": [
        "french-multi-vf-hd-bluray-web",
        "french-multi-vf-uhd-bluray-web",
        "french-multi-vo-hd-bluray-web",
        "hd-bluray-web",
        "radarr-german-hd-bluray-web",
        "remux-web-1080p",
        "uhd-bluray-web",
    ],
}


#: Diagnostic Docker d'illustration. L'ecran d'accueil affiche celui de la
#: machine : sans cela, une machine sans Docker (une CI, par exemple) produit une
#: capture rouge, et le chemin du binaire trahit le systeme de l'auteur.
SHOWN_DOCKER = (
    ("docker", "trouve: /usr/bin/docker"),
    ("daemon docker", "version serveur 27.3.1"),
    ("docker compose", "v2.29.7"),
)


def freeze_environment() -> None:
    """Rend la capture independante de la machine qui la produit."""
    from arrsenal import orchestrator, runner, seed
    from arrsenal.tui import screens

    runner.check_docker = lambda: [  # type: ignore[assignment]
        runner.Check(name, True, detail) for name, detail in SHOWN_DOCKER
    ]

    fixed_ids = (1000, 1000, "profil generic-linux", True)
    orchestrator.resolve_ids = lambda profile: fixed_ids  # type: ignore[assignment]
    screens.resolve_ids = lambda profile: fixed_ids  # type: ignore[assignment]
    seed.generate_api_key = lambda: SHOWN_API_KEY  # type: ignore[assignment]
    seed.generate_password = lambda *a, **kw: SHOWN_PASSWORD  # type: ignore[assignment]
    screens.recyclarr_cfg.available_templates = (  # type: ignore[assignment]
        lambda config_dir=None, **kw: (dict(SHOWN_TEMPLATES), None)
    )


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
    freeze_environment()

    async def shot(app: ArrsenalApp, pilot, name: str) -> None:
        # Le `Footer` monte ses raccourcis de facon asynchrone. Exporter sans
        # l'attendre donne, selon l'ordonnancement, une capture avec pied de page
        # et une capture sans : deux executions de suite ne coincidaient pas.
        for _ in range(20):
            footer = app.screen.query(Footer)
            if footer and footer.first().children:
                break
            await pilot.pause()
        path = OUT / f"{name}.svg"
        # newline="" : sans cela Python traduit les sauts de ligne en CRLF sous
        # Windows. Git le rattrape a la normalisation, mais un depot configure
        # autrement verrait le controle de la CI echouer sans rien de reel.
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(app.export_screenshot())
        print(f"  {path.relative_to(ROOT)}")

    app = ArrsenalApp(project_dir=SHOWN_PROJECT_DIR)
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
        # Une barre sans total s'affiche en mode INDETERMINE, c'est-a-dire animee :
        # deux captures ne coincideraient jamais. Lui donner un total la fige, et
        # montre au passage ce que l'utilisateur voit vraiment.
        screen._set_total(len(FAKE_STEPS))
        for _ in FAKE_STEPS:
            screen._advance()
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
