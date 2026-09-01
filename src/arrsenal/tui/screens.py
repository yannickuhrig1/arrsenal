"""Ecrans de l'assistant.

Aucune logique metier ici : chaque ecran lit le catalogue et appelle
orchestrator.py. Un service ajoute au catalogue apparait automatiquement dans la
selection, sans toucher a ce fichier.
"""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Input,
    Label,
    ProgressBar,
    RadioButton,
    RadioSet,
    RichLog,
    Rule,
    Select,
    Static,
)

from .. import catalog, journal, orchestrator
from ..clients import recyclarr as recyclarr_cfg
from ..layout import (
    PROFILE_DEFAULTS,
    default_profile,
    hardlink_supported,
    path_warning,
    resolve_ids,
)
from ..models import Category, PlatformProfile
from ..orchestrator import InstallAborted, Progress
from ..wiring import StepResult

CATEGORY_TITLES = {
    Category.ARR: "Mediatheque",
    Category.DOWNLOAD: "Telechargement",
    Category.MEDIA: "Serveur media",
    Category.UI: "Interfaces",
}


class WizardHeader(Static):
    """Bandeau de titre maison.

    Le `Header` de Textual monte ses enfants de facon asynchrone et met a jour son
    titre depuis l'application : enchainer deux `push_screen` rapidement le fait
    lever `NoMatches: No nodes match 'HeaderTitle'`. Un simple Static rend la meme
    chose sans course, et sans dependre d'un detail interne du framework.
    """

    def __init__(self, subtitle: str) -> None:
        # La version est affichee sur CHAQUE ecran : c'est la premiere chose a
        # demander quand quelqu'un signale un probleme, et la derniere qu'il
        # pense a donner.
        from .. import __version__

        super().__init__(f"arrsenal {__version__}  —  {subtitle}", id="wizard-header")


class WizardScreen(Screen):
    """Socle commun : entete, pied de page, navigation."""

    BINDINGS = [("escape", "app.pop_screen", "Retour"), ("ctrl+q", "app.quit", "Quitter")]

    #: Sous-titre affiche dans le bandeau.
    SUB_TITLE = ""

    def compose(self) -> ComposeResult:
        yield WizardHeader(self.SUB_TITLE)
        yield from self.content()
        yield Footer()

    def content(self) -> ComposeResult:  # pragma: no cover - surcharge
        return iter(())


# --------------------------------------------------------------------- accueil


class WelcomeScreen(WizardScreen):
    SUB_TITLE = "Deploie ET cable une stack media complete"

    def content(self) -> ComposeResult:
        with Vertical(id="welcome"):
            yield Static(
                "Cet assistant va deployer les services que vous choisissez, puis "
                "[b]les cabler entre eux[/b] : cles API echangees, indexeurs "
                "synchronises, dossiers racine crees, bibliotheques scannees.\n\n"
                "Rien n'est ecrit avant l'ecran de recapitulatif.",
                id="pitch",
            )
            yield Rule()
            yield Static(id="docker-status")
            yield Horizontal(
                Button("Commencer", variant="primary", id="start", disabled=True),
                Button("Quitter", id="quit"),
                classes="actions",
            )

    def on_mount(self) -> None:
        self.check_docker()

    @work(thread=True)
    def check_docker(self) -> None:
        from ..runner import check_docker

        try:
            checks = check_docker()
        except Exception as exc:  # noqa: BLE001
            journal.LOGGER.exception("diagnostic docker")
            self.app.call_from_thread(
                self._render_docker, f"[red]Diagnostic impossible : {exc}[/red]", False
            )
            return
        lines, ok = [], True
        for check in checks:
            mark = "[green]OK[/green]" if check.ok else "[red]ECHEC[/red]"
            lines.append(f"{mark}  {check.name} : {check.detail}")
            ok = ok and check.ok
        self.app.call_from_thread(self._render_docker, "\n".join(lines), ok)

    def _render_docker(self, text: str, ok: bool) -> None:
        self.query_one("#docker-status", Static).update(text)
        self.query_one("#start", Button).disabled = not ok

    @on(Button.Pressed, "#start")
    def go(self) -> None:
        self.app.push_screen(ServicesScreen())

    @on(Button.Pressed, "#quit")
    def leave(self) -> None:
        self.app.exit(0)


