"""Configuration de Recyclarr.

Recyclarr synchronise les profils de qualite et les custom formats des TRaSH
Guides vers Sonarr et Radarr. arrsenal ne reimplemente rien : il demande a
Recyclarr de generer sa configuration a partir d'un template OFFICIEL, puis se
contente d'y ecrire l'adresse et la cle API. La repartition est nette — TRaSH
fournit les profils, arrsenal fournit le cablage.

Trois choses relevees sur l'image 8.7.1, aucune devinable :

- `config create --template X` ignore `--path` et ecrit `/config/configs/X.yml`,
  un fichier par template. Recyclarr charge ensuite tout ce dossier ;
- les templates arrivent avec des marqueurs en clair : `base_url: Put your Sonarr
  URL here` et `api_key: Put your API key here`. Ce sont eux qu'on remplace ;
- le conteneur n'a pas d'interface web. Il tourne sur une planification,
  `CRON_SCHEDULE=@daily` par defaut.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: Marqueurs poses par les templates officiels. Les remplacer est tout ce
#: qu'arrsenal a a faire.
#:
#: On borne l'espace a l'espace HORIZONTAL. `\s` matche aussi le retour a la
#: ligne : un `\s*$` gourmand avale les lignes vides qui suivent le marqueur et
#: reformate le fichier des TRaSH Guides au passage, ce que ce module s'interdit.
_HSPACE = r"[^\S\n]*"
_URL_MARKER = re.compile(
    rf"^({_HSPACE}base_url:{_HSPACE}).*Put your .* URL here{_HSPACE}$", re.MULTILINE
)
_KEY_MARKER = re.compile(
    rf"^({_HSPACE}api_key:{_HSPACE}).*Put your API key here{_HSPACE}$", re.MULTILINE
)

#: Templates par defaut. Choisis parce qu'ils sont les points de depart les plus
#: courants des TRaSH Guides, pas parce qu'ils conviendraient a tout le monde :
#: le materiel et la bande passante decident, et l'utilisateur peut en changer.
DEFAULT_TEMPLATES = {"sonarr": "web-1080p", "radarr": "hd-bluray-web"}


@dataclass
class Filled:
    path: Path
    service: str
    url_written: bool
    key_written: bool

    @property
    def ok(self) -> bool:
        return self.url_written and self.key_written


def template_names(config_dir: Path, service: str) -> list[str]:
    """Templates officiels presents sur disque, pour un service donne.

    Recyclarr clone le depot des templates dans son dossier de ressources au
    premier demarrage. On lit ce qu'il a reellement, plutot que d'embarquer une
    liste qui vieillirait.
    """
    folder = (
        config_dir / "resources" / "config-templates" / "git" / "official" / service / "templates"
    )
    if not folder.is_dir():
        return []
    return sorted(p.stem for p in folder.glob("*.yml"))


def fill(config_file: Path, base_url: str, api_key: str, service: str) -> Filled:
    """Ecrit l'adresse et la cle dans un fichier genere par Recyclarr.

    On remplace les marqueurs, on ne reecrit pas le fichier : tout le reste vient
    des TRaSH Guides et doit rester intact.
    """
    text = config_file.read_text(encoding="utf-8")
    # Le remplacement passe par une fonction, pas par une chaine : dans une chaine
    # de remplacement, re interprete les antislashs. Une url_base saisie a la main
    # avec un antislash ferait lever « bad escape » au lieu d'ecrire le fichier.
    text, url_count = _URL_MARKER.subn(lambda m: m.group(1) + base_url, text)
    text, key_count = _KEY_MARKER.subn(lambda m: m.group(1) + api_key, text)
    if url_count or key_count:
        config_file.write_text(text, encoding="utf-8")
    return Filled(
        path=config_file,
        service=service,
        url_written=bool(url_count),
        key_written=bool(key_count),
    )


def target_service(config_file: Path) -> str | None:
    """Quel service ce fichier configure-t-il ?

    Le template le declare a la racine du YAML : `sonarr:` ou `radarr:`. On le lit
    plutot que de se fier au nom du fichier, qui n'est qu'un titre de template.
    """
    try:
        for line in config_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("sonarr:", "radarr:")):
                return stripped.rstrip(":").strip()
    except OSError:
        return None
    return None


def pending_markers(config_dir: Path) -> list[Path]:
    """Fichiers ou un marqueur n'a pas ete remplace.

    Un marqueur oublie fait echouer la synchronisation avec un message obscur :
    mieux vaut le detecter avant.
    """
    configs = config_dir / "configs"
    if not configs.is_dir():
        return []
    return [
        path
        for path in sorted(configs.glob("*.yml"))
        if "Put your" in path.read_text(encoding="utf-8")
    ]
