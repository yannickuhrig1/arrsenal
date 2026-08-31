"""Arborescence de donnees et profils de plateforme.

Le point critique du projet (PROMPT.md sec. 4.2) : un montage UNIQUE `/data` dans
tous les conteneurs. Deux montages separes (/downloads + /media) font echouer les
hardlinks silencieusement, et chaque import recopie le fichier.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .models import PlatformProfile

#: Sous-dossiers crees sous DATA_ROOT. Meme structure cote hote et cote conteneur.
DATA_SUBDIRS = (
    "torrents",
    "torrents/movies",
    "torrents/tv",
    "torrents/.incomplete",
    "media",
    "media/movies",
    "media/tv",
)

#: Correspondance categorie *arr -> chemin conteneur.
CONTAINER_PATHS = {
    "torrents_root": "/data/torrents",
    "torrents_incomplete": "/data/torrents/.incomplete",
    "torrents_tv": "/data/torrents/tv",
    "torrents_movies": "/data/torrents/movies",
    "media_tv": "/data/media/tv",
    "media_movies": "/data/media/movies",
}


@dataclass(frozen=True)
class ProfileDefaults:
    config_root: str
    data_root: str
    puid: int
    pgid: int
    verified: bool
    note: str = ""


#: TODO(verify) : les UID/GID Unraid et Synology doivent etre confirmes contre la
#: documentation officielle de chaque plateforme avant d'etre presentes sans avertissement.
#: Tant que `verified` est False, la CLI demande une confirmation explicite.
PROFILE_DEFAULTS: dict[PlatformProfile, ProfileDefaults] = {
    PlatformProfile.GENERIC_LINUX: ProfileDefaults(
        config_root="/opt/arrsenal/config",
        data_root="/srv/data",
        puid=1000,
        pgid=1000,
        verified=True,
    ),
    PlatformProfile.UNRAID: ProfileDefaults(
        config_root="/mnt/user/appdata/arrsenal",
        data_root="/mnt/user/data",
        puid=99,
        pgid=100,
        verified=False,
        note="UID/GID 99:100 (nobody:users) a confirmer contre la doc Unraid.",
    ),
    PlatformProfile.SYNOLOGY: ProfileDefaults(
        config_root="/volume1/docker/arrsenal",
        data_root="/volume1/data",
        puid=1026,
        pgid=100,
        verified=False,
        note="UID/GID a confirmer : varient selon l'utilisateur DSM cree.",
    ),
}


def detect_ids() -> tuple[int, int]:
    """UID/GID courants. Retombe sur 1000:1000 la ou os.getuid n'existe pas (Windows)."""
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if getuid is None or getgid is None:
        return 1000, 1000
    return getuid(), getgid()


def create_tree(data_root: str | Path, config_root: str | Path, service_ids: list[str]) -> list[Path]:
    """Cree l'arborescence. Idempotent."""
    created: list[Path] = []
    data_root, config_root = Path(data_root), Path(config_root)
    for sub in DATA_SUBDIRS:
        p = data_root / sub
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(p)
    for sid in service_ids:
        p = config_root / sid
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created.append(p)
    return created


def hardlink_supported(data_root: str | Path) -> tuple[bool, str]:
    """Teste REELLEMENT qu'un hardlink est possible entre torrents/ et media/.

    C'est le diagnostic qui distingue une stack qui recopie 40 Go a chaque import
    d'une stack qui fait un lien instantane. On ne suppose rien, on essaie.
    """
    data_root = Path(data_root)
    src_dir, dst_dir = data_root / "torrents", data_root / "media"
    try:
        src_dir.mkdir(parents=True, exist_ok=True)
        dst_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"impossible de creer {src_dir} ou {dst_dir}: {exc}"

    fd, src = tempfile.mkstemp(dir=src_dir, prefix=".arrsenal-hardlink-")
    os.close(fd)
    dst = dst_dir / (Path(src).name + ".link")
    try:
        os.link(src, dst)
        return True, "hardlink OK entre torrents/ et media/"
    except OSError as exc:
        return False, (
            f"hardlink impossible ({exc}). Les imports recopieront les fichiers au lieu "
            f"de les lier. Verifiez que {src_dir} et {dst_dir} sont sur le MEME systeme "
            f"de fichiers, et que DATA_ROOT est monte d'un seul bloc."
        )
    finally:
        for p in (dst, Path(src)):
            try:
                p.unlink()
            except OSError:
                pass