# ------------------------------------------------------------------- selection


class ServicesScreen(WizardScreen):
    SUB_TITLE = "Etape 1/3 - Quels services installer ?"

    #: Repartition en deux colonnes. La mediatheque, la plus fournie, occupe la
    #: gauche a elle seule.
    COLUMNS = ((Category.ARR,), (Category.DOWNLOAD, Category.MEDIA, Category.UI))

    def content(self) -> ComposeResult:
        with Horizontal(id="services"):
            for index, categories in enumerate(self.COLUMNS):
                with VerticalScroll(classes="service-column", id=f"column-{index}"):
                    for category in categories:
                        specs = [s for s in catalog.CATALOG.values() if s.category is category]
                        if not specs:
                            continue
                        yield Label(CATEGORY_TITLES[category], classes="group-title")
                        for spec in sorted(specs, key=lambda s: s.display_name):
                            yield Checkbox(
                                spec.display_name,
                                value=spec.id in catalog.DEFAULT_SELECTION,
                                id=f"svc-{spec.id}",
                                classes="service",
                            )
                            yield Label(spec.notes, classes="service-note")
        yield Static(id="selection-summary")
        yield Horizontal(
            Button("Continuer", variant="primary", id="next"),
            Button("Retour", id="back"),
            classes="actions",
        )

    def on_mount(self) -> None:
        self._refresh_summary()

    @on(Checkbox.Changed)
    def _on_toggle(self) -> None:
        self._refresh_summary()

    def selection(self) -> list[str]:
        return [
            box.id.removeprefix("svc-")
            for box in self.query(Checkbox)
            if box.value and box.id is not None
        ]

    def _refresh_summary(self) -> None:
        chosen = self.selection()
        summary = self.query_one("#selection-summary", Static)
        if not chosen:
            summary.update("[yellow]Selectionnez au moins un service.[/yellow]")
            self.query_one("#next", Button).disabled = True
            return

        resolved = catalog.resolve_dependencies(chosen)
        added = [s for s in resolved if s not in chosen]
        cfg = orchestrator.build_config(services=resolved)
        text = f"[b]{len(resolved)} services[/b] - [b]{orchestrator.planned_links(cfg)} liens[/b] seront cables"
        if added:
            names = ", ".join(catalog.get(s).display_name for s in added)
            text += f"\n[cyan]Ajoute automatiquement (prerequis) : {names}[/cyan]"
        summary.update(text)
        self.query_one("#next", Button).disabled = False

    @on(Button.Pressed, "#next")
    def go(self) -> None:
        self.app.selection = catalog.resolve_dependencies(self.selection())
        self.app.push_screen(PathsScreen())

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.app.pop_screen()


# ---------------------------------------------------------------------- chemins


