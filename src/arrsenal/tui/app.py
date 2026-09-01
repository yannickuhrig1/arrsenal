"""Application Textual : l'assistant interactif.

L'application ne porte que l'etat saisi par l'utilisateur et delegue tout le reste
a orchestrator.py, exactement comme la CLI.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App

from .. import orchestrator
from ..models import PlatformProfile, StackConfig, VpnConfig
from ..wiring import StepResult
from .screens import WelcomeScreen


class ArrsenalApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "arrsenal"

    def __init__(self, project_dir: Path | None = None) -> None:
        super().__init__()
        self.project_dir = project_dir or Path.cwd()
        # Etat collecte au fil des ecrans.
        self.selection: list[str] = []
        self.config_root: str | None = None
        self.data_root: str | None = None
        self.timezone: str = "Etc/UTC"
        self.username: str = "arrsenal"
        #: Hote des URL du rapport final. `localhost` ne vaut que si le
        #: navigateur tourne sur la machine qui heberge la stack.
        self.host: str = "localhost"
        self.vpn: VpnConfig = VpnConfig()
        self.platform: PlatformProfile = PlatformProfile.GENERIC_LINUX
        #: Template TRaSH choisi par service. Vide = celui par defaut.
        self.recyclarr_templates: dict[str, str] = {}
        self.stack_config: StackConfig | None = None
        self.results: list[StepResult] = []
        #: Ouvrir la page d'acces a la fin. Mis a False par le generateur de
        #: captures et par les tests : lancer un navigateur pendant une CI
        #: n'aurait aucun sens.
        self.auto_open_page: bool = True

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())

    def build_config(self) -> StackConfig:
        """Materialise la saisie en StackConfig. Les secrets sont generes ici."""
        cfg = orchestrator.build_config(
            services=self.selection,
            config_root=self.config_root,
            data_root=self.data_root,
            platform=self.platform,
            timezone=self.timezone,
            username=self.username,
            host=self.host,
        )
        cfg.recyclarr_templates = dict(self.recyclarr_templates)
        cfg.vpn = self.vpn
        return cfg


def run_wizard(project_dir: Path | None = None, *, open_page: bool = True) -> int:
    """Lance l'assistant. Renvoie le code de sortie."""
    app = ArrsenalApp(project_dir)
    app.auto_open_page = open_page
    result = app.run()
    return int(result) if isinstance(result, int) else 0
