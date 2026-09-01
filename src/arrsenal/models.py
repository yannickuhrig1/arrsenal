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
    WINDOWS = "windows"


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
    #: Services requis pour que celui-ci ait un sens. Tous obligatoires.
    requires: tuple[str, ...] = ()
    #: Au moins UN de ces services est necessaire. Sert aux interfaces qui
    #: acceptent plusieurs backends, comme Flood.
    requires_one_of: tuple[str, ...] = ()
    #: Famille d'API, pilote le cablage. Voir wiring.py.
    api_family: str | None = None
    #: Version d'API des *arr : v3 pour Sonarr/Radarr, v1 pour Prowlarr.
    api_version: str = "v3"
    notes: str = ""

    @property
    def needs_config_volume(self) -> bool:
        return self.config_dir is not None


#: Fournisseurs acceptes par Gluetun. Liste obtenue de Gluetun LUI-MEME, en lui
#: passant un nom invalide : il repond avec l'enumeration exacte. Verifie contre
#: la v3.41.3, jamais recopiee d'un article.
VPN_PROVIDERS = (
    "airvpn", "cyberghost", "expressvpn", "fastestvpn", "giganews", "hidemyass",
    "ipvanish", "ivpn", "mullvad", "nordvpn", "perfect privacy", "privado",
    "private internet access", "privatevpn", "protonvpn", "purevpn", "slickvpn",
    "surfshark", "torguard", "vpnsecure", "vpn unlimited", "vyprvpn", "windscribe",
    "custom", "pia",
)