class PathsScreen(WizardScreen):
    SUB_TITLE = "Etape 2/3 - Chemins et plateforme"

    def content(self) -> ComposeResult:
        # Le profil propose est celui de la machine. Proposer generic-linux a un
        # utilisateur Windows le menait droit dans le piege : il gardait des
        # chemins Linux, crees ensuite a la racine du disque courant.
        courant = default_profile()
        defaults = PROFILE_DEFAULTS[courant]
        with Vertical(id="paths"):
            yield Label("Profil de plateforme", classes="group-title")
            with RadioSet(id="platform"):
                for profile in PlatformProfile:
                    yield RadioButton(
                        profile.value,
                        value=profile is courant,
                        id=f"plat-{profile.value}",
                    )
            yield Static(id="platform-note")

            yield Label("Racine des configurations", classes="group-title")
            yield Input(value=defaults.config_root, id="config-root")

            yield Label(
                "Racine des donnees [dim](montee sur /data dans TOUS les conteneurs)[/dim]",
                classes="group-title",
            )
            yield Input(value=defaults.data_root, id="data-root")

            yield Label(
                "Identifiant [dim](le meme pour tous les services installes)[/dim]",
                classes="group-title",
            )
            yield Input(value="arrsenal", id="username")

            yield Label("Fuseau horaire", classes="group-title")
            yield Input(value="Europe/Paris", id="tz")

            yield Rule()
            yield Static(id="paths-check")
        yield Horizontal(
            Button("Verifier les chemins", id="check"),
            Button("Continuer", variant="primary", id="next"),
            Button("Retour", id="back"),
            classes="actions",
        )

    def on_mount(self) -> None:
        self._update_note(default_profile())

    @on(RadioSet.Changed, "#platform")
    def _on_platform(self, event: RadioSet.Changed) -> None:
        profile = PlatformProfile(str(event.pressed.label))
        defaults = PROFILE_DEFAULTS[profile]
        self.query_one("#config-root", Input).value = defaults.config_root
        self.query_one("#data-root", Input).value = defaults.data_root
        self._update_note(profile)

    #: « 1000:1000 » ne dit rien a qui n'a jamais administre un systeme Unix, et
    #: cette valeur decide pourtant de qui possedera les fichiers telecharges.
    IDS_EXPLICATION = (
        "[dim]PUID/PGID = l'utilisateur Linux, a l'interieur des conteneurs, "
        "qui possedera vos fichiers.[/dim]"
    )

    def _update_note(self, profile: PlatformProfile) -> None:
        uid, gid, source, certain = resolve_ids(profile)
        note = self.query_one("#platform-note", Static)
        entete = f"[dim]PUID/PGID[/dim] [b]{uid}:{gid}[/b]"
        if certain:
            note.update(f"{entete} [dim]- {source}[/dim]\n{self.IDS_EXPLICATION}")
        else:
            note.update(
                f"{entete} [yellow]- non detectables ici, valeur de repli.[/yellow]\n"
                f"{self.IDS_EXPLICATION}\n"
                f"[dim]Sur un NAS, lancez `id` et corrigez ces valeurs.[/dim]"
            )

    def platform(self) -> PlatformProfile:
        pressed = self.query_one("#platform", RadioSet).pressed_button
        return PlatformProfile(str(pressed.label)) if pressed else PlatformProfile.GENERIC_LINUX

    @on(Button.Pressed, "#check")
    def check(self) -> None:
        data_root = self.query_one("#data-root", Input).value.strip()
        target = self.query_one("#paths-check", Static)
        if not data_root:
            target.update("[red]La racine des donnees ne peut pas etre vide.[/red]")
            return

        lignes: list[str] = []
        # D'abord OU le dossier va reellement atterrir. Sans cette ligne, le
        # controle repondait « hardlink OK » pour `/mnt/user/data` saisi sous
        # Windows — vrai, mais dans `C:\mnt\user\data`, que personne ne voulait.
        avertissement = path_warning(data_root)
        if avertissement:
            lignes.append(f"[yellow]{avertissement}[/yellow]")
        else:
            lignes.append(f"[dim]Dossier vise : {Path(data_root).resolve()}[/dim]")

        try:
            Path(data_root).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            lignes.append(f"[red]Impossible de le creer : {exc}[/red]")
            target.update("\n".join(lignes))
            return

        ok, detail = hardlink_supported(data_root)
        colour = "green" if ok else "yellow"
        lignes.append(f"[{colour}]{detail}[/{colour}]")
        lignes.append(
            "[dim]Un hardlink reel a ete cree puis supprime entre torrents/ et media/.[/dim]"
        )
        target.update("\n".join(lignes))

    @on(Button.Pressed, "#next")
    def go(self) -> None:
        self.app.config_root = self.query_one("#config-root", Input).value.strip()
        self.app.data_root = self.query_one("#data-root", Input).value.strip()
        self.app.timezone = self.query_one("#tz", Input).value.strip() or "Etc/UTC"
        self.app.username = self.query_one("#username", Input).value.strip() or "arrsenal"
        self.app.platform = self.platform()
        # Ecran facultatif : il n'a de sens que si Recyclarr est installe ET s'il a
        # au moins un *arr a configurer.
        if "recyclarr" in self.app.selection and any(
            sid in self.app.selection for sid in TemplatesScreen.SERVICES
        ):
            self.app.push_screen(TemplatesScreen())
        else:
            self.app.push_screen(SummaryScreen())

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.app.pop_screen()


