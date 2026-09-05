"""Sauvegarde et restauration d'une installation complete.

Demande a l'usage : « un systeme de sauvegarde complete de notre config, pour
la reinstaller. Ca eviterait de remettre tous les parametres des indexeurs
etc. »

C'est la distinction qui donne sa forme a ce module. PlugArr sait deja
regenerer tout ce qu'il a GENERE — mots de passe, cles API, ports : ils vivent
dans `stack.yml`. Il ne sait rien de ce que vous avez saisi ENSUITE. Vos
indexeurs sont dans la base SQLite de Prowlarr, vos profils dans celle de
Sonarr, vos listes de lecture dans celle de Jellyfin. Voila ce qu'une
reinstallation perdait.

Trois emplacements, et il faut les trois :

1. **le repertoire du projet** — `stack.yml`, `.env`, `docker-compose.yml`.
   Sans eux, les secrets generes sont perdus et aucun service ne se rouvre ;
2. **`CONFIG_ROOT`** — la configuration de chaque service. C'est le gros, et
   c'est ce qui contient votre travail ;
3. **les volumes Docker** — la base de Silo n'est PAS sous `CONFIG_ROOT`, elle
   vit dans un volume pour des raisons de vitesse. Une sauvegarde qui n'archive
   que des dossiers la manquerait en silence, et la restauration rendrait un
   Silo qui redemarre en boucle.

`DATA_ROOT` n'est jamais touche. Vos medias ne sont pas une configuration, ils
pesent des teraoctets, et les inclure transformerait une sauvegarde de trente
secondes en une nuit de copie.

**Les conteneurs sont arretes pendant la copie.** Une base SQLite copiee
pendant qu'on ecrit dedans donne un fichier valide en apparence et corrompu en
pratique — le genre de sauvegarde qui ne se revele inutilisable que le jour ou
l'on en a besoin. `--live` existe pour qui accepte ce risque en connaissance de
cause, et le dit.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from . import compose as compose_mod
from .i18n import t
from .models import StackConfig
from .runner import Compose, _run, volume_exists

#: Version du FORMAT d'archive, pas celle de PlugArr. Elle ne bouge que si la
#: disposition interne change, pour qu'une restauration sache dire « cette
#: archive vient d'une version que je ne sais pas lire » plutot que de deballer
#: n'importe quoi.
FORMAT = 1

MANIFESTE = "plugarr-sauvegarde.json"
DOSSIER_PROJET = "projet"
DOSSIER_CONFIG = "config"
DOSSIER_VOLUMES = "volumes"

#: Fichiers du repertoire de projet qui entrent dans l'archive. Le journal n'y
#: est pas : il raconte une installation passee, il ne la reconstitue pas.
FICHIERS_PROJET = ("stack.yml", ".env", "docker-compose.yml", ".gitignore")

#: Ce qu'on ne copie jamais depuis CONFIG_ROOT. Des caches et des journaux qui
#: se refabriquent, et qui pesent souvent plus lourd que la configuration
#: elle-meme — les miniatures de Jellyfin a elles seules.
EXCLUS = (
    "logs",
    "Logs",
    "cache",
    "Cache",
    "transcodes",
    "transcoding-temp",
    "metadata/library",
    "MediaCover",
    "Sentry",
    "data/transcodes",
)


@dataclass
class Rapport:
    """Ce qu'une sauvegarde a REELLEMENT ecrit."""

    archive: Path
    services: list[str]
    fichiers: int
    octets: int
    volumes: list[str]
    arret: bool

    @property
    def mega(self) -> float:
        return round(self.octets / 1_048_576, 1)


def _horodatage() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def nom_par_defaut(cfg: StackConfig) -> str:
    return f"plugarr-{cfg.project_name}-{_horodatage()}.zip"


def _exclu(chemin: Path, racine: Path) -> bool:
    relatif = chemin.relative_to(racine).as_posix()
    return any(f"/{relatif}/".find(f"/{motif}/") >= 0 for motif in EXCLUS)


def volumes_du_projet(cfg: StackConfig) -> list[str]:
    """Volumes Docker qui portent de l'etat a sauvegarder.

    Deduits du catalogue : la base de Silo et celle de DroppedNeedle
    aujourd'hui. Une sauvegarde qui n'archive que des dossiers les manquerait
    en silence, et la restauration rendrait des services qui refusent les
    identifiants annonces.
    """
    from .orchestrator import volumes_nommes

    return [
        nom
        for sid in cfg.services
        for nom in volumes_nommes(cfg, sid)
        if volume_exists(nom)
    ]


