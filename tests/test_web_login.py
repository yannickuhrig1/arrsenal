"""Tests de l'acces a l'interface web des *arr.

Le pre-semis ecrit `<Username>` et `<Password>` dans config.xml. Sonarr 4.0.19 et
Radarr 6.3.0 les consomment au premier demarrage et creent le compte.
**Prowlarr 2.5.2 les EFFACE sans creer personne** : sa page de connexion n'offre
aucune creation de compte, son interface devient donc definitivement inaccessible.

Le cablage, lui, continuait de fonctionner par cle API : la panne ne se voyait
nulle part, sauf en essayant de se connecter. Ces tests existent pour qu'elle ne
puisse plus revenir en silence.
"""

from __future__ import annotations

import httpx
import pytest

from arrsenal.clients.arr import ArrClient
from arrsenal.orchestrator import build_config
from arrsenal.wiring import Wirer


class FakeHttp:
    """Double de la couche HTTP : ne repond qu'au formulaire de connexion."""

    def __init__(self, responses):
        self._responses = responses
        self.posts: list[tuple[str, dict]] = []

    def post(self, path, data=None, **kw):
        self.posts.append((path, data or {}))
        value = self._responses.get(path)
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        pass


def _client(responses) -> ArrClient:
    client = ArrClient("http://sonarr:8989", "cle", name="sonarr")
    client._http = FakeHttp(responses)
    return client


def _redirect(location: str, status: int = 302):
    return httpx.Response(status, headers={"location": location})


# ------------------------------------------------------- lecture de la reponse


def test_une_redirection_vers_la_racine_vaut_succes():
    client = _client({"/login": _redirect("/")})
    assert client.web_login_works("arrsenal", "secret") is True


def test_loginfailed_dans_la_redirection_vaut_echec():
    """C'est la reponse exacte de Prowlarr quand aucun compte n'existe."""
    client = _client({"/login": _redirect("/login?returnUrl=&loginFailed=true")})
    assert client.web_login_works("arrsenal", "secret") is False


def test_la_casse_de_loginfailed_ne_change_rien():
    client = _client({"/login": _redirect("/login?LoginFailed=True")})
    assert client.web_login_works("arrsenal", "secret") is False


def test_une_page_rendue_sans_redirection_vaut_echec():
    """Un succes redirige toujours. Un 200 est la page de connexion reaffichee."""
    client = _client({"/login": httpx.Response(200, text="<html>Login</html>")})
    assert client.web_login_works("arrsenal", "secret") is False


def test_un_service_injoignable_ne_leve_pas():
    """La verification ne doit pas interrompre le cablage."""
    client = _client({"/login": httpx.ConnectError("refuse")})
    assert client.web_login_works("arrsenal", "secret") is False


def test_sans_identifiants_il_n_y_a_rien_a_verifier():
    client = _client({})
    assert client.web_login_works("", "secret") is False
    assert client.web_login_works("arrsenal", "") is False
    assert client._http.posts == [], "aucun appel ne devait partir"


def test_le_formulaire_est_poste_comme_un_navigateur():
    client = _client({"/login": _redirect("/")})
    client.web_login_works("arrsenal", "secret")

    path, data = client._http.posts[0]
    assert path == "/login"
    assert data["username"] == "arrsenal"
    assert data["password"] == "secret"


# ------------------------------------------------------------- reparation


class RecordingClient(ArrClient):
    """Enregistre les appels d'API et simule la reparation du compte."""

    def __init__(self, *, works_after_repair: bool):
        super().__init__("http://prowlarr:9696", "cle", api_version="v1", name="prowlarr")
        self.works_after_repair = works_after_repair
        self.repaired = False
        self.puts: list[tuple[str, dict]] = []

    def get(self, resource):
        assert resource == "config/host"
        return {"id": 1, "bindAddress": "*", "port": 9696, "username": "", "password": ""}

    def put(self, resource, payload):
        self.puts.append((resource, payload))
        self.repaired = True
        return payload

    def web_login_works(self, username, password):
        return self.repaired and self.works_after_repair

    def close(self):
        pass


def _wirer(tmp_path, client):
    cfg = build_config(
        services=["prowlarr"], config_root=str(tmp_path / "c"), data_root=str(tmp_path / "d")
    )
    wirer = Wirer(cfg)
    wirer._arr_cache["prowlarr"] = client
    return wirer, cfg


def test_le_compte_manquant_est_cree_et_reverifie(tmp_path):
    client = RecordingClient(works_after_repair=True)
    wirer, cfg = _wirer(tmp_path, client)

    result = wirer.step_web_login("prowlarr")

    assert result.ok and result.created
    assert result.detail == "compte cree"
    resource, payload = client.puts[0]
    assert resource == "config/host/1"
    inst = cfg.services["prowlarr"]
    assert payload["username"] == inst.username
    assert payload["password"] == inst.password
    assert payload["passwordConfirmation"] == inst.password
    # Le reste de la configuration hote est renvoye tel quel.
    assert payload["port"] == 9696 and payload["bindAddress"] == "*"


def test_un_compte_qui_marche_n_est_pas_touche(tmp_path):
    """Reecrire un mot de passe deja bon serait une modification pour rien."""
    client = RecordingClient(works_after_repair=True)
    client.repaired = True  # la connexion fonctionne des le depart
    wirer, _cfg = _wirer(tmp_path, client)

    result = wirer.step_web_login("prowlarr")

    assert result.ok and not result.created
    assert result.detail == "connexion verifiee"
    assert client.puts == [], "aucune ecriture ne devait avoir lieu"


def test_une_reparation_sans_effet_est_signalee(tmp_path):
    client = RecordingClient(works_after_repair=False)
    wirer, _cfg = _wirer(tmp_path, client)

    result = wirer.step_web_login("prowlarr")

    assert not result.ok
    assert any("n'ouvrent pas l'interface" in w for w in result.warnings)
    assert any("Settings > General" in w for w in result.warnings)


# ----------------------------------------------------------------- le graphe


@pytest.mark.parametrize("service", ["prowlarr", "sonarr", "radarr", "lidarr"])
def test_chaque_arr_voit_son_acces_verifie(tmp_path, service):
    """Prowlarr compris : c'est lui qui n'ouvrait pas."""
    cfg = build_config(
        services=[service], config_root=str(tmp_path / "c"), data_root=str(tmp_path / "d")
    )
    names = [s.name for s in Wirer(cfg).build_plan()]

    assert f"{service}/acces-web" in names


def test_la_verification_precede_le_reste_du_cablage(tmp_path):
    """Inutile de poser des liens dans une application ou personne ne pourra entrer."""
    cfg = build_config(
        services=["prowlarr", "sonarr"],
        config_root=str(tmp_path / "c"),
        data_root=str(tmp_path / "d"),
    )
    names = [s.name for s in Wirer(cfg).build_plan()]

    assert names.index("sonarr/acces-web") < names.index("sonarr/rootfolder")
