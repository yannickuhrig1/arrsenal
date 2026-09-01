"""Client autobrr.

autobrr ecoute les canaux d'annonce IRC des trackers et pousse les sorties vers
les applications, au lieu d'attendre le prochain sondage RSS. La difference se
compte en secondes plutot qu'en minutes.

Tout ce qui suit a ete releve sur une instance v1.85.0, pas suppose. Quatre
particularites valaient d'etre notees, parce qu'aucune ne se devine :

- l'en-tete d'authentification est **`X-API-Token`**, pas `X-Api-Key` comme les
  *arr. Se tromper donne un 403 sans explication ;
- une cle API exige un champ `scopes` : sans lui, la creation echoue en 500 sur
  une contrainte SQL ;
- Sonarr, Radarr et Lidarr sont declares comme des **clients de telechargement**,
  au meme endpoint que qBittorrent, avec un `type` different ;
- l'accueil n'est jouable qu'une fois : `GET /api/auth/onboard` renvoie **503**
  des qu'un utilisateur existe. C'est ce qui rend l'etape idempotente.
"""

from __future__ import annotations

from typing import Any, Self

import httpx

from .base import WiringError, new_client, wait_until

#: Types acceptes par autobrr, verifies un par un contre l'instance.
CLIENT_TYPES = {
    "qbittorrent": "QBITTORRENT",
    "transmission": "TRANSMISSION",
    "sonarr": "SONARR",
    "radarr": "RADARR",
    "lidarr": "LIDARR",
}

#: Chemin a ajouter a l'adresse du service, quand autobrr attend un point
#: d'entree precis plutot que la racine.
#:
#: Transmission n'expose pas son RPC a la racine : `http://transmission:9091/`
#: repond une redirection HTML, et autobrr, qui attend du JSON, echoue sur
#: « invalid character '<' ». Le vrai point d'entree est `/transmission/rpc`, qui
#: repond 409 (« il me faut un jeton de session ») — c'est la reponse normale.
#:
#: Verifie contre l'API d'autobrr v1.85.0 : racine -> HTTP 500,
#: `/transmission/rpc` -> HTTP 204. Les *arr, eux, n'ont pas ce probleme : leur
#: gabarit de client de telechargement porte un champ `urlBase` distinct.
CLIENT_PATHS = {"transmission": "/transmission/rpc"}


def client_host(service_id: str, base_url: str) -> str:
    """Adresse a declarer dans autobrr pour ce service."""
    return base_url.rstrip("/") + CLIENT_PATHS.get(service_id, "")


class AutobrrClient:
    def __init__(self, base_url: str, *, name: str = "autobrr"):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self._http = new_client(self.base_url)
        self._token: str | None = None

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- primitives ----------------------------------------------------------

    def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        headers = dict(kw.pop("headers", {}))
        if self._token:
            headers["X-API-Token"] = self._token
        try:
            return self._http.request(method, path, headers=headers, **kw)
        except httpx.HTTPError as exc:
            raise WiringError(
                f"{self.name}: appel {method} {path} impossible",
                str(exc),
                f"verifiez que {self.base_url} repond",
            ) from exc

    def _expect(self, resp: httpx.Response, path: str, *ok: int) -> httpx.Response:
        if resp.status_code not in ok:
            raise WiringError(
                f"{self.name}: {path} a echoue",
                f"HTTP {resp.status_code} - {resp.text[:300]}",
                "l'API d'autobrr a peut-etre change de forme",
            )
        return resp

    # -- disponibilite -------------------------------------------------------

    def wait_ready(self, timeout: float = 180.0) -> None:
        def probe() -> bool:
            return self._request("GET", "/api/healthz/liveness").status_code == 200

        result = wait_until(probe, label=self.name, timeout=timeout)
        if not result.ready:
            raise WiringError(
                "autobrr n'est jamais devenu disponible",
                result.detail,
                "inspectez `docker logs autobrr`",
            )

    # -- premier utilisateur -------------------------------------------------

    @property
    def onboarded(self) -> bool:
        """Un utilisateur existe-t-il deja ?

        `GET /api/auth/onboard` renvoie 204 tant qu'aucun compte n'existe, puis
        503 « user already registered ». C'est ce qui rend l'etape rejouable.
        """
        return self._request("GET", "/api/auth/onboard").status_code != 204

    def onboard(self, username: str, password: str) -> bool:
        """Cree le premier utilisateur. Renvoie False s'il existait deja."""
        if self.onboarded:
            return False
        self._expect(
            self._request(
                "POST", "/api/auth/onboard", json={"username": username, "password": password}
            ),
            "creation du premier utilisateur",
            200,
            201,
        )
        return True

    def login(self, username: str, password: str) -> None:
        """Ouvre une session. Le cookie est garde par le client HTTP."""
        self._expect(
            self._request(
                "POST", "/api/auth/login", json={"username": username, "password": password}
            ),
            "connexion",
            200,
            204,
        )

    # -- cle API -------------------------------------------------------------

    def ensure_api_key(self, name: str) -> str:
        """Recupere ou cree une cle API. Necessite une session ouverte.

        `scopes` est obligatoire : sans lui autobrr repond 500 sur une contrainte
        `NOT NULL` de sa base.
        """
        existing = self._request("GET", "/api/keys")
        if existing.status_code == 200:
            for entry in existing.json() or []:
                if entry.get("name") == name and entry.get("key"):
                    self._token = entry["key"]
                    return self._token

        created = self._expect(
            self._request(
                "POST", "/api/keys", json={"name": name, "scopes": ["read", "write"]}
            ),
            "creation de la cle API",
            200,
            201,
        ).json()
        key = created.get("key")
        if not key:
            raise WiringError(
                "autobrr: aucune cle renvoyee",
                f"reponse inattendue : {created}",
                "l'API a peut-etre change de forme",
            )
        self._token = key
        return key

    # -- clients et applications ---------------------------------------------

    def clients(self) -> list[dict]:
        resp = self._request("GET", "/api/download_clients")
        return resp.json() if resp.status_code == 200 else []

    def ensure_client(
        self,
        *,
        name: str,
        service_id: str,
        host: str,
        api_key: str | None = None,
        username: str = "",
        password: str = "",
    ) -> tuple[bool, str]:
        """Declare un client de telechargement OU une application.

        autobrr ne fait pas la difference : Sonarr et qBittorrent passent par le
        meme endpoint, seul le `type` change.
        """
        client_type = CLIENT_TYPES.get(service_id)
        if client_type is None:
            raise WiringError(
                f"autobrr: {service_id} n'est pas un type connu",
                f"types acceptes : {', '.join(sorted(CLIENT_TYPES))}",
                "completez CLIENT_TYPES apres verification contre une instance",
            )

        if any(c.get("name") == name for c in self.clients()):
            return False, "deja present"

        payload: dict[str, Any] = {
            "name": name,
            "type": client_type,
            "enabled": True,
            "host": client_host(service_id, host),
            "username": username,
            "password": password,
            "settings": {"apikey": api_key} if api_key else {},
        }
        self._expect(
            self._request("POST", "/api/download_clients", json=payload),
            f"ajout de {name}",
            200,
            201,
        )
        return True, "cree"

    def test_client(self, name: str) -> tuple[bool, str]:
        """Declenche le test de connexion d'autobrr sur un client enregistre."""
        target = next((c for c in self.clients() if c.get("name") == name), None)
        if target is None:
            return False, "introuvable a la relecture"
        resp = self._request("POST", "/api/download_clients/test", json=target)
        if resp.status_code in (200, 204):
            return True, "test OK"
        return False, resp.text.strip()[:200]
