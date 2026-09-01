"""Arborescence de donnees et profils de plateforme.

Le point critique du projet (PROMPT.md sec. 4.2) : un montage UNIQUE `/data` dans
tous les conteneurs. Deux montages separes (/downloads + /media) font echouer les
hardlinks silencieusement, et chaque import recopie le fichier.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .models import PlatformProfile

#: Sous-dossiers crees sous DATA_ROOT. Meme structure cote hote et cote conteneur.
DATA_SUBDIRS = (
    "torrents",
    "torrents/movies",
    "torrents/tv",
    "torrents/music",
    "torrents/.incomplete",
    "media",
    "media/movies",
    "media/tv",
    "media/music",
)

#: Correspondance categorie *arr -> chemin conteneur.
CONTAINER_PATHS = {
    "torrents_root": "/data/torrents",
    "torrents_incomplete": "/data/torrents/.incomplete",
    "torrents_tv": "/data/torrents/tv",
    "torrents_movies": "/data/torrents/movies",
    "torrents_music": "/data/torrents/music",
    "media_tv": "/data/media/tv",
    "media_movies": "/data/media/movies",
    "media_music": "/data/media/music",
}


@dataclass(frozen=True)
class ProfileDefaults:
    config_root: str
    data_root: str
    puid: int
    pgid: int
    #: True quand les identifiants corrects sont ceux de l'utilisateur courant et
    #: doivent etre DETECTES. False quand la plateforme impose une constante.
    prefer_detection: bool
    #: D'ou viennent puid/pgid. Affiche a l'utilisateur : il doit pouvoir juger.
    source: str


PROFILE_DEFAULTS: dict[PlatformProfile, ProfileDefaults] = {
    PlatformProfile.GENERIC_LINUX: ProfileDefaults(
        config_root="/opt/arrsenal/config",
        data_root="/srv/data",
        puid=1000,
        pgid=1000,
        prefer_detection=True,
        source="utilisateur courant",
    ),
    PlatformProfile.WINDOWS: ProfileDefaults(
        # Des chemins Windows, evidemment. Sans ce profil, un utilisateur Windows
        # n'avait AUCUNE option correcte : les trois autres proposent des chemins
        # Linux, que Docker Desktop cree alors a la racine du disque courant
        # (`/mnt/user/data` devient `C:\mnt\user\data`) sans que rien ne le dise.
        config_root="C:/arrsenal/config",
        data_root="C:/arrsenal/data",
        # Docker Desktop n'applique pas la propriete Unix aux montages venus de
        # Windows : ces valeurs n'ont aucun effet ici. On garde 1000:1000, qui est
        # ce qu'attendent les images LinuxServer, et on le DIT plutot que
        # d'afficher un avertissement inquietant et sans objet.
        puid=1000,
        pgid=1000,
        prefer_detection=False,
        source="sans effet sous Docker Desktop : Windows ne porte pas ces droits",
    ),
    PlatformProfile.UNRAID: ProfileDefaults(
        config_root="/mnt/user/appdata/arrsenal",
        data_root="/mnt/user/data",
        puid=99,
        pgid=100,
        prefer_detection=False,
        source="constante Unraid : nobody:users = 99:100",
    ),
    PlatformProfile.SYNOLOGY: ProfileDefaults(
        config_root="/volume1/docker/arrsenal",
        data_root="/volume1/data",
        # Valeurs de repli seulement. Sur DSM, l'UID depend de l'ordre de creation
        # des utilisateurs : 1026 pour le premier, mais on rencontre couramment
        # bien plus haut. Une constante serait fausse par conception, d'ou la
        # detection.
        puid=1026,
        pgid=100,
        prefer_detection=True,
        source="utilisateur courant (les UID DSM varient selon l'utilisateur cree)",
    ),
}


def detect_ids() -> tuple[int, int] | None:
    """UID/GID de l'utilisateur courant, ou None si la plateforme ne les expose pas.

    Renvoie None plutot que 1000:1000 sous Windows : une valeur inventee
    silencieusement est pire qu'une absence de valeur, puisqu'elle empeche de
    prevenir l'utilisateur.
    """
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if getuid is None or getgid is None:
        return None
    return getuid(), getgid()


def resolve_ids(profile: PlatformProfile) -> tuple[int, int, str, bool]:
    """Determine PUID/PGID pour un profil.

    Renvoie (uid, gid, explication, sur). `sur` a False signifie "l'utilisateur doit
    regarder cette valeur avant de continuer" : l'explication dit pourquoi.
    """
    defaults = PROFILE_DEFAULTS[profile]
    if not defaults.prefer_detection:
        return defaults.puid, defaults.pgid, defaults.source, True

    detected = detect_ids()
    if detected is None:
        return (
            defaults.puid,
            defaults.pgid,
            "valeur par defaut : detection impossible sur cette plateforme",
            False,
        )
    if detected[0] == 0:
        # Constate lors du premier essai sur Linux natif : `sudo arrsenal install`
        # detecte 0:0 et fait tourner TOUTE la stack en root, en silence. Les
        # medias telecharges appartiennent alors a root, et l'utilisateur ne peut
        # plus y toucher sans sudo. On propose la valeur, on ne l'impose pas, mais
        # on ne la laisse pas passer sans le dire.
        return (
            0,
            detected[1],
            "lance en root : conteneurs et medias appartiendront a root",
            False,
        )
    return detected[0], detected[1], f"detecte ({defaults.source})", True


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


def default_profile() -> PlatformProfile:
    """Profil correspondant a la machine qui execute arrsenal.

    Proposer `generic-linux` a un utilisateur Windows le conduisait droit dans le
    piege : il gardait des chemins Linux, et Docker Desktop les creait a la racine
    du disque courant sans que rien ne le signale.
    """
    return PlatformProfile.WINDOWS if sys.platform == "win32" else PlatformProfile.GENERIC_LINUX


def path_warning(path: str) -> str | None:
    r"""Avertissement quand un chemin ne correspond pas a cette machine.

    Renvoie None si le chemin est coherent. C'est le controle qui manquait :
    `/mnt/user/data` saisi sous Windows passait sans un mot, et l'installation
    partait vers `C:\mnt\user\data`.
    """
    texte = path.strip()
    if not texte:
        return None
    # `[\\/]` et non `[\/]` : dans une classe, `\/` ne vaut que la barre oblique.
    # La forme fautive ne reconnaissait AUCUN chemin a antislash, donc pas meme
    # `C:\Users\...`, et les signalait tous comme « pas un chemin Windows ».
    ressemble_windows = bool(re.match(r"^[A-Za-z]:[\\/]", texte))
    if sys.platform == "win32" and not ressemble_windows:
        return (
            f"« {texte} » n'est pas un chemin Windows. Il sera cree dans "
            f"{Path(texte).resolve()}, ce qui n'est probablement pas voulu."
        )
    if sys.platform != "win32" and ressemble_windows:
        return f"« {texte} » est un chemin Windows, sur une machine qui ne l'est pas."
    return None
