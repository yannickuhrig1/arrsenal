"""Socle HTTP commun : attente de disponibilite et erreurs exploitables."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from ..i18n import t


class WiringError(RuntimeError):
    """Erreur de cablage porteuse d'un diagnostic actionnable."""

    def __init__(self, what: str, why: str, fix: str = "") -> None:
        self.what, self.why, self.fix = what, why, fix
        message = f"{what}\n  {t('cause')} : {why}"
        if fix:
            message += f"\n  {t('action')} : {fix}"
        super().__init__(message)


@dataclass
class ReadinessResult:
    ready: bool
    elapsed: float
    detail: str


def wait_until(
    probe: Callable[[], bool],
    *,
    label: str,
    timeout: float = 300.0,
    initial_delay: float = 1.0,
    max_delay: float = 8.0,
) -> ReadinessResult:
    """Backoff exponentiel plafonne. Jamais de `sleep` fixe : on interroge le service.

    Un service est pret quand il repond correctement, pas quand un chronometre expire.
    """
    start = time.monotonic()
    delay = initial_delay
    last_error = ""
    while time.monotonic() - start < timeout:
        try:
            if probe():
                return ReadinessResult(
                    True,
                    time.monotonic() - start,
                    t("{service} pret", service=label),
                )
        except Exception as exc:  # noqa: BLE001 - on veut le message brut
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(delay)
        delay = min(delay * 1.6, max_delay)
    return ReadinessResult(
        False,
        time.monotonic() - start,
        t(
            "{service} n'a pas repondu en {secondes:.0f}s. Dernier retour : {dernier}",
            service=label,
            secondes=timeout,
            dernier=last_error or t("aucun"),
        ),
    )


def new_client(base_url: str, *, headers: dict[str, str] | None = None) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/"),
        headers=headers or {},
        timeout=httpx.Timeout(20.0, connect=5.0),
        follow_redirects=True,
    )


def mask(secret: str | None) -> str:
    """Masquage systematique des secrets dans les logs (contrainte sec. 8.4)."""
    if not secret:
        return "-"
    return f"{secret[:4]}...{secret[-2:]}" if len(secret) > 8 else "***"
