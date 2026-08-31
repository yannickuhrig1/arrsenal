"""Generation de docker-compose.yml et .env.

Artefacts derives de StackConfig, jamais edites a la main.

Le rendu du client torrent existe en DEUX formes (PROMPT.md sec. 11.1) : avec et
sans VPN. Avec Gluetun le service perd son propre reseau et ses ports publies
migrent vers le conteneur VPN. La bascule est prevue ici des le depart pour ne pas
etre une rustine plus tard, meme si la Phase 1 n'expose que la forme sans VPN.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from . import catalog
from .models import Category, StackConfig

NETWORK_NAME = "arrsenal"

#: Tag epingle de Gluetun. Le depot a ete transfere de qdm12/gluetun vers
#: passteque/gluetun ; l'image, elle, reste qmcgaw/gluetun.
GLUETUN_TAG = "v3.41.3"
_HEADER = (
    "# Genere par arrsenal - NE PAS EDITER A LA MAIN.\n"
    "# Modifiez stack.yml puis relancez `arrsenal generate`.\n"
)


def _flood_block(cfg: StackConfig) -> dict:
    """Options de Flood, selon le client de telechargement present.

    Flood n'est pas une image LinuxServer : ni PUID/PGID, ni UMASK. Il se
    configure entierement par ligne de commande.

    Les options ont ete relevees sur `flood --help` de l'image 4.16.1, pas
    supposees : `--qburl/--qbuser/--qbpass` pour qBittorrent,
    `--trurl/--truser/--trpass` pour Transmission.

    Quand les deux clients sont installes, qBittorrent gagne : son API est plus
    riche et Flood n'en pilote qu'un a la fois.
    """
    block: dict = {
        "environment": {"HOME": "/config", "TZ": cfg.timezone},
        "command": ["--port=3000", "--host=0.0.0.0", "--auth=none"],
    }
    for client_id, options in (
        ("qbittorrent", ("--qburl", "--qbuser", "--qbpass")),
        ("transmission", ("--trurl", "--truser", "--trpass")),
    ):
        if not cfg.enabled(client_id):
            continue
        spec, inst = catalog.get(client_id), cfg.services[client_id]
        base = f"http://{spec.id}:{spec.internal_port}"
        url_option, user_option, pass_option = options
        block["command"] += [
            url_option,
            base if client_id == "qbittorrent" else f"{base}/transmission/rpc",
            user_option,
            inst.username or "",
            pass_option,
            inst.password or "",
        ]
        block["depends_on"] = [client_id]
        break
    return block


def _gluetun_block(cfg: StackConfig) -> dict:
    """Le conteneur VPN, et les ports qu'il porte a la place du client.

    Un service en `network_mode: service:gluetun` n'a plus de pile reseau propre :
    il ne PEUT plus publier de port. Les siens doivent donc etre declares ici,
    sinon son interface web devient injoignable — panne silencieuse et tres
    deroutante.

    `cap_add: NET_ADMIN` et `/dev/net/tun` sont indispensables pour monter le
    tunnel. Le healthcheck est fourni par l'image elle-meme (verifie sur la
    v3.41.3), ce qui permet aux services qui en dependent d'attendre une
    connexion VPN reellement etablie, et pas seulement un conteneur demarre.
    """
    ports = []
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        spec = catalog.get(sid)
        if spec.category is Category.DOWNLOAD:
            ports.append(f"{cfg.services[sid].host_port}:{spec.internal_port}")
    return {
        "image": f"qmcgaw/gluetun:{GLUETUN_TAG}",
        "container_name": f"{cfg.project_name}-gluetun",
        "restart": "unless-stopped",
        "labels": {"arrsenal.managed": "true", "arrsenal.service": "gluetun"},
        "cap_add": ["NET_ADMIN"],
        "devices": ["/dev/net/tun:/dev/net/tun"],
        "environment": cfg.vpn.environment(cfg.timezone),
        "volumes": ["${CONFIG_ROOT}/gluetun:/gluetun"],
        "ports": ports,
        "networks": [NETWORK_NAME],
    }


def _service_block(cfg: StackConfig, service_id: str) -> dict:
    spec = catalog.get(service_id)
    inst = cfg.services[service_id]

    block: dict = {
        # L'image vient de l'INSTANCE, pas du catalogue : c'est ce qui permet de
        # mettre a jour un service sans attendre une nouvelle version d'arrsenal.
        "image": inst.image or spec.image,
        # Prefixe par le nom de projet, pour ne PAS entrer en collision avec une
        # stack existante. Beaucoup de NAS font deja tourner un conteneur nomme
        # `sonarr` : sans ce prefixe, `docker compose up` echoue ou, pire, prend
        # la place du conteneur de production.
        # Le cablage n'est pas affecte : les conteneurs se joignent par leur nom de
        # SERVICE compose (`http://sonarr:8989`), pas par container_name.
        "container_name": f"{cfg.project_name}-{spec.id}",
        "restart": "unless-stopped",
        # Marqueur explicite, pour que `scan` reconnaisse nos propres conteneurs
        # sans deviner d'apres leur nom. Deviner produisait des faux positifs sur
        # des noms legitimes comme "mon-sonarr" ou "media-sonarr", et sautait donc
        # en silence des conteneurs qui ne nous appartiennent pas.
        "labels": {"arrsenal.managed": "true", "arrsenal.service": spec.id},
        "environment": {
            "PUID": str(cfg.puid),
            "PGID": str(cfg.pgid),
            "TZ": cfg.timezone,
            "UMASK": cfg.umask,
        },
        "volumes": [
            f"${{CONFIG_ROOT}}/{spec.config_dir}:/config",
            "${DATA_ROOT}:/data",
        ],
        "networks": [NETWORK_NAME],
    }

    if service_id == "flood":
        block.update(_flood_block(cfg))
    elif service_id == "qui":
        # qui n'est pas une image LinuxServer : ni PUID/PGID ni UMASK. Il decouvre
        # ses instances qBittorrent par sa propre interface, on ne fait que lui
        # donner un port et un dossier de donnees.
        block["environment"] = {"TZ": cfg.timezone, "QUI__HOST": "0.0.0.0"}
        block["volumes"] = [f"${{CONFIG_ROOT}}/{spec.config_dir}:/config"]
        block["depends_on"] = ["qbittorrent"]
    elif service_id == "autobrr":
        # autobrr n'a pas besoin de /data : il ne touche pas aux fichiers, il
        # pousse des sorties vers les applications.
        block["volumes"] = [f"${{CONFIG_ROOT}}/{spec.config_dir}:/config"]

    torrent_client = spec.category is Category.DOWNLOAD
    if cfg.vpn_enabled and torrent_client:
        # Forme VPN : le client perd son reseau et ses ports. Gluetun les porte.
        block.pop("networks", None)
        block["network_mode"] = "service:gluetun"
        block["depends_on"] = {"gluetun": {"condition": "service_healthy"}}
    else:
        block["ports"] = [f"{inst.host_port}:{spec.internal_port}"]

    return block


def build_compose(cfg: StackConfig) -> dict:
    services = {
        sid: _service_block(cfg, sid)
        for sid in catalog.STARTUP_ORDER
        if cfg.enabled(sid)
    }
    if not services:
        raise ValueError("aucun service selectionne")
    if cfg.vpn.enabled:
        gaps = cfg.vpn.missing()
        if gaps:
            raise ValueError("VPN active mais incomplet : il manque " + ", ".join(gaps))
        services = {"gluetun": _gluetun_block(cfg), **services}
    return {
        "name": cfg.project_name,
        "services": services,
        "networks": {NETWORK_NAME: {"driver": "bridge"}},
    }


def render_compose(cfg: StackConfig) -> str:
    return _HEADER + yaml.safe_dump(
        build_compose(cfg), sort_keys=False, default_flow_style=False, width=100
    )


def render_env(cfg: StackConfig) -> str:
    lines = [
        "# Genere par arrsenal. Contient des secrets : ne JAMAIS commiter.",
        f"COMPOSE_PROJECT_NAME={cfg.project_name}",
        f"CONFIG_ROOT={cfg.config_root}",
        f"DATA_ROOT={cfg.data_root}",
        f"PUID={cfg.puid}",
        f"PGID={cfg.pgid}",
        f"TZ={cfg.timezone}",
        f"UMASK={cfg.umask}",
        "",
        "# Cles API pre-semees - utilisees par le cablage automatique.",
    ]
    for sid in catalog.STARTUP_ORDER:
        inst = cfg.services.get(sid)
        if inst is None:
            continue
        up = sid.upper()
        if inst.api_key:
            lines.append(f"{up}_API_KEY={inst.api_key}")
        if inst.username:
            lines.append(f"{up}_USER={inst.username}")
        if inst.password:
            lines.append(f"{up}_PASS={inst.password}")
    return "\n".join(lines) + "\n"


def write_artifacts(cfg: StackConfig, target_dir: Path) -> list[Path]:
    """Ecrit docker-compose.yml, .env et stack.yml. Renvoie les chemins ecrits."""
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    compose_path = target_dir / "docker-compose.yml"
    compose_path.write_text(render_compose(cfg), encoding="utf-8")
    written.append(compose_path)

    env_path = target_dir / ".env"
    env_path.write_text(render_env(cfg), encoding="utf-8")
    _restrict(env_path)
    written.append(env_path)

    stack_path = target_dir / "stack.yml"
    stack_path.write_text(
        _HEADER.replace("docker-compose.yml", "stack.yml")
        + yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    written.append(stack_path)
    return written


def _restrict(path: Path) -> None:
    """chmod 600. Sans effet utile sur Windows, silencieux plutot que bruyant."""
    try:
        path.chmod(0o600)
    except (OSError, NotImplementedError):
        pass
