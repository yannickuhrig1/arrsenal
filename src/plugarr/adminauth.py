"""Authentification de la page d'administration.

Cette page arrete des conteneurs, affiche des mots de passe et en change. Le
jeton tire au hasard a chaque demarrage convient tant qu'on lance `plugarr
serve` a la main : il s'affiche dans le terminal, juste au-dessus de l'URL.

Il ne convient PLUS des que la console tourne en permanence. Personne ne va lire
un journal de conteneur pour retrouver un jeton a chaque redemarrage, et un
jeton qui vit dans l'URL finit dans l'historique du navigateur.

D'ou un mot de passe, stocke **hache** dans `stack.yml` — jamais en clair, parce
que ce fichier est celui qu'on ouvre pour retrouver un port. PBKDF2-HMAC-SHA256,
600 000 iterations, sel de 16 octets : le parametre recommande par l'OWASP pour
cet algorithme, et c'est la seule raison de ce chiffre.

Le jeton reste accepte en parallele. Un utilisateur qui lance la console depuis
son terminal ne doit pas avoir a inventer un mot de passe pour regarder l'etat
de ses services.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

ALGO = "pbkdf2-sha256"
ITERATIONS = 600_000
SALT_BYTES = 16

#: Duree de vie d'une session. Assez longue pour ne pas gener une soiree de
#: reglages, assez courte pour qu'un navigateur oublie ne reste pas ouvert.
SESSION_SECONDS = 12 * 3600

#: Au-dela, plus aucune tentative n'est acceptee pendant `LOCKOUT_SECONDS`. La
#: console est jointe par le reseau local des qu'on la sort de 127.0.0.1 : sans
#: cela, un mot de passe se devine en quelques heures.
MAX_ATTEMPTS = 10
LOCKOUT_SECONDS = 300


def hash_password(password: str) -> str:
    """Empreinte stockable. Format : `pbkdf2-sha256$<iters>$<sel>$<empreinte>`."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return "$".join(
        [ALGO, str(ITERATIONS), base64.b64encode(salt).decode(), base64.b64encode(digest).decode()]
    )


def verify_password(password: str, stored: str) -> bool:
    """Le mot de passe correspond-il a l'empreinte ?

    Toute empreinte mal formee renvoie False plutot que de lever : une
    `stack.yml` modifiee a la main ne doit pas empecher la console de repondre,
    elle doit empecher d'entrer.
    """
    try:
        algo, iterations, salt, digest = stored.split("$")
        if algo != ALGO:
            return False
        candidat = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    # compare_digest : une comparaison naive fuite l'empreinte octet par octet.
    return hmac.compare_digest(candidat, base64.b64decode(digest))


class Sessions:
    """Sessions en memoire, avec limitation des tentatives.

    En memoire et non sur disque, volontairement : redemarrer la console doit
    deconnecter tout le monde. C'est le comportement qu'on attend d'un outil
    d'administration, et cela evite d'avoir a expirer des jetons persistes.
    """

    def __init__(self, *, now=time.monotonic) -> None:
        self._now = now
        self._sessions: dict[str, float] = {}
        self._failures: list[float] = []

    # -- tentatives ----------------------------------------------------------

    @property
    def locked_out(self) -> bool:
        maintenant = self._now()
        self._failures = [t for t in self._failures if maintenant - t < LOCKOUT_SECONDS]
        return len(self._failures) >= MAX_ATTEMPTS

    def record_failure(self) -> None:
        self._failures.append(self._now())

    def clear_failures(self) -> None:
        self._failures.clear()

    def retry_in(self) -> int:
        """Secondes restantes avant une nouvelle tentative. 0 si aucune attente."""
        if not self.locked_out:
            return 0
        return max(0, int(LOCKOUT_SECONDS - (self._now() - min(self._failures))))

    # -- sessions ------------------------------------------------------------

    def open(self) -> str:
        jeton = secrets.token_urlsafe(32)
        self._sessions[jeton] = self._now() + SESSION_SECONDS
        return jeton

    def valid(self, jeton: str) -> bool:
        if not jeton:
            return False
        expiration = self._sessions.get(jeton)
        if expiration is None:
            return False
        if self._now() > expiration:
            del self._sessions[jeton]
            return False
        return True

    def close(self, jeton: str) -> None:
        self._sessions.pop(jeton, None)
