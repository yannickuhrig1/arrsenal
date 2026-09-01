"""Rendu console : recapitulatif, progression, rapport final."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import catalog
from .models import StackConfig
from .runner import Check
from .wiring import StepResult

console = Console()


def print_checks(checks: list[Check]) -> bool:
    """Affiche le preflight. Renvoie False si un controle BLOQUANT a echoue."""
    table = Table(title="Preflight", show_lines=False)
    table.add_column("Controle", style="bold")
    table.add_column("")
    table.add_column("Detail", overflow="fold")
    blocked = False
    for check in checks:
        if check.ok:
            mark, style = "OK", "green"
        elif check.blocking:
            mark, style, blocked = "ECHEC", "red", True
        else:
            mark, style = "ATTENTION", "yellow"
        table.add_row(check.name, f"[{style}]{mark}[/{style}]", check.detail)
    console.print(table)
    return not blocked


def print_summary(cfg: StackConfig) -> None:
    table = Table(title="Recapitulatif - rien n'a encore ete ecrit")
    for col in ("Service", "Image", "URL", "Config"):
        table.add_column(col, overflow="fold")
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        spec, inst = catalog.get(sid), cfg.services[sid]
        table.add_row(
            spec.display_name,
            spec.image,
            inst.url(cfg.host) if inst.has_web_ui else "tache de fond",
            cfg.config_path(sid),
        )
    console.print(table)

    console.print(
        Panel(
            f"CONFIG_ROOT : {cfg.config_root}\n"
            f"DATA_ROOT   : {cfg.data_root}  (monte sur /data dans TOUS les conteneurs)\n"
            f"PUID:PGID   : {cfg.puid}:{cfg.pgid}  ({cfg.ids_source})\n"
            f"UMASK / TZ  : {cfg.umask}   {cfg.timezone}\n"
            f"Plateforme  : {cfg.platform.value}",
            title="Chemins",
            border_style="blue",
        )
    )

    if not cfg.vpn_enabled and any(cfg.enabled(s) for s in catalog.DOWNLOAD_CLIENTS):
        console.print(
            Panel(
                "Aucun VPN n'est configure pour le client torrent.\n"
                "Le trafic BitTorrent sortira sur l'adresse IP publique de cette machine, "
                "visible par les autres pairs.\n"
                "Pour ajouter un VPN, relancez avec --vpn (disponible en phase 4).",
                title="Avertissement VPN",
                border_style="yellow",
            )
        )


def print_step(result: StepResult) -> None:
    mark = "[green]OK   [/green]" if result.ok else "[red]ECHEC[/red]"
    console.print(f"  {mark} {result.name} - {result.detail}")
    for warning in result.warnings:
        console.print(f"         [yellow]attention[/yellow] {warning}")


def install_with_progress(cfg: StackConfig, project_dir, install) -> list[StepResult]:
    """Deroule l'installation sous une barre de progression.

    L'installation dure plusieurs minutes, dont un `docker compose up` muet le
    temps de telecharger les images. Sans barre, l'utilisateur ne sait pas si le
    programme travaille ou s'il est bloque.

    Les lignes de detail continuent d'etre imprimees AU-DESSUS de la barre :
    c'est Rich qui s'en charge, a condition de lui passer la meme console.
    """
    from rich.progress import BarColumn, TextColumn, TimeElapsedColumn
    from rich.progress import Progress as RichProgress

    from . import orchestrator

    total = orchestrator.expected_events(cfg)
    with RichProgress(
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=None),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as bar:
        task = bar.add_task("preparation", total=total)

        def advance(description: str) -> None:
            # Borne l'avancement : le total est une estimation, et une barre qui
            # depasse 100 % ferait douter du reste de l'affichage.
            done = min(bar.tasks[0].completed + 1, total)
            bar.update(task, completed=done, description=description[:28])

        def on_progress(progress: orchestrator.Progress) -> None:
            mark = "[green]OK[/green]" if progress.ok else "[red]ECHEC[/red]"
            console.print(f"  {mark} {progress.phase} : {progress.message}")
            advance(progress.phase)

        def on_step(result: StepResult) -> None:
            print_step(result)
            advance(result.name.split(":")[0])

        try:
            return install(cfg, project_dir, on_progress=on_progress, on_step=on_step)
        finally:
            # Une barre laissee a 94 % apres un succes se lit comme un echec.
            bar.update(task, completed=total, description="termine")


def print_final(cfg: StackConfig, results: list[StepResult]) -> None:
    failed = [r for r in results if not r.ok]
    created = sum(1 for r in results if r.created)

    table = Table(title="Acces")
    for col in ("Service", "URL", "Identifiant", "Mot de passe", "Cle API"):
        table.add_column(col, overflow="fold")
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        spec, inst = catalog.get(sid), cfg.services[sid]
        table.add_row(
            spec.display_name,
            inst.url(cfg.host) if inst.has_web_ui else "tache de fond",
            inst.username or "-",
            inst.password or "-",
            inst.api_key or "-",
        )
    console.print(table)
    console.print(
        "[dim]Ces identifiants sont aussi dans .env (chmod 600, deja dans .gitignore).[/dim]\n"
    )

    style = "green" if not failed else "red"
    headline = (
        f"{len(results) - len(failed)}/{len(results)} liens etablis, {created} crees a ce passage."
    )
    body = [headline]
    if failed:
        body.append("\nEchecs :")
        body += [f"  - {r.name}: {r.detail}" for r in failed]
        body.append("\nDiagnostic : `arrsenal doctor`")
    else:
        body.append(
            "\nProchaine etape : ajoutez vos indexeurs dans Prowlarr.\n"
            "Ils descendront automatiquement vers Sonarr et Radarr.\n"
            "arrsenal ne fournit aucun indexeur : ce choix vous appartient."
        )
    console.print(Panel("\n".join(body), title="Resultat", border_style=style))
