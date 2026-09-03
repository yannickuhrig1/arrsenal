"""Client Silo : accueil, connexion, bibliotheques.

Silo est en PRE-VERSION. Son README l'ecrit noir sur blanc : « son API, sa
configuration et ses migrations de base peuvent changer avant sa premiere
version stable ». Ce client vise `build-522`, epingle par digest dans le
catalogue — ce qui protege qui n'update pas, et personne d'autre.

Tout ce qui suit a ete releve contre une instance reelle, pas lu dans une
documentation : la documentation publiee couvre les preferences client, pas
l'administration.

    GET  /api/v1/auth/setup      -> {"needs_setup": true|false}
    POST /api/v1/auth/setup      -> 201 + {"access_token", "refresh_token"}
    POST /api/v1/auth/login      -> 200 + jetons
    GET  /api/v1/libraries       -> [ ... ]
    POST /api/v1/libraries       -> 201

Le contrat de creation a demande trois essais. `path`, `root_path` et `kind`
sont tous refuses par « Paths, type, and name are required » : c'est
`paths`, au PLURIEL et en tableau, avec `type` et `name`.
"""

from __future__ import annotations

from typing import Any, Self

import httpx

from .base import WiringError, new_client, wait_until

#: Types acceptes, releves un par un contre l'instance : chacun a ete envoye et
#: la reponse lue. Un type inconnu est refuse en 400.
LIBRARY_TYPES = ("movie", "show", "music", "book", "audiobook", "photo")


class SiloClient:
    def __init__(self, base_url: str, *, name: str = "silo"):
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
            resp = self._http.request(method, f"/api/v1{path}", headers=headers, **kw)
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
        """Silo demarre lentement : trente secondes observees, base saine comprise.

        Il redemarre en boucle tant que sa base ne repond pas. Attendre son
        API plutot que son conteneur evite de cabler dans le vide.
        """

        def probe() -> bool:
            try:
                return "needs_setup" in (self._request("GET", "/auth/setup") or {})
            except WiringError:
                return False

        result = wait_until(probe, label=self.name, timeout=timeout)
        if not result.ready:
            raise WiringError(
                "Silo n'est jamais devenu disponible",
                result.detail,
                "inspectez `docker logs arrsenal-silo`",
            )

    @property
    def needs_setup(self) -> bool:
        return bool((self._request("GET", "/auth/setup") or {}).get("needs_setup"))

    # -- accueil -------------------------------------------------------------

    def setup(self, *, username: str, password: str, email: str = "") -> bool:
        """Cree le premier compte administrateur. Renvoie True si cree.

        Un second appel echouerait : l'accueil ne se rejoue pas. On relit donc
        l'etat plutot que de deviner, exactement comme pour Jellyfin.

        L'adresse est OBLIGATOIRE — « Username, email, and password are
        required », constate en l'omettant. Faute d'en connaitre une, on en
        fabrique une sous `.invalid`, domaine reserve par la RFC 2606 qui ne
        peut par construction jamais resoudre : rien ne partira jamais dessus.
        """
        if not self.needs_setup:
            return False
        corps: dict[str, Any] = {
            "username": username,
            "password": password,
            "email": email or f"{username}@arrsenal.invalid",
        }
        reponse = self._request("POST", "/auth/setup", json=corps) or {}
        self._token = reponse.get("access_token")
        return True

    def login(self, username: str, password: str) -> None:
        reponse = (
            self._request("POST", "/auth/login", json={"username": username, "password": password})
            or {}
        )
        jeton = reponse.get("access_token")
        if not jeton:
            raise WiringError(
                f"{self.name}: connexion refusee",
                "aucun jeton dans la reponse",
                "les identifiants annonces sont-ils bien ceux du compte ?",
            )
        self._token = jeton

    # -- profils -------------------------------------------------------------

    def profiles(self) -> list[dict]:
        """Profils du foyer. La reponse est un OBJET, pas un tableau."""
        return (self._request("GET", "/profiles") or {}).get("profiles") or []

    def ensure_profile(self, name: str) -> bool:
        """Cree le premier profil du foyer si aucun n'existe. True si cree.

        Silo separe le COMPTE du PROFIL, et cette distinction bloque l'entree :
        sans profil, l'application affiche « Create your first profile — You
        need a profile before you can enter the app » et rien d'autre.

        Signale a l'usage, en ouvrant l'interface apres un cablage pourtant
        reussi : le compte existait, les bibliotheques aussi, et l'utilisateur
        se retrouvait quand meme devant un mur. Creer le compte sans creer le
        profil, c'est livrer une porte sans poignee.

        Le premier profil devient `is_primary` tout seul.
        """
        if self.profiles():
            return False
        self._request("POST", "/profiles", json={"name": name})
        return True

    # -- bibliotheques -------------------------------------------------------

    def libraries(self) -> list[dict]:
        return self._request("GET", "/libraries") or []

    def ensure_library(self, name: str, kind: str, path: str, *, language: str = "") -> bool:
        """Cree une bibliotheque si aucune ne porte deja ce chemin. True si creee.

        Le doublon se juge sur le CHEMIN et non sur le nom : Silo refuse en 409
        « A library with this path already exists », quel que soit le nom
        propose. Se fier au nom ferait echouer un second passage.
        """
        if kind not in LIBRARY_TYPES:
            raise WiringError(
                f"{self.name}: type de bibliotheque inconnu: {kind!r}",
                f"types acceptes : {', '.join(LIBRARY_TYPES)}",
                "completez LIBRARY_TYPES apres verification contre une instance",
            )
        if any(path in (lib.get("paths") or []) for lib in self.libraries()):
            return False
        corps: dict[str, Any] = {"name": name, "type": kind, "paths": [path]}
        if language:
            # Silo range la langue par BIBLIOTHEQUE, pas globalement : c'est
            # `metadata_language`, verifie en le posant et en le relisant.
            corps["metadata_language"] = language
        self._request("POST", "/libraries", json=corps)
        return True

    def refresh_metadata(self, library_id: int) -> bool:
        """Declenche l'analyse d'une bibliotheque. Rend la main tout de suite."""
        try:
            self._request("POST", f"/libraries/{library_id}/refresh-metadata")
        except WiringError:
            return False
        return True
