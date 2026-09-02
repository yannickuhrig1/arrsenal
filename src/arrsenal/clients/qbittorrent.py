"""Client qBittorrent WebUI API v2.

Sert uniquement a creer les categories avec leur chemin de sauvegarde. Le reste du
cablage passe par les *arr, qui parlent directement a qBittorrent.
"""

from __future__ import annotations

import json
from typing import Self

import httpx

from .base import WiringError, new_client, wait_until


class QBittorrentClient:
    def __init__(self, base_url: str, username: str, password: str, *, name: str = "qbittorrent"):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self._username, self._password = username, password
        self._http = new_client(self.base_url, headers={"Referer": self.base_url})
        self._authenticated = False

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- session -------------------------------------------------------------

    def login(self) -> bool:
        """Ouvre une session. Renvoie True si authentifie.

        qBittorrent 5.x repond 204 avec un cookie QBT_SID en cas de succes, et 200
        avec le corps "Fails." en cas d'echec. C'est donc la PRESENCE DU COOKIE qui
        fait foi, pas le code de retour. Verifie contre 5.2.3.
        """
        try:
            resp = self._http.post(
                "/api/v2/auth/login",
                data={"username": self._username, "password": self._password},
            )
        except httpx.HTTPError as exc:
            raise WiringError(
                f"{self.name}: connexion impossible",
                str(exc),
                f"verifiez que {self.base_url} repond",
            ) from exc
        if "Fails." in resp.text:
            raise WiringError(
                f"{self.name}: identifiants refuses",
                'la WebUI a repondu "Fails."',
                "le qBittorrent.conf pre-seme a peut-etre ete ecrase. Relancez `arrsenal doctor`.",
            )
        self._authenticated = any(c.startswith("QBT_SID") for c in self._http.cookies) or (
            resp.status_code in (200, 204)
        )
        return self._authenticated

    def wait_ready(self, timeout: float = 300.0) -> None:
        def probe() -> bool:
            return bool(self._http.get("/api/v2/app/version").text.strip())

        result = wait_until(probe, label=self.name, timeout=timeout)
        if not result.ready:
            raise WiringError(
                "qBittorrent n'est jamais devenu disponible",
                result.detail,
                "inspectez `docker logs qbittorrent`",
            )
        self.login()

    @property
    def version(self) -> str:
        return self._http.get("/api/v2/app/version").text.strip()

    # -- categories ----------------------------------------------------------

    def categories(self) -> dict:
        resp = self._http.get("/api/v2/torrents/categories")
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError as exc:
            # Sur une session refusee, qBittorrent repond "Forbidden" en texte
            # brut avec un code 200. Sans ce garde-fou, l'appelant recevait une
            # JSONDecodeError nue au lieu d'un diagnostic.
            raise WiringError(
                "qbittorrent: reponse illisible sur les categories",
                f"contenu non JSON : {resp.text[:120]!r}",
                "les identifiants sont probablement refuses",
            ) from exc

    def ensure_category(self, name: str, save_path: str) -> bool:
        """Cree la categorie si absente. Renvoie True si creee.

        La categorie porte son chemin de sauvegarde : c'est ainsi que les
        telechargements de Sonarr atterrissent dans /data/torrents/tv sans que les
        *arr aient besoin de poser un repertoire explicite.
        """
        if name in self.categories():
            return False
        resp = self._http.post(
            "/api/v2/torrents/createCategory",
            data={"category": name, "savePath": save_path},
        )
        if resp.status_code >= 400:
            raise WiringError(
                f"{self.name}: creation de la categorie {name!r} refusee",
                f"HTTP {resp.status_code} - {resp.text[:200]}",
                "la session est-elle bien authentifiee ?",
            )
        return True

    def set_password(self, password: str) -> None:
        """Change le mot de passe de la WebUI par l'API de qBittorrent.

        `setPreferences` attend un JSON dans un champ de formulaire nomme `json` :
        ce n'est pas un corps JSON. Verifie contre 5.2.3.

        Passer par l'API plutot que par `qBittorrent.conf` evite d'arreter le
        conteneur : qBittorrent garde sa configuration en memoire et reecrit le
        fichier a l'arret, donc une modification a chaud du fichier serait
        purement et simplement perdue.
        """
        resp = self._http.post(
            "/api/v2/app/setPreferences",
            data={"json": json.dumps({"web_ui_password": password})},
        )
        if resp.status_code >= 400:
            raise WiringError(
                f"{self.name}: changement de mot de passe refuse",
                f"HTTP {resp.status_code} - {resp.text[:200]}",
                "la session est-elle bien authentifiee ?",
            )
        self._password = password
