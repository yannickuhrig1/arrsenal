"""Client Audiobookshelf : accueil, connexion, bibliotheques.

Tout ce qui suit a ete releve contre une instance reelle en 2.36.0, et deux
fausses pistes valent d'etre consignees parce qu'elles couteraient une journee
a qui les reprend.

**Audiobookshelf met environ quarante secondes a demarrer.** Il applique ses
migrations, cree ses declencheurs SQLite, lance un ANALYZE, puis seulement
ecoute. Sonde plus tot, il repond `404` sur `/` et donne l'impression que son
interface n'est pas servie. Elle l'est. C'est pourquoi `wait_ready` interroge
`/status` et non le conteneur.

**`isInit` vaut exactement `Database.hasRootUser`**, lu dans son code source :

    router.get('/status', (req, res) => {
      // server has been initialized if a root user exists
      isInit: Database.hasRootUser,

Une lecture de sa base SQLite qui montre une table `users` vide alors que
`isInit` repond `true` ne signale pas une incoherence : elle signale qu'on a
copie `absdatabase.sqlite` SANS son journal `-wal`, ou vivent les ecritures
recentes. Le piege est facile et la conclusion trompeuse.

Le contrat, verifie appel par appel :

    GET  /status        -> {"isInit": false, "serverVersion": "2.36.0", ...}
    POST /init          -> 200, corps {"newRoot": {"username", "password"}}
                           500 si un compte racine existe deja
    POST /login         -> 200, jeton dans user.accessToken
    GET  /api/libraries -> {"libraries": [...]}   (objet, pas tableau)
    POST /api/libraries -> 200 + la bibliotheque creee
"""

from __future__ import annotations

from typing import Any, Self

import httpx

from .base import WiringError, new_client, wait_until

#: Fournisseurs de metadonnees, releves sur l'instance. `audible` pour ce qui
#: s'ecoute, `google` pour ce qui se lit : ce sont ceux qui rendent des
#: resultats utiles sans clef d'API a fournir.
PROVIDERS = {"audiobooks": "audible", "books": "google"}


class AudiobookshelfClient:
    def __init__(self, base_url: str, *, name: str = "audiobookshelf"):
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

    def _request(self, method: str, path: str, **kw: Any) -> Any:
        headers = dict(kw.pop("headers", {}))
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
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
                f"HTTP {resp.status_code} - {resp.text[:300]}",
                "l'accueil a peut-etre deja ete termine manuellement",
            )
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    # -- disponibilite -------------------------------------------------------

    def wait_ready(self, timeout: float = 300.0) -> None:
        """Attend que le SERVEUR reponde, pas que le conteneur tourne.

        Quarante secondes observees au premier demarrage : migrations,
        declencheurs SQLite, ANALYZE. Sonder trop tot rend des 404 qui font
        croire a une image cassee.
        """

        def probe() -> bool:
            try:
                return "isInit" in (self._request("GET", "/status") or {})
            except WiringError:
                return False

        result = wait_until(probe, label=self.name, timeout=timeout)
        if not result.ready:
            raise WiringError(
                "Audiobookshelf n'est jamais devenu disponible",
                result.detail,
                "inspectez `docker logs plugarr-audiobookshelf`",
            )

    @property
    def status(self) -> dict:
        return self._request("GET", "/status") or {}

    @property
    def needs_setup(self) -> bool:
        return not self.status.get("isInit")

    @property
    def version(self) -> str:
        return str(self.status.get("serverVersion", "?"))

    # -- accueil -------------------------------------------------------------

    def setup(self, *, username: str, password: str) -> bool:
        """Cree le compte racine. Renvoie True s'il a ete cree ici.

        NE CONNECTE PAS. `POST /init` repond 200 avec un corps vide et ne rend
        aucun jeton — contrairement a Silo, dont l'accueil en renvoie deux.
        L'appelant doit enchainer sur `login`, sinon le premier appel a l'API
        repond 401.

        `POST /init` repond 500 si un compte racine existe deja — on relit donc
        l'etat avant, plutot que d'interpreter un code d'erreur.

        Le mot de passe VIDE est accepte par Audiobookshelf, qui se contente
        d'un avertissement dans son journal. On ne s'en sert jamais : un serveur
        media sans mot de passe sur un reseau domestique est une porte ouverte.
        """
        if not self.needs_setup:
            return False
        if not password:
            raise WiringError(
                f"{self.name}: mot de passe vide refuse",
                "Audiobookshelf accepterait, mais laisserait le compte sans protection",
                "laissez PlugArr generer le mot de passe",
            )
        self._request("POST", "/init", json={"newRoot": {"username": username, "password": password}})
        return True

    def login(self, username: str, password: str) -> None:
        reponse = self._request("POST", "/login", json={"username": username, "password": password})
        utilisateur = (reponse or {}).get("user") or {}
        jeton = utilisateur.get("accessToken") or utilisateur.get("token")
        if not jeton:
            raise WiringError(
                f"{self.name}: connexion refusee",
                "aucun jeton dans la reponse",
                "les identifiants annonces sont-ils bien ceux du compte ?",
            )
        self._token = jeton

    # -- bibliotheques -------------------------------------------------------

    def libraries(self) -> list[dict]:
        """La reponse est un OBJET portant `libraries`, pas un tableau."""
        return (self._request("GET", "/api/libraries") or {}).get("libraries") or []

    def ensure_library(self, name: str, chemin: str, *, provider: str = "google") -> bool:
        """Cree une bibliotheque si aucune ne couvre deja ce chemin. True si creee.

        Le doublon se juge sur le CHEMIN et non sur le nom : deux bibliotheques
        sur le meme dossier scanneraient les memes fichiers deux fois, et se
        fier au nom ferait echouer un second passage apres un renommage.
        """
        for lib in self.libraries():
            if any(d.get("fullPath") == chemin for d in lib.get("folders") or []):
                return False
        self._request(
            "POST",
            "/api/libraries",
            json={
                "name": name,
                "folders": [{"fullPath": chemin}],
                # `book` couvre les livres ET les livres audio : c'est le
                # dossier qui les distingue, pas le type.
                "mediaType": "book",
                "provider": provider,
                "icon": "audiobookshelf",
            },
        )
        return True

    def scan(self, library_id: str) -> bool:
        """Declenche l'analyse d'une bibliotheque. Rend la main tout de suite.

        Sans elle, la bibliotheque reste vide jusqu'a la premiere analyse
        planifiee, et l'utilisateur croit que rien n'a fonctionne.
        """
        try:
            self._request("POST", f"/api/libraries/{library_id}/scan")
        except WiringError:
            return False
        return True
