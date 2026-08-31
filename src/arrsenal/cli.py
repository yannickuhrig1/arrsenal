"""Interface en ligne de commande.

Phase 1 : CLI non interactive uniquement. Le wizard Textual arrive en phase 3 et
consommera exactement les memes fonctions du coeur.
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from . import catalog, compose, report, seed
from .clients.arr import ArrClient
from .layout import PROFILE_DEFAULTS, create_tree, detect_ids
from .models import PlatformProfile, ServiceInstance, StackConfig
from .runner import Check, Compose, check_disk_space, check_docker, check_hardlinks, check_port_free
from .wiring import Wirer

app = typer.Typer(
    add_completion=False,
    help="Deploie ET cable automatiquement une stack media *arr.",
    no_args_is_help=True,
)
console = report.console

STACK_FILE = "stack.yml"


# --------------------------------------------------------------------- helpers


def _build_config(
    *,
    services: list[str],
    config_root: str | None,
    data_root: str | None,
    platform: PlatformProfile,
    host: str,
    timezone: str,
) -> StackConfig:
    defaults = PROFILE_DEFAULTS[platform]
    uid, gid = detect_ids() if platform is PlatformProfile.GENERIC_LINUX else (
        defaults.puid,
        defaults.pgid,
    )

    selection = catalog.resolve_dependencies(services)
    cfg = StackConfig(
        platform=platform,
        config_root=config_root or defaults.config_root,
        data_root=data_root or defaults.data_root,
        puid=uid,
        pgid=gid,
        timezone=timezone,
        host=host,
    )
    for sid in selection:
        spec = catalog.get(sid)
        inst = ServiceInstance(spec_id=sid, host_port=spec.default_host_port)
        if spec.api_family == "arr":
            inst.api_key = seed.generate_api_key()
            inst.username = "arrsenal"
            inst.password = seed.generate_password()
        elif spec.api_family in ("transmission", "jellyfin"):
            inst.username = "arrsenal"
            inst.password = seed.generate_password()
        cfg.services[sid] = inst
    return cfg


def _load_config(project_dir: Path) -> StackConfig:
    path = project_dir / STACK_FILE
    if not path.exists():
        raise typer.BadParameter(
            f"{path} introuvable. Lancez d'abord `arrsenal install`."
        )
    return StackConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _preflight(cfg: StackConfig) -> list[Check]:
    checks = check_docker()
    for sid in catalog.STARTUP_ORDER:
        if cfg.enabled(sid):
            checks.append(check_port_free(cfg.services[sid].host_port, sid))
    checks.append(check_disk_space(cfg.data_root))
    checks.append(check_hardlinks(cfg.data_root))
    return checks


def _seed_all(cfg: StackConfig) -> list[str]:
    """Pre-seme les configs. Renvoie les libelles des actions effectuees."""
    actions: list[str] = []
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        spec, inst = catalog.get(sid), cfg.services[sid]
        cfg_dir = Path(cfg.config_path(sid))
        if spec.api_family == "arr":
            effective, written = seed.seed_arr(
                cfg_dir,
                api_key=inst.api_key or "",
                port=spec.internal_port,
                instance_name=spec.display_name,
                username=inst.username or "arrsenal",
                password=inst.password or "",
            )
            if not written:
                # Un config.xml existait : SA cle fait autorite, on s'aligne.
                inst.api_key = effective
            actions.append(
                f"{sid}: config.xml {'pre-seme' if written else 'existant, cle reprise'}"
            )
        elif spec.api_family == "transmission":
            written, message = seed.seed_transmission(
                cfg_dir,
                rpc_username=inst.username or "arrsenal",
                rpc_password=inst.password or "",
            )
            actions.append(f"{sid}: {message}")
    return actions


# ---------------------------------------------------------------------- commands


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
) -> None:
    """Deploie et cable la stack de bout en bout."""
    selection = [s.strip() for s in services.split(",") if s.strip()]
    for sid in selection:
        catalog.get(sid)  # leve une erreur lisible si inconnu

    cfg = _build_config(
        services=selection,
        config_root=config_root,
        data_root=data_root,
        platform=platform,
        host=host,
        timezone=timezone,
    )

    defaults = PROFILE_DEFAULTS[platform]
    if not defaults.verified:
        console.print(
            f"[yellow]Profil {platform.value} : valeurs par defaut NON VERIFIEES."
            f"\n{defaults.note}\nVerifiez PUID/PGID et les chemins avant de continuer.[/yellow]"
        )

    if not report.print_checks(_preflight(cfg)):
        raise typer.Exit(1)

    report.print_summary(cfg)

    if dry_run:
        console.print("[cyan]--dry-run : aucune ecriture. Compose qui serait genere :[/cyan]")
        console.print(compose.render_compose(cfg))
        raise typer.Exit(0)

    if not yes and not typer.confirm("Ecrire les fichiers et demarrer la stack ?", default=True):
        raise typer.Exit(0)

    created = create_tree(cfg.data_root, cfg.config_root, list(cfg.services))
    console.print(f"Arborescence : {len(created)} dossiers crees.")

    for action in _seed_all(cfg):
        console.print(f"  {action}")

    written = compose.write_artifacts(cfg, project_dir)
    console.print("Artefacts : " + ", ".join(p.name for p in written))

    runner = Compose(project_dir, cfg.project_name)
    valid, message = runner.config_valid()
    if not valid:
        console.print(f"[red]compose invalide :[/red] {message}")
        raise typer.Exit(1)

    console.print("Demarrage des conteneurs (le premier lancement peut prendre plusieurs minutes)...")
    ok, message = runner.up()
    if not ok:
        console.print(f"[red]docker compose up a echoue :[/red] {message}")
        raise typer.Exit(1)

    console.print("Attente de disponibilite des services...")
    _wait_all(cfg)

    console.print("Cablage :")
    wirer = Wirer(cfg)
    try:
        results = wirer.execute(on_step=report.print_step)
    finally:
        wirer.close()

    # Le cablage peut enrichir la config (la cle API Jellyfin n'existe qu'apres
    # l'assistant de demarrage). On repersiste pour que .env et stack.yml soient
    # complets et que `wire` soit rejouable seul.
    compose.write_artifacts(cfg, project_dir)

    report.print_final(cfg, results)
    raise typer.Exit(0 if all(r.ok for r in results) else 2)


def _wait_all(cfg: StackConfig) -> None:
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        spec, inst = catalog.get(sid), cfg.services[sid]
        if spec.api_family != "arr":
            continue
        with ArrClient(
            inst.url(cfg.host), inst.api_key or "", api_version=spec.api_version, name=sid
        ) as client:
            client.wait_ready()
            console.print(f"  [green]OK[/green] {sid} {client.version}")


@app.command()
def generate(
    project_dir: Path = typer.Option(Path("."), help="Repertoire du stack.yml."),
) -> None:
    """Regenere docker-compose.yml et .env depuis stack.yml, sans rien demarrer."""
    cfg = _load_config(project_dir)
    written = compose.write_artifacts(cfg, project_dir)
    console.print("Regenere : " + ", ".join(p.name for p in written))


@app.command()
def wire(
    project_dir: Path = typer.Option(Path("."), help="Repertoire du stack.yml."),
) -> None:
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
def doctor(
    project_dir: Path = typer.Option(Path("."), help="Repertoire du stack.yml."),
) -> None:
    """Diagnostique une installation existante."""
    cfg = _load_config(project_dir)
    if not report.print_checks(_preflight(cfg)):
        console.print("[red]Des controles bloquants ont echoue.[/red]")

    console.print("\nEtat des conteneurs :")
    console.print(Compose(project_dir, cfg.project_name).ps())

    console.print("Joignabilite des API :")
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        spec, inst = catalog.get(sid), cfg.services[sid]
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
        if not typer.confirm("Confirmez une seconde fois : cette action est irreversible.", default=False):
            raise typer.Exit(0)
        import shutil as _shutil

        _shutil.rmtree(cfg.config_root, ignore_errors=True)
        console.print(f"{cfg.config_root} supprime.")
    console.print(
        f"[dim]Vos medias dans {cfg.data_root} n'ont pas ete touches.[/dim]"
    )


@app.command("list")
def list_services() -> None:
    """Liste le catalogue."""
    from rich.table import Table

    table = Table(title="Catalogue (Phase 1)")
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
