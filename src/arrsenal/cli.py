"""Interface en ligne de commande.

Toute la logique vit dans orchestrator.py : cette couche ne fait que traduire des
options en appels et rendre les evenements. Le TUI (tui/app.py) consomme exactement
les memes fonctions, ce qui garantit qu'ils ne divergeront pas.
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml

from . import (
    __version__,
    admin,
    catalog,
    compose,
    dashboard,
    discovery,
    indexers_cli,
    journal,
    orchestrator,
    report,
)
from . import adopt as adopt_mod
from .clients import recyclarr as recyclarr_cfg
from .clients.arr import ArrClient
from .layout import default_profile, path_warning
from .models import VPN_PROVIDERS, PlatformProfile, StackConfig, VpnConfig
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


def _show_version(value: bool) -> None:
    if value:
        console.print(f"arrsenal {__version__}")
        raise typer.Exit(0)


@app.callback()
def main(
    ctx: typer.Context,
    _version: bool = typer.Option(
        False, "--version", "-V", callback=_show_version, is_eager=True,
        help="Affiche la version et quitte.",
    ),
) -> None:
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


def _traiter_config_existante(
    cfg: StackConfig, reset: bool | None, *, assume_yes: bool
) -> None:
    """Propose de repartir de zero quand une configuration inutilisable est la.

    « Inutilisable » a un sens precis : qBittorrent, Transmission, Jellyfin,
    autobrr et qui ne stockent leur mot de passe que hache. arrsenal ne peut ni
    le relire ni le reinitialiser, et ceux qu'il annonce seront refuses.

    Sans reponse explicite, on CONSERVE : effacer la configuration de quelqu'un
    par defaut serait inacceptable.
    """
    concernes = orchestrator.unusable_configs(cfg)
    if not concernes:
        return

    console.print(
        f"\n[yellow]Configuration existante detectee[/yellow] pour "
        f"[bold]{', '.join(concernes)}[/bold] dans {cfg.config_root}.\n"
        f"[dim]Leurs mots de passe n'y sont stockes que haches : arrsenal ne peut pas "
        f"les reprendre, et ceux qu'il va annoncer seront refuses.[/dim]"
    )
    for sid in concernes:
        console.print(f"  [dim]{cfg.config_path(sid)}[/dim]")

    if reset is None:
        if assume_yes:
            # `--yes` repond oui aux questions, pas aux suppressions.
            console.print(
                "[dim]Conservee (--yes ne supprime rien). Utilisez --reset-config pour "
                "repartir de zero.[/dim]"
            )
            return
        console.print(
            "\n[dim]Vos medias ne sont jamais touches : seuls ces dossiers de "
            "configuration le seraient.[/dim]"
        )
        reset = typer.confirm("Supprimer ces configurations et repartir de zero ?", default=False)

    if not reset:
        console.print("[dim]Configurations conservees.[/dim]")
        return

    efface = orchestrator.reset_configs(cfg, concernes)
    for chemin in efface:
        console.print(f"  [green]supprime[/green] {chemin}")
    journal.finish(f"configurations supprimees : {', '.join(concernes)}")


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
    # Defaut : le profil de la machine. Imposer generic-linux sous Windows
    # proposait des chemins Linux, crees ensuite a la racine du disque courant.
    platform: PlatformProfile = typer.Option(default_profile(), help="Profil de plateforme."),
    host: str = typer.Option("localhost", help="Hote pour les URL du rapport final."),
    timezone: str = typer.Option("Etc/UTC", "--tz"),
    project_dir: Path = typer.Option(Path("."), help="Ou ecrire les artefacts."),
    dry_run: bool = typer.Option(False, "--dry-run", help="N'ecrit rien, montre tout."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Ne pas demander confirmation."),
    open_page: bool = typer.Option(
        True, "--open/--no-open", help="Ouvrir la page d'acces dans le navigateur."
    ),
    vpn: bool = typer.Option(False, "--vpn", help="Faire passer le client torrent par un VPN."),
    vpn_provider: str = typer.Option(
        "", help="Fournisseur VPN. Voir `arrsenal vpn-providers`."
    ),
    vpn_type: str = typer.Option("wireguard", help="wireguard ou openvpn."),
    vpn_user: str = typer.Option("", help="Identifiant OpenVPN."),
    vpn_pass: str = typer.Option("", help="Mot de passe OpenVPN."),
    vpn_key: str = typer.Option("", help="Cle privee WireGuard."),
    vpn_countries: str = typer.Option("", help="Pays souhaites, separes par des virgules."),
    recyclarr_sonarr: str = typer.Option(
        "",
        help="Template TRaSH pour Sonarr. Voir `arrsenal templates`. Vide = defaut.",
    ),
    recyclarr_radarr: str = typer.Option(
        "",
        help="Template TRaSH pour Radarr. Voir `arrsenal templates`. Vide = defaut.",
    ),
    reset_config: bool | None = typer.Option(
        None,
        "--reset-config/--keep-config",
        help=(
            "Configuration existante : repartir de zero, ou la conserver. "
            "Sans l'option, la question est posee."
        ),
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

    chosen = {"sonarr": recyclarr_sonarr.strip(), "radarr": recyclarr_radarr.strip()}
    chosen = {sid: name for sid, name in chosen.items() if name}
    if chosen and not cfg.enabled("recyclarr"):
        console.print(
            "[yellow]Un template a ete choisi mais Recyclarr n'est pas dans la "
            "selection : il ne sera pas applique.[/yellow]"
        )
    if chosen:
        # Un nom invalide ne se voit qu'a la toute fin, quand `config create`
        # echoue apres le demarrage de la stack. Le dire avant d'ecrire quoi que
        # ce soit coute une requete.
        known, problem = recyclarr_cfg.available_templates()
        for sid, name in chosen.items():
            if not problem and name not in known.get(sid, []):
                console.print(
                    f"[red]Template inconnu pour {sid} : {name}[/red]\n"
                    f"[dim]`arrsenal templates` liste les noms acceptes.[/dim]"
                )
                raise typer.Exit(1)
        if problem:
            console.print(f"[yellow]Noms de templates non verifies : {problem}[/yellow]")
        cfg.recyclarr_templates = chosen

    if vpn:
        cfg.vpn = VpnConfig(
            enabled=True,
            provider=vpn_provider,
            vpn_type=vpn_type,
            openvpn_user=vpn_user,
            openvpn_password=vpn_pass,
            wireguard_private_key=vpn_key,
            countries=vpn_countries,
        )
        gaps = cfg.vpn.missing()
        if gaps:
            console.print(
                f"[red]VPN active mais incomplet : il manque {', '.join(gaps)}.[/red]\n"
                f"[dim]Sans cela Gluetun refuse de demarrer, et le client torrent "
                f"reste injoignable puisqu'il partage sa pile reseau.[/dim]"
            )
            raise typer.Exit(1)
        if not any(cfg.enabled(sid) for sid in catalog.DOWNLOAD_CLIENTS):
            console.print(
                "[yellow]--vpn sans client de telechargement : Gluetun ne protegerait "
                "rien.[/yellow]"
            )

    if not cfg.ids_certain:
        console.print(
            f"[yellow]PUID/PGID {cfg.puid}:{cfg.pgid} - {cfg.ids_source}.[/yellow]\n"
            f"[dim]C'est l'utilisateur Linux, a l'interieur des conteneurs, qui possedera "
            f"vos fichiers. Sur un NAS, lancez `id` en tant que l'utilisateur voulu.[/dim]"
        )

    # Un chemin Linux saisi sous Windows est cree a la racine du disque courant,
    # sans que rien ne le signale : `/mnt/user/data` devient `C:\mnt\user\data`.
    for label, chemin in (("--data-root", cfg.data_root), ("--config-root", cfg.config_root)):
        avertissement = path_warning(chemin)
        if avertissement:
            console.print(f"[yellow]{label} : {avertissement}[/yellow]")

    console.print(f"[dim]arrsenal {__version__}[/dim]")
    chemin_journal = journal.start(project_dir, "install")
    journal.config(cfg)
    _traiter_config_existante(cfg, reset_config, assume_yes=yes)

    controles = orchestrator.preflight(cfg, project_dir)
    journal.checks(controles)
    if not report.print_checks(controles):
        journal.failure("preflight bloquant : installation abandonnee")
        console.print(f"[dim]Journal : {chemin_journal}[/dim]")
        raise typer.Exit(1)

    report.print_summary(cfg)

    if dry_run:
        console.print("[cyan]--dry-run : aucune ecriture. Compose qui serait genere :[/cyan]")
        console.print(compose.render_compose(cfg))
        raise typer.Exit(0)

    if not yes and not typer.confirm("Ecrire les fichiers et demarrer la stack ?", default=True):
        raise typer.Exit(0)

    try:
        results = report.install_with_progress(cfg, project_dir, orchestrator.install)
    except InstallAborted as exc:
        journal.failure(str(exc))
        console.print(f"[red]{exc}[/red]")
        console.print(f"[dim]Journal : {chemin_journal}[/dim]")
        raise typer.Exit(1) from exc
    except Exception as exc:
        journal.LOGGER.exception("installation")
        console.print(f"[red]{type(exc).__name__} : {exc}[/red]")
        console.print(f"[dim]Detail complet dans {chemin_journal}[/dim]")
        raise typer.Exit(1) from exc

    report.print_final(cfg, results)
    echecs = [r for r in results if not r.ok]
    journal.finish(f"{len(results) - len(echecs)}/{len(results)} liens etablis")
    _announce_page(project_dir / dashboard.FILENAME, open_page)
    # Le journal n'est signale que s'il sert a quelque chose : tout annoncer a
    # chaque fois finit par n'etre plus lu.
    if echecs:
        console.print(f"\n[dim]Journal detaille : {chemin_journal}[/dim]")
    raise typer.Exit(0 if not echecs else 2)


@app.command()
def scan(include_stopped: bool = typer.Option(False, "--all", help="Inclure les arretes.")) -> None:
    """Liste les services deja installes sur cette machine. N'ecrit rien."""
    from rich.table import Table

    found = discovery.scan(include_stopped=include_stopped)
    if not found:
        console.print("Aucun service connu detecte sur cette machine.")
        raise typer.Exit(0)

    table = Table(title=f"{len(found)} service(s) detecte(s)")
    for column in ("Service", "Conteneur", "Port", "Cle API", "Etat"):
        table.add_column(column, overflow="fold")
    for entry in found:
        if discovery.looks_like_arrsenal(entry):
            state = "[dim]gere par arrsenal[/dim]"
        elif entry.usable:
            state = "[green]adoptable[/green]"
        else:
            state = "[yellow]" + (entry.problems[0] if entry.problems else "inutilisable") + "[/yellow]"
        table.add_row(
            catalog.get(entry.service_id).display_name,
            entry.container,
            str(entry.host_port or "-"),
            discovery.mask_key(entry.api_key),
            state,
        )
    console.print(table)

    doubles = discovery.duplicates([e for e in found if e.usable])
    for service_id, items in doubles.items():
        names = ", ".join(i.container for i in items)
        console.print(
            f"[yellow]{catalog.get(service_id).display_name} est present {len(items)} fois "
            f"({names}).[/yellow]\n"
            f"[dim]Precisez lequel cabler : --pick {service_id}=<conteneur>[/dim]"
        )


