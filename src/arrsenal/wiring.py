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
from .clients.qbittorrent import QBittorrentClient
from .downloadclients import ARR_ROUTING, profile_for
from .layout import CONTAINER_PATHS
from .models import StackConfig

#: Categories d'indexeurs Prowlarr poussees vers chaque application (conventions Newznab).
#: 2000 = Movies, 3000 = Audio, 5000 = TV.
SYNC_CATEGORIES = {
    "sonarr": [5000, 5010, 5020, 5030, 5040, 5045, 5050],
    "radarr": [2000, 2010, 2020, 2030, 2040, 2045, 2050],
    "lidarr": [3000, 3010, 3030, 3040, 3050, 3060],
}

#: Dossier racine de bibliotheque de chaque application.
ROOT_FOLDERS = {
    "sonarr": CONTAINER_PATHS["media_tv"],
    "radarr": CONTAINER_PATHS["media_movies"],
    "lidarr": CONTAINER_PATHS["media_music"],
}


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
        extra: dict[str, object] = {}
        if arr_id == "lidarr":
            # Lidarr refuse un dossier racine sans nom ni profils par defaut, la ou
            # Sonarr et Radarr se contentent du chemin. Les identifiants de profils
            # ne sont pas stables entre versions : on les resout par nom.
            extra = {
                "name": "Musique",
                "defaultQualityProfileId": client.profile_id("qualityprofile", "Standard"),
                "defaultMetadataProfileId": client.profile_id("metadataprofile", "Standard"),
            }
        _folder, created = client.ensure_root_folder(path, extra)
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

    def step_download_client(self, arr_id: str, dl_id: str) -> StepResult:
        """Rattache un client de telechargement a un *arr.

        Les noms de champs et le mode de routage varient selon le client et selon
        l'application : toute cette variabilite est isolee dans downloadclients.py,
        pour que cette etape reste identique quel que soit le couple.
        """
        client = self.arr(arr_id)
        profile = profile_for(dl_id)
        dl_spec = catalog.get(dl_id)
        dl = self.cfg.services[dl_id]

        values = profile.arr_values(
            host=dl_spec.id,
            port=dl_spec.internal_port,
            username=dl.username or "",
            password=dl.password or "",
            arr_id=arr_id,
        )
        obj, created, skipped = client.ensure_resource(
            "downloadclient",
            name=dl_spec.display_name,
            implementation=profile.implementation,
            values=values,
            extra={"enable": True, "protocol": profile.protocol, "priority": 1},
        )
        warnings = (
            [f"champs absents du gabarit {arr_id}, ignores: {', '.join(skipped)}"]
            if skipped
            else []
        )
        result = StepResult(
            f"{arr_id}: client de telechargement {dl_spec.display_name}",
            ok=client.find_by_name("downloadclient", dl_spec.display_name) is not None,
            detail=("cree" if created else "deja present") + f" (id={obj.get('id', '?')})",
            created=created,
            warnings=warnings,
        )
        return self._verify(client, "downloadclient", dl_spec.display_name, result)

    def step_qbittorrent_categories(self) -> StepResult:
        """Cree les categories qBittorrent avec leur chemin de sauvegarde."""
        inst = self.cfg.services["qbittorrent"]
        url = f"http://{self.cfg.host}:{inst.host_port}"
        with QBittorrentClient(url, inst.username or "", inst.password or "") as qb:
            qb.wait_ready()
            wanted = {
                category: path
                for arr_id, (category, path) in ARR_ROUTING.items()
                if self.cfg.enabled(arr_id)
            }
            if self.cfg.enabled("prowlarr"):
                # Prowlarr cree sinon lui-meme une categorie "prowlarr" SANS chemin
                # de sauvegarde. On la pose d'abord, avec le bon chemin : nos etapes
                # Prowlarr passent apres celle-ci dans le plan.
                wanted["prowlarr"] = CONTAINER_PATHS["torrents_root"]
            made = [c for c, path in wanted.items() if qb.ensure_category(c, path)]
            present = set(qb.categories())
        expected = set(wanted)
        return StepResult(
            "qbittorrent: categories avec chemin de sauvegarde",
            ok=expected <= present,
            detail=f"creees: {', '.join(made) or 'aucune (deja presentes)'}",
            created=bool(made),
        )

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

    def step_prowlarr_download_client(self, dl_id: str) -> StepResult:
        prowlarr = self.arr("prowlarr")
        profile = profile_for(dl_id)
        dl_spec = catalog.get(dl_id)
        dl = self.cfg.services[dl_id]

        obj, created, skipped = prowlarr.ensure_resource(
            "downloadclient",
            name=dl_spec.display_name,
            implementation=profile.implementation,
            values=profile.prowlarr_values(
                host=dl_spec.id,
                port=dl_spec.internal_port,
                username=dl.username or "",
                password=dl.password or "",
            ),
            extra={"enable": True, "protocol": profile.protocol, "priority": 1},
        )
        warnings = [f"champs ignores: {', '.join(skipped)}"] if skipped else []
        result = StepResult(
            f"prowlarr: client de telechargement {dl_spec.display_name}",
            ok=prowlarr.find_by_name("downloadclient", dl_spec.display_name) is not None,
            detail=("cree" if created else "deja present") + f" (id={obj.get('id', '?')})",
            created=created,
            warnings=warnings,
        )
        return self._verify(prowlarr, "downloadclient", dl_spec.display_name, result)

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
            wanted = [
                (arr_id, name, ctype, path)
                for arr_id, name, ctype, path in (
                    ("radarr", "Films", "movies", CONTAINER_PATHS["media_movies"]),
                    ("sonarr", "Series", "tvshows", CONTAINER_PATHS["media_tv"]),
                    ("lidarr", "Musique", "music", CONTAINER_PATHS["media_music"]),
                )
                if self.cfg.enabled(arr_id)
            ]
            made = [
                name for _a, name, ctype, path in wanted if jf.ensure_library(name, ctype, path)
            ]
            names = {lib.get("Name") for lib in jf.libraries()}
        ok = {name for _a, name, _c, _p in wanted} <= names
        detail = ("assistant execute" if ran else "assistant deja termine")
        detail += f", bibliotheques creees: {', '.join(made) or 'aucune (deja presentes)'}"
        return StepResult("jellyfin: assistant + bibliotheques", ok=ok, detail=detail, created=ran)

    # -- graphe --------------------------------------------------------------

    def build_plan(self) -> list[WiringStep]:
        """Construit le graphe a partir de la selection, sans liste codee en dur.

        Ajouter un *arr ou un client de telechargement au catalogue suffit a le
        faire apparaitre ici : c'est ce qui rend la phase 2 peu couteuse.
        """
        cfg = self.cfg
        steps: list[WiringStep] = []
        arrs = [a for a in catalog.MANAGED_ARRS if cfg.enabled(a)]
        clients = [d for d in catalog.DOWNLOAD_CLIENTS if cfg.enabled(d)]

        for arr_id in arrs:
            steps.append(
                WiringStep(
                    f"{arr_id}/rootfolder",
                    lambda a=arr_id: self.step_root_folder(a, ROOT_FOLDERS[a]),
                )
            )

        if cfg.enabled("qbittorrent"):
            # Les categories doivent exister avant que les *arr n'y envoient quoi
            # que ce soit : sinon qBittorrent les cree sans chemin de sauvegarde.
            steps.append(
                WiringStep("qbittorrent/categories", self.step_qbittorrent_categories)
            )

        for dl_id in clients:
            for arr_id in arrs:
                steps.append(
                    WiringStep(
                        f"{arr_id}/downloadclient/{dl_id}",
                        lambda a=arr_id, d=dl_id: self.step_download_client(a, d),
                    )
                )
            if cfg.enabled("prowlarr"):
                steps.append(
                    WiringStep(
                        f"prowlarr/downloadclient/{dl_id}",
                        lambda d=dl_id: self.step_prowlarr_download_client(d),
                    )
                )

        if cfg.enabled("prowlarr"):
            for arr_id in arrs:
                steps.append(
                    WiringStep(
                        f"prowlarr/application/{arr_id}",
                        lambda a=arr_id: self.step_prowlarr_application(a),
                    )
                )

        if cfg.enabled("jellyfin"):
            steps.append(WiringStep("jellyfin/setup", self.step_jellyfin_setup))
            for arr_id in arrs:
                if arr_id == "lidarr":
                    continue  # la notification MediaBrowser n'existe pas dans Lidarr
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
