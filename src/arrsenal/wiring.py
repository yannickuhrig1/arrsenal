"""Le graphe de cablage. C'est la raison d'etre du projet.

Chaque etape est idempotente et verifiable. Une etape se declare :
  - `run`    : execute le cablage, renvoie un libelle de resultat
  - `verify` : RELIT depuis l'API cible pour confirmer, plutot que de faire
               confiance au code de retour du POST

Toutes les URL de cablage sont des URL INTERNES au reseau compose
(http://sonarr:8989), jamais localhost : c'est un conteneur qui parle a un autre.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from . import catalog
from .clients.arr import ArrClient
from .clients.base import WiringError
from .clients.jellyfin import JellyfinClient
from .layout import CONTAINER_PATHS
from .models import StackConfig

#: Categories d'indexeurs Prowlarr poussees vers chaque application.
#: 5000 = TV, 2000 = Movies (conventions Newznab).
SYNC_CATEGORIES = {"sonarr": [5000, 5010, 5020, 5030, 5040, 5045, 5050], "radarr": [2000, 2010, 2020, 2030, 2040, 2045, 2050]}


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str
    created: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class WiringStep:
    name: str
    run: Callable[[], StepResult]
    requires: tuple[str, ...] = ()


class Wirer:
    """Construit et execute le graphe pour une StackConfig donnee."""

    def __init__(self, cfg: StackConfig, *, run_tests: bool = True):
        self.cfg = cfg
        #: Declenche le bouton "Test" de l'application apres chaque lien. C'est la
        #: difference entre "le POST est passe" et "la connexion fonctionne".
        self.run_tests = run_tests
        self._arr_cache: dict[str, ArrClient] = {}

    def _verify(
        self, client: ArrClient, resource: str, name: str, result: StepResult
    ) -> StepResult:
        """Fait valider le lien par l'application elle-meme."""
        if not self.run_tests:
            return result
        obj = client.find_by_name(resource, name)
        if obj is None:
            result.ok = False
            result.detail += " - introuvable a la relecture"
            return result
        ok, message = client.test_resource(resource, obj)
        if ok:
            result.detail += ", test OK"
        else:
            result.ok = False
            result.detail += " - le test de connexion a echoue"
            result.warnings.append(message.splitlines()[0])
        return result

    # -- fabriques de clients -----------------------------------------------

    def arr(self, service_id: str) -> ArrClient:
        """Client vers un *arr, vu depuis l'HOTE (c'est nous qui appelons)."""
        if service_id not in self._arr_cache:
            spec = catalog.get(service_id)
            inst = self.cfg.services[service_id]
            self._arr_cache[service_id] = ArrClient(
                f"http://{self.cfg.host}:{inst.host_port}",
                inst.api_key or "",
                api_version=spec.api_version,
                name=service_id,
            )
        return self._arr_cache[service_id]

    def internal_url(self, service_id: str) -> str:
        """URL du service vue par un AUTRE conteneur."""
        spec = catalog.get(service_id)
        return f"http://{spec.id}:{spec.internal_port}"

    def close(self) -> None:
        for client in self._arr_cache.values():
            client.close()
        self._arr_cache.clear()

    # -- etapes --------------------------------------------------------------

    def step_root_folder(self, arr_id: str, path: str) -> StepResult:
        client = self.arr(arr_id)
        _folder, created = client.ensure_root_folder(path)
        present = any(
            f.get("path", "").rstrip("/") == path.rstrip("/")
            for f in client.get("rootfolder") or []
        )
        return StepResult(
            f"{arr_id}: dossier racine {path}",
            ok=present,
            detail="cree" if created else "deja present",
            created=created,
        )

    def step_download_client(self, arr_id: str) -> StepResult:
        """Rattache Transmission a un *arr.

        Le nom des champs varie selon l'application : Sonarr expose `tvDirectory`,
        Radarr `movieDirectory`. On ne pousse que le prefixe pertinent, pour ne pas
        generer d'avertissement de champ inconnu a chaque passage.
        """
        client = self.arr(arr_id)
        tr_spec = catalog.get("transmission")
        tr = self.cfg.services["transmission"]
        directory = CONTAINER_PATHS["torrents_tv" if arr_id == "sonarr" else "torrents_movies"]

        # Category et Directory sont MUTUELLEMENT EXCLUSIFS : renseigner les deux
        # fait echouer la validation avec "Cannot use Category and Directory"
        # (verifie contre Sonarr 4.0.19 et Radarr 6.3.0).
        #
        # Piege : le gabarit arrive avec une categorie PAR DEFAUT deja remplie
        # ("tv-sonarr", "radarr"). Il ne suffit donc pas d'omettre le champ, il
        # faut le VIDER explicitement, sinon la valeur par defaut entre en conflit
        # avec le repertoire qu'on pose.
        #
        # On garde Directory : un chemin explicite sous /data/torrents correspond a
        # l'arborescence creee par arrsenal et garde les hardlinks possibles.
        prefix = "tv" if arr_id == "sonarr" else "movie"
        values = {
            "host": tr_spec.id,
            "port": tr_spec.internal_port,
            "urlBase": "/transmission/",
            "username": tr.username,
            "password": tr.password,
            "useSsl": False,
            f"{prefix}Directory": directory,
            f"{prefix}Category": "",
        }
        obj, created, skipped = client.ensure_resource(
            "downloadclient",
            name="Transmission",
            implementation="Transmission",
            values=values,
            extra={"enable": True, "protocol": "torrent", "priority": 1},
        )
        warnings = (
            [f"champs absents du gabarit {arr_id}, ignores: {', '.join(skipped)}"]
            if skipped
            else []
        )
        result = StepResult(
            f"{arr_id}: client de telechargement Transmission",
            ok=client.find_by_name("downloadclient", "Transmission") is not None,
            detail=("cree" if created else "deja present") + f" (id={obj.get('id', '?')})",
            created=created,
            warnings=warnings,
        )
        return self._verify(client, "downloadclient", "Transmission", result)

    def step_prowlarr_application(self, arr_id: str) -> StepResult:
        """Enregistre Sonarr/Radarr comme Application dans Prowlarr.

        C'est le lien qui fait descendre automatiquement tous les indexeurs de
        Prowlarr vers les *arr. `syncLevel=fullSync` maintient la synchronisation.
        """
        prowlarr = self.arr("prowlarr")
        target = self.cfg.services[arr_id]
        implementation = catalog.get(arr_id).display_name  # "Sonarr" / "Radarr"

        values = {
            "prowlarrUrl": self.internal_url("prowlarr"),
            "baseUrl": self.internal_url(arr_id),
            "apiKey": target.api_key,
            "syncCategories": SYNC_CATEGORIES[arr_id],
        }
        obj, created, skipped = prowlarr.ensure_resource(
            "applications",
            name=implementation,
            implementation=implementation,
            values=values,
            extra={"syncLevel": "fullSync"},
        )
        warnings = (
            [f"champs absents du gabarit Prowlarr, ignores: {', '.join(skipped)}"]
            if skipped
            else []
        )
        result = StepResult(
            f"prowlarr -> {arr_id} (Application, fullSync)",
            ok=prowlarr.find_by_name("applications", implementation) is not None,
            detail=("cree" if created else "deja present") + f" (id={obj.get('id', '?')})",
            created=created,
            warnings=warnings,
        )
        return self._verify(prowlarr, "applications", implementation, result)

    def step_prowlarr_download_client(self) -> StepResult:
        prowlarr = self.arr("prowlarr")
        tr_spec = catalog.get("transmission")
        tr = self.cfg.services["transmission"]
        values = {
            "host": tr_spec.id,
            "port": tr_spec.internal_port,
            "urlBase": "/transmission/",
            "username": tr.username,
            "password": tr.password,
            "useSsl": False,
        }
        obj, created, skipped = prowlarr.ensure_resource(
            "downloadclient",
            name="Transmission",
            implementation="Transmission",
            values=values,
            extra={"enable": True, "protocol": "torrent", "priority": 1},
        )
        warnings = [f"champs ignores: {', '.join(skipped)}"] if skipped else []
        result = StepResult(
            "prowlarr: client de telechargement Transmission",
            ok=prowlarr.find_by_name("downloadclient", "Transmission") is not None,
            detail=("cree" if created else "deja present") + f" (id={obj.get('id', '?')})",
            created=created,
            warnings=warnings,
        )
        return self._verify(prowlarr, "downloadclient", "Transmission", result)

    def step_jellyfin_notification(self, arr_id: str) -> StepResult:
        """Fait rafraichir la bibliotheque Jellyfin apres chaque import."""
        client = self.arr(arr_id)
        jf_spec = catalog.get("jellyfin")
        jf_key = self.cfg.services["jellyfin"].api_key
        if not jf_key:
            raise WiringError(
                f"{arr_id} -> jellyfin: cle API Jellyfin absente",
                "l'etape jellyfin/setup ne s'est pas executee ou a echoue",
                "relancez `arrsenal wire` : la cle est creee par cette etape",
            )
        values = {
            "host": jf_spec.id,
            "port": jf_spec.internal_port,
            "useSsl": False,
            "apiKey": jf_key,
            "updateLibrary": True,
            "notify": False,
        }
        obj, created, skipped = client.ensure_resource(
            "notification",
            name="Jellyfin",
            implementation="MediaBrowser",
            values=values,
            extra={
                "onDownload": True,
                "onUpgrade": True,
                "onRename": True,
                "onMovieDelete": True,
                "onEpisodeFileDelete": True,
            },
        )
        warnings = [f"champs ignores: {', '.join(skipped)}"] if skipped else []
        result = StepResult(
            f"{arr_id} -> jellyfin (rafraichissement de bibliotheque)",
            ok=client.find_by_name("notification", "Jellyfin") is not None,
            detail=("cree" if created else "deja present") + f" (id={obj.get('id', '?')})",
            created=created,
            warnings=warnings,
        )
        return self._verify(client, "notification", "Jellyfin", result)

    def step_jellyfin_setup(self) -> StepResult:
        inst = self.cfg.services["jellyfin"]
        url = f"http://{self.cfg.host}:{inst.host_port}"
        with JellyfinClient(url) as jf:
            jf.wait_ready()
            ran = jf.run_startup_wizard(
                admin_user=inst.username or "arrsenal",
                admin_password=inst.password or "",
            )
            jf.authenticate(inst.username or "arrsenal", inst.password or "")
            # La cle API alimente les notifications Sonarr/Radarr -> Jellyfin,
            # qui refusent un apiKey vide. Elle est reinjectee dans la config
            # pour etre persistee dans .env et stack.yml.
            inst.api_key = jf.ensure_api_key("arrsenal")
            made = [
                name
                for name, ctype, path in (
                    ("Films", "movies", CONTAINER_PATHS["media_movies"]),
                    ("Series", "tvshows", CONTAINER_PATHS["media_tv"]),
                )
                if jf.ensure_library(name, ctype, path)
            ]
            names = {lib.get("Name") for lib in jf.libraries()}
        ok = {"Films", "Series"} <= names
        detail = ("assistant execute" if ran else "assistant deja termine")
        detail += f", bibliotheques creees: {', '.join(made) or 'aucune (deja presentes)'}"
        return StepResult("jellyfin: assistant + bibliotheques", ok=ok, detail=detail, created=ran)

    # -- graphe --------------------------------------------------------------

    def build_plan(self) -> list[WiringStep]:
        cfg = self.cfg
        steps: list[WiringStep] = []

        if cfg.enabled("sonarr"):
            steps.append(
                WiringStep(
                    "sonarr/rootfolder",
                    lambda: self.step_root_folder("sonarr", CONTAINER_PATHS["media_tv"]),
                )
            )
        if cfg.enabled("radarr"):
            steps.append(
                WiringStep(
                    "radarr/rootfolder",
                    lambda: self.step_root_folder("radarr", CONTAINER_PATHS["media_movies"]),
                )
            )

        if cfg.enabled("transmission"):
            for arr_id in ("sonarr", "radarr"):
                if cfg.enabled(arr_id):
                    steps.append(
                        WiringStep(
                            f"{arr_id}/downloadclient",
                            lambda a=arr_id: self.step_download_client(a),
                        )
                    )
            if cfg.enabled("prowlarr"):
                steps.append(
                    WiringStep("prowlarr/downloadclient", self.step_prowlarr_download_client)
                )

        if cfg.enabled("prowlarr"):
            for arr_id in ("sonarr", "radarr"):
                if cfg.enabled(arr_id):
                    steps.append(
                        WiringStep(
                            f"prowlarr/application/{arr_id}",
                            lambda a=arr_id: self.step_prowlarr_application(a),
                        )
                    )

        if cfg.enabled("jellyfin"):
            steps.append(WiringStep("jellyfin/setup", self.step_jellyfin_setup))
            for arr_id in ("sonarr", "radarr"):
                if cfg.enabled(arr_id):
                    steps.append(
                        WiringStep(
                            f"{arr_id}/notification/jellyfin",
                            lambda a=arr_id: self.step_jellyfin_notification(a),
                        )
                    )
        return steps

    def execute(self, *, on_step: Callable[[StepResult], None] | None = None) -> list[StepResult]:
        results: list[StepResult] = []
        for step in self.build_plan():
            try:
                result = step.run()
            except WiringError as exc:
                result = StepResult(step.name, ok=False, detail=str(exc))
            results.append(result)
            if on_step:
                on_step(result)
        return results
