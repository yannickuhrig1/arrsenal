"""Interface en ligne de commande.

Toute la logique vit dans orchestrator.py : cette couche ne fait que traduire des
options en appels et rendre les evenements. Le TUI (tui/app.py) consomme exactement
les memes fonctions, ce qui garantit qu'ils ne divergeront pas.
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from . import catalog, compose, dashboard, indexers_cli, orchestrator, report
from .clients.arr import ArrClient
from .models import PlatformProfile, StackConfig
from .orchestrator import InstallAborted, Progress
from .runner import Compose
from .wiring import Wirer

app = typer.Typer(
    add_completion=False,
    help="Deploie ET cable automatiquement une stack media *arr.",
    invoke_without_command=True,
)
console = report.console

STACK_FILE = "stack.yml"

app.add_typer(indexers_cli.app, name="indexers")


@app.callback()
def main(ctx: typer.Context) -> None:
    """Sans sous-commande, lance l'assistant interactif."""
    if ctx.invoked_subcommand is not None:
        return
    from .tui.app import run_wizard

    raise typer.Exit(run_wizard())


def _load_config(project_dir: Path) -> StackConfig:
    path = project_dir / STACK_FILE
    if not path.exists():
        raise typer.BadParameter(f"{path} introuvable. Lancez d'abord `arrsenal install`.")
    return StackConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _announce_page(path: Path, open_page: bool) -> None:
    """Signale la page d'acces, et l'ouvre si un navigateur existe.

    L'echec d'ouverture est normal sur un NAS sans environnement graphique : le
    chemin reste affiche, c'est lui qui compte.
    """
    if not path.exists():
        return
    console.print(f"\nPage d'acces : [bold]{path}[/bold]")
    if open_page and dashboard.open_in_browser(path):
        console.print("[dim]Ouverte dans votre navigateur.[/dim]")
    elif open_page:
        console.print("[dim]Aucun navigateur disponible ici : ouvrez ce fichier a la main.[/dim]")


def _echo(progress: Progress) -> None:
    mark = "[green]OK[/green]" if progress.ok else "[red]ECHEC[/red]"
    console.print(f"  {mark} {progress.phase} : {progress.message}")


# ---------------------------------------------------------------------- commands


@app.command()
def wizard() -> None:
    """Lance l'assistant interactif plein ecran."""
    from .tui.app import run_wizard

    raise typer.Exit(run_wizard())