# ------------------------------------------------------------ profils qualite


class TemplatesScreen(WizardScreen):
    """Choix du profil de qualite TRaSH, service par service.

    Etape facultative : les defauts conviennent a la plupart des installations,
    et le bouton « Passer » est la pour le dire. Elle n'apparait que si Recyclarr
    est selectionne avec au moins un *arr a configurer.

    La liste vient du manifeste officiel, pas d'une copie embarquee dans le code.
    Elle est chargee dans un thread : l'ecran doit s'afficher tout de suite, meme
    si le reseau traine.
    """

    SUB_TITLE = "Etape optionnelle - profils de qualite"

    #: Services que Recyclarr sait configurer, dans l'ordre d'affichage.
    SERVICES = ("sonarr", "radarr")

    def __init__(self) -> None:
        super().__init__()
        self._available: dict[str, list[str]] = {}

    def _targets(self) -> list[str]:
        return [sid for sid in self.SERVICES if sid in self.app.selection]

    def content(self) -> ComposeResult:
        yield Static(
            "Sans profil de qualite, un *arr accepte [b]n'importe quel[/b] encodage : "
            "le premier resultat venu, pas le meilleur.\n"
            "[dim]Les profils viennent des TRaSH Guides. arrsenal ne fait que poser "
            "l'adresse et la cle API dans le template que vous choisissez ici.[/dim]",
            id="templates-intro",
        )
        with VerticalScroll(id="templates"):
            for sid in self._targets():
                spec = catalog.get(sid)
                default = recyclarr_cfg.DEFAULT_TEMPLATES.get(sid, "")
                yield Label(spec.display_name, classes="group-title")
                # Une LISTE, pas un champ libre. Il y a 22 profils pour Sonarr et
                # 35 pour Radarr : demander de taper un nom obligeait a le
                # connaitre par coeur, et l'ecran n'en montrait que six.
                yield Select(
                    [(default, default)] if default else [],
                    value=default or Select.BLANK,
                    allow_blank=not default,
                    id=f"tpl-{sid}",
                )
                yield Static(id=f"tpl-choices-{sid}", classes="service-note")
        yield Static(id="templates-status")
        yield Horizontal(
            Button("Continuer", variant="primary", id="next"),
            Button("Passer", id="skip"),
            Button("Retour", id="back"),
            classes="actions",
        )

    def on_mount(self) -> None:
        self.query_one("#templates-status", Static).update(
            "[dim]Chargement de la liste officielle…[/dim]"
        )
        self._load()

    @work(thread=True)
    def _load(self) -> None:
        config_dir = Path(self.app.config_root) / "recyclarr" if self.app.config_root else None
        try:
            names, problem = recyclarr_cfg.available_templates(config_dir)
        except Exception as exc:  # noqa: BLE001
            journal.LOGGER.exception("liste des templates Recyclarr")
            names, problem = {}, f"liste indisponible : {exc}"
        self.app.call_from_thread(self._loaded, names, problem)

    def _loaded(self, names: dict[str, list[str]], problem: str | None) -> None:
        self._available = names
        status = self.query_one("#templates-status", Static)
        if problem:
            # Le nom reste saisissable : ne pas pouvoir lister n'est pas une raison
            # d'empecher quelqu'un qui sait ce qu'il veut.
            status.update(
                f"[yellow]{problem}[/yellow]\n"
                "[dim]Les noms ne seront pas verifies ici. Les defauts restent valables.[/dim]"
            )
            return
        status.update("")
        for sid in self._targets():
            available = names.get(sid, [])
            defaut = recyclarr_cfg.DEFAULT_TEMPLATES.get(sid, "")
            liste = self.query_one(f"#tpl-{sid}", Select)
            liste.set_options((nom, nom) for nom in available)
            if defaut in available:
                liste.value = defaut
            self.query_one(f"#tpl-choices-{sid}", Static).update(
                f"[dim]{len(available)} profils proposes par les TRaSH Guides. "
                f"Cliquez pour derouler la liste.[/dim]"
            )
        self._validate()

    @on(Select.Changed)
    def _on_change(self) -> None:
        self._validate()

    def choices(self) -> dict[str, str]:
        retenus = {}
        for sid in self._targets():
            valeur = self.query_one(f"#tpl-{sid}", Select).value
            if isinstance(valeur, str) and valeur:
                retenus[sid] = valeur
        return retenus

    def _validate(self) -> bool:
        """Un nom inconnu n'echoue qu'a la toute fin du cablage. On le dit ici."""
        if not self._available:
            return True
        unknown = [
            f"{sid} : {name}"
            for sid, name in self.choices().items()
            if name not in self._available.get(sid, [])
        ]
        status = self.query_one("#templates-status", Static)
        button = self.query_one("#next", Button)
        if unknown:
            status.update(
                f"[red]Template inconnu — {', '.join(unknown)}[/red]\n"
                "[dim]Recyclarr refuserait de generer la configuration.[/dim]"
            )
            button.disabled = True
            return False
        status.update("")
        button.disabled = False
        return True

    @on(Button.Pressed, "#next")
    def go(self) -> None:
        if not self._validate():
            return
        self.app.recyclarr_templates = self.choices()
        self.app.push_screen(SummaryScreen())

    @on(Button.Pressed, "#skip")
    def skip(self) -> None:
        self.app.recyclarr_templates = {}
        self.app.push_screen(SummaryScreen())

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.app.pop_screen()