class VpnConfig(BaseModel):
    """Reglages Gluetun.

    Deux modes, et ils n'exigent pas les memes champs — constate en lancant
    Gluetun a vide et en lisant ce qu'il reclame :

    - `wireguard` : `WIREGUARD_PRIVATE_KEY` obligatoire, et la cle doit etre une
      vraie cle base64 ; Gluetun refuse toute autre chaine ;
    - `openvpn` : `OPENVPN_USER` et `OPENVPN_PASSWORD`.
    """

    enabled: bool = False
    provider: str = ""
    vpn_type: str = "wireguard"
    openvpn_user: str = ""
    openvpn_password: str = ""
    wireguard_private_key: str = ""
    wireguard_addresses: str = ""
    #: Filtre de pays, facultatif. Ex : "Switzerland,Netherlands".
    countries: str = ""

    @field_validator("provider")
    @classmethod
    def _known_provider(cls, v: str) -> str:
        v = v.strip().lower()
        if v and v not in VPN_PROVIDERS:
            raise ValueError(
                f"fournisseur VPN inconnu de Gluetun: {v!r}. "
                f"Choix possibles : {', '.join(VPN_PROVIDERS)}"
            )
        return v

    @field_validator("vpn_type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("wireguard", "openvpn"):
            raise ValueError(f"type de VPN inconnu: {v!r} (attendu wireguard ou openvpn)")
        return v

    def missing(self) -> list[str]:
        """Ce qui manque pour que Gluetun demarre. Vide = pret."""
        if not self.enabled:
            return []
        gaps: list[str] = []
        if not self.provider:
            gaps.append("le fournisseur VPN (--vpn-provider)")
        if self.vpn_type == "wireguard":
            if not self.wireguard_private_key:
                gaps.append("la cle privee WireGuard (--vpn-key)")
        elif not self.openvpn_user or not self.openvpn_password:
            gaps.append("les identifiants OpenVPN (--vpn-user et --vpn-pass)")
        return gaps

    def environment(self, timezone: str) -> dict[str, str]:
        env = {
            "VPN_SERVICE_PROVIDER": self.provider,
            "VPN_TYPE": self.vpn_type,
            "TZ": timezone,
        }
        if self.vpn_type == "wireguard":
            env["WIREGUARD_PRIVATE_KEY"] = self.wireguard_private_key
            if self.wireguard_addresses:
                env["WIREGUARD_ADDRESSES"] = self.wireguard_addresses
        else:
            env["OPENVPN_USER"] = self.openvpn_user
            env["OPENVPN_PASSWORD"] = self.openvpn_password
        if self.countries:
            env["SERVER_COUNTRIES"] = self.countries
        return env


class ServiceInstance(BaseModel):
    """Un service reellement selectionne, avec ses secrets et son port resolus."""

    spec_id: str
    host_port: int
    #: Cle API pre-semee pour les *arr. None pour les services sans cle.
    api_key: str | None = None
    username: str | None = None
    password: str | None = None

    #: True quand le service existait DEJA et n'est pas gere par arrsenal :
    #: aucun conteneur n'est genere pour lui, on se contente de le cabler.
    adopted: bool = False
    #: Nom du conteneur existant, pour un service adopte.
    container: str | None = None
    #: `UrlBase` du service, quand il n'est pas servi a la racine.
    url_base: str = ""

    #: Image REELLEMENT deployee, tag compris. Le catalogue ne fournit que la
    #: valeur par defaut : sans ce champ, la version serait figee dans le code
    #: d'arrsenal et personne ne pourrait mettre a jour Sonarr sans attendre une
    #: nouvelle version de l'outil.
    image: str = ""

    @property
    def has_web_ui(self) -> bool:
        """Ce service publie-t-il quelque chose a ouvrir dans un navigateur ?

        Recyclarr n'a pas d'interface : il tourne sur une planification et ne
        publie aucun port. Tout affichage doit le savoir, sans quoi il propose un
        lien vers `http://hote:0` — un lien mort au milieu d'une page de
        raccourcis fait conclure que l'installation a echoue.
        """
        return bool(self.host_port)

    def url(self, host: str = "localhost") -> str:
        base = f"http://{host}:{self.host_port}"
        return f"{base}/{self.url_base}" if self.url_base else base

    def internal_url(
        self, spec: ServiceSpec, host: str = "localhost", *, behind_vpn: bool = False
    ) -> str:
        """URL a utiliser quand un service en appelle un autre.

        Pour une stack geree par arrsenal, les conteneurs partagent un reseau
        compose : le nom de SERVICE resout, et c'est le plus robuste.

        Sous VPN, un client de telechargement perd son alias DNS : il partage la
        pile reseau de Gluetun. C'est `behind_vpn` qui l'exprime.

        Pour un service ADOPTE, non plus. Les conteneurs existants vivent sur leurs
        propres reseaux, souvent differents les uns des autres : `http://sonarr:8989`
        ne resout pas d'un reseau a l'autre. Il faut passer par l'adresse de
        l'hote et le port publie, seul chemin garanti entre deux conteneurs
        etrangers l'un a l'autre.
        """
        if self.adopted:
            return self.url(host)
        if behind_vpn:
            # Sous `network_mode: service:gluetun`, le conteneur n'a plus de pile
            # reseau propre : il perd son alias DNS. `http://qbittorrent:8080` ne
            # resout plus, il faut viser gluetun, qui porte desormais sa place
            # dans le reseau ET ses ports.
            return f"http://gluetun:{spec.internal_port}"
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

    #: D'ou viennent puid/pgid. Affiche a l'utilisateur : des identifiants faux
    #: cassent les permissions de toute la stack, il doit pouvoir les juger.
    ids_source: str = "non renseigne"
    #: False quand on s'est rabattu sur une valeur par defaut faute de detection.
    ids_certain: bool = True

    services: dict[str, ServiceInstance] = Field(default_factory=dict)

    vpn: VpnConfig = Field(default_factory=VpnConfig)

    #: Template TRaSH choisi par service. Vide = celui par defaut de Recyclarr.
    recyclarr_templates: dict[str, str] = Field(default_factory=dict)
    #: Repertoire des artefacts, necessaire pour lancer une commande ponctuelle.
    #: Renseigne a l'execution, pas persiste : il depend d'ou l'on se trouve.
    project_dir: object | None = Field(default=None, exclude=True)

    @property
    def vpn_enabled(self) -> bool:
        """Raccourci de lecture. Desactive = avertissement au recapitulatif."""
        return self.vpn.enabled

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
