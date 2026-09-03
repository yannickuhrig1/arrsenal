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
    "autobrr": "v1.85.0",
    "qui": "v1.28.0",
    "recyclarr": "8.7.1",
}

#: Silo s'epingle autrement : il ne publie pas de version au sens habituel, mais
#: un numero de construction monotone. `build-522` porte l'etiquette
#: `org.opencontainers.image.version` de l'image, relevee dans l'image elle-meme.
#:
#: Le DIGEST accompagne le tag. Docker retient le digest, donc le contenu est
#: fige ; le tag reste lisible et comparable pour la detection de mises a jour.
#: C'est la seule forme qui donne les deux a la fois.
#:
#: Ses deux appoints sont epingles de la meme facon : `redis:alpine` et
#: `pgvector:pg18` sont des tags FLOTTANTS, qui designent un nom et non un
#: contenu. Sans digest, deux installations du meme jour peuvent differer.
_SILO = {
    "silo": (
        "ghcr.io/silo-server/silo-server:build-522"
        "@sha256:d3cb4ad9df66c727506c562ea3a9263b8938352d66ac5c247425d654b585b5df"
    ),
    "postgres": (
        "pgvector/pgvector:pg18"
        "@sha256:2ba9ca5f2e7daa0f0e7723cba1ee9167bab54efd3640516a44ac1a928dd67e7a"
    ),
    "redis": (
        "redis:alpine"
        "@sha256:becdda6c7f4b3fb42e42fd7f120bbf5c54c4caaaf16f26da24e4563d2c1f0576"
    ),
}

#: Repris tel quel du README de Silo. Ce n'est pas notre jugement sur le projet,
#: c'est ce que le projet dit de lui-meme.
_SILO_AVERTISSEMENT = (
    "Silo est en pre-version : son API, sa configuration et ses migrations de "
    "base peuvent changer avant sa premiere version stable. Sauvegardez avant "
    "toute mise a jour."
)

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
    "silo-postgres": ServiceSpec(
        id="silo-postgres",
        display_name="PostgreSQL (Silo)",
        category=Category.MEDIA,
        image=_SILO["postgres"],
        # Aucun port publie : la base ne sert qu'a Silo, sur le reseau interne.
        # L'exposer sur l'hote serait une surface d'attaque pour rien.
        internal_port=0,
        default_host_port=0,
        # Aucun dossier sur l'hote : ses donnees vivent dans un VOLUME Docker.
        # Un montage vers le disque Windows rendait ses migrations 590 fois plus
        # lentes — 2935 s contre 5 s, mesure. Voir compose.PG_VOLUME.
        config_dir=None,
        internal=True,
        notes="Base de donnees de Silo. Installee avec lui, jamais seule.",
    ),
    "silo-redis": ServiceSpec(
        id="silo-redis",
        display_name="Redis (Silo)",
        category=Category.MEDIA,
        image=_SILO["redis"],
        internal_port=0,
        default_host_port=0,
        config_dir="silo/redis",
        internal=True,
        notes="Cache de Silo. Installe avec lui, jamais seul.",
    ),
    "silo": ServiceSpec(
        id="silo",
        display_name="Silo",
        category=Category.MEDIA,
        image=_SILO["silo"],
        internal_port=8080,
        default_host_port=8090,
        config_dir="silo",
        # Trois portes sur le meme conteneur. Le libelle compte : « API
        # Jellyfin » dit a quoi ca sert, « port 8096 » non.
        extra_ports=(("API Jellyfin", 8096), ("API Audiobookshelf", 13378)),
        requires=("silo-postgres", "silo-redis"),
        # SAINS, pas seulement demarres : Silo refuse de demarrer si sa base n'a
        # pas fini son initialisation.
        depends_on_healthy=("silo-postgres", "silo-redis"),
        api_family="silo",
        needs_secret_key=True,
        experimental=_SILO_AVERTISSEMENT,
        notes="Serveur media, API compatible Jellyfin. Meilisearch est optionnel "
        "et n'est pas installe.",
    ),
    "autobrr": ServiceSpec(
        id="autobrr",
        display_name="autobrr",
        category=Category.ARR,
        image=f"ghcr.io/autobrr/autobrr:{_TAGS['autobrr']}",
        internal_port=7474,
        default_host_port=7474,
        config_dir="autobrr",
        requires_one_of=("sonarr", "radarr", "lidarr"),
        api_family="autobrr",
        notes="Ecoute les annonces IRC. Plus rapide que le sondage RSS.",
    ),
    "qui": ServiceSpec(
        id="qui",
        display_name="qui",
        category=Category.UI,
        image=f"ghcr.io/autobrr/qui:{_TAGS['qui']}",
        internal_port=7476,
        default_host_port=7476,
        config_dir="qui",
        requires=("qbittorrent",),
        api_family="qui",
        notes="UI web pour qBittorrent. N'est pas un client.",
    ),
    "recyclarr": ServiceSpec(
        id="recyclarr",
        display_name="Recyclarr",
        category=Category.ARR,
        image=f"ghcr.io/recyclarr/recyclarr:{_TAGS['recyclarr']}",
        #: Aucune interface web : Recyclarr tourne sur une planification et sort.
        #: Le port 0 signale qu'il n'y a rien a publier.
        internal_port=0,
        default_host_port=0,
        config_dir="recyclarr",
        requires_one_of=("sonarr", "radarr"),
        api_family="recyclarr",
        notes="Profils de qualite TRaSH. Aucune interface web.",
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
    # Recyclarr apres les *arr : il ecrit dans leurs profils de qualite.
    "recyclarr",
    # autobrr apres les *arr ET apres les clients : il les declare tous les deux
    # au meme endpoint, et son test de connexion les contacte reellement.
    "autobrr",
    "jellyfin",
    # Les appoints de Silo AVANT lui : `depends_on` exige qu'ils soient sains,
    # et l'ordre de cette liste decide aussi de l'ordre d'affichage.
    "silo-postgres",
    "silo-redis",
    "silo",
    "flood",
    "qui",
)

