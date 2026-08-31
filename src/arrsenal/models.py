"""Modele de donnees d'une stack.

`StackConfig` est l'unique source de verite. `docker-compose.yml` et `.env` en sont
des artefacts generes, jamais edites a la main (voir PROMPT.md sec. 6).
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import PurePosixPath

from pydantic import BaseModel, Field, field_validator


class Category(str, Enum):
    ARR = "arr"
    DOWNLOAD = "download"
    MEDIA = "media"
    UI = "ui"


class PlatformProfile(str, Enum):
    GENERIC_LINUX = "generic-linux"
    UNRAID = "unraid"
    SYNOLOGY = "synology"


class ServiceSpec(BaseModel):
    """Definition statique d'un service. Immuable, vit dans catalog.py."""

    id: str
    display_name: str
    category: Category
    image: str
    internal_port: int
    default_host_port: int
    #: Sous-dossier sous CONFIG_ROOT. None = le service n'a pas de config persistante.
    config_dir: str | None = None
    #: Services requis pour que celui-ci ait un sens.
    requires: tuple[str, ...] = ()
    #: Famille d'API, pilote le cablage. Voir wiring.py.
    api_family: str | None = None
    #: Version d'API des *arr : v3 pour Sonarr/Radarr, v1 pour Prowlarr.
    api_version: str = "v3"
    notes: str = ""

    @property
    def needs_config_volume(self) -> bool:
        return self.config_dir is not None


class ServiceInstance(BaseModel):
    """Un service reellement selectionne, avec ses secrets et son port resolus."""

    spec_id: str
    host_port: int
    #: Cle API pre-semee pour les *arr. None pour les services sans cle.
    api_key: str | None = None
    username: str | None = None
    password: str | None = None

    def url(self, host: str = "localhost") -> str:
        return f"http://{host}:{self.host_port}"

    def internal_url(self, spec: ServiceSpec) -> str:
        """URL vue depuis un autre conteneur du meme reseau compose."""
        return f"http://{spec.id}:{spec.internal_port}"


class StackConfig(BaseModel):
    """Etat canonique versionnable (stack.yml)."""

    version: int = 1
    project_name: str = "arrsenal"
    platform: PlatformProfile = PlatformProfile.GENERIC_LINUX

    config_root: str
    data_root: str

    puid: int = 1000
    pgid: int = 1000
    umask: str = "002"
    timezone: str = "Etc/UTC"

    #: Hote joignable depuis le navigateur de l'utilisateur, pour le rapport final.
    host: str = "localhost"

    services: dict[str, ServiceInstance] = Field(default_factory=dict)

    #: Desactive = avertissement explicite au recapitulatif (PROMPT.md sec. 11.1).
    vpn_enabled: bool = False

    @field_validator("config_root", "data_root")
    @classmethod
    def _no_trailing_sep(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("le chemin ne peut pas etre vide")
        return v.rstrip("/\\") or v

    @field_validator("umask")
    @classmethod
    def _umask_form(cls, v: str) -> str:
        if not (len(v) in (3, 4) and all(c in "01234567" for c in v)):
            raise ValueError(f"umask invalide: {v!r} (attendu 3 ou 4 chiffres octaux)")
        return v

    # -- chemins -------------------------------------------------------------

    def config_path(self, service_id: str) -> str:
        # Separateurs normalises : ces chemins finissent dans un .env lu par Docker,
        # qui n'aime pas les antislashs melanges aux slashs.
        return f"{self.config_root.replace(os.sep, '/')}/{service_id}"

    @staticmethod
    def container_data_root() -> PurePosixPath:
        """Montage unique dans TOUS les conteneurs. C'est ce qui rend les
        hardlinks possibles entre /data/torrents et /data/media."""
        return PurePosixPath("/data")

    def enabled(self, service_id: str) -> bool:
        return service_id in self.services
