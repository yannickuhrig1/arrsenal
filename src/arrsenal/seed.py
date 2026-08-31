"""Pre-semis des fichiers de configuration AVANT le premier demarrage.

C'est le coeur de l'architecture (PROMPT.md sec. 4.4). Plutot que de demarrer les
conteneurs puis de courir apres la cle API generee aleatoirement, on ecrit nous-memes
la cle dans `config.xml`. Le cablage devient deterministe et rejouable.

Le pre-semis n'ecrase JAMAIS un fichier existant : re-lancer `install` sur une stack
deja installee ne doit pas casser une configuration que l'utilisateur a modifiee.
"""

from __future__ import annotations

import json
import secrets
import string
from pathlib import Path
from xml.etree import ElementTree as ET

from .layout import CONTAINER_PATHS


def generate_api_key() -> str:
    """32 caracteres hexadecimaux, format attendu par les *arr."""
    return secrets.token_hex(16)


def generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# --------------------------------------------------------------------------- *arr


def render_arr_config(
    *,
    api_key: str,
    port: int,
    instance_name: str,
    username: str,
    password: str,
    url_base: str = "",
    branch: str = "main",
) -> str:
    """Genere le config.xml minimal d'un *arr.

    Choix d'authentification, verifie empiriquement contre Sonarr 4.0.19.2979 :

    `Forms` + `Enabled` + un couple identifiant/mot de passe genere. C'est le seul
    reglage qui satisfait les trois contraintes a la fois :
      - l'UI web exige un login (GET / renvoie 302 vers /login)
      - l'API sans cle est refusee (401)
      - l'API avec X-Api-Key fonctionne, donc le cablage automatique reste possible

    L'alternative `External` + `DisabledForLocalAddresses` marche aussi pour le
    cablage, mais laisse les interfaces web ouvertes a tout le LAN. Refuse.

    Bonus verifie : l'application consomme <Username>/<Password> au premier
    demarrage, les migre en base, puis les EFFACE du fichier. Le mot de passe en
    clair ne survit donc pas sur le disque.
    """
    root = ET.Element("Config")
    values = {
        "BindAddress": "*",
        "Port": str(port),
        "UrlBase": url_base,
        "ApiKey": api_key,
        "AuthenticationMethod": "Forms",
        "AuthenticationRequired": "Enabled",
        "Username": username,
        "Password": password,
        "PasswordConfirmation": password,
        "InstanceName": instance_name,
        "Branch": branch,
        "LogLevel": "info",
        "UpdateMechanism": "Docker",
        "AnalyticsEnabled": "False",
    }
    for key, value in values.items():
        ET.SubElement(root, key).text = value
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode") + "\n"


def read_api_key(config_xml: Path) -> str | None:
    """Relit la cle d'un config.xml existant, pour rester idempotent."""
    try:
        text = config_xml.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        node = ET.fromstring(text).find("ApiKey")
    except ET.ParseError:
        return None
    return node.text.strip() if node is not None and node.text else None


def seed_arr(
    config_dir: Path,
    *,
    api_key: str,
    port: int,
    instance_name: str,
    username: str,
    password: str,
) -> tuple[str, bool]:
    """Ecrit config.xml s'il n'existe pas. Renvoie (cle_effective, a_ete_ecrit).

    Si le fichier existe deja, on adopte SA cle : l'utilisateur ou un run precedent
    fait autorite, jamais nous.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    target = config_dir / "config.xml"
    if target.exists():
        existing = read_api_key(target)
        if existing:
            return existing, False
    target.write_text(
        render_arr_config(
            api_key=api_key,
            port=port,
            instance_name=instance_name,
            username=username,
            password=password,
        ),
        encoding="utf-8",
    )
    return api_key, True


# ------------------------------------------------------------------- Transmission


def render_transmission_settings(*, rpc_username: str, rpc_password: str) -> dict:
    """settings.json de Transmission.

    Points importants :
    - `rpc-whitelist-enabled: false` : sans ca, les conteneurs Sonarr/Radarr sont
      refuses par Transmission (adresses du reseau bridge non whitelistees).
    - `rpc-host-whitelist-enabled: false` : meme raison, cote en-tete Host.
    - `download-dir` sous /data/torrents pour que les hardlinks vers /data/media
      restent possibles.
    - Transmission hashe le mot de passe en clair au premier demarrage et REECRIT
      ce fichier a l'arret. Ne jamais l'editer pendant que le conteneur tourne.
    """
    return {
        "rpc-enabled": True,
        "rpc-bind-address": "0.0.0.0",
        "rpc-port": 9091,
        "rpc-url": "/transmission/",
        "rpc-authentication-required": True,
        "rpc-username": rpc_username,
        "rpc-password": rpc_password,
        "rpc-whitelist-enabled": False,
        "rpc-host-whitelist-enabled": False,
        "download-dir": CONTAINER_PATHS["torrents_root"],
        "incomplete-dir": CONTAINER_PATHS["torrents_incomplete"],
        "incomplete-dir-enabled": True,
        "rename-partial-files": True,
        "start-added-torrents": True,
        "watch-dir-enabled": False,
        "umask": 2,
    }


def seed_transmission(
    config_dir: Path, *, rpc_username: str, rpc_password: str
) -> tuple[bool, str]:
    """Ecrit settings.json s'il n'existe pas. Renvoie (a_ete_ecrit, message)."""
    config_dir.mkdir(parents=True, exist_ok=True)
    target = config_dir / "settings.json"
    if target.exists():
        return False, "settings.json existe deja, conserve tel quel"
    target.write_text(
        json.dumps(
            render_transmission_settings(
                rpc_username=rpc_username, rpc_password=rpc_password
            ),
            indent=4,
        )
        + "\n",
        encoding="utf-8",
    )
    return True, "settings.json pre-seme"
