"""Tests du client qui. Aucun reseau : les reponses sont simulees.

Les formes reproduites ici viennent d'une instance v1.27.0 reelle.
"""

from __future__ import annotations

import pytest

from arrsenal.clients.base import WiringError
from arrsenal.clients.qui import QuiClient


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else []
        self.text = text

    def json(self):
        return self._payload


class FakeClient(QuiClient):
    """Remplace la couche HTTP par un journal d'appels et des reponses fixes."""

    def __init__(self, responses):
        super().__init__("http://qui:7476")
        self._responses = responses
        self.calls: list[tuple[str, str, dict]] = []

    def _request(self, method, path, **kw):
        self.calls.append((method, path, kw.get("json") or {}))
        value = self._responses.get(f"{method} {path}", FakeResponse(200, []))
        return value(self) if callable(value) else value


# ------------------------------------------------------------------- accueil


def test_428_signifie_installation_a_terminer():
    """Tout repond 428 tant qu'aucun compte n'existe, y compris la connexion.

    Un service qui repond 428 EST demarre : le confondre avec une panne ferait
    attendre le cablage jusqu'au delai maximum, pour rien.
    """
    client = FakeClient({"GET /api/auth/me": FakeResponse(428, text="setup required")})
    client.wait_ready(timeout=5)  # ne doit pas lever


def test_setup_rejoue_ne_casse_pas_le_cablage():
    """`POST /api/auth/setup` repond 400 « Setup already completed » une fois joue.

    C'est ce qui rend l'etape rejouable : `arrsenal wire` doit pouvoir repasser.
    """
    created = FakeClient({"POST /api/auth/setup": FakeResponse(201)})
    assert created.setup("arrsenal", "x") is True

    again = FakeClient(
        {"POST /api/auth/setup": FakeResponse(400, text='{"error":"Setup already completed"}')}
    )
    assert again.setup("arrsenal", "x") is False


def test_un_echec_de_setup_inattendu_est_signale():
    client = FakeClient({"POST /api/auth/setup": FakeResponse(500, text="boom")})
    with pytest.raises(WiringError):
        client.setup("arrsenal", "x")


def test_un_mot_de_passe_refuse_est_dit_clairement():
    client = FakeClient({"POST /api/auth/login": FakeResponse(401, text="unauthorized")})
    with pytest.raises(WiringError) as exc:
        client.login("arrsenal", "faux")
    assert "connexion refusee" in str(exc.value)


# ------------------------------------------------------------------ instances


def test_l_instance_est_declaree_avec_son_port():
    """Passer host et port separement est accepte, mais le port est PERDU.

    qui enregistre alors `http://qbittorrent`, repond 201, et ne se connecte
    jamais. Verifie sur une instance reelle : sans port `connected=False`, avec
    port `connected=True`.
    """
    client = FakeClient({"POST /api/instances": FakeResponse(201, {"id": 1})})
    assert client.ensure_instance(
        name="qBittorrent", host="http://qbittorrent:8080", username="u", password="p"
    )

    posted = [c for c in client.calls if c[0] == "POST"][-1]
    assert posted[2]["host"] == "http://qbittorrent:8080"
    assert "port" not in posted[2]


def test_une_instance_deja_declaree_n_est_pas_recreee():
    """qui n'interdit PAS les doublons : declarer deux fois donne deux entrees.

    Sans cette verification, chaque `arrsenal wire` ajouterait une instance.
    """
    client = FakeClient(
        {"GET /api/instances": FakeResponse(200, [{"host": "http://qbittorrent:8080"}])}
    )
    assert client.ensure_instance(
        name="qBittorrent", host="http://qbittorrent:8080", username="u", password="p"
    ) is False
    assert not [c for c in client.calls if c[0] == "POST"]


def test_la_barre_finale_ne_trompe_pas_la_comparaison():
    client = FakeClient(
        {"GET /api/instances": FakeResponse(200, [{"host": "http://qbittorrent:8080/"}])}
    )
    assert client.ensure_instance(
        name="qBittorrent", host="http://qbittorrent:8080", username="u", password="p"
    ) is False


def test_un_refus_de_creation_est_signale():
    client = FakeClient({"POST /api/instances": FakeResponse(422, text="bad host")})
    with pytest.raises(WiringError):
        client.ensure_instance(name="q", host="http://x:1", username="u", password="p")


# --------------------------------------------------------------- verification


def test_la_connexion_est_confirmee_par_qui_lui_meme():
    """Un 201 ne prouve rien : c'est `connected` qui fait foi."""
    client = FakeClient(
        {
            "GET /api/instances": FakeResponse(
                200,
                [{"host": "http://qbittorrent:8080", "connected": True,
                  "connectionStatus": "connected"}],
            )
        }
    )
    linked, detail = client.connected("http://qbittorrent:8080", timeout=5)

    assert linked and "connected" in detail


def test_une_instance_injoignable_est_rapportee():
    client = FakeClient(
        {
            "GET /api/instances": FakeResponse(
                200,
                [{"host": "http://qbittorrent:8080", "connected": False,
                  "connectionStatus": "error"}],
            )
        }
    )
    linked, detail = client.connected("http://qbittorrent:8080", timeout=3)

    assert not linked and "error" in detail


def test_aucune_instance_a_cette_adresse():
    client = FakeClient({"GET /api/instances": FakeResponse(200, [])})
    linked, detail = client.connected("http://qbittorrent:8080", timeout=3)

    assert not linked and "aucune instance" in detail


# -------------------------------------------------------------------- cablage


def test_l_etape_est_prevue_quand_qui_et_qbittorrent_sont_installes(tmp_path):
    from arrsenal.orchestrator import build_config
    from arrsenal.wiring import Wirer

    cfg = build_config(
        services=["qui", "qbittorrent"],
        config_root=str(tmp_path / "c"),
        data_root=str(tmp_path / "d"),
    )
    names = [s.name for s in Wirer(cfg).build_plan()]

    assert "qui/qbittorrent" in names


def test_qui_recoit_bien_des_identifiants(tmp_path):
    """Sans compte genere, l'etape ne pourrait pas creer le premier utilisateur."""
    from arrsenal.orchestrator import build_config

    cfg = build_config(
        services=["qui"], config_root=str(tmp_path / "c"), data_root=str(tmp_path / "d")
    )
    inst = cfg.services["qui"]

    assert inst.username == "arrsenal"
    assert inst.password
