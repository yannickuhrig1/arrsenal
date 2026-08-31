"""Ecran optionnel : saisie des indexeurs de l'utilisateur.

arrsenal ne fournit aucun indexeur. La liste presentee ici est celle que le
Prowlarr de l'utilisateur embarque : cet ecran n'est qu'un formulaire de saisie
par-dessus les donnees de Prowlarr. Rien n'est preselectionne, et l'etape se
passe d'un bouton.
"""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from .. import catalog
from ..clients.arr import ArrClient
from ..clients.prowlarr import IndexerDefinition, ProwlarrIndexers
from .screens import WizardScreen

MAX_RESULTS = 40


class IndexersScreen(WizardScreen):
    SUB_TITLE = "Etape optionnelle - vos indexeurs"

    def __init__(self) -> None:
        super().__init__()
        self._indexers: ProwlarrIndexers | None = None
        self._client: ArrClient | None = None
        self._matches: list[IndexerDefinition] = []
        self._current: IndexerDefinition | None = None

    def content(self) -> ComposeResult:
        yield Static(
            "arrsenal ne fournit et ne recommande [b]aucun[/b] indexeur. La liste "
            "ci-dessous est celle que votre propre Prowlarr embarque.\n"
            "[dim]Ajouter un indexeur le contacte pour valider vos identifiants : "
            "c'est Prowlarr qui l'impose, il n'existe pas d'enregistrement hors ligne.[/dim]",
            id="indexers-intro",
        )
        with Horizontal(id="indexers-body"):
            with Vertical(classes="indexers-pane"):
                yield Input(placeholder="Rechercher un indexeur...", id="indexer-search")
                yield ListView(id="indexer-results")
            with VerticalScroll(classes="indexers-pane", id="indexer-form"):
                yield Static("Choisissez un indexeur a gauche.", id="indexer-detail")
        yield Static(id="indexer-status")
        yield Horizontal(
            Button("Ajouter cet indexeur", variant="primary", id="add", disabled=True),
            Button("Passer cette etape", id="skip"),
            classes="actions",
        )

    def on_mount(self) -> None:
        self.load_definitions()

    # -- chargement ----------------------------------------------------------

    @work(thread=True)
    def load_definitions(self) -> None:
        """5,7 Mo de definitions : chargement hors du fil d'affichage."""
        cfg = self.app.stack_config
        spec = catalog.get("prowlarr")
        inst = cfg.services["prowlarr"]
        client = ArrClient(
            inst.url(cfg.host), inst.api_key or "", api_version=spec.api_version, name="prowlarr"
        )
        indexers = ProwlarrIndexers(client)
        try:
            count = len(indexers.definitions())
            already = [i.get("name", "?") for i in indexers.configured()]
        except Exception as exc:  # noqa: BLE001
            self.app.call_from_thread(
                self._set_status, f"[red]Prowlarr injoignable : {exc}[/red]"
            )
            client.close()
            return
        self._client, self._indexers = client, indexers
        self.app.call_from_thread(self._ready, count, already)

    def _ready(self, count: int, already: list[str]) -> None:
        configured = f" - deja configures : {', '.join(already)}" if already else ""
        self._set_status(
            f"[dim]{count} definitions fournies par votre Prowlarr{configured}[/dim]"
        )

    def _set_status(self, text: str) -> None:
        self.query_one("#indexer-status", Static).update(text)

    # -- recherche -----------------------------------------------------------

    @on(Input.Changed, "#indexer-search")
    def _search(self, event: Input.Changed) -> None:
        results = self.query_one("#indexer-results", ListView)
        results.clear()
        self._matches = []
        if self._indexers is None or len(event.value.strip()) < 2:
            return
        self._matches = self._indexers.search(event.value, MAX_RESULTS)
        for definition in self._matches:
            marker = "prive" if definition.is_private else "public"
            results.append(
                ListItem(Label(f"{definition.name}  [dim]{marker} - {definition.protocol}[/dim]"))
            )

    @on(ListView.Selected, "#indexer-results")
    def _select(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        if index is None or index >= len(self._matches):
            return
        self._current = self._matches[index]
        self._render_form(self._current)

    def _render_form(self, definition: IndexerDefinition) -> None:
        form = self.query_one("#indexer-form", VerticalScroll)
        form.remove_children()
        form.mount(
            Static(
                f"[b]{definition.name}[/b]  [dim]{definition.privacy} - "
                f"{definition.protocol}[/dim]\n[dim]{definition.description[:160]}[/dim]",
                classes="indexer-title",
            )
        )
        fields = definition.editable_fields()
        if not fields:
            form.mount(Static("[dim]Aucun identifiant requis.[/dim]"))
        for field in fields:
            form.mount(Label(field.label, classes="group-title"))
            form.mount(
                Input(
                    value=field.prefill,
                    password=field.secret,
                    id=f"fld-{field.name}",
                    classes="indexer-field",
                )
            )
        if len(definition.urls) > 1:
            form.mount(
                Static(
                    "[dim]Autres miroirs connus : " + ", ".join(definition.urls[1:4]) + "[/dim]"
                )
            )
        self.query_one("#add", Button).disabled = False

    # -- ajout ---------------------------------------------------------------

    @on(Button.Pressed, "#add")
    def _add(self) -> None:
        if self._current is None or self._indexers is None:
            return
        values = {
            inp.id.removeprefix("fld-"): inp.value
            for inp in self.query(".indexer-field").results(Input)
            if inp.id
        }
        self._set_status(f"[dim]Validation de {self._current.name} par Prowlarr...[/dim]")
        self.query_one("#add", Button).disabled = True
        self.submit(self._current, values)

    @work(thread=True)
    def submit(self, definition: IndexerDefinition, values: dict[str, str]) -> None:
        assert self._indexers is not None
        ok, message = self._indexers.add(definition, values)
        already = [i.get("name", "?") for i in self._indexers.configured()]
        self.app.call_from_thread(self._added, definition.name, ok, message, already)

    def _added(self, name: str, ok: bool, message: str, already: list[str]) -> None:
        colour = "green" if ok else "red"
        configured = f"\n[dim]Configures : {', '.join(already) or 'aucun'}[/dim]"
        self._set_status(f"[{colour}]{name} : {message}[/{colour}]{configured}")
        self.query_one("#add", Button).disabled = False
        self.query_one("#skip", Button).label = "Continuer"

    # -- sortie --------------------------------------------------------------

    @on(Button.Pressed, "#skip")
    def _skip(self) -> None:
        if self._client is not None:
            self._client.close()
        from .screens import ReportScreen

        self.app.push_screen(ReportScreen())
