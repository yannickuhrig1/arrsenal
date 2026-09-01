"""Le graphe de cablage. C'est la raison d'etre du projet.

Chaque etape est idempotente et verifiable. Une etape se declare :
  - `run`    : execute le cablage, renvoie un libelle de resultat
  - `verify` : RELIT depuis l'API cible pour confirmer, plutot que de faire
               confiance au code de retour du POST

Toutes les URL de cablage sont des URL INTERNES au reseau compose
(http://sonarr:8989), jamais localhost : c'est un conteneur qui parle a un autre.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from . import catalog, journal
from .clients import recyclarr as recyclarr_cfg
from .clients.arr import ArrClient
from .clients.autobrr import AutobrrClient
from .clients.base import WiringError
from .clients.jellyfin import JellyfinClient
from .clients.qbittorrent import QBittorrentClient
from .clients.qui import QuiClient
from .downloadclients import ARR_ROUTING, profile_for
from .layout import CONTAINER_PATHS
from .models import Category, StackConfig

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
        self,
        client: ArrClient,
        resource: str,
        name: str,
        result: StepResult,
        on_auth_failure: Callable[[], bool] | None = None,
    ) -> StepResult:
        """Fait valider le lien par l'application elle-meme.

        `on_auth_failure` permet de tenter UNE reparation quand le refus vient
        d'un bannissement plutot que d'un mauvais mot de passe : les deux se
        presentent a l'identique, « Authentication Failure ».
        """
        if not self.run_tests:
            return result
        obj = client.find_by_name(resource, name)
        if obj is None:
            result.ok = False
            result.detail += " - introuvable a la relecture"
            return result
        ok, message = client.test_resource(resource, obj)
        # La reparation ne vaut que pour un refus d'AUTHENTIFICATION. L'avoir
        # elargie a tout echec redemarrait qBittorrent sur un simple defaut de
        # connexion — et ce redemarrage cassait a son tour l'adresse mise en
        # cache par Sonarr, qui echouait alors sur « Unable to connect ». Le
        # remede fabriquait la panne suivante.
        refus = not ok and "Authentication Failure" in message
        if refus and on_auth_failure and on_auth_failure():
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
        """URL du service vue par un AUTRE conteneur.

        Delegue a ServiceInstance : un service adopte n'est pas sur le reseau
        compose et doit etre joint par l'hote.
        """
        spec = catalog.get(service_id)
        behind_vpn = self.cfg.vpn.enabled and spec.category is Category.DOWNLOAD
        return self.cfg.services[service_id].internal_url(
            spec, self.cfg.host, behind_vpn=behind_vpn
        )

    def close(self) -> None:
        for client in self._arr_cache.values():
            client.close()
        self._arr_cache.clear()

    # -- etapes --------------------------------------------------------------

    def step_root_folder(self, arr_id: str, path: str) -> StepResult:
        client = self.arr(arr_id)

        if self.cfg.services[arr_id].adopted:
            # Une stack adoptee a DEJA son arborescence, et ce n'est pas la notre.
            # Constate en conditions reelles : imposer /data/media/tv a un Sonarr
            # existant echoue avec "Path does not exist", et ce serait de toute
            # facon une intrusion. Adopter, c'est cabler des services entre eux,
            # pas reorganiser les dossiers de quelqu'un.
            existing = [f.get("path", "") for f in client.get("rootfolder") or []]
            if existing:
                return StepResult(
                    f"{arr_id}: dossier racine",
                    ok=True,
                    detail=f"deja configure ({', '.join(existing)}), respecte",
                )
            return StepResult(
                f"{arr_id}: dossier racine",
                ok=True,
                detail="aucun dossier racine configure",
                warnings=[
                    (
                        f"{arr_id} n'a aucun dossier racine et arrsenal ne peut pas "
                        f"deviner votre arborescence. Ajoutez-le dans {arr_id} avant "
                        f"d'importer."
                    )
                ],
            )

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

    def _conseil_config_existante(self, sid: str) -> str:
        """Explication a joindre quand un service refuse nos identifiants.

        Trois services ne stockent leur mot de passe que HACHE : Jellyfin,
        autobrr et qui. Si leur configuration vient d'une installation
        precedente, arrsenal ne peut ni le relire ni le reinitialiser — aucune
        API ne le permet sans le mot de passe actuel.

        Le message brut (« connexion a echoue », « HTTP 401 ») envoyait chercher
        une panne reseau. La cause est ailleurs, et la solution tient en une
        ligne.
        """
        from pathlib import Path

        dossier = Path(self.cfg.config_path(sid))
        if not (dossier.is_dir() and any(dossier.iterdir())):
            return ""
        return (
            f"{sid} a une configuration prealable dans {dossier}. Son mot de passe "
            f"n'y est stocke que hache : arrsenal ne peut pas le retrouver, et celui "
            f"qu'il annonce est refuse. Supprimez ce dossier pour repartir a zero, ou "
            f"reprenez l'installation d'origine avec --project-dir."
        )

    def _unban_download_client(self, dl_id: str) -> bool:
        """Redemarre un client de telechargement pour lever un bannissement.

        qBittorrent bannit une adresse apres cinq echecs d'authentification, une
        heure durant. Le bannissement est PAR ADRESSE : sonde depuis l'hote, tout
        va bien ; depuis le conteneur Sonarr, c'est un 403. Le *arr traduit ce
        403 en « Authentication Failure » et accuse les identifiants, alors
        qu'ils sont corrects.

        Vu en conditions reelles : 204 depuis l'hote et 403 depuis Sonarr, au
        meme instant, avec le meme mot de passe. Un redemarrage vide la liste des
        bannis.
        """
        from pathlib import Path

        from .runner import Compose

        if dl_id != "qbittorrent" or self.cfg.project_dir is None:
            return False
        runner = Compose(Path(str(self.cfg.project_dir)), self.cfg.project_name)
        ok, _ = runner.control("restart", dl_id)
        if not ok:
            return False
        with QBittorrentClient(
            self.cfg.services[dl_id].url(self.cfg.host),
            self.cfg.services[dl_id].username or "",
            self.cfg.services[dl_id].password or "",
        ) as client:
            client.wait_ready(timeout=120.0)
        return True

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

        if dl.adopted:
            # Le client existant n'est pas sur le reseau compose : on le joint par
            # l'hote. Et son mot de passe est hache dans sa configuration, donc
            # illisible : il doit venir de l'utilisateur.
            if not dl.password:
                return StepResult(
                    f"{arr_id}: client de telechargement {dl_spec.display_name}",
                    ok=False,
                    detail="identifiants inconnus",
                    warnings=[
                        (
                            f"Le mot de passe de {dl_spec.display_name} est hache dans "
                            f"sa configuration : arrsenal ne peut pas le lire. Passez "
                            f"--dl-user et --dl-pass."
                        )
                    ],
                )
            host, port = self.cfg.host, dl.host_port
        elif self.cfg.vpn.enabled:
            # Le client partage la pile reseau de Gluetun : c'est gluetun qu'il
            # faut viser, pas son propre nom de service qui ne resout plus.
            host, port = "gluetun", dl_spec.internal_port
        else:
            host, port = dl_spec.id, dl_spec.internal_port

        values = profile.arr_values(
            host=host,
            port=port,
            username=dl.username or "",
            password=dl.password or "",
            arr_id=arr_id,
        )
        if dl.adopted:
            # Ne pas imposer notre arborescence a une stack existante : on laisse
            # le routage par categorie et on efface tout repertoire que le profil
            # aurait pose.
            values = {k: ("" if k.endswith("Directory") else v) for k, v in values.items()}
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

        etat = "cree" if created else "deja present"
        if not created:
            # Une entree existante garde les identifiants d'alors. Si le mot de
            # passe du client a change depuis — une reinstallation suffit — elle
            # reste en place et son test echoue, sans que rien ne l'explique. On
            # realigne les seuls champs d'identification.
            identifiants = {
                nom: values[nom] for nom in ("username", "password") if nom in values
            }
            try:
                modifies = client.sync_fields("downloadclient", obj, identifiants)
            except WiringError:
                # Un bannissement se presente comme un refus d'identifiants. On
                # le leve une fois, puis on reessaie : si l'echec persiste, c'est
                # bien le mot de passe qui est en cause.
                if not self._unban_download_client(dl_id):
                    raise
                modifies = client.sync_fields("downloadclient", obj, identifiants)
            if modifies:
                etat = f"identifiants mis a jour ({', '.join(modifies)})"

        result = StepResult(
            f"{arr_id}: client de telechargement {dl_spec.display_name}",
            ok=client.find_by_name("downloadclient", dl_spec.display_name) is not None,
            detail=etat + f" (id={obj.get('id', '?')})",
            created=created,
            warnings=warnings,
        )
        return self._verify(
            client,
            "downloadclient",
            dl_spec.display_name,
            result,
            on_auth_failure=lambda: self._unban_download_client(dl_id),
        )

    def step_qbittorrent_categories(self) -> StepResult:
        """Cree les categories qBittorrent avec leur chemin de sauvegarde."""
        inst = self.cfg.services["qbittorrent"]
        if inst.adopted:
            # Meme raison que pour les dossiers racine : un client existant a deja
            # ses categories et ses chemins. Les ecraser deplacerait les
            # telechargements en cours de quelqu'un.
            return StepResult(
                "qbittorrent: categories",
                ok=True,
                detail="client existant, categories laissees telles quelles",
            )
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

        etat = "cree" if created else "deja present"
        if not created:
            # Meme raison que pour les *arr : une entree existante garde les
            # identifiants d'alors, et son test echoue apres un changement de mot
            # de passe. Prowlarr passe par une etape distincte, il avait donc
            # ete oublie — 13 liens sur 14 au lieu de 14.
            identifiants = {"username": dl.username or "", "password": dl.password or ""}
            try:
                modifies = prowlarr.sync_fields("downloadclient", obj, identifiants)
            except WiringError:
                if not self._unban_download_client(dl_id):
                    raise
                modifies = prowlarr.sync_fields("downloadclient", obj, identifiants)
            if modifies:
                etat = f"identifiants mis a jour ({', '.join(modifies)})"

        result = StepResult(
            f"prowlarr: client de telechargement {dl_spec.display_name}",
            ok=prowlarr.find_by_name("downloadclient", dl_spec.display_name) is not None,
            detail=etat + f" (id={obj.get('id', '?')})",
            created=created,
            warnings=warnings,
        )
        return self._verify(
            prowlarr,
            "downloadclient",
            dl_spec.display_name,
            result,
            on_auth_failure=lambda: self._unban_download_client(dl_id),
        )

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
            # Les bibliotheques sont creees sans analyse, pour ne pas bloquer
            # l'installation. Encore faut-il en lancer une : sans elle Jellyfin
            # garde un index VIDE, et les notifications d'import de Sonarr — qui
            # repondent pourtant 200 — n'y changent rien. Constate sur une stack
            # reelle, deux episodes sur le disque et zero dans Jellyfin.
            analyse = jf.refresh_libraries()
        ok = {name for _a, name, _c, _p in wanted} <= names
        detail = ("assistant execute" if ran else "assistant deja termine")
        detail += f", bibliotheques creees: {', '.join(made) or 'aucune (deja presentes)'}"
        detail += ", analyse lancee" if analyse else ""
        return StepResult(
            "jellyfin: assistant + bibliotheques",
            ok=ok,
            detail=detail,
            created=ran,
            warnings=[] if analyse else ["l'analyse des bibliotheques n'a pas pu etre lancee"],
        )

    def step_autobrr(self) -> StepResult:
        """Declare les applications et le client de telechargement dans autobrr.

        autobrr ne distingue pas les deux : Sonarr et qBittorrent passent par le
        meme endpoint, seul le `type` change.
        """
        inst = self.cfg.services["autobrr"]
        url = f"http://{self.cfg.host}:{inst.host_port}"
        created: list[str] = []
        warnings: list[str] = []

        with AutobrrClient(url) as brr:
            brr.wait_ready()
            first = brr.onboard(inst.username or "arrsenal", inst.password or "")
            brr.login(inst.username or "arrsenal", inst.password or "")
            inst.api_key = brr.ensure_api_key("arrsenal")

            targets = [
                sid
                for sid in (*catalog.MANAGED_ARRS, *catalog.DOWNLOAD_CLIENTS)
                if self.cfg.enabled(sid)
            ]
            for sid in targets:
                spec, target = catalog.get(sid), self.cfg.services[sid]
                added, _ = brr.ensure_client(
                    name=spec.display_name,
                    service_id=sid,
                    host=self.internal_url(sid),
                    api_key=target.api_key,
                    username=target.username or "",
                    password=target.password or "",
                )
                if added:
                    created.append(spec.display_name)
                if self.run_tests:
                    ok, message = brr.test_client(spec.display_name)
                    if not ok:
                        warnings.append(f"{spec.display_name} : {message.splitlines()[0]}")

        detail = "accueil execute" if first else "utilisateur existant"
        detail += f", declares : {', '.join(created) or 'aucun (deja presents)'}"
        return StepResult(
            "autobrr: applications et client de telechargement",
            ok=not warnings,
            detail=detail,
            created=bool(created),
            warnings=warnings,
        )

    def step_recyclarr(self) -> StepResult:
        """Genere la configuration Recyclarr et y ecrit adresses et cles.

        arrsenal ne reimplemente pas les TRaSH Guides : il demande a Recyclarr de
        generer sa configuration a partir de templates OFFICIELS, puis remplace
        les marqueurs `Put your ... here`. Tout le contenu des profils reste
        celui du guide.
        """
        from pathlib import Path

        from .runner import Compose

        config_dir = Path(self.cfg.config_path("recyclarr"))
        runner = Compose(self.cfg.project_dir or Path("."), self.cfg.project_name)

        wanted = {
            sid: self.cfg.recyclarr_templates.get(
                sid, recyclarr_cfg.DEFAULT_TEMPLATES.get(sid, "")
            )
            for sid in ("sonarr", "radarr")
            if self.cfg.enabled(sid)
        }
        wanted = {sid: name for sid, name in wanted.items() if name}
        if not wanted:
            return StepResult(
                "recyclarr: profils de qualite",
                ok=True,
                detail="aucun template choisi, rien a generer",
            )

        # Recyclarr REFUSE d'ecraser un fichier existant, et il a raison : celui-ci
        # a pu etre modifie a la main. On ne demande donc que ce qui manque. Sans
        # cela, rejouer `wire` echouait sur « File already exists », alors que la
        # commande est censee etre idempotente.
        #
        # `--force` existe, mais l'employer detruirait les reglages de
        # l'utilisateur a chaque passage.
        args = []
        for name in wanted.values():
            if not (config_dir / "configs" / f"{name}.yml").exists():
                args += ["--template", name]

        if args:
            ok, message = runner.run_once("recyclarr", ["config", "create", *args])
            if not ok:
                return StepResult(
                    "recyclarr: profils de qualite",
                    ok=False,
                    detail="generation impossible",
                    warnings=[message.splitlines()[-1][:200] if message else "aucun detail"],
                )

        filled, kept, warnings = [], [], []
        for path in sorted((config_dir / "configs").glob("*.yml")):
            service = recyclarr_cfg.target_service(path)
            if service is None or not self.cfg.enabled(service):
                continue
            result = recyclarr_cfg.fill(
                path,
                self.internal_url(service),
                self.cfg.services[service].api_key or "",
                service,
            )
            # Un fichier deja renseigne n'a plus de marqueur a remplacer : ce n'est
            # pas un echec, c'est un second passage. Seul un marqueur RESTANT est
            # un probleme, et `pending_markers` le voit.
            (filled if (result.url_written or result.key_written) else kept).append(
                f"{path.stem} -> {service}"
            )

        for leftover in recyclarr_cfg.pending_markers(config_dir):
            warnings.append(
                f"{leftover.name} contient encore un marqueur : la synchronisation "
                f"echouera tant qu'il est la"
            )

        parts = list(filled)
        if kept:
            parts.append(f"{len(kept)} deja configure{'s' if len(kept) > 1 else ''}")

        # Premiere synchronisation immediate. Sans elle, Recyclarr n'ecrit rien
        # avant son reveil planifie : l'utilisateur ouvre Sonarr juste apres
        # l'installation, ne voit aucun profil TRaSH et en conclut que rien n'a
        # marche. La fonctionnalite doit etre visible a la fin du cablage, pas
        # vingt-quatre heures plus tard.
        # L'echec de cette synchronisation ne remet pas en cause le cablage : les
        # fichiers sont ecrits et la planification quotidienne reessaiera. C'est un
        # avertissement, pas un echec — d'ou ce `ok` calcule avant.
        wired = not warnings and bool(filled or kept)
        if wired:
            synced, message = runner.run_once("recyclarr", ["sync"])
            if synced:
                groups = re.findall(r"Created \d+ Profiles: \[([^\]]*)\]", message)
                names = sorted({n.strip('" ') for group in groups for n in group.split(",")})
                parts.append(f"synchronise{' : ' + ', '.join(names) if names else ''}")
            else:
                last = message.strip().splitlines()[-1][:200] if message.strip() else "aucun detail"
                warnings.append(
                    f"premiere synchronisation echouee ({last}). La configuration est "
                    f"ecrite : Recyclarr reessaiera a sa planification quotidienne."
                )

        return StepResult(
            "recyclarr: profils de qualite",
            ok=wired,
            detail=", ".join(parts) or "aucun fichier rempli",
            created=bool(filled),
            warnings=warnings,
        )

    def step_web_login(self, arr_id: str) -> StepResult:
        """Garantit que les identifiants annonces ouvrent vraiment l'interface.

        Le pre-semis ecrit `<Username>` et `<Password>` dans config.xml. Sonarr et
        Radarr les consomment au premier demarrage et creent le compte. **Prowlarr
        2.5.2 les EFFACE sans creer personne** : son interface devient
        definitivement inaccessible, puisque sa page de connexion n'offre aucune
        creation de compte. Le cablage, lui, continuait de fonctionner par cle
        API — la panne ne se voyait donc nulle part, sauf en essayant de se
        connecter.

        On teste la connexion comme un navigateur, et on ne repare que si elle
        echoue : reecrire un mot de passe deja bon serait une modification pour
        rien.
        """
        inst = self.cfg.services[arr_id]
        username, password = inst.username or "", inst.password or ""
        client = self.arr(arr_id)

        if not username or not password:
            return StepResult(
                f"{arr_id}: acces web",
                ok=True,
                detail="aucun identifiant genere, rien a verifier",
            )

        if client.web_login_works(username, password):
            return StepResult(f"{arr_id}: acces web", ok=True, detail="connexion verifiee")

        client.ensure_web_user(username, password)
        repaired = client.web_login_works(username, password)
        return StepResult(
            f"{arr_id}: acces web",
            ok=repaired,
            detail="compte cree" if repaired else "compte cree, connexion toujours refusee",
            created=repaired,
            warnings=[]
            if repaired
            else [
                (
                    f"les identifiants annonces pour {arr_id} n'ouvrent pas l'interface. "
                    f"Definissez-en depuis Settings > General."
                )
            ],
        )

    def step_qui(self) -> StepResult:
        """Relie l'interface qui a l'instance qBittorrent de la stack.

        qui ne sert a rien seule : c'est une interface pour qBittorrent. Elle
        etait installee sans lien, et redemandait a l'utilisateur une adresse et
        des identifiants qu'arrsenal venait de generer.
        """
        inst = self.cfg.services["qui"]
        qb = self.cfg.services["qbittorrent"]
        host = self.internal_url("qbittorrent")

        with QuiClient(inst.url(self.cfg.host)) as client:
            client.wait_ready()
            client.setup(inst.username or "arrsenal", inst.password or "")
            client.login(inst.username or "arrsenal", inst.password or "")
            created = client.ensure_instance(
                name=catalog.get("qbittorrent").display_name,
                host=host,
                username=qb.username or "",
                password=qb.password or "",
            )

            if not self.run_tests:
                return StepResult(
                    "qui: instance qBittorrent",
                    ok=True,
                    detail="declaree" if created else "deja declaree",
                    created=created,
                )

            # C'est qui elle-meme qui dit si la connexion tient. Un 201 ne prouve
            # rien : une adresse sans port est acceptee puis ne se connecte jamais.
            linked, detail = client.connected(host)
            return StepResult(
                "qui: instance qBittorrent",
                ok=linked,
                detail=("declaree" if created else "deja declaree") + f", {detail}",
                created=created,
                warnings=[] if linked else [f"qui ne parvient pas a joindre {host} ({detail})"],
            )

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

        # Prowlarr compris : c'est LUI qui n'ouvrait pas. La verification passe par
        # la page de connexion, donc elle vaut pour toute la famille.
        for arr_id in (a for a in catalog.STARTUP_ORDER if cfg.enabled(a) and _is_arr(a)):
            steps.append(
                WiringStep(f"{arr_id}/acces-web", lambda a=arr_id: self.step_web_login(a))
            )

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

        if cfg.enabled("recyclarr"):
            steps.append(WiringStep("recyclarr/profils", self.step_recyclarr))

        if cfg.enabled("autobrr"):
            steps.append(WiringStep("autobrr/clients", self.step_autobrr))

        # qui n'a d'interet que reliee a une instance. Sans cette etape, elle etait
        # installee puis laissee vide : l'utilisateur ouvrait une interface qui lui
        # redemandait tout ce qu'arrsenal savait deja.
        if cfg.enabled("qui") and cfg.enabled("qbittorrent"):
            steps.append(WiringStep("qui/qbittorrent", self.step_qui))

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
                # Un refus d'identifiants sur un service au mot de passe hache a
                # presque toujours la meme cause : une configuration heritee d'une
                # installation precedente. Le dire ici evite d'envoyer l'
                # utilisateur chercher une panne reseau.
                service = step.name.split("/")[0]
                if service in _HASHED_ONLY and any(
                    mot in str(exc).lower() for mot in ("401", "refus", "echoue", "unauthorized")
                ):
                    conseil = self._conseil_config_existante(service)
                    if conseil:
                        result.warnings.append(conseil)
            except Exception as exc:  # noqa: BLE001
                # Un bug dans UNE etape ne doit pas emporter tout le cablage.
                # Vu en integration : une erreur de programmation a l'avant-
                # derniere etape a fait echouer l'installation apres 40 etapes
                # reussies, sans rapport ni page d'acces — alors que tout le
                # reste etait correctement cable et fonctionnel.
                journal.LOGGER.exception("etape %s", step.name)
                result = StepResult(
                    step.name,
                    ok=False,
                    detail=f"erreur inattendue ({type(exc).__name__}) : {exc}",
                    warnings=["ceci est un defaut d'arrsenal, pas de votre installation"],
                )
            results.append(result)
            if on_step:
                on_step(result)
        return results


def _is_arr(service_id: str) -> bool:
    """Un service de la famille *arr, Prowlarr compris."""
    return catalog.get(service_id).api_family == "arr"


#: Services dont le mot de passe n'existe que hache : arrsenal ne peut ni le
#: relire ni le reinitialiser sans lui.
_HASHED_ONLY = ("jellyfin", "autobrr", "qui")
