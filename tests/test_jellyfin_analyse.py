"""Tests de l'analyse initiale des bibliotheques Jellyfin.

Signale a l'usage : « j'ai telecharge une serie avec Sonarr mais je ne la vois
pas dans Jellyfin ».

Le diagnostic a demande plusieurs etapes, et aucune ne pointait vers la vraie
cause : Sonarr avait bien importe les fichiers, ils etaient sur le disque, la
notification vers Jellyfin existait et son test repondait 200. Mais l'index de
Jellyfin etait VIDE — les bibliotheques sont creees avec `refreshLibrary=false`,
et rien ne les analysait ensuite. Un evenement « bibliotheque mise a jour » ne
construit pas un index qui n'existe pas encore.

Ces tests branchent un transport HTTP simule et laissent tourner le VRAI
`_request`. Une premiere version le remplacait par un faux qui rendait un objet
avec un `.status_code` : elle passait au vert alors que le code plantait des la
premiere installation reelle, parce que `_request` rend le CORPS decode — donc
`None` sur un 204 sans contenu. Un test qui remplace ce qu'il devrait exercer
ne teste plus que la croyance de qui l'a ecrit.
"""

from __future__ import annotations

import httpx
import pytest

from arrsenal.clients.jellyfin import JellyfinClient


def client_simule(handler) -> JellyfinClient:
    client = JellyfinClient("http://jellyfin:8096")
    client._http = httpx.Client(
        base_url="http://jellyfin:8096", transport=httpx.MockTransport(handler)
    )
    return client


@pytest.mark.parametrize(
    ("code", "corps"),
    [
        (204, b""),  # ce que Jellyfin 10.11.11 renvoie reellement
        (200, b"{}"),
        (202, b""),
    ],
)
def test_l_analyse_est_consideree_lancee(code, corps):
    appels: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        appels.append((request.method, request.url.path))
        return httpx.Response(code, content=corps)

    assert client_simule(handler).refresh_libraries() is True
    assert appels == [("POST", "/Library/Refresh")]


def test_un_204_sans_corps_ne_fait_pas_planter():
    """La regression exacte : `_request` rend `None`, et lire `.status_code`
    dessus faisait echouer TOUTE l'installation apres 40 etapes reussies."""
    client = client_simule(lambda _r: httpx.Response(204))

    assert client.refresh_libraries() is True


@pytest.mark.parametrize("code", [401, 403, 500])
def test_un_refus_est_rapporte_sans_interrompre(code):
    """Mieux vaut un avertissement qu'une installation avortee : tout le reste
    est cable, et une analyse se relance d'un clic depuis Jellyfin."""
    client = client_simule(lambda _r: httpx.Response(code, text="non"))

    assert client.refresh_libraries() is False


def test_une_panne_reseau_est_rapportee_sans_interrompre():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("injoignable", request=request)

    assert client_simule(handler).refresh_libraries() is False


def test_l_appel_rend_la_main_sans_attendre():
    """L'analyse d'une mediatheque peut durer des heures : la bloquer ici
    figerait l'installation."""
    appels: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        appels.append(request.url.path)
        return httpx.Response(204)

    client_simule(handler).refresh_libraries()

    # Un seul appel, aucun sondage d'avancement.
    assert appels == ["/Library/Refresh"]