#: Applications *arr pilotables par Prowlarr et rattachables a un client de download.
MANAGED_ARRS = ("sonarr", "radarr", "lidarr")

#: Services jouant le role de client de telechargement.
DOWNLOAD_CLIENTS = ("transmission", "qbittorrent")

#: Selection par defaut du profil "Debutant tout-en-un" en Phase 1.
#: Coches par defaut dans l'assistant. Recyclarr en fait partie : il ne coute
#: presque rien (pas de port, pas d'interface, un reveil par jour) et c'est lui
#: qui evite qu'un *arr accepte n'importe quel encodage. Une stack sans profil de
#: qualite telecharge, mais telecharge mal.
DEFAULT_SELECTION = ("prowlarr", "sonarr", "radarr", "transmission", "jellyfin", "recyclarr")


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


def selectable() -> list[ServiceSpec]:
    """Services qu'un utilisateur peut cocher.

    Les conteneurs d'appoint en sont exclus : une base de donnees n'est pas un
    service qu'on choisit, c'est une piece de celui qui en depend. La proposer a
    cote de Sonarr n'aurait aucun sens, et l'installer seule non plus.
    """
    return [spec for spec in CATALOG.values() if not spec.internal]


#: Familles dont le mot de passe peut etre change sans reinstaller. Liste fermee :
#: chaque entree correspond a un chemin VERIFIE contre le service, pas a une
#: supposition. Elle vit ici parce que deux modules en ont besoin — la page
#: d'administration pour afficher le bouton, l'orchestrateur pour agir — et que
#: la page ne peut pas importer l'orchestrateur, qui l'importe deja.
ROTATABLE_FAMILIES = ("arr", "qbittorrent", "transmission")
