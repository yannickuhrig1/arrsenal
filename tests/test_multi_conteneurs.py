"""Un service peut avoir plusieurs conteneurs et plusieurs ports.

Deuxieme socle necessaire a Silo, qui est une pile de quatre conteneurs —
PostgreSQL, Redis, Meilisearch et lui-meme — et publie TROIS ports : son
interface sur 8080, une API compatible Jellyfin sur 8096, une API compatible
Audiobookshelf sur 13378.

Le choix de conception : un conteneur d'appoint est un SERVICE DU CATALOGUE
marque `internal`, pas une structure a part. Tout ce qui existe deja s'applique
alors — resolution des prerequis, generation du compose, allocation des ports,
dossiers de configuration — au lieu d'etre reecrit. Il suffit qu'il ne soit
jamais PROPOSE : une base de donnees n'est pas un service qu'on coche.

Debloque aussi Jellystat, qui exige un PostgreSQL, et Tracearr.
"""

from __future__ import annotations

import pytest

from arrsenal import catalog, compose, dashboard, orchestrator
from arrsenal.models import Category, ServiceSpec


@pytest.fixture
def catalogue_etendu(monkeypatch):
    """Un service a trois ports, appuye sur un conteneur interne."""
    appoint = ServiceSpec(
        id="essai-db",
        display_name="Essai PostgreSQL",
        category=Category.MEDIA,
        image="pgvector/pgvector:pg18",
        internal_port=0,
        default_host_port=0,
        config_dir="essai-db",
        internal=True,
    )
    principal = ServiceSpec(
        id="essai",
        display_name="Essai",
        category=Category.MEDIA,
        image="exemple/essai:1.0",
        internal_port=8080,
        default_host_port=8090,
        config_dir="essai",
        extra_ports=(("API Jellyfin", 8096), ("API Audiobookshelf", 13378)),
        requires=("essai-db",),
        depends_on_healthy=("essai-db",),
    )
    etendu = {**catalog.CATALOG, "essai-db": appoint, "essai": principal}
    monkeypatch.setattr(catalog, "CATALOG", etendu)
    monkeypatch.setattr(catalog, "STARTUP_ORDER", (*catalog.STARTUP_ORDER, "essai-db", "essai"))
    return etendu


def _cfg(services):
    return orchestrator.build_config(services=services, config_root="/c", data_root="/d")


# -------------------------------------------------- le conteneur d'appoint


def test_l_appoint_est_tire_comme_prerequis(catalogue_etendu):
    cfg = _cfg(["essai"])

    assert set(cfg.services) == {"essai", "essai-db"}


def test_l_appoint_n_est_jamais_propose_au_choix(catalogue_etendu):
    """Une base de donnees a cote de Sonarr dans la liste des services n'aurait
    aucun sens, et l'installer seule non plus."""
    choisissables = {spec.id for spec in catalog.selectable()}

    assert "essai" in choisissables
    assert "essai-db" not in choisissables


def test_l_appoint_n_apparait_pas_dans_ce_qu_on_peut_ajouter(catalogue_etendu):
    cfg = _cfg(["sonarr"])

    ajoutables = orchestrator.installable(cfg)

    assert "essai" in ajoutables
    assert "essai-db" not in ajoutables


def test_l_appoint_n_a_pas_de_bouton_sur_la_page(catalogue_etendu):
    page = dashboard.render(_cfg(["sonarr"]), live=True)

    assert 'data-add="essai"' in page
    assert 'data-add="essai-db"' not in page


def test_l_appoint_existe_bien_dans_le_compose(catalogue_etendu):
    """Invisible au choix, mais parfaitement present a l'execution."""
    services = compose.build_compose(_cfg(["essai"]))["services"]

    assert "essai-db" in services
    assert services["essai-db"]["image"] == "pgvector/pgvector:pg18"


# ------------------------------------------------------- plusieurs ports


def test_les_trois_ports_sont_publies(catalogue_etendu):
    bloc = compose.build_compose(_cfg(["essai"]))["services"]["essai"]

    assert bloc["ports"] == ["8090:8080", "8096:8096", "13378:13378"]


def test_le_port_hote_peut_etre_decale_sans_toucher_au_conteneur(catalogue_etendu):
    """C'est la reponse au conflit avec Jellyfin : Silo garde 8096 en INTERNE,
    seul le cote hote bouge. Son propre compose le prevoit explicitement —
    « PORT and JF_PORT in .env are host-side published-port overrides »."""
    cfg = _cfg(["essai"])
    cfg.services["essai"].extra_ports[8096] = 8097

    bloc = compose.build_compose(cfg)["services"]["essai"]

    assert "8097:8096" in bloc["ports"]
    assert "8096:8096" not in bloc["ports"]


def test_un_service_ordinaire_garde_un_seul_port(catalogue_etendu):
    """L'ajout ne doit rien changer pour les onze services existants."""
    bloc = compose.build_compose(_cfg(["sonarr"]))["services"]["sonarr"]

    assert len(bloc["ports"]) == 1


# --------------------------------------------------- attendre un service SAIN


def test_l_attente_porte_sur_la_sante_pas_sur_le_demarrage(catalogue_etendu):
    """Silo refuse de demarrer si sa base n'a pas fini son initialisation, et un
    `depends_on` nu ne l'attend pas."""
    bloc = compose.build_compose(_cfg(["essai"]))["services"]["essai"]

    assert bloc["depends_on"] == {"essai-db": {"condition": "service_healthy"}}


def test_une_dependance_absente_n_est_pas_declaree(catalogue_etendu):
    """Un `depends_on` vers un service non installe fait echouer `compose up`
    pour la pile entiere."""
    cfg = _cfg(["essai"])
    del cfg.services["essai-db"]

    bloc = compose.build_compose(cfg)["services"]["essai"]

    assert bloc["depends_on"] == {}


# ------------------------------------------------------------- preflight


def test_tous_les_ports_publies_sont_controles(catalogue_etendu):
    """Un seul conflit fait echouer `compose up` pour la pile entiere : les
    controler tous ou n'en controler aucun."""
    cfg = _cfg(["essai"])

    controles = {c.name for c in orchestrator.preflight(cfg)}

    assert any("8090" in nom for nom in controles)
    assert any("8096" in nom for nom in controles)
    assert any("13378" in nom for nom in controles)


def test_un_port_a_zero_n_est_pas_controle(catalogue_etendu):
    """Recyclarr n'expose rien : « port 0 : libre » n'apprend rien et fait
    douter du reste du tableau."""
    controles = {c.name for c in orchestrator.preflight(_cfg(["recyclarr"]))}

    assert not any("port 0" in nom for nom in controles)
