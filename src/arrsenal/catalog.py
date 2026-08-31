"""Catalogue des services de la Phase 1.

Regle du projet : les tags d'image sont EPINGLES. Un tag flottant `latest` rend le
cablage non reproductible et fait exploser l'outil a chaque release amont.
La version testee est consignee dans docs/COMPATIBILITY.md.
"""

from __future__ import annotations

from .models import Category, ServiceSpec

# Tags epingles. A remonter via une PR dediee + un passage de la CI d'integration.
_TAGS = {
    "sonarr": "4.0.19",
    "radarr": "6.3.0",
    "prowlarr": "2.5.2",
    "transmission": "4.1.3",
    "jellyfin": "10.11.11",
    "flood": "4.16.1",
}

CATALOG: dict[str, ServiceSpec] = {
    "prowlarr": ServiceSpec(
        id="prowlarr",
        display_name="Prowlarr",
        category=Category.ARR,
        image=f"lscr.io/linuxserver/prowlarr:{_TAGS['prowlarr']}",
        internal_port=9696,
        default_host_port=9696,
        config_dir="prowlarr",
        api_family="arr",
        api_version="v1",
        notes="Pivot du cablage : pousse les indexeurs vers Sonarr/Radarr.",
    ),
    "sonarr": ServiceSpec(
        id="sonarr",
        display_name="Sonarr",
        category=Category.ARR,
        image=f"lscr.io/linuxserver/sonarr:{_TAGS['sonarr']}",
        internal_port=8989,
        default_host_port=8989,
        config_dir="sonarr",
        api_family="arr",
        api_version="v3",
        notes="Series TV.",
    ),
    "radarr": ServiceSpec(
        id="radarr",
        display_name="Radarr",
        category=Category.ARR,
        image=f"lscr.io/linuxserver/radarr:{_TAGS['radarr']}",
        internal_port=7878,
        default_host_port=7878,
        config_dir="radarr",
        api_family="arr",
        api_version="v3",
        notes="Films.",
    ),
    "transmission": ServiceSpec(
        id="transmission",
        display_name="Transmission",
        category=Category.DOWNLOAD,
        image=f"lscr.io/linuxserver/transmission:{_TAGS['transmission']}",
        internal_port=9091,
        default_host_port=9091,
        config_dir="transmission",
        api_family="transmission",
        notes="Client torrent par defaut (PROMPT.md sec. 11).",
    ),
    "jellyfin": ServiceSpec(
        id="jellyfin",
        display_name="Jellyfin",
        category=Category.MEDIA,
        image=f"lscr.io/linuxserver/jellyfin:{_TAGS['jellyfin']}",
        internal_port=8096,
        default_host_port=8096,
        config_dir="jellyfin",
        api_family="jellyfin",
        notes="Serveur media. Assistant de demarrage automatisable par API.",
    ),
    "flood": ServiceSpec(
        id="flood",
        display_name="Flood",
        category=Category.UI,
        image=f"jesec/flood:{_TAGS['flood']}",
        internal_port=3000,
        default_host_port=3001,
        config_dir="flood",
        requires=("transmission",),
        api_family=None,
        notes=(
            "UI web pour Transmission. N'est PAS un client. Les *arr parlent au RPC "
            "Transmission, jamais a Flood : zero impact sur la matrice de cablage."
        ),
    ),
}

#: Ordre de demarrage et de cablage. Prowlarr en dernier : il a besoin que
#: Sonarr/Radarr repondent deja pour enregistrer ses Applications.
STARTUP_ORDER = ("transmission", "sonarr", "radarr", "prowlarr", "jellyfin", "flood")

#: Selection par defaut du profil "Debutant tout-en-un" en Phase 1.
DEFAULT_SELECTION = ("prowlarr", "sonarr", "radarr", "transmission", "jellyfin")


def get(service_id: str) -> ServiceSpec:
    try:
        return CATALOG[service_id]
    except KeyError:
        known = ", ".join(sorted(CATALOG))
        raise KeyError(f"service inconnu: {service_id!r}. Connus: {known}") from None


def resolve_dependencies(selection: list[str]) -> list[str]:
    """Ajoute les prerequis manquants et renvoie la selection dans l'ordre de demarrage."""
    wanted = set(selection)
    changed = True
    while changed:
        changed = False
        for sid in list(wanted):
            for dep in get(sid).requires:
                if dep not in wanted:
                    wanted.add(dep)
                    changed = True
    return [sid for sid in STARTUP_ORDER if sid in wanted]
