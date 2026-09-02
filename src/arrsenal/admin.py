"""Serveur d'administration local : etat des services, demarrer / arreter / redemarrer.

La page d'acces statique ne peut pas piloter Docker : un fichier HTML n'execute
rien. Il faut un serveur. Celui-ci est volontairement minuscule et repose
uniquement sur la bibliotheque standard.

Modele de securite, parce qu'une page capable d'arreter des conteneurs n'est pas
anodine :

- **ecoute sur 127.0.0.1 par defaut.** Exposer sur le reseau demande `--host`,
  et l'avertissement est explicite ;
- **jeton obligatoire**, tire au hasard a chaque demarrage, jamais ecrit sur
  disque. Il arrive par l'URL puis est stocke en cookie `HttpOnly` ;
- **comparaison a temps constant**, pour ne pas fuiter le jeton octet par octet ;
- **listes fermees** : le nom de service est valide contre la configuration et
  l'action contre trois valeurs, avant de rejoindre une ligne de commande.
"""

from __future__ import annotations

import hmac
import json
import secrets
import sys
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import catalog, compose, dashboard, orchestrator, updates
from .models import StackConfig
from .runner import Compose

ACTIONS = ("start", "stop", "restart")

#: Le controle interroge les registres : quelques secondes. On garde le resultat
#: brievement pour que l'ouverture de la page ne le relance pas a chaque fois.
UPDATE_CACHE_SECONDS = 300
COOKIE = "arrsenal_token"


@dataclass
class ServiceState:
    service: str
    state: str  # running, exited, created, paused...
    status: str  # libelle lisible ("Up 3 minutes")
    health: str = ""

    @property
    def up(self) -> bool:
        return self.state == "running"


def read_states(compose: Compose) -> dict[str, ServiceState]:
    """Etat par service, indexe par nom de service compose."""
    states: dict[str, ServiceState] = {}
    for entry in compose.ps_json():
        name = entry.get("Service")
        if not name:
            continue
        states[name] = ServiceState(
            service=name,
            state=str(entry.get("State", "")),
            status=str(entry.get("Status", "")),
            health=str(entry.get("Health", "") or ""),
        )
    return states


def status_payload(cfg: StackConfig, compose: Compose) -> dict:
    """Etat de chaque service SELECTIONNE, meme absent de docker : un service
    installe mais jamais demarre doit apparaitre, pas disparaitre."""
    states = read_states(compose)
    services = []
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        found = states.get(sid)
        services.append(
            {
                "id": sid,
                "name": catalog.get(sid).display_name,
                "state": found.state if found else "absent",
                "status": found.status if found else "conteneur absent",
                "health": found.health if found else "",
                "up": bool(found and found.up),
            }
        )
    return {"services": services}


def updates_payload(cfg: StackConfig) -> dict:
    """Etat des mises a jour, service par service."""
    entries = []
    for info in updates.check(cfg):
        entries.append(
            {
                "id": info.service,
                "name": catalog.get(info.service).display_name,
                "current": info.current_tag,
                "latest": info.latest_tag,
                "rebuilt": info.rebuilt,
                "available": info.has_update,
                "problems": info.problems,
            }
        )
    return {"services": entries}


def apply_update(
    cfg: StackConfig, runner: Compose, project_dir: Path, service: str, target: str | None
) -> tuple[bool, str]:
    """Met a jour UN service.

    Sans `target`, on retire la meme image reconstruite. Avec, on change le tag
    deploye : `stack.yml` et le compose sont reecrits AVANT le pull, sinon Docker
    retirerait l'ancienne version.
    """
    inst = cfg.services[service]
    previous = inst.image or catalog.get(service).image

    if target:
        reference = previous.rpartition(":")[0]
        inst.image = f"{reference}:{target}"
        compose.write_artifacts(cfg, project_dir)

    ok, message = runner.pull(service)
    if not ok:
        if target:
            inst.image = previous
            compose.write_artifacts(cfg, project_dir)
        return False, f"telechargement echoue, version inchangee : {message[:300]}"

    ok, message = runner.recreate(service)
    if not ok:
        return False, f"image a jour mais recreation echouee : {message[:300]}"
    return True, f"{previous.rpartition(':')[2]} -> {inst.image.rpartition(':')[2]}"


