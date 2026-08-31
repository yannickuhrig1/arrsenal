"""Client Jellyfin : assistant de demarrage + bibliotheques.

Jellyfin est le seul service de la Phase 1 dont la configuration initiale ne peut
pas etre pre-semee : il faut passer par son assistant, exposé en HTTP tant que
`StartupWizardCompleted` est faux.

Attention securite : cette fenetre est ouverte a tout le monde tant que l'assistant
n'est pas termine. On la referme le plus tot possible dans le cablage.
"""

from __future__ import annotations

from typing import Any, Self

import httpx

from .base import WiringError, new_client, wait_until

_CLIENT_HEADER = (
    'MediaBrowser Client="arrsenal", Device="arrsenal", DeviceId="arrsenal", Version="0.1.0"'
)


class JellyfinClient:
    def __init__(self, base_url: str, *, name: str = "jellyfin"):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self._http = new_client(self.base_url, headers={"Authorization": _CLIENT_HEADER})
        self._token: str | None = None

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- primitives ----------------------------------------------------------

    def _request(self, method: str, path: str, **kw: Any) -> Any:
        headers = dict(kw.pop("headers", {}))
        if self._token:
            headers["Authorization"] = f'{_CLIENT_HEADER}, Token="{self._token}"'
        try:
            resp = self._http.request(method, path, headers=headers, **kw)
        except httpx.HTTPError as exc:
            raise WiringError(
                f"{self.name}: appel {method} {path} impossible",
                str(exc),
                f"verifiez que {self.base_url} repond",
            ) from exc
        if resp.status_code >= 400:
            raise WiringError(
                f"{self.name}: {method} {path} a echoue",
                f"HTTP {resp.status_code} - {resp.text[:400]}",
                "l'assistant de demarrage a peut-etre deja ete termine manuellement",
            )
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    # -- disponibilite -------------------------------------------------------

    def public_info(self) -> dict:
        return self._request("GET", "/System/Info/Public") or {}

    def wait_ready(self, timeout: float = 300.0) -> None:
        def probe() -> bool:
            return bool(self.public_info().get("Version"))

        result = wait_until(probe, label=self.name, timeout=timeout)
        if not result.ready:
            raise WiringError(
                "Jellyfin n'est jamais devenu disponible",
                result.detail,
                "inspectez `docker logs jellyfin`",
            )

    @property
    def wizard_done(self) -> bool:
        return bool(self.public_info().get("StartupWizardCompleted"))

    # -- assistant de demarrage ---------------------------------------------

    def run_startup_wizard(
        self,
        *,
        admin_user: str,
        admin_password: str,
        ui_culture: str = "fr",
        country: str = "FR",
        metadata_language: str = "fr",
    ) -> bool:
        """Termine l'assistant. Idempotent : ne fait rien s'il est deja termine.

        Renvoie True si l'assistant a effectivement ete execute.
        """
        if self.wizard_done:
            return False

        self._request(
            "POST",
            "/Startup/Configuration",
            json={
                "UICulture": ui_culture,
                "MetadataCountryCode": country,
                "PreferredMetadataLanguage": metadata_language,
            },
        )
        # Cet appel doit preceder la creation de l'utilisateur : il initialise
        # l'utilisateur par defaut cote serveur.
        self._request("GET", "/Startup/User")
        self._request(
            "POST", "/Startup/User", json={"Name": admin_user, "Password": admin_password}
        )
        self._request(
            "POST",
            "/Startup/RemoteAccess",
            json={"EnableRemoteAccess": True, "EnableAutomaticPortMapping": False},
        )
        self._request("POST", "/Startup/Complete")
        return True

    # -- session -------------------------------------------------------------

    def authenticate(self, username: str, password: str) -> str:
        data = self._request(
            "POST",
            "/Users/AuthenticateByName",
            json={"Username": username, "Pw": password},
        )
        token = (data or {}).get("AccessToken")
        if not token:
            raise WiringError(
                "Jellyfin: authentification refusee",
                "aucun AccessToken dans la reponse",
                "l'assistant de demarrage a-t-il bien cree l'utilisateur ?",
            )
        self._token = token
        return token

    # -- cles API ------------------------------------------------------------

    def ensure_api_key(self, app_name: str) -> str:
        """Recupere ou cree une cle API Jellyfin.

        Necessaire car la notification `MediaBrowser` de Sonarr/Radarr exige un
        champ `apiKey` non vide : sans elle, le lien "rafraichir la bibliotheque"
        est refuse avec un HTTP 400. Verifie contre Jellyfin 10.11.11.
        """
        existing = self._find_key(app_name)
        if existing:
            return existing
        self._request("POST", "/Auth/Keys", params={"app": app_name})
        created = self._find_key(app_name)
        if not created:
            raise WiringError(
                "Jellyfin: cle API introuvable apres creation",
                f"aucune entree {app_name!r} dans /Auth/Keys",
                "verifiez que l'utilisateur administrateur a bien ete cree",
            )
        return created

    def _find_key(self, app_name: str) -> str | None:
        data = self._request("GET", "/Auth/Keys") or {}
        for item in data.get("Items", []):
            if item.get("AppName") == app_name and item.get("AccessToken"):
                return str(item["AccessToken"])
        return None

    # -- bibliotheques -------------------------------------------------------

    def libraries(self) -> list[dict]:
        return self._request("GET", "/Library/VirtualFolders") or []

    def ensure_library(self, name: str, collection_type: str, path: str) -> bool:
        """Cree une bibliotheque si aucune du meme nom n'existe. Renvoie True si creee."""
        if any(lib.get("Name") == name for lib in self.libraries()):
            return False
        self._request(
            "POST",
            "/Library/VirtualFolders",
            params={"name": name, "collectionType": collection_type, "refreshLibrary": "false"},
            json={"LibraryOptions": {"PathInfos": [{"Path": path}]}},
        )
        return True
