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
    "qbittorrent": "5.2.3",
    "lidarr": "3.1.0",
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
        notes="Pivot du cablage : alimente les autres en indexeurs.",
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
        notes="Client torrent par defaut.",
    ),
    "lidarr": ServiceSpec(
        id="lidarr",
        display_name="Lidarr",
        category=Category.ARR,
        image=f"lscr.io/linuxserver/lidarr:{_TAGS['lidarr']}",
        internal_port=8686,
        default_host_port=8686,
        config_dir="lidarr",
        api_family="arr",
        api_version="v1",
        notes="Musique. Son API est en v1, pas en v3.",
    ),
    "qbittorrent": ServiceSpec(
        id="qbittorrent",
        display_name="qBittorrent",
        category=Category.DOWNLOAD,
        image=f"lscr.io/linuxserver/qbittorrent:{_TAGS['qbittorrent']}",
        internal_port=8080,
        default_host_port=8080,
        config_dir="qbittorrent",
        api_family="qbittorrent",
        notes="Categories natives avec chemin dedie.",
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
        notes="Serveur media. Bibliotheques creees pour vous.",
    ),
    "flood": ServiceSpec(
        id="flood",
        display_name="Flood",
        category=Category.UI,
        image=f"jesec/flood:{_TAGS['flood']}",
        internal_port=3000,
        default_host_port=3001,
        config_dir="flood",
        #: Flood pilote qBittorrent OU Transmission. `requires` ne sait exprimer
        #: qu'un ET : l'alternative est verifiee par `missing_requirements`.
        requires=(),
        requires_one_of=("qbittorrent", "transmission"),
        api_family=None,
        notes="UI web pour qBittorrent ou Transmission. N'est pas un client.",
    ),
}

#: Ordre de demarrage et de cablage. Prowlarr en dernier : il a besoin que
#: Sonarr/Radarr repondent deja pour enregistrer ses Applications.
STARTUP_ORDER = (
    "transmission",
    "qbittorrent",
    "sonarr",
    "radarr",
    "lidarr",
    "prowlarr",
    "jellyfin",
    "flood",
)

#: Applications *arr pilotables par Prowlarr et rattachables a un client de download.
MANAGED_ARRS = ("sonarr", "radarr", "lidarr")

#: Services jouant le role de client de telechargement.
DOWNLOAD_CLIENTS = ("transmission", "qbittorrent")

#: Selection par defaut du profil "Debutant tout-en-un" en Phase 1.
DEFAULT_SELECTION = ("prowlarr", "sonarr", "radarr", "transmission", "jellyfin")


def get(service_id: str) -> ServiceSpec:
    try:
        return CATALOG[service_id]
    except KeyError:
        known = ", ".join(sorted(CATALOG))
        raise KeyError(f"service inconnu: {service_id!r}. Connus: {known}") from None


def resolve_dependencies(selection: list[str]) -> list[str]:
    """Ajoute les prerequis manquants et renvoie la selection dans l'ordre de demarrage.

    Pour un service qui accepte plusieurs backends (`requires_one_of`), on n'ajoute
    le premier de la liste que si AUCUN n'est deja selectionne : cocher Flood a cote
    de qBittorrent ne doit pas tirer Transmission en plus.
    """
    wanted = set(selection)
    changed = True
    while changed:
        changed = False
        for sid in list(wanted):
            spec = get(sid)
            for dep in spec.requires:
                if dep not in wanted:
                    wanted.add(dep)
                    changed = True
            if spec.requires_one_of and not (set(spec.requires_one_of) & wanted):
                wanted.add(spec.requires_one_of[0])
                changed = True
    return [sid for sid in STARTUP_ORDER if sid in wanted]
