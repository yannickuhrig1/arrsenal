"""Le trafic torrent sort-il VRAIMENT par le VPN ?

Signale a l'usage, dans ces termes : « c'est le coup a lancer un torrent et ne
pas etre protege par le VPN ». La crainte est fondee, et plugarr ne verifiait
rien du tout : il ecrivait `network_mode: service:gluetun` dans le compose et
considerait l'affaire close.

Or ce reglage se perd. Constate en vrai le 2026-09-03 : une installation lancee
par-dessus une pile existante, depuis une configuration ou le VPN n'etait pas
active, a recree les clients torrent sur le reseau nu. Docker identifie une pile
par son nom : les conteneurs ont ete remplaces sans un mot, et rien dans
plugarr n'aurait signale que la protection avait disparu.

Deux controles, du moins cher au plus concluant.

**1. Structure.** `docker inspect` doit rendre `container:<id de gluetun>` pour
chaque client torrent. Hors ligne, instantane, et c'est celui qui aurait attrape
l'incident ci-dessus.

**2. Sortie reelle.** Depuis l'INTERIEUR du client, on interroge le serveur de
controle de Gluetun sur `127.0.0.1:8000`. Ce test est concluant parce qu'il ne
peut pas reussir par accident : seul un conteneur qui partage la pile reseau de
Gluetun voit ce `127.0.0.1`. Verifie dans les deux sens contre une pile reelle :

    depuis qbittorrent -> {"public_ip": ..., "country": "Netherlands", ...}
    depuis sonarr      -> can't connect to remote host (127.0.0.1): refused

L'adresse vient de Gluetun lui-meme, sans service exterieur.

**3. Le tunnel ressort-il ailleurs que chez vous ?** Un tunnel qui reboucle sur
la connexion du domicile ne protege de rien, et les deux controles precedents le
declarent pourtant bon : le conteneur EST dans le tunnel. Le cas est apparu sur
le banc d'essai — un serveur WireGuard local qui traduisait les adresses vers la
sortie de la maison — et un fournisseur mal configure produirait la meme chose.
On compare donc l'adresse du tunnel a celle de la machine.

C'est le SEUL appel exterieur de ce module, et il est facultatif : s'il echoue,
le controle rend quand meme son verdict, d'un cran moins ferme.

L'adresse IP n'est jamais journalisee, ni celle du tunnel ni celle de la
machine. On ne garde que le pays et l'operateur, qui suffisent a reconnaitre un
tunnel d'un fournisseur d'acces — et le journal est le fichier qu'on demande aux
utilisateurs de joindre a un rapport de bug.
"""

from __future__ import annotations

import json

import httpx

from . import catalog
from .models import Category, StackConfig
from .runner import Check, container_id, exec_in, network_mode

#: Serveur de controle de Gluetun, dans sa propre pile reseau. Le port n'est
#: jamais publie sur l'hote : il n'est visible que de l'interieur du tunnel,
#: et c'est precisement ce qui rend le test concluant.
CONTROLE = "http://127.0.0.1:8000/v1/publicip/ip"


def clients_torrent(cfg: StackConfig) -> list[str]:
    return [
        sid
        for sid in catalog.STARTUP_ORDER
        if cfg.enabled(sid) and catalog.get(sid).category is Category.DOWNLOAD
    ]


def ip_de_l_hote() -> str | None:
    """Adresse publique de la MACHINE, hors tunnel. None si indeterminable.

    Le seul appel exterieur de tout ce module, et il est facultatif : sans lui
    le controle rend quand meme son verdict, un cran moins ferme.
    """
    try:
        reponse = httpx.get("https://ipinfo.io/json", timeout=6.0)
        return str(reponse.json().get("ip") or "") or None
    except Exception:  # noqa: BLE001 - un diagnostic ne tombe pas pour ca
        return None


def _sortie(conteneur: str) -> tuple[bool, str]:
    """Pays et operateur vus depuis l'interieur du conteneur.

    Renvoie (protege, description). L'IP elle-meme n'est JAMAIS renvoyee : le
    journal est le fichier qu'on demande de joindre aux rapports de bug.
    """
    ok, sortie = exec_in(conteneur, ["wget", "-qO-", "--timeout=8", CONTROLE])
    if not ok or not sortie:
        return False, "le serveur de controle de Gluetun est injoignable depuis ce conteneur"
    try:
        donnees = json.loads(sortie)
    except ValueError:
        return False, f"reponse illisible de Gluetun : {sortie[:80]}"
    tunnel = donnees.get("public_ip")
    if not tunnel:
        return False, "Gluetun ne rapporte aucune adresse publique : le tunnel est-il monte ?"
    pays = donnees.get("country") or "?"
    operateur = (donnees.get("organization") or "?")[:40]

    # Un tunnel qui RESSORT chez vous ne protege de rien. Le cas s'est presente
    # pour de vrai sur un serveur WireGuard d'essai qui traduisait les adresses
    # vers la connexion de la maison : le conteneur etait bien dans le tunnel,
    # tout etait vert, et l'adresse vue de l'exterieur restait celle du domicile.
    # Un fournisseur commercial ne fait jamais cela ; une configuration
    # bricolee, si.
    hote = ip_de_l_hote()
    if hote and hote == tunnel:
        return False, (
            f"NON PROTEGE : le tunnel ressort sur VOTRE adresse publique "
            f"({pays}, {operateur}). Verifiez la configuration du fournisseur."
        )
    if hote is None:
        return True, f"sortie par {pays}, {operateur} (adresse de l'hote indeterminable)"
    return True, f"sortie par {pays}, {operateur}, differente de la votre"


def verifier(cfg: StackConfig) -> list[Check]:
    """Controles de fuite VPN. Vide si aucun client torrent n'est installe."""
    clients = clients_torrent(cfg)
    if not clients:
        return []

    if not cfg.vpn.enabled:
        # Ce n'est pas une panne : se passer de VPN est un choix. Mais il doit
        # etre visible, pas silencieux.
        return [
            Check(
                "VPN",
                True,
                f"aucun VPN configure : {', '.join(clients)} sort par votre connexion",
                blocking=False,
            )
        ]

    gluetun = container_id(f"{cfg.project_name}-gluetun")
    controles: list[Check] = []
    for sid in clients:
        conteneur = f"{cfg.project_name}-{sid}"
        mode = network_mode(conteneur)
        if mode is None:
            controles.append(Check(f"VPN {sid}", True, "conteneur arrete", blocking=False))
            continue

        # Le test structurel d'abord : il ne coute rien et sa reponse est nette.
        attendu = f"container:{gluetun}" if gluetun else None
        if not mode.startswith("container:"):
            controles.append(
                Check(
                    f"VPN {sid}",
                    False,
                    f"NON PROTEGE : le conteneur est sur le reseau {mode}, pas dans le "
                    f"tunnel. Tout torrent lance sort par votre connexion. "
                    f"Regenerez la pile puis redemarrez-la.",
                )
            )
            continue
        if attendu and mode != attendu:
            controles.append(
                Check(
                    f"VPN {sid}",
                    False,
                    f"il partage la pile reseau d'un AUTRE conteneur que "
                    f"{cfg.project_name}-gluetun ({mode[:24]}...)",
                )
            )
            continue

        protege, description = _sortie(conteneur)
        controles.append(Check(f"VPN {sid}", protege, description, blocking=not protege))
    return controles