# ----------------------------------------------------------------- recapitulatif


class SummaryScreen(WizardScreen):
    SUB_TITLE = "Etape 3/3 - Recapitulatif (rien n'est encore ecrit)"

    def content(self) -> ComposeResult:
        with VerticalScroll(id="summary"):
            yield DataTable(id="summary-table", cursor_type="row")
            yield Static(id="summary-paths")
            yield Static(id="summary-warnings")
            # Choix propose UNIQUEMENT si une configuration inutilisable existe.
            # Il n'apparait donc jamais lors d'une premiere installation.
            yield Static(id="config-existante", classes="hidden")
            with RadioSet(id="config-choix", classes="hidden"):
                yield RadioButton("Conserver ces configurations", value=True, id="cfg-garder")
                yield RadioButton("Supprimer et repartir de zero", id="cfg-supprimer")
        yield Horizontal(
            Button("Installer et cabler", variant="success", id="install"),
            Button("Retour", id="back"),
            classes="actions",
        )

    def on_mount(self) -> None:
        cfg = self.app.build_config()
        table = self.query_one("#summary-table", DataTable)
        table.add_columns("Service", "Image", "URL")
        for sid, inst in orchestrator.iter_selected(cfg):
            spec = catalog.get(sid)
            table.add_row(
                spec.display_name,
                spec.image,
                inst.url(cfg.host) if inst.has_web_ui else "tache de fond",
            )

        self.query_one("#summary-paths", Static).update(
            f"[b]Configurations[/b]  {cfg.config_root}\n"
            f"[b]Donnees[/b]        {cfg.data_root}  -> /data dans tous les conteneurs\n"
            f"[b]PUID:PGID[/b]      {cfg.puid}:{cfg.pgid} [dim]({cfg.ids_source})[/dim]\n"
            f"[b]UMASK / TZ[/b]     {cfg.umask}   {cfg.timezone}\n"
            f"[b]Liens a cabler[/b] {orchestrator.planned_links(cfg)}"
        )

        vpn_warning = (
            "[yellow]Aucun VPN n'est configure pour le client torrent.[/yellow]\n"
            "[dim]Le trafic BitTorrent sortira sur l'adresse IP publique de cette "
            "machine, visible par les autres pairs.[/dim]"
        )
        warnings = [vpn_warning] if orchestrator.has_download_client(cfg) else []
        if not cfg.ids_certain:
            warnings.append(
                f"[yellow]PUID/PGID non detectables ici : repli sur "
                f"{cfg.puid}:{cfg.pgid}.[/yellow]\n"
                f"[dim]Des identifiants faux font ecrire toute la stack avec de "
                f"mauvaises permissions. Sur un NAS, lancez `id`.[/dim]"
            )
        self.query_one("#summary-warnings", Static).update("\n\n".join(warnings))
        self._proposer_reset(cfg)

    def _proposer_reset(self, cfg) -> None:
        """Affiche le choix garder / repartir de zero, s'il a lieu d'etre.

        Le cas : qBittorrent, Transmission, Jellyfin, autobrr et qui ne stockent
        leur mot de passe que hache. Une configuration heritee d'une installation
        precedente ne peut donc pas etre reprise — les identifiants annonces
        seront refuses, avec des messages incomprehensibles.

        Le choix par defaut reste « conserver » : effacer la configuration de
        quelqu'un sans qu'il l'ait demande serait inacceptable.
        """
        concernes = orchestrator.unusable_configs(cfg)
        if not concernes:
            return

        chemins = "\n".join(f"  {cfg.config_path(sid)}" for sid in concernes)
        bandeau = self.query_one("#config-existante", Static)
        bandeau.update(
            f"[yellow]Une configuration existe deja pour {', '.join(concernes)}.[/yellow]\n"
            f"[dim]Leurs mots de passe n'y sont stockes que haches : arrsenal ne peut "
            f"pas les reprendre, et ceux qu'il va vous annoncer seront refuses.[/dim]\n"
            f"[dim]{chemins}[/dim]\n"
            f"[dim]Vos medias ne sont jamais touches.[/dim]"
        )
        bandeau.remove_class("hidden")
        self.query_one("#config-choix", RadioSet).remove_class("hidden")

    def reset_demande(self) -> bool:
        choix = self.query_one("#config-choix", RadioSet).pressed_button
        return choix is not None and choix.id == "cfg-supprimer"

    @on(Button.Pressed, "#install")
    def go(self) -> None:
        cfg = self.app.stack_config or self.app.build_config()
        self.app.stack_config = cfg
        if self.reset_demande():
            # Suppression demandee explicitement : elle a lieu ICI, avant que
            # l'installation ne commence, pour que le pre-semis reparte d'un
            # dossier vide.
            efface = orchestrator.reset_configs(cfg, orchestrator.unusable_configs(cfg))
            journal.finish(f"configurations supprimees : {len(efface)}")
        self.app.push_screen(InstallScreen())

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.app.pop_screen()


