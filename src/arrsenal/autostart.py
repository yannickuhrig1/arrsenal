"""Lancement automatique de la console d'administration, sur l'HOTE.

Pourquoi pas dans un conteneur, alors que c'est la demande naturelle : la
console doit creer, demarrer et recreer des conteneurs. Traduit en API Docker,
cela veut dire `POST /containers/create` puis `/start` — et un conteneur qu'on
cree peut monter la racine de l'hote et tourner en root. Un proxy de socket qui
autorise ces deux appels n'enferme donc rien, et sans eux la console ne peut
plus rien faire. Mettre cette console dans un conteneur avec le socket revient
a exposer sur le reseau un service qui a les pleins pouvoirs sur la machine.

Sur l'hote, elle tourne sous le compte de l'utilisateur, ecoute sur 127.0.0.1,
et n'est pas joignable depuis le reseau Docker. Le confort recherche — ne plus
avoir a lancer une commande — est le meme.

Trois mecanismes, aucun n'exigeant les droits administrateur :

- **Windows** : un raccourci dans le dossier Demarrage de l'utilisateur. Visible,
  supprimable a la main, aucune elevation. `schtasks` ferait la meme chose en
  moins lisible et en demandant parfois une elevation ;
- **systemd** : une unite UTILISATEUR dans `~/.config/systemd/user/`. Attention,
  elle s'arrete a la deconnexion tant que `loginctl enable-linger` n'a pas ete
  passe : c'est dit, pas cache ;
- **ailleurs** (Unraid, Synology, BSD) : rien d'automatique. On rend la commande
  a coller, plutot que d'inventer un mecanisme non verifie.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

NOM = "arrsenal-console"
UNIT = f"{NOM}.service"


@dataclass
class Etat:
    """Ce qui est en place, et ou."""

    mecanisme: str
    actif: bool
    chemin: Path | None = None
    detail: str = ""


def mecanisme() -> str:
    """Quel mecanisme cette machine sait utiliser."""
    if sys.platform == "win32":
        return "demarrage-windows"
    if shutil.which("systemctl"):
        return "systemd-utilisateur"
    return "aucun"


# ------------------------------------------------------------------ Windows


def _dossier_demarrage() -> Path:
    """Dossier Demarrage de l'utilisateur courant.

    `APPDATA` est defini sur toute session Windows ; le chemin qui suit est fixe
    depuis Windows 7 et n'est pas localise, contrairement a son affichage dans
    l'explorateur.
    """
    import os

    return (
        Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
        / "Microsoft/Windows/Start Menu/Programs/Startup"
    )


def _script_windows(commande: str) -> str:
    return (
        "@echo off\r\n"
        "rem Genere par `arrsenal autostart`. Supprimez ce fichier pour arreter\r\n"
        "rem le lancement automatique de la console d'administration.\r\n"
        "title arrsenal - console\r\n"
        f"{commande}\r\n"
    )


# ------------------------------------------------------------------ systemd


def _dossier_systemd() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def _unite_systemd(commande: str, project_dir: Path) -> str:
    return (
        "[Unit]\n"
        "Description=Console d'administration arrsenal\n"
        "After=docker.service\n"
        "\n"
        "[Service]\n"
        f"WorkingDirectory={project_dir}\n"
        f"ExecStart={commande}\n"
        "Restart=on-failure\n"
        "RestartSec=10\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def _systemctl(*args: str) -> tuple[bool, str]:
    proc = subprocess.run(
        ["systemctl", "--user", *args], capture_output=True, text=True, timeout=60, check=False
    )
    return proc.returncode == 0, (proc.stderr or proc.stdout).strip()


# ------------------------------------------------------------------- actions


def commande(project_dir: Path, *, host: str, port: int) -> str:
    """Commande a lancer au demarrage.

    Reprend le chemin REELLEMENT utilise : quelqu'un qui a double-clique un
    executable n'a pas `arrsenal` dans son PATH.

    `--no-open` est essentiel : ouvrir un navigateur a chaque ouverture de
    session serait insupportable.
    """
    cible = f'"{Path(project_dir).resolve()}"'
    base = f'"{Path(sys.executable).resolve()}"'
    if not getattr(sys, "frozen", False):
        base += " -m arrsenal"
    return f"{base} serve --project-dir {cible} --host {host} --port {port} --no-open"


def status(project_dir: Path) -> Etat:
    """Le lancement automatique est-il en place ?"""
    quel = mecanisme()
    if quel == "demarrage-windows":
        cible = _dossier_demarrage() / f"{NOM}.cmd"
        return Etat(quel, cible.is_file(), cible)
    if quel == "systemd-utilisateur":
        cible = _dossier_systemd() / UNIT
        actif, sortie = _systemctl("is-enabled", UNIT)
        return Etat(quel, cible.is_file() and actif, cible, sortie)
    return Etat(quel, False, None, "aucun mecanisme connu sur cette plateforme")


def enable(project_dir: Path, *, host: str = "127.0.0.1", port: int = 7373) -> tuple[bool, str]:
    """Installe le lancement automatique. Renvoie (succes, message)."""
    quel = mecanisme()
    ligne = commande(project_dir, host=host, port=port)

    if quel == "demarrage-windows":
        dossier = _dossier_demarrage()
        dossier.mkdir(parents=True, exist_ok=True)
        cible = dossier / f"{NOM}.cmd"
        cible.write_text(_script_windows(ligne), encoding="utf-8", newline="")
        return True, f"lancement automatique installe : {cible}"

    if quel == "systemd-utilisateur":
        dossier = _dossier_systemd()
        dossier.mkdir(parents=True, exist_ok=True)
        cible = dossier / UNIT
        cible.write_text(_unite_systemd(ligne, Path(project_dir).resolve()), encoding="utf-8")
        _systemctl("daemon-reload")
        ok, sortie = _systemctl("enable", "--now", UNIT)
        if not ok:
            return False, f"systemctl a refuse : {sortie[:300]}"
        return True, f"unite installee et demarree : {cible}"

    return False, (
        "aucun mecanisme de lancement automatique connu sur cette plateforme. "
        f"Lancez cette commande au demarrage de votre machine :\n  {ligne}"
    )


def disable(project_dir: Path) -> tuple[bool, str]:
    """Retire le lancement automatique."""
    quel = mecanisme()

    if quel == "demarrage-windows":
        cible = _dossier_demarrage() / f"{NOM}.cmd"
        if not cible.is_file():
            return True, "aucun lancement automatique installe"
        cible.unlink()
        return True, f"retire : {cible}"

    if quel == "systemd-utilisateur":
        cible = _dossier_systemd() / UNIT
        _systemctl("disable", "--now", UNIT)
        if cible.is_file():
            cible.unlink()
        _systemctl("daemon-reload")
        return True, f"unite retiree : {cible}"

    return True, "aucun mecanisme installe sur cette plateforme"
