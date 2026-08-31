"""Orchestration : preflight, pre-semis, generation, demarrage, cablage.

Ce module ne connait NI Typer NI Textual. La CLI et le TUI l'appellent tous les
deux, et ne font que rendre les evenements qu'il emet. C'est ce qui garantit que
le wizard et la ligne de commande ne divergeront jamais.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from . import catalog, compose, dashboard, seed
from .clients.arr import ArrClient
from .layout import PROFILE_DEFAULTS, create_tree, resolve_ids
from .models import PlatformProfile, ServiceInstance, StackConfig
from .runner import (
    Check,
    Compose,
    check_disk_space,
    check_docker,
    check_hardlinks,
    check_port_free,
)
from .wiring import StepResult, Wirer


class InstallAborted(RuntimeError):
    """Echec bloquant : le message est destine a l'utilisateur tel quel."""


@dataclass
class Progress:
    """Evenement d'avancement, rendu differemment par la CLI et par le TUI."""

    phase: str
    message: str
    ok: bool = True
    done: bool = False


ProgressFn = Callable[[Progress], None]


def _noop(_: Progress) -> None:
    return None


# ----------------------------------------------------------------- construction


def build_config(
    *,
    services: list[str],
    config_root: str | None = None,
    data_root: str | None = None,
    platform: PlatformProfile = PlatformProfile.GENERIC_LINUX,
    host: str = "localhost",
    timezone: str = "Etc/UTC",
) -> StackConfig:
    """Construit une StackConfig complete, secrets generes.

    Les prerequis manquants sont ajoutes automatiquement : cocher Flood tire
    Transmission.
    """
    defaults = PROFILE_DEFAULTS[platform]
    uid, gid, source, certain = resolve_ids(platform)

    cfg = StackConfig(
        platform=platform,
        config_root=config_root or defaults.config_root,
        data_root=data_root or defaults.data_root,
        puid=uid,
        pgid=gid,
        timezone=timezone,
        host=host,
        ids_source=source,
        ids_certain=certain,
    )
    for sid in catalog.resolve_dependencies(services):
        spec = catalog.get(sid)
        inst = ServiceInstance(spec_id=sid, host_port=spec.default_host_port)
        if spec.api_family == "arr":
            inst.api_key = seed.generate_api_key()
        if spec.api_family in ("arr", "transmission", "qbittorrent", "jellyfin"):
            inst.username = "arrsenal"
            inst.password = seed.generate_password()
        cfg.services[sid] = inst
    return cfg


def preflight(cfg: StackConfig) -> list[Check]:
    checks = check_docker()
    for sid in catalog.STARTUP_ORDER:
        if cfg.enabled(sid):
            checks.append(check_port_free(cfg.services[sid].host_port, sid))
    checks.append(check_disk_space(cfg.data_root))
    checks.append(check_hardlinks(cfg.data_root))
    return checks


def blocking_failures(checks: list[Check]) -> list[Check]:
    return [c for c in checks if not c.ok and c.blocking]


def seed_all(cfg: StackConfig) -> list[str]:
    """Pre-seme les configurations. Renvoie les actions effectuees.

    Un fichier existant fait toujours autorite : on adopte sa cle plutot que de
    lui imposer la notre.
    """
    actions: list[str] = []
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        spec, inst = catalog.get(sid), cfg.services[sid]
        cfg_dir = Path(cfg.config_path(sid))

        if spec.api_family == "arr":
            effective, written = seed.seed_arr(
                cfg_dir,
                api_key=inst.api_key or "",
                port=spec.internal_port,
                instance_name=spec.display_name,
                username=inst.username or "arrsenal",
                password=inst.password or "",
            )
            if not written:
                inst.api_key = effective
            actions.append(
                f"{sid} : config.xml {'pre-seme' if written else 'existant, cle reprise'}"
            )
        elif spec.api_family == "qbittorrent":
            _written, message = seed.seed_qbittorrent(
                cfg_dir,
                username=inst.username or "arrsenal",
                password=inst.password or "",
                port=spec.internal_port,
            )
            actions.append(f"{sid} : {message}")
        elif spec.api_family == "transmission":
            _written, message = seed.seed_transmission(
                cfg_dir,
                rpc_username=inst.username or "arrsenal",
                rpc_password=inst.password or "",
            )
            actions.append(f"{sid} : {message}")
    return actions


def wait_for_arrs(cfg: StackConfig, on_progress: ProgressFn = _noop) -> None:
    """Attend que chaque *arr reponde AVEC NOTRE CLE, pas juste qu'il ecoute."""
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        spec, inst = catalog.get(sid), cfg.services[sid]
        if spec.api_family != "arr":
            continue
        with ArrClient(
            inst.url(cfg.host), inst.api_key or "", api_version=spec.api_version, name=sid
        ) as client:
            client.wait_ready()
            on_progress(Progress("attente", f"{spec.display_name} {client.version}"))


# -------------------------------------------------------------------- pipeline


def install(
    cfg: StackConfig,
    project_dir: Path,
    *,
    on_progress: ProgressFn = _noop,
    on_step: Callable[[StepResult], None] | None = None,
) -> list[StepResult]:
    """Deroule l'installation complete et renvoie le resultat du cablage.

    Leve InstallAborted avec un message actionnable en cas d'echec bloquant.
    """
    created = create_tree(cfg.data_root, cfg.config_root, list(cfg.services))
    on_progress(Progress("arborescence", f"{len(created)} dossiers crees"))

    for action in seed_all(cfg):
        on_progress(Progress("pre-semis", action))

    written = compose.write_artifacts(cfg, project_dir)
    on_progress(Progress("artefacts", ", ".join(p.name for p in written)))

    runner = Compose(project_dir, cfg.project_name)
    valid, message = runner.config_valid()
    if not valid:
        raise InstallAborted(f"Le fichier compose genere est invalide : {message}")

    on_progress(Progress("demarrage", "docker compose up (peut prendre plusieurs minutes)"))
    ok, message = runner.up()
    if not ok:
        raise InstallAborted(f"docker compose up a echoue : {message}")

    wait_for_arrs(cfg, on_progress)

    wirer = Wirer(cfg)
    try:
        results = wirer.execute(on_step=on_step)
    finally:
        wirer.close()

    # Le cablage enrichit la config : la cle API Jellyfin n'existe qu'apres son
    # assistant de demarrage. On repersiste pour que .env et stack.yml soient
    # complets et que `wire` reste rejouable seul.
    compose.write_artifacts(cfg, project_dir)

    page = dashboard.write(cfg, project_dir, failed=sum(1 for r in results if not r.ok))
    on_progress(Progress("page d'acces", str(page)))

    on_progress(Progress("cablage", "termine", ok=all(r.ok for r in results), done=True))
    return results


# ------------------------------------------------------------------ inspection


def has_download_client(cfg: StackConfig) -> bool:
    """Un client de telechargement est-il installe ?

    Sans lui, l'avertissement VPN n'a aucun sens : il n'y a pas de trafic
    BitTorrent a proteger.
    """
    return any(cfg.enabled(sid) for sid in catalog.DOWNLOAD_CLIENTS)


def planned_links(cfg: StackConfig) -> int:
    """Nombre de liens que le cablage va poser. Sert au recapitulatif."""
    return len(Wirer(cfg).build_plan())


def iter_selected(cfg: StackConfig) -> Iterator[tuple[str, ServiceInstance]]:
    for sid in catalog.STARTUP_ORDER:
        if cfg.enabled(sid):
            yield sid, cfg.services[sid]