# ------------------------------------------------------------------ installation


class InstallScreen(WizardScreen):
    SUB_TITLE = "Installation et cablage"
    BINDINGS = [("ctrl+q", "app.quit", "Quitter")]

    def content(self) -> ComposeResult:
        yield Static("Preparation...", id="install-phase")
        # Le telechargement des images est muet et peut durer plusieurs minutes :
        # sans barre, rien ne distingue « ca travaille » de « c'est bloque ».
        yield ProgressBar(id="install-progress", show_eta=False)
        yield RichLog(id="install-log", markup=True, wrap=True)
        yield Horizontal(
            Button("Terminer", variant="primary", id="done", disabled=True),
            classes="actions",
        )

    def on_mount(self) -> None:
        self.run_install()

    def _log(self, text: str) -> None:
        self.query_one("#install-log", RichLog).write(text)

    def _phase(self, text: str) -> None:
        self.query_one("#install-phase", Static).update(text)

    def _advance(self) -> None:
        bar = self.query_one("#install-progress", ProgressBar)
        # Le total est une estimation : on borne plutot que de depasser 100 %.
        if bar.total is not None and bar.progress < bar.total:
            bar.advance(1)

    def _complete(self) -> None:
        bar = self.query_one("#install-progress", ProgressBar)
        if bar.total is not None:
            bar.progress = bar.total

    @work(thread=True)
    def run_install(self) -> None:
        app = self.app
        cfg = app.stack_config or app.build_config()
        app.stack_config = cfg
        chemin = journal.start(Path(app.project_dir), "assistant : installation")
        journal.config(cfg)
        app.call_from_thread(self._log, f"[dim]Journal detaille : {chemin}[/dim]")
        app.call_from_thread(self._set_total, orchestrator.expected_events(cfg))

        def on_progress(progress: Progress) -> None:
            mark = "[green]OK[/green]" if progress.ok else "[red]ECHEC[/red]"
            journal.progress(progress.phase, progress.message, progress.ok)
            app.call_from_thread(self._phase, f"{progress.phase} : {progress.message}")
            app.call_from_thread(self._log, f"  {mark}  {progress.phase} : {progress.message}")
            app.call_from_thread(self._advance)

        def on_step(result: StepResult) -> None:
            journal.step(result)
            mark = "[green]OK[/green]" if result.ok else "[red]ECHEC[/red]"
            app.call_from_thread(self._log, f"  {mark}  {result.name} - {result.detail}")
            for warning in result.warnings:
                app.call_from_thread(self._log, f"        [yellow]{warning}[/yellow]")
            app.call_from_thread(self._advance)

        try:
            results = orchestrator.install(
                cfg, app.project_dir, on_progress=on_progress, on_step=on_step
            )
        except InstallAborted as exc:
            journal.failure(str(exc))
            app.call_from_thread(self._log, f"[red]{exc}[/red]")
            app.call_from_thread(self._phase, "[red]Installation interrompue[/red]")
            app.call_from_thread(self._enable_done, [])
            return
        except Exception as exc:  # noqa: BLE001 - rien ne doit tuer l'assistant
            # Sans ce filet, une erreur imprevue fait disparaitre la fenetre en
            # plein cablage : l'utilisateur perd l'ecran ET l'explication.
            journal.LOGGER.exception("installation")
            app.call_from_thread(self._log, f"[red]{type(exc).__name__} : {exc}[/red]")
            app.call_from_thread(
                self._log, f"[dim]Detail complet dans {app.project_dir / journal.FILENAME}[/dim]"
            )
            app.call_from_thread(self._phase, "[red]Installation interrompue[/red]")
            app.call_from_thread(self._enable_done, [])
            return
        app.call_from_thread(self._enable_done, results)

    def _set_total(self, total: int) -> None:
        self.query_one("#install-progress", ProgressBar).update(total=total, progress=0)

    def _enable_done(self, results: list[StepResult]) -> None:
        self.app.results = results
        # Une barre figee a 94 % apres un succes se lit comme un echec.
        self._complete()
        ok = sum(1 for r in results if r.ok)
        self._phase(
            f"[green]Termine : {ok}/{len(results)} liens etablis[/green]"
            if results and ok == len(results)
            else f"[yellow]Termine : {ok}/{len(results)} liens etablis[/yellow]"
        )
        self.query_one("#done", Button).disabled = False

    @on(Button.Pressed, "#done")
    def go(self) -> None:
        # L'etape indexeurs n'a de sens que si Prowlarr tourne : c'est lui qui
        # fournit les definitions et qui recevra les identifiants.
        if self.app.stack_config and self.app.stack_config.enabled("prowlarr"):
            from .indexers import IndexersScreen

            self.app.push_screen(IndexersScreen())
        else:
            self.app.push_screen(ReportScreen())


