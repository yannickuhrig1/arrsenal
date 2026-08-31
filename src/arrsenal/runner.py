"""Pilotage de docker compose et preflight."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .layout import hardlink_supported


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    blocking: bool = True


def _run(args: list[str], cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
    )


# --------------------------------------------------------------------- preflight


def check_docker() -> list[Check]:
    checks: list[Check] = []
    binary = shutil.which("docker")
    if not binary:
        return [
            Check(
                "docker",
                False,
                "binaire `docker` introuvable dans le PATH. Installez Docker Engine "
                "ou Docker Desktop, puis relancez.",
            )
        ]
    checks.append(Check("docker", True, f"trouve: {binary}"))

    info = _run(["docker", "info", "--format", "{{.ServerVersion}}"])
    if info.returncode != 0:
        checks.append(
            Check(
                "daemon docker",
                False,
                "le binaire repond mais le daemon est injoignable. Demarrez Docker "
                f"(Desktop, ou `systemctl start docker`). Detail: {info.stderr.strip()[:200]}",
            )
        )
        return checks
    checks.append(Check("daemon docker", True, f"version serveur {info.stdout.strip()}"))

    compose = _run(["docker", "compose", "version", "--short"])
    checks.append(
        Check(
            "docker compose",
            compose.returncode == 0,
            f"v{compose.stdout.strip()}"
            if compose.returncode == 0
            else "plugin `docker compose` absent. Installez docker-compose-plugin.",
        )
    )
    return checks


def check_port_free(port: int, label: str) -> Check:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        busy = sock.connect_ex(("127.0.0.1", port)) == 0
    return Check(
        f"port {port} ({label})",
        not busy,
        "libre" if not busy else f"deja utilise. Changez le port de {label} dans stack.yml.",
    )


def check_hardlinks(data_root: str | Path) -> Check:
    ok, detail = hardlink_supported(data_root)
    # Non bloquant : la stack fonctionne sans hardlinks, elle est juste beaucoup
    # moins efficace. L'utilisateur doit le savoir, pas etre arrete.
    return Check("hardlinks /data", ok, detail, blocking=False)


def check_disk_space(path: str | Path, min_gb: int = 20) -> Check:
    try:
        usage = shutil.disk_usage(Path(path).anchor or str(path))
    except OSError as exc:
        return Check("espace disque", False, f"impossible de lire {path}: {exc}", blocking=False)
    free_gb = usage.free / 1024**3
    return Check(
        "espace disque",
        free_gb >= min_gb,
        f"{free_gb:.1f} Go libres"
        + ("" if free_gb >= min_gb else f" - moins que le minimum conseille de {min_gb} Go"),
        blocking=False,
    )


# ---------------------------------------------------------------------- compose


class Compose:
    def __init__(self, project_dir: Path, project_name: str):
        self.dir = project_dir
        self.name = project_name

    def _cmd(self, *args: str) -> list[str]:
        return ["docker", "compose", "-p", self.name, *args]

    def up(self, timeout: int = 1800) -> tuple[bool, str]:
        proc = _run(self._cmd("up", "-d", "--remove-orphans"), cwd=self.dir, timeout=timeout)
        return proc.returncode == 0, (proc.stderr or proc.stdout).strip()

    def down(self, *, volumes: bool = False) -> tuple[bool, str]:
        args = ["down"] + (["-v"] if volumes else [])
        proc = _run(self._cmd(*args), cwd=self.dir)
        return proc.returncode == 0, (proc.stderr or proc.stdout).strip()

    def config_valid(self) -> tuple[bool, str]:
        proc = _run(self._cmd("config", "--quiet"), cwd=self.dir)
        return proc.returncode == 0, (proc.stderr or "compose valide").strip()

    def ps(self) -> str:
        return _run(self._cmd("ps"), cwd=self.dir).stdout

    def ps_json(self) -> list[dict]:
        """Etat de chaque service.

        Docker Compose 5.x emet un objet JSON PAR LIGNE ; les versions plus
        anciennes emettent un tableau unique. Les deux formes sont acceptees.
        """
        proc = _run(self._cmd("ps", "--all", "--format", "json"), cwd=self.dir)
        raw = (proc.stdout or "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            entries = []
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return entries
        return parsed if isinstance(parsed, list) else [parsed]

    def control(self, action: str, service: str) -> tuple[bool, str]:
        """Demarre, arrete ou redemarre UN service.

        `action` et `service` sont valides par l'appelant contre des listes
        fermees : ils finissent dans une ligne de commande.
        """
        if action not in ("start", "stop", "restart"):
            raise ValueError(f"action non autorisee: {action!r}")
        proc = _run(self._cmd(action, service), cwd=self.dir, timeout=180)
        return proc.returncode == 0, (proc.stderr or proc.stdout).strip()

    def logs(self, service: str, tail: int = 50) -> str:
        return _run(self._cmd("logs", "--tail", str(tail), service), cwd=self.dir).stdout