@app.command()
def adopt(
    data_root: str = typer.Option(..., help="Racine des medias de la stack existante."),
    config_root: str = typer.Option(..., help="Racine des configurations existantes."),
    pick: list[str] = typer.Option(
        [], "--pick", help="Lever une ambiguite : service=conteneur. Repetable."
    ),
    host: str | None = typer.Option(
        None, help="Adresse de cette machine, joignable DEPUIS les conteneurs."
    ),
    dl_user: str | None = typer.Option(
        None, help="Identifiant du client de telechargement existant."
    ),
    dl_pass: str | None = typer.Option(
        None, help="Mot de passe du client existant. Illisible depuis sa configuration."
    ),
    project_dir: Path = typer.Option(Path("."), help="Ou ecrire stack.yml."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Montrer le plan, ne rien faire."),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Cable une stack DEJA installee, sans la recreer.

    Aucun conteneur n'est demarre, arrete ou recree, et aucun docker-compose.yml
    n'est genere : ces services ne sont pas geres par arrsenal.
    """
    picks: dict[str, str] = {}
    for item in pick:
        if "=" not in item:
            raise typer.BadParameter(f"attendu service=conteneur, recu {item!r}")
        key, _, value = item.partition("=")
        picks[key.strip()] = value.strip()

    # Les services adoptes vivent sur des reseaux Docker differents. Le cablage
    # les fait se joindre par l'hote — et depuis l'INTERIEUR d'un conteneur,
    # `localhost` designe ce conteneur, pas la machine. Il faut donc une vraie
    # adresse. Constate en conditions reelles : Prowlarr repondait "cannot connect
    # to Sonarr" sur une URL en localhost.
    if host in (None, "localhost", "127.0.0.1"):
        detected = dashboard.primary_lan_ip()
        if detected is None:
            console.print(
                "[red]Impossible de determiner l'adresse de cette machine sur le "
                "reseau.[/red]\n"
                "[dim]Les conteneurs doivent pouvoir se joindre entre eux : "
                "`localhost` ne convient pas. Passez --host <adresse>.[/dim]"
            )
            raise typer.Exit(1)
        host = detected
        console.print(f"[dim]Adresse retenue pour le cablage : {host}[/dim]")

    plan = adopt_mod.build_plan(discovery.scan(), picks)

    for entry, why in plan.skipped:
        console.print(f"[dim]ignore  {entry.container} ({why})[/dim]")
    for service_id, items in plan.ambiguous.items():
        names = ", ".join(i.container for i in items)
        console.print(
            f"[red]{service_id} est ambigu : {names}.[/red] "
            f"[dim]Ajoutez --pick {service_id}=<conteneur>[/dim]"
        )
    if not plan.chosen:
        console.print("[red]Rien d'adoptable. Lancez `arrsenal scan` pour comprendre.[/red]")
        raise typer.Exit(1)
    if plan.ambiguous:
        raise typer.Exit(1)

    cfg = adopt_mod.config_from_plan(
        plan, data_root=data_root, config_root=config_root, host=host
    )
    for sid in catalog.DOWNLOAD_CLIENTS:
        if cfg.enabled(sid) and (dl_user or dl_pass):
            cfg.services[sid].username = dl_user or ""
            cfg.services[sid].password = dl_pass or ""
    for note in adopt_mod.missing_for_wiring(cfg):
        console.print(f"[yellow]{note}[/yellow]")

    console.print()
    report.print_summary(cfg)
    console.print(
        f"[cyan]{orchestrator.planned_links(cfg)} lien(s) seraient poses sur ces "
        f"conteneurs existants. Aucun ne sera recree.[/cyan]"
    )

    if dry_run:
        raise typer.Exit(0)
    if not yes and not typer.confirm("Cabler ces services ?", default=True):
        raise typer.Exit(0)

    adopt_mod.write_stack(cfg, project_dir)
    wirer = Wirer(cfg)
    try:
        results = wirer.execute(on_step=report.print_step)
    finally:
        wirer.close()
    adopt_mod.write_stack(cfg, project_dir)
    report.print_final(cfg, results)
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
    cfg.project_dir = project_dir
    wirer = Wirer(cfg)
    try:
        results = wirer.execute(on_step=report.print_step)
    finally:
        wirer.close()
    compose.write_artifacts(cfg, project_dir)
    report.print_final(cfg, results)
    raise typer.Exit(0 if all(r.ok for r in results) else 2)


@app.command()
def serve(
    project_dir: Path = typer.Option(Path("."), help="Repertoire du stack.yml."),
    host: str = typer.Option("127.0.0.1", help="Adresse d'ecoute."),
    port: int = typer.Option(7373, help="Port d'ecoute."),
    open_page: bool = typer.Option(True, "--open/--no-open", help="Ouvrir le navigateur."),
) -> None:
    """Page d'administration : etat des services, demarrer / arreter / redemarrer.

    Ecoute sur 127.0.0.1 par defaut. L'acces exige un jeton tire au hasard a
    chaque demarrage : il est dans l'URL affichee ci-dessous.
    """
    cfg = _load_config(project_dir)
    token = admin.generate_token()

    if host not in ("127.0.0.1", "localhost"):
        console.print(
            f"[yellow]Ecoute sur {host} : la page sera joignable depuis le reseau.[/yellow]\n"
            f"[dim]Elle permet d'arreter vos services et affiche vos identifiants. "
            f"Le jeton est la seule protection ; ne partagez pas l'URL.[/dim]"
        )

    def ready(url: str, _token: str) -> None:
        console.print(f"\nAdministration : [bold]{url}[/bold]")
        console.print("[dim]Le jeton change a chaque demarrage. Ctrl+C pour arreter.[/dim]")
        if open_page:
            import webbrowser

            try:
                webbrowser.open(url)
            except Exception:  # noqa: BLE001
                # Pas de navigateur ici : cas normal sur un NAS. L'URL est affichee.
                console.print("[dim]Aucun navigateur : ouvrez l'URL ci-dessus.[/dim]")

    try:
        admin.serve(cfg, project_dir, host=host, port=port, token=token, on_ready=ready)
    except OSError as exc:
        console.print(f"[red]Impossible d'ecouter sur {host}:{port} : {exc}[/red]")
        raise typer.Exit(1) from exc
    console.print("Serveur arrete.")


@app.command()
def doctor(project_dir: Path = typer.Option(Path("."), help="Repertoire du stack.yml.")) -> None:
    """Diagnostique une installation existante."""
    cfg = _load_config(project_dir)
    if not report.print_checks(orchestrator.preflight(cfg, project_dir)):
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


@app.command("vpn-providers")
def vpn_providers() -> None:
    """Liste les fournisseurs VPN acceptes par Gluetun."""
    console.print("[dim]Liste obtenue de Gluetun v3.41.3 lui-meme, pas recopiee.[/dim]\n")
    for name in VPN_PROVIDERS:
        console.print(f"  {name}")


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
            # Un service sans interface web ne publie rien : « 0 » se lirait comme
            # un port, pas comme une absence.
            str(spec.default_host_port or "-"),
            spec.notes,
        )
    console.print(table)


@app.command("templates")
def list_templates(
    config_root: str | None = typer.Option(
        None, help="Racine des configurations, pour lire le manifeste deja clone."
    ),
) -> None:
    """Liste les profils de qualite TRaSH proposables a Recyclarr."""
    from rich.table import Table

    config_dir = Path(config_root) / "recyclarr" if config_root else None
    names, problem = recyclarr_cfg.available_templates(config_dir)
    if problem:
        console.print(f"[red]{problem}[/red]")
        raise typer.Exit(1)

    table = Table(title="Templates officiels Recyclarr")
    table.add_column("Service")
    table.add_column("Template", overflow="fold")
    table.add_column("Defaut")
    for service in sorted(names):
        default = recyclarr_cfg.DEFAULT_TEMPLATES.get(service, "")
        for name in names[service]:
            table.add_row(service, name, "oui" if name == default else "")
    console.print(table)
    console.print(
        "[dim]Choix a l'installation : "
        "`arrsenal install --recyclarr-sonarr <nom> --recyclarr-radarr <nom>`.[/dim]"
    )


if __name__ == "__main__":
    app()