# ------------------------------------------------------------------- rapport


class ReportScreen(WizardScreen):
    SUB_TITLE = "Acces"
    BINDINGS = [("ctrl+q", "app.quit", "Quitter")]

    def content(self) -> ComposeResult:
        with VerticalScroll(id="report"):
            yield DataTable(id="report-table", cursor_type="row")
            yield Static(id="report-next")
        yield Horizontal(
            Button("Ouvrir la page d'acces", variant="success", id="open-page"),
            Button("Fermer", variant="primary", id="close"),
            classes="actions",
        )

    def on_mount(self) -> None:
        cfg = self.app.stack_config
        table = self.query_one("#report-table", DataTable)
        table.add_columns("Service", "URL", "Identifiant", "Mot de passe", "Cle API")
        for sid, inst in orchestrator.iter_selected(cfg):
            table.add_row(
                catalog.get(sid).display_name,
                inst.url(cfg.host),
                inst.username or "-",
                inst.password or "-",
                inst.api_key or "-",
            )
        failed = [r for r in self.app.results if not r.ok]
        if failed:
            body = "[red]Liens en echec :[/red]\n" + "\n".join(
                f"  - {r.name} : {r.detail.splitlines()[0]}" for r in failed
            )
            body += "\n\n[dim]Diagnostic : arrsenal doctor[/dim]"
        else:
            body = (
                "[b]Prochaine etape[/b] : ajoutez vos indexeurs dans Prowlarr.\n"
                "Ils descendront automatiquement vers vos applications.\n\n"
                "[dim]arrsenal ne fournit aucun indexeur : ce choix vous appartient.[/dim]"
            )
        body += (
            f"\n\n[dim]Ces identifiants sont aussi dans "
            f"{self.app.project_dir / '.env'} (chmod 600).[/dim]"
        )
        self.query_one("#report-next", Static).update(body)
        self._ouvrir_automatiquement()

    def _ouvrir_automatiquement(self) -> None:
        """Ouvre la page d'acces sans attendre un clic.

        La ligne de commande le faisait deja ; l'assistant, lui, se contentait
        d'un bouton. Or c'est precisement la que l'utilisateur a besoin de la
        page : elle porte les adresses et les identifiants qu'il vient de se voir
        annoncer.

        Le bouton reste, comme second essai : sur un NAS sans environnement
        graphique, aucun navigateur ne repond.
        """
        from .. import dashboard

        if not self.app.auto_open_page:
            return
        chemin = Path(self.app.project_dir) / dashboard.FILENAME
        if chemin.exists() and dashboard.open_in_browser(chemin):
            self.query_one("#open-page", Button).label = "Rouvrir la page d'acces"

    @on(Button.Pressed, "#open-page")
    def open_page(self) -> None:
        from .. import dashboard

        path = self.app.project_dir / dashboard.FILENAME
        target = self.query_one("#report-next", Static)
        if not path.exists():
            target.update(f"[yellow]Page introuvable : {path}[/yellow]")
            return
        if dashboard.open_in_browser(path):
            target.update(
                f"[green]Page ouverte dans votre navigateur.[/green]\n[dim]{path}[/dim]"
            )
        else:
            # Cas normal sur un NAS sans environnement graphique.
            target.update(
                f"[yellow]Aucun navigateur disponible ici.[/yellow]\n"
                f"[dim]Ouvrez ce fichier depuis un autre appareil : {path}[/dim]"
            )

    @on(Button.Pressed, "#close")
    def close(self) -> None:
        self.app.exit(0 if all(r.ok for r in self.app.results) else 2)