def _sauver_volume(nom: str, destination: Path) -> bool:
    """Copie le contenu d'un volume Docker dans une archive tar.

    On passe par un conteneur jetable qui monte le volume : c'est le seul moyen
    portable de lire un volume, dont l'emplacement reel sur le disque n'est ni
    documente ni accessible sous Windows.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    proc = _run(
        [
            "docker", "run", "--rm",
            "-v", f"{nom}:/source:ro",
            "-v", f"{destination.parent.as_posix()}:/sortie",
            "alpine:3.20",
            "tar", "-czf", f"/sortie/{destination.name}", "-C", "/source", ".",
        ],
        timeout=1800,
    )
    return proc.returncode == 0 and destination.exists()


def _restaurer_volume(nom: str, source: Path) -> bool:
    proc = _run(
        [
            "docker", "run", "--rm",
            "-v", f"{nom}:/cible",
            "-v", f"{source.parent.as_posix()}:/entree:ro",
            "alpine:3.20",
            "sh", "-c", f"rm -rf /cible/* /cible/..?* 2>/dev/null; tar -xzf /entree/{source.name} -C /cible",
        ],
        timeout=1800,
    )
    return proc.returncode == 0


def sauvegarder(
    cfg: StackConfig,
    project_dir: Path,
    destination: Path,
    *,
    live: bool = False,
    on_progress: Callable[[str], None] | None = None,
) -> Rapport:
    """Ecrit une archive complete. Renvoie ce qu'elle contient reellement."""
    dire = on_progress or (lambda _m: None)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    runner = Compose(project_dir, cfg.project_name)
    arrete = False
    if not live:
        dire(t("arret des conteneurs (une base copiee a chaud est corrompue)"))
        arrete, _ = runner.stop()

    try:
        volumes = volumes_du_projet(cfg)
        temporaires = destination.parent / f".{destination.stem}-volumes"
        archives_volumes: dict[str, Path] = {}
        for nom in volumes:
            dire(f"volume {nom}")
            cible = temporaires / f"{nom}.tar.gz"
            if _sauver_volume(nom, cible):
                archives_volumes[nom] = cible

        config_root = Path(cfg.config_root)
        fichiers = 0
        octets = 0
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for nom_fichier in FICHIERS_PROJET:
                source = project_dir / nom_fichier
                if source.is_file():
                    zf.write(source, f"{DOSSIER_PROJET}/{nom_fichier}")
                    fichiers += 1
                    octets += source.stat().st_size

            if config_root.is_dir():
                dire(f"configuration : {config_root}")
                for chemin in sorted(config_root.rglob("*")):
                    if not chemin.is_file() or _exclu(chemin, config_root):
                        continue
                    relatif = chemin.relative_to(config_root).as_posix()
                    try:
                        zf.write(chemin, f"{DOSSIER_CONFIG}/{relatif}")
                    except (OSError, PermissionError):
                        # Un fichier verrouille ne doit pas faire echouer toute
                        # la sauvegarde : on le note et on continue.
                        dire(f"ignore (verrouille) : {relatif}")
                        continue
                    fichiers += 1
                    octets += chemin.stat().st_size

            for nom, chemin in archives_volumes.items():
                zf.write(chemin, f"{DOSSIER_VOLUMES}/{nom}.tar.gz")
                fichiers += 1
                octets += chemin.stat().st_size

            zf.writestr(
                MANIFESTE,
                json.dumps(
                    {
                        "format": FORMAT,
                        "date": datetime.now(UTC).isoformat(timespec="seconds"),
                        "project_name": cfg.project_name,
                        "config_root": cfg.config_root,
                        "data_root": cfg.data_root,
                        "services": sorted(cfg.services),
                        "volumes": sorted(archives_volumes),
                        "a_chaud": live,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
            )
        shutil.rmtree(temporaires, ignore_errors=True)
    finally:
        if arrete:
            dire(t("redemarrage des conteneurs"))
            runner.up()

    compose_mod._restrict(destination)
    return Rapport(
        archive=destination,
        services=sorted(cfg.services),
        fichiers=fichiers,
        octets=octets,
        volumes=sorted(archives_volumes),
        arret=arrete,
    )


def lire_manifeste(archive: Path) -> dict:
    """Manifeste d'une archive, sans rien deballer.

    `zipfile.BadZipFile` herite d'`Exception`, PAS de `ValueError` ni
    d'`OSError` : les deux appelants la laissaient donc passer, et un fichier
    qui n'est pas une archive faisait sortir `plugarr restore` sur une trace
    Python brute. Constate en lancant l'executable publie sur un fichier
    texte renomme en .zip. On la convertit ici, une fois, plutot que dans
    chaque appelant.
    """
    try:
        zf = zipfile.ZipFile(archive)
    except zipfile.BadZipFile as exc:
        raise ValueError(
            t("{fichier} n'est pas une archive lisible", fichier=archive.name)
        ) from exc
    with zf:
        if MANIFESTE not in zf.namelist():
            raise ValueError(
                t("{fichier} n'est pas une sauvegarde PlugArr", fichier=archive.name)
            )
        manifeste = json.loads(zf.read(MANIFESTE))
    if manifeste.get("format") != FORMAT:
        raise ValueError(
            t(
                "archive au format {trouve}, cette version lit le format {attendu}",
                trouve=manifeste.get("format"),
                attendu=FORMAT,
            )
        )
    return manifeste


def restaurer(
    archive: Path,
    project_dir: Path,
    *,
    config_root: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> dict:
    """Deballe une archive. Renvoie son manifeste.

    `config_root` permet de restaurer AILLEURS que l'origine : une machine
    neuve n'a pas forcement les memes lettres de lecteur. Les chemins de
    `stack.yml` et du `.env` sont alors reecrits, sans quoi la pile pointerait
    vers un dossier inexistant.
    """
    dire = on_progress or (lambda _m: None)
    manifeste = lire_manifeste(archive)
    cible_config = Path(config_root or manifeste["config_root"])
    project_dir.mkdir(parents=True, exist_ok=True)
    cible_config.mkdir(parents=True, exist_ok=True)

    temporaires = project_dir / ".plugarr-restauration"
    shutil.rmtree(temporaires, ignore_errors=True)
    temporaires.mkdir(parents=True)

    try:
        with zipfile.ZipFile(archive) as zf:
            for membre in zf.namelist():
                if membre.startswith(f"{DOSSIER_PROJET}/"):
                    nom = membre.split("/", 1)[1]
                    if nom:
                        (project_dir / nom).write_bytes(zf.read(membre))
                elif membre.startswith(f"{DOSSIER_CONFIG}/"):
                    relatif = membre.split("/", 1)[1]
                    if not relatif or membre.endswith("/"):
                        continue
                    cible = cible_config / relatif
                    cible.parent.mkdir(parents=True, exist_ok=True)
                    cible.write_bytes(zf.read(membre))
                elif membre.startswith(f"{DOSSIER_VOLUMES}/"):
                    (temporaires / Path(membre).name).write_bytes(zf.read(membre))

        for nom in manifeste.get("volumes", []):
            source = temporaires / f"{nom}.tar.gz"
            if source.is_file():
                dire(f"volume {nom}")
                _restaurer_volume(nom, source)

        if config_root and config_root != manifeste["config_root"]:
            dire(f"chemins reecrits vers {config_root}")
            _reecrire_chemins(project_dir, manifeste["config_root"], config_root)
    finally:
        shutil.rmtree(temporaires, ignore_errors=True)

    for nom in (".env", "stack.yml"):
        chemin = project_dir / nom
        if chemin.is_file():
            compose_mod._restrict(chemin)
    return manifeste


def _reecrire_chemins(project_dir: Path, ancien: str, nouveau: str) -> None:
    """Remplace l'ancienne racine de configuration dans stack.yml et .env."""
    stack = project_dir / "stack.yml"
    if stack.is_file():
        donnees = yaml.safe_load(stack.read_text(encoding="utf-8"))
        donnees["config_root"] = nouveau
        stack.write_text(yaml.safe_dump(donnees, sort_keys=False), encoding="utf-8")
    env = project_dir / ".env"
    if env.is_file():
        # Les separateurs sont normalises a la generation : on compare sur la
        # meme forme, sinon un antislash Windows fait rater le remplacement.
        texte = env.read_text(encoding="utf-8")
        env.write_text(
            texte.replace(ancien.replace("\\", "/"), nouveau.replace("\\", "/")),
            encoding="utf-8",
        )
