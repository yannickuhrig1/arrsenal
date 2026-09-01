"""Journal d'installation.

Une installation touche a Docker, a huit API et a une dizaine de fichiers. Quand
quelque chose echoue, l'ecran ne montre que la derniere ligne, et le terminal se
ferme. Ce module ecrit tout dans un fichier, a cote des artefacts, pour qu'un
rapport de bug contienne autre chose que « ca ne marche pas ».

**Aucun secret n'y figure.** Les mots de passe et les cles API de la stack sont
remplaces par leur nom avant ecriture. C'est la condition pour qu'un utilisateur
puisse joindre ce fichier a une issue publique sans y reflechir.
"""

from __future__ import annotations

import logging
import platform
import sys
from datetime import datetime
from pathlib import Path

LOGGER = logging.getLogger("arrsenal")

#: Nom du fichier, a cote de docker-compose.yml et stack.yml.
FILENAME = "arrsenal.log"

#: En dessous de cette longueur, une valeur n'est pas masquee : elle serait trop
#: courte pour etre un secret, et la masquer rendrait le journal illisible.
MIN_SECRET = 8


class _Masker(logging.Filter):
    """Remplace les secrets connus par leur nom, avant ecriture.

    Le filtre porte sur les VALEURS enregistrees explicitement, jamais sur une
    forme devinee. Un filtre qui tente de reconnaitre « ce qui ressemble a un
    secret » laisse forcement passer ce qu'il n'a pas prevu.
    """

    def __init__(self) -> None:
        super().__init__()
        self._secrets: dict[str, str] = {}

    def remember(self, label: str, value: str | None) -> None:
        if value and len(value) >= MIN_SECRET:
            self._secrets[value] = f"<{label}>"

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for value, replacement in self._secrets.items():
            message = message.replace(value, replacement)
        record.msg, record.args = message, ()
        return True


_MASKER = _Masker()


def remember_secrets(cfg: object) -> None:
    """Enregistre les secrets d'une StackConfig pour qu'ils soient masques."""
    services = getattr(cfg, "services", {}) or {}
    for sid, inst in services.items():
        _MASKER.remember(f"cle-api-{sid}", getattr(inst, "api_key", None))
        _MASKER.remember(f"mot-de-passe-{sid}", getattr(inst, "password", None))
    vpn = getattr(cfg, "vpn", None)
    if vpn is not None:
        _MASKER.remember("cle-wireguard", getattr(vpn, "wireguard_private_key", None))
        _MASKER.remember("mot-de-passe-openvpn", getattr(vpn, "openvpn_password", None))


def start(project_dir: Path, commande: str) -> Path:
    """Ouvre le journal et ecrit l'entete de session. Renvoie son chemin.

    Le fichier est ouvert en AJOUT : deux installations successives se relisent
    l'une apres l'autre, ce qui est precisement ce qu'on veut pour comprendre un
    second passage qui echoue la ou le premier avait reussi.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / FILENAME

    LOGGER.handlers.clear()
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.propagate = False

    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s"))
    handler.addFilter(_MASKER)
    LOGGER.addHandler(handler)

    from . import __version__

    LOGGER.info("=" * 78)
    LOGGER.info("arrsenal %s - %s", __version__, datetime.now().astimezone().isoformat(" ", "seconds"))
    LOGGER.info("commande   : %s", commande)
    LOGGER.info("plateforme : %s %s (%s)", platform.system(), platform.release(), sys.platform)
    LOGGER.info("python     : %s", sys.version.split()[0])
    LOGGER.info("gele       : %s", getattr(sys, "frozen", False))
    LOGGER.info("=" * 78)
    return path


def config(cfg: object) -> None:
    """Enregistre la configuration retenue, secrets exclus."""
    remember_secrets(cfg)
    LOGGER.info("plateforme choisie : %s", getattr(getattr(cfg, "platform", None), "value", "?"))
    LOGGER.info("config_root        : %s", getattr(cfg, "config_root", "?"))
    LOGGER.info("data_root          : %s", getattr(cfg, "data_root", "?"))
    LOGGER.info("PUID/PGID          : %s:%s (%s)", getattr(cfg, "puid", "?"),
                getattr(cfg, "pgid", "?"), getattr(cfg, "ids_source", "?"))
    LOGGER.info("services           : %s", ", ".join(getattr(cfg, "services", {})))


def checks(items: list) -> None:
    for check in items:
        LOGGER.log(
            logging.INFO if check.ok else logging.WARNING,
            "preflight %-24s %-5s %s",
            check.name,
            "OK" if check.ok else "ECHEC",
            check.detail,
        )


def progress(phase: str, message: str, ok: bool = True) -> None:
    LOGGER.log(logging.INFO if ok else logging.ERROR, "%-14s %s", phase, message)


def step(result: object) -> None:
    ok = getattr(result, "ok", False)
    LOGGER.log(
        logging.INFO if ok else logging.ERROR,
        "%-5s %s - %s",
        "OK" if ok else "ECHEC",
        getattr(result, "name", "?"),
        getattr(result, "detail", ""),
    )
    for warning in getattr(result, "warnings", []) or []:
        LOGGER.warning("      %s", warning)


def failure(message: str) -> None:
    LOGGER.error("%s", message)


def finish(message: str) -> None:
    LOGGER.info("%s", message)
    for handler in LOGGER.handlers:
        handler.flush()
