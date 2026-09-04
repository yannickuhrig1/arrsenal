"""Profils de clients de telechargement.

Chaque client expose des champs differents dans les *arr, et surtout une facon
differente de router les telechargements :

- Transmission n'a pas de vraies categories : on lui donne un REPERTOIRE.
- qBittorrent a des categories natives, avec chemin de sauvegarde par categorie :
  on lui donne une CATEGORIE, et on cree cette categorie cote qBittorrent avec le
  bon chemin.

Poser les deux fait echouer la validation ("Cannot use Category and Directory"),
et le gabarit /schema arrive avec une categorie par defaut deja remplie. Chaque
profil doit donc explicitement vider celui des deux qu'il n'utilise pas.
"""

from __future__ import annotations

from dataclasses import dataclass

from .layout import CONTAINER_PATHS

#: Prefixe des champs de categorie/repertoire selon l'application.
#: Sonarr expose tvCategory/tvDirectory, Radarr movieCategory/movieDirectory, etc.
ARR_FIELD_PREFIX = {"sonarr": "tv", "radarr": "movie", "lidarr": "music"}

#: Nom de la categorie et chemin de telechargement associes a chaque application.
ARR_ROUTING = {
    "sonarr": ("tv", CONTAINER_PATHS["torrents_tv"]),
    "radarr": ("movies", CONTAINER_PATHS["torrents_movies"]),
    "lidarr": ("music", CONTAINER_PATHS["torrents_music"]),
}


@dataclass(frozen=True)
class DownloadClientProfile:
    service_id: str
    #: Nom technique de l'implementation dans les *arr, pas le libelle affiche.
    implementation: str
    protocol: str
    #: True = router par categorie native, False = router par repertoire explicite.
    routes_by_category: bool

    def arr_values(self, *, host: str, port: int, username: str, password: str, arr_id: str) -> dict:
        """Valeurs a poser dans le gabarit du *arr `arr_id`.

        On ne pousse que le prefixe pertinent : envoyer `movieDirectory` a Sonarr
        genererait un avertissement de champ inconnu a chaque passage.
        """
        prefix = ARR_FIELD_PREFIX[arr_id]
        category, directory = ARR_ROUTING[arr_id]
        values: dict[str, object] = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "useSsl": False,
        }
        if self.service_id == "transmission":
            values["urlBase"] = "/transmission/"
        if self.service_id == "sabnzbd":
            # SABnzbd s'authentifie par CLE API. Son identifiant et son mot de
            # passe restent vides : les poser ferait echouer le test de
            # connexion, l'interface n'en demandant pas.
            values["apiKey"] = password
            values["username"] = ""
            values["password"] = ""
        if self.routes_by_category:
            values[f"{prefix}Category"] = category
            values[f"{prefix}Directory"] = ""
        else:
            values[f"{prefix}Directory"] = directory
            values[f"{prefix}Category"] = ""
        return values

    def prowlarr_values(self, *, host: str, port: int, username: str, password: str) -> dict:
        """Prowlarr n'a pas de notion de categorie par media : pas de prefixe."""
        values: dict[str, object] = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "useSsl": False,
        }
        if self.service_id == "transmission":
            values["urlBase"] = "/transmission/"
        if self.service_id == "sabnzbd":
            values["apiKey"] = password
            values["username"] = ""
            values["password"] = ""
        return values


PROFILES: dict[str, DownloadClientProfile] = {
    "transmission": DownloadClientProfile(
        service_id="transmission",
        implementation="Transmission",
        protocol="torrent",
        routes_by_category=False,
    ),
    "qbittorrent": DownloadClientProfile(
        service_id="qbittorrent",
        implementation="QBittorrent",
        protocol="torrent",
        routes_by_category=True,
    ),
    "sabnzbd": DownloadClientProfile(
        service_id="sabnzbd",
        implementation="Sabnzbd",
        # USENET, pas torrent. Ce n'est pas un detail d'etiquette : les *arr
        # rangent leurs clients par protocole et ne proposent un client Usenet
        # que pour les publications Usenet.
        protocol="usenet",
        routes_by_category=True,
    ),
}


def profile_for(service_id: str) -> DownloadClientProfile:
    try:
        return PROFILES[service_id]
    except KeyError:
        known = ", ".join(sorted(PROFILES))
        raise KeyError(
            f"pas de profil de client de telechargement pour {service_id!r}. Connus: {known}"
        ) from None
