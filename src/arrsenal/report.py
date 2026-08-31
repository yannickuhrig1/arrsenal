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
            spec.display_name, spec.image, inst.url(cfg.host), cfg.config_path(sid)
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
            inst.url(cfg.host),
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
