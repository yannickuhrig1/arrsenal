"""Client qui.

qui est une interface web moderne pour qBittorrent, du meme auteur qu'autobrr.
Elle sait piloter plusieurs instances, et n'a d'interet que reliee a au moins une.

Tout ce qui suit a ete releve sur v1.27.0, pas suppose :

- **tout repond 428** tant que le premier compte n'existe pas, y compris la page
  de connexion. C'est le signal « installation a terminer » ;
- le point d'entree de cette premiere creation est `POST /api/auth/setup`, et il
  repond **400 « Setup already completed »** une fois joue. C'est ce qui rend
  l'etape rejouable ;
- une instance se declare avec son **URL complete**. Passer `host` et `port`
  separement est accepte avec un 201 rassurant, mais le port est perdu : qui
  enregistre `http://qbittorrent` et la connexion ne s'etablit jamais ;
- **les doublons ne sont pas refuses**. Declarer deux fois la meme instance donne
  deux entrees. C'est a l'appelant de verifier avant d'ecrire ;
- `GET /api/instances` expose `connected` et `connectionStatus` : de quoi
  verifier le lien aupres de qui lui-meme, plutot que de croire le 201.
"""

from __future__ import annotations

from typing import Any, Self

import httpx

from .base import WiringError, new_client, wait_until


class QuiClient:
    def __init__(self, base_url: str, *, name: str = "qui"):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self._http = new_client(self.base_url)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- primitives ----------------------------------------------------------

    def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        try:
            return self._http.request(method, path, **kw)
        except httpx.HTTPError as exc:
            raise WiringError(
                f"{self.name}: appel {method} {path} impossible",
                str(exc),
                f"verifiez que {self.base_url} repond",
            ) from exc

    # -- disponibilite -------------------------------------------------------

    def wait_ready(self, timeout: float = 120.0) -> None:
        """Attend que le serveur reponde, installe ou non.

        428 signifie « je suis la, mais il n'y a pas encore de compte » : c'est
        une reponse valable pour dire que le service est demarre.
        """

        def probe() -> bool:
            return self._request("GET", "/api/auth/me").status_code in (200, 401, 428)

        result = wait_until(probe, label=self.name, timeout=timeout)
        if not result.ready:
            raise WiringError(
                "qui n'est jamais devenu disponible",
                result.detail,
                "inspectez `docker logs qui`",
            )

    # -- premier compte ------------------------------------------------------

    def setup(self, username: str, password: str) -> bool:
        """Cree le compte initial. Renvoie False s'il existait deja."""
        resp = self._request(
            "POST", "/api/auth/setup", json={"username": username, "password": password}
        )
        if resp.status_code in (200, 201):
            return True
        if resp.status_code == 400 and "already" in resp.text.lower():
            return False
        raise WiringError(
            "qui: creation du compte initial impossible",
            f"HTTP {resp.status_code} - {resp.text[:300]}",
            "l'API de qui a peut-etre change de forme",
        )

    def login(self, username: str, password: str) -> None:
        resp = self._request(
            "POST", "/api/auth/login", json={"username": username, "password": password}
        )
        if resp.status_code not in (200, 204):
            raise WiringError(
                "qui: connexion refusee",
                f"HTTP {resp.status_code} - {resp.text[:200]}",
                "le mot de passe enregistre ne correspond pas au compte existant",
            )

    # -- instances -----------------------------------------------------------

    def instances(self) -> list[dict]:
        resp = self._request("GET", "/api/instances")
        return resp.json() if resp.status_code == 200 else []

    @staticmethod
    def _same_host(left: str, right: str) -> bool:
        return left.rstrip("/") == right.rstrip("/")

    def ensure_instance(self, *, name: str, host: str, username: str, password: str) -> bool:
        """Declare une instance qBittorrent. Renvoie False si elle existait deja.

        qui n'interdit pas les doublons : sans cette verification, chaque passage
        de `arrsenal wire` ajouterait une entree de plus.
        """
        if any(self._same_host(i.get("host", ""), host) for i in self.instances()):
            return False

        resp = self._request(
            "POST",
            "/api/instances",
            json={"name": name, "host": host, "username": username, "password": password},
        )
        if resp.status_code not in (200, 201):
            raise WiringError(
                "qui: declaration de l'instance qBittorrent impossible",
                f"HTTP {resp.status_code} - {resp.text[:300]}",
                "verifiez que qBittorrent est demarre",
            )
        return True

    def connected(self, host: str, timeout: float = 60.0) -> tuple[bool, str]:
        """La connexion est-elle etablie, selon qui lui-meme ?

        L'etat n'est pas immediat apres la creation : qui doit d'abord ouvrir une
        session vers qBittorrent. On laisse le temps de s'etablir plutot que de
        conclure trop tot.
        """
        state = {"detail": "aucune instance a cette adresse"}

        def probe() -> bool:
            for inst in self.instances():
                if not self._same_host(inst.get("host", ""), host):
                    continue
                status = inst.get("connectionStatus") or "inconnu"
                state["detail"] = f"etat {status}"
                return bool(inst.get("connected"))
            return False

        result = wait_until(probe, label=self.name, timeout=timeout)
        return result.ready, state["detail"]