@app.command()
def install(
    services: str = typer.Option(
        ",".join(catalog.DEFAULT_SELECTION),
        "--services",
        "-s",
        help="Liste separee par des virgules. Connus: " + ", ".join(sorted(catalog.CATALOG)),
    ),
    config_root: str | None = typer.Option(None, help="Racine des configurations."),
    data_root: str | None = typer.Option(None, help="Racine des donnees (monte sur /data)."),
    platform: PlatformProfile = typer.Option(PlatformProfile.GENERIC_LINUX, help="Profil."),
    host: str = typer.Option("localhost", help="Hote pour les URL du rapport final."),
    timezone: str = typer.Option("Etc/UTC", "--tz"),
    project_dir: Path = typer.Option(Path("."), help="Ou ecrire les artefacts."),
    dry_run: bool = typer.Option(False, "--dry-run", help="N'ecrit rien, montre tout."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Ne pas demander confirmation."),
    open_page: bool = typer.Option(
        True, "--open/--no-open", help="Ouvrir la page d'acces dans le navigateur."
    ),
) -> None:
    """Deploie et cable la stack de bout en bout, sans interaction."""
    selection = [s.strip() for s in services.split(",") if s.strip()]
    for sid in selection:
        catalog.get(sid)  # leve une erreur lisible si inconnu

    cfg = orchestrator.build_config(
        services=selection,
        config_root=config_root,
        data_root=data_root,
        platform=platform,
        host=host,
        timezone=timezone,
    )

    if not cfg.ids_certain:
        console.print(
            f"[yellow]PUID/PGID {cfg.puid}:{cfg.pgid} - {cfg.ids_source}.[/yellow]\n"
            f"[dim]Cette valeur decide de qui possede vos medias. Verifiez-la : sur un "
            f"NAS, lancez `id` en tant que l'utilisateur voulu.[/dim]"
        )

    if not report.print_checks(orchestrator.preflight(cfg)):
        raise typer.Exit(1)

    report.print_summary(cfg)

    if dry_run:
        console.print("[cyan]--dry-run : aucune ecriture. Compose qui serait genere :[/cyan]")
        console.print(compose.render_compose(cfg))
        raise typer.Exit(0)

    if not yes and not typer.confirm("Ecrire les fichiers et demarrer la stack ?", default=True):
        raise typer.Exit(0)

    try:
        results = orchestrator.install(
            cfg, project_dir, on_progress=_echo, on_step=report.print_step
        )
    except InstallAborted as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    report.print_final(cfg, results)
    _announce_page(project_dir / dashboard.FILENAME, open_page)
    raise typer.Exit(0 if all(r.ok for r in results) else 2)


@app.command()
def generate(project_dir: Path = typer.Option(Path("."), help="Repertoire du stack.yml.")) -> None:
    """Regenere docker-compose.yml et .env depuis stack.yml, sans rien demarrer."""
    written = compose.write_artifacts(_load_config(project_dir), project_dir)
    console.print("Regenere : " + ", ".join(p.name for p in written))


@app.command()
def wire(project_dir: Path = typer.Option(Path("."), help="Repertoire du stack.yml.")) -> None:
    """Rejoue uniquement le cablage sur une stack deja demarree. Idempotent."""
    cfg = _load_config(project_dir)
    wirer = Wirer(cfg)
    try:
        results = wirer.execute(on_step=report.print_step)
    finally:
        wirer.close()
    compose.write_artifacts(cfg, project_dir)
    report.print_final(cfg, results)
    raise typer.Exit(0 if all(r.ok for r in results) else 2)


@app.command()
def doctor(project_dir: Path = typer.Option(Path("."), help="Repertoire du stack.yml.")) -> None:
    """Diagnostique une installation existante."""
    cfg = _load_config(project_dir)
    if not report.print_checks(orchestrator.preflight(cfg)):
        console.print("[red]Des controles bloquants ont echoue.[/red]")

    console.print("\nEtat des conteneurs :")
    console.print(Compose(project_dir, cfg.project_name).ps())

    console.print("Joignabilite des API :")
    for sid, inst in orchestrator.iter_selected(cfg):
        spec = catalog.get(sid)
        if spec.api_family != "arr":
            continue
        try:
            with ArrClient(
                inst.url(cfg.host), inst.api_key or "", api_version=spec.api_version, name=sid
            ) as client:
                console.print(f"  [green]OK[/green] {sid} {client.version}")
        except Exception as exc:  # noqa: BLE001
            console.print(f"  [red]ECHEC[/red] {sid} : {exc}")


@app.command()
def uninstall(
    project_dir: Path = typer.Option(Path("."), help="Repertoire du stack.yml."),
    remove_config: bool = typer.Option(False, "--remove-config", help="Supprime CONFIG_ROOT."),
) -> None:
    """Arrete la stack. Ne touche JAMAIS a DATA_ROOT."""
    cfg = _load_config(project_dir)
    ok, message = Compose(project_dir, cfg.project_name).down()
    console.print(message if not ok else "Conteneurs arretes et supprimes.")

    if remove_config:
        if not typer.confirm(
            f"Supprimer definitivement {cfg.config_root} (bases, historiques, reglages) ?",
            default=False,
        ):
            raise typer.Exit(0)
        if not typer.confirm(
            "Confirmez une seconde fois : cette action est irreversible.", default=False
        ):
            raise typer.Exit(0)
        import shutil

        shutil.rmtree(cfg.config_root, ignore_errors=True)
        console.print(f"{cfg.config_root} supprime.")
    console.print(f"[dim]Vos medias dans {cfg.data_root} n'ont pas ete touches.[/dim]")


@app.command("list")
def list_services() -> None:
    """Liste le catalogue."""
    from rich.table import Table

    table = Table(title="Catalogue")
    for col in ("id", "Nom", "Categorie", "Image", "Port", "Notes"):
        table.add_column(col, overflow="fold")
    for sid in catalog.STARTUP_ORDER:
        spec = catalog.get(sid)
        table.add_row(
            spec.id,
            spec.display_name,
            spec.category.value,
            spec.image,
            str(spec.default_host_port),
            spec.notes,
        )
    console.print(table)


if __name__ == "__main__":
    app()
