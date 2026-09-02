"""Ecran optionnel : saisie des indexeurs de l'utilisateur.

arrsenal ne fournit aucun indexeur. La liste presentee ici est celle que le
Prowlarr de l'utilisateur embarque : cet ecran n'est qu'un formulaire de saisie
par-dessus les donnees de Prowlarr. Rien n'est preselectionne, et l'etape se
passe d'un bouton.
"""

from __future__ import annotations

from rich.markup import escape
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from .. import catalog, journal
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
            journal.LOGGER.exception("chargement des definitions Prowlarr")
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
            # Le nom vient de Prowlarr et se retrouve dans NOTRE balisage : il
            # faut l'echapper, sinon une balise fermante isolee ferait lever
            # `MarkupError` en plein rendu de la liste.
            results.append(
                ListItem(
                    Label(f"{escape(definition.name)}  [dim]{marker} - {definition.protocol}[/dim]")
                )
            )

    @on(ListView.Selected, "#indexer-results")
    async def _select(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        if index is None or index >= len(self._matches):
            return
        self._current = self._matches[index]
        await self._render_form(self._current)

    async def _render_form(self, definition: IndexerDefinition) -> None:
        """Peuple le formulaire pour la definition choisie.

        `remove_children()` et `mount()` sont ASYNCHRONES : ils rendent la main
        avant que le DOM ait bouge. Sans les attendre, le second indexeur
        selectionne montait un `Input` dont l'ancien existait encore, et Textual
        levait `DuplicateIds` — depuis un gestionnaire d'evenement, donc
        l'assistant se fermait net. Constate a l'usage : le premier choix
        s'affichait, le suivant tuait l'application. Reproduit ensuite sur les
        625 definitions d'un Prowlarr reel, ou 39 des 40 correspondances de
        « tr » plantaient a la seconde selection.
        """
        form = self.query_one("#indexer-form", VerticalScroll)
        await form.remove_children()
        # `markup=False` : ces textes viennent de Prowlarr, pas de nous. Verifie
        # sur les 625 definitions du moment : aucune ne casse aujourd'hui, et
        # `Torrent[CORE]` s'affiche tel quel. Mais une balise fermante isolee
        # comme `[/dim]` leverait `MarkupError`, et un `[bold]` disparaitrait
        # sans bruit. La liste bouge a chaque version de Prowlarr ; on ne parie
        # pas dessus.
        await form.mount(
            Static(
                f"{definition.name}  ({definition.privacy} - {definition.protocol})\n"
                f"{definition.description[:160]}",
                classes="indexer-title",
                markup=False,
            )
        )
        fields = definition.editable_fields()
        if not fields:
            await form.mount(Static("[dim]Aucun identifiant requis.[/dim]"))
        for field in fields:
            await form.mount(Label(field.label, classes="group-title", markup=False))
            await form.mount(
                Input(
                    value=field.prefill,
                    password=field.secret,
                    id=f"fld-{field.name}",
                    classes="indexer-field",
                )
            )
        if len(definition.urls) > 1:
            await form.mount(
                Static(
                    "Autres miroirs connus : " + ", ".join(definition.urls[1:4]),
                    classes="indexer-mirrors",
                    markup=False,
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
        """Ajoute l'indexeur, et ne laisse RIEN s'echapper.

        Une exception levee dans un worker Textual arrete l'application : le
        terminal se ferme, et l'utilisateur perd tout ce qu'il venait de saisir.
        `add` protege son propre appel HTTP, mais pas `configured()` ni
        `app_profile_id()`, qui interrogent Prowlarr eux aussi. Constate a
        l'usage : saisie d'un tracker, clic sur Ajouter, fenetre disparue.
        """
        if self._indexers is None:
            return
        try:
            ok, message = self._indexers.add(definition, values)
            already = [i.get("name", "?") for i in self._indexers.configured()]
        except Exception as exc:  # noqa: BLE001 - aucune ne doit tuer l'assistant
            journal.LOGGER.exception("ajout de l'indexeur %s", definition.name)
            ok, message = False, f"{type(exc).__name__} : {exc}"
            already = []
        try:
            # `call_from_thread` RENVOIE au fil appelant ce que le rappel a leve.
            # L'appel etait hors du `try`, donc une erreur d'affichage remontait
            # dans le worker, hors de toute garde, et Textual arretait
            # l'application. Le `assert` qui precedait avait le meme defaut.
            self.app.call_from_thread(self._added, definition.name, ok, message, already)
        except Exception:  # noqa: BLE001
            journal.LOGGER.exception("affichage du resultat pour %s", definition.name)

    def _added(self, name: str, ok: bool, message: str, already: list[str]) -> None:
        # On ASSEMBLE le contenu au lieu de l'ecrire en balisage. Ces trois
        # textes viennent de Prowlarr et de l'indexeur contacte : les faire
        # passer par l'analyseur de balisage revient a lui donner du texte
        # arbitraire. Le message reel de C411 le montre bien :
        #
        #   Unable to connect: ... [401:Unauthorized] [GET] at [https://c411.org
        #   /api/torznab?apikey=...&t=search&l
        #
        # tronque en pleine URL, il laisse un `[` ouvert et Textual leve
        # « Expected markup value ». L'assistant se fermait la, sans une ligne
        # de journal. Ni `rich.markup.escape` ni `textual.markup.escape` n'y
        # changent quoi que ce soit : verifie, tous deux rendent cette chaine
        # INCHANGEE. Seul un `Content` construit a la main est sur — et il
        # preserve au passage les noms comme `Torrent[CORE]`, que l'analyseur
        # amputait de la moitie.
        couleur = "green" if ok else "red"
        noms = ", ".join(already) or "aucun"
        self.query_one("#indexer-status", Static).update(
            Content(f"{name} : {message}").stylize(couleur)
            + Content("\n")
            + Content(f"Configures : {noms}").stylize("dim")
        )
        self.query_one("#add", Button).disabled = False
        self.query_one("#skip", Button).label = "Continuer"

    # -- sortie --------------------------------------------------------------

    @on(Button.Pressed, "#skip")
    def _skip(self) -> None:
        if self._client is not None:
            self._client.close()
        from .screens import ReportScreen

        self.app.push_screen(ReportScreen())
