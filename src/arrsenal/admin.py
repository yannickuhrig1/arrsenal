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
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import catalog, dashboard
from .models import StackConfig
from .runner import Compose

ACTIONS = ("start", "stop", "restart")
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


class _Handler(BaseHTTPRequestHandler):
    # Renseignes par serve()
    cfg: StackConfig
    compose: Compose
    token: str

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
        else:
            self._json({"error": "route inconnue"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._authorised():
            self._deny()
            return
        if urlparse(self.path).path != "/api/action":
            self._json({"error": "route inconnue"}, HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "corps JSON invalide"}, HTTPStatus.BAD_REQUEST)
            return

        action = str(payload.get("action", ""))
        service = str(payload.get("service", ""))

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
        },
    )
    server = ThreadingHTTPServer((host, port), handler)
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