class _Handler(BaseHTTPRequestHandler):
    # Renseignes par serve()
    cfg: StackConfig
    compose: Compose
    token: str
    project_dir: Path

    server_version = "arrsenal"
    sys_version = ""

    def log_message(self, fmt: str, *args: object) -> None:
        """Silence : le serveur tourne au premier plan dans le terminal de
        l'utilisateur, un journal d'acces n'y apporterait rien."""

    # -- authentification ---------------------------------------------------

    def _presented_token(self) -> str:
        query = parse_qs(urlparse(self.path).query)
        if query.get("t"):
            return query["t"][0]
        for part in (self.headers.get("Cookie") or "").split(";"):
            key, _, value = part.strip().partition("=")
            if key == COOKIE:
                return value
        return ""

    def _authorised(self) -> bool:
        # compare_digest : une comparaison naive fuite le jeton octet par octet.
        return hmac.compare_digest(self._presented_token(), self.token)

    def _deny(self) -> None:
        body = b"Jeton absent ou invalide. Utilisez l'URL affichee par `arrsenal serve`."
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send(self, status: HTTPStatus, body: bytes, content_type: str, cookie: bool = False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header(
                "Set-Cookie", f"{COOKIE}={self.token}; Path=/; HttpOnly; SameSite=Strict"
            )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    # -- routes -------------------------------------------------------------

    def do_GET(self) -> None:
        if not self._authorised():
            self._deny()
            return
        route = urlparse(self.path).path
        if route == "/":
            page = dashboard.render(self.cfg, live=True).encode("utf-8")
            self._send(HTTPStatus.OK, page, "text/html; charset=utf-8", cookie=True)
        elif route == "/api/status":
            self._json(status_payload(self.cfg, self.compose))
        elif route == "/api/updates":
            self._json(updates_payload(self.cfg))
        else:
            self._json({"error": "route inconnue"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._authorised():
            self._deny()
            return
        route = urlparse(self.path).path
        if route not in ("/api/action", "/api/update", "/api/rotate"):
            self._json({"error": "route inconnue"}, HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "corps JSON invalide"}, HTTPStatus.BAD_REQUEST)
            return

        service = str(payload.get("service", ""))
        if route == "/api/rotate":
            if not self.cfg.enabled(service):
                self._json({"error": f"service inconnu: {service}"}, HTTPStatus.BAD_REQUEST)
                return
            ok, message, mot_de_passe = orchestrator.rotate_password(
                self.cfg, self.project_dir, service
            )
            # Le mot de passe part vers la page qui vient de le demander, et
            # nulle part ailleurs : ni journal, ni sortie terminal.
            self._json(
                {"ok": ok, "service": service, "message": message, "password": mot_de_passe},
                HTTPStatus.OK if ok else HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        if route == "/api/update":
            if not self.cfg.enabled(service):
                self._json({"error": f"service inconnu: {service}"}, HTTPStatus.BAD_REQUEST)
                return
            target = payload.get("target")
            if target is not None and updates.parse_version(str(target)) is None:
                # Le tag finit dans une image Docker : il doit ressembler a une
                # version, jamais a ce que le client veut bien envoyer.
                self._json(
                    {"error": f"tag refuse: {target}"}, HTTPStatus.BAD_REQUEST
                )
                return
            ok, message = apply_update(
                self.cfg, self.compose, self.project_dir, service,
                str(target) if target else None,
            )
            self._json(
                {"ok": ok, "service": service, "message": message},
                HTTPStatus.OK if ok else HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        action = str(payload.get("action", ""))

        # Listes fermees : ces deux valeurs finissent dans une ligne de commande.
        if action not in ACTIONS:
            self._json({"error": f"action refusee: {action}"}, HTTPStatus.BAD_REQUEST)
            return
        if not self.cfg.enabled(service):
            self._json({"error": f"service inconnu: {service}"}, HTTPStatus.BAD_REQUEST)
            return

        ok, message = self.compose.control(action, service)
        self._json(
            {"ok": ok, "service": service, "action": action, "message": message[:400]},
            HTTPStatus.OK if ok else HTTPStatus.INTERNAL_SERVER_ERROR,
        )


class _Server(ThreadingHTTPServer):
    """Serveur qui refuse de partager son port.

    `HTTPServer` active `allow_reuse_address`. Sous Linux, SO_REUSEADDR n'autorise
    pas deux ecoutes simultanees. Sous Windows, SI : un second `bind` reussit en
    silence et les requetes partent au hasard vers l'un ou l'autre processus.

    Constate en conditions reelles — deux `arrsenal serve` lances de suite, et la
    page renvoyait « jeton invalide » une fois sur deux, chaque processus ayant
    tire son propre jeton. Mieux vaut un echec net au demarrage, que la CLI sait
    deja rapporter.
    """

    allow_reuse_address = sys.platform != "win32"


def build_server(
    cfg: StackConfig, project_dir: Path, *, host: str, port: int, token: str
) -> ThreadingHTTPServer:
    handler = type(
        "BoundHandler",
        (_Handler,),
        {
            "cfg": cfg,
            "compose": Compose(project_dir, cfg.project_name),
            "token": token,
            "project_dir": project_dir,
        },
    )
    server = _Server((host, port), handler)
    server.daemon_threads = True
    return server


def generate_token() -> str:
    return secrets.token_urlsafe(24)


def serve(
    cfg: StackConfig,
    project_dir: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 7373,
    token: str | None = None,
    on_ready=None,
) -> None:
    """Sert la page d'administration jusqu'a interruption."""
    token = token or generate_token()
    server = build_server(cfg, project_dir, host=host, port=port, token=token)
    url = f"http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}/?t={token}"
    if on_ready:
        on_ready(url, token)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
