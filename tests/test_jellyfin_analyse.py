"""Tests de l'analyse initiale des bibliotheques Jellyfin.

Signale a l'usage : « j'ai telecharge une serie avec Sonarr mais je ne la vois
pas dans Jellyfin ».

Le diagnostic a demande plusieurs etapes, et aucune ne pointait vers la vraie
cause : Sonarr avait bien importe les fichiers, ils etaient sur le disque, la
notification vers Jellyfin existait et son test repondait 200. Mais l'index de
Jellyfin etait VIDE — les bibliotheques sont creees avec `refreshLibrary=false`,
et rien ne les analysait ensuite.

Un evenement « bibliotheque mise a jour » ne construit pas un index qui n'existe
pas encore.
"""

from __future__ import annotations

import httpx
import pytest

from arrsenal.clients.jellyfin import JellyfinClient


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = ""

    def json(self):
        return self._payload


class FakeJellyfin(JellyfinClient):
    """Journalise les appels au lieu de les emettre."""

    def __init__(self, responses=None):
        super().__init__("http://jellyfin:8096")
        self._responses = responses or {}
        self.calls: list[tuple[str, str]] = []

    def _request(self, method, path, **kw):
        self.calls.append((method, path))
        return self._responses.get(f"{method} {path}", FakeResponse(204))


@pytest.mark.parametrize("code", [200, 202, 204])
def test_l_analyse_est_consideree_lancee(code):
    client = FakeJellyfin({"POST /Library/Refresh": FakeResponse(code)})

    assert client.refresh_libraries() is True
    assert ("POST", "/Library/Refresh") in client.calls


def test_un_refus_est_rapporte():
    """Mieux vaut un avertissement qu'une bibliotheque muette."""
    client = FakeJellyfin({"POST /Library/Refresh": FakeResponse(403)})

    assert client.refresh_libraries() is False


def test_l_appel_rend_la_main_sans_attendre():
    """L'analyse d'une mediatheque peut durer des heures : la bloquer ici
    figerait l'installation."""
    client = FakeJellyfin({"POST /Library/Refresh": FakeResponse(204)})

    client.refresh_libraries()

    # Un seul appel, aucun sondage d'avancement.
    assert client.calls == [("POST", "/Library/Refresh")]


def test_le_client_reel_vise_le_bon_chemin():
    """Le chemin est celui de l'API Jellyfin 10.11.11, pas une invention."""
    appels = []

    class Espion(JellyfinClient):
        def _request(self, method, path, **kw):
            appels.append((method, path))
            return httpx.Response(204)

    Espion("http://jellyfin:8096").refresh_libraries()

    assert appels == [("POST", "/Library/Refresh")]
