"""Reinstaller par-dessus une installation existante sans tout perdre.

`install` construisait sa configuration de zero et **ne regardait jamais le
`stack.yml` deja present**. Reinstaller effacait donc tout ce qu'il portait.
Mesure sur une installation d'essai :

    | | avant | apres reinstallation |
    | identifiant       | yannick             | plugarr    |
    | VPN               | mullvad + cle       | DESACTIVE  |
    | profils Recyclarr | choisis             | vides      |
    | mot de passe console | pose             | perdu      |

Le VPN est le cas grave : il disparait **en silence**, et l'installation
affiche « Aucun VPN n'est configure » — quelqu'un qui reinstalle pour reparer
autre chose se retrouve avec son trafic torrent en clair sans l'avoir voulu.

**Reprendre repare aussi un defaut plus ancien.** qBittorrent, Jellyfin,
autobrr, qui et les autres ne stockent leur mot de passe que HACHE : PlugArr ne
peut pas le relire dans leur configuration, en generait un nouveau, l'annoncait,
et le service le refusait. Mais quand c'est PlugArr qui a installe, le mot de
passe est dans SON `stack.yml` — il n'a jamais eu besoin de le relire ailleurs.
Reprendre les identifiants precedents fait donc coincider ce qui est annonce et
ce qui est en place.

**Ce qu'on ne reprend pas** : la selection de services, les racines, la
plateforme. Ce sont les reponses de l'installation en cours, pas des reglages
qu'on herite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import migrations
from .i18n import t
from .models import StackConfig


@dataclass
class Reprise:
    """Ce qui a ete repris d'une installation precedente, pour l'afficher.

    Une reprise silencieuse serait pire que pas de reprise : l'utilisateur doit
    voir ce que PlugArr a decide de garder a sa place.
    """

    reglages: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.reglages or self.services)


def precedente(project_dir: Path) -> StackConfig | None:
    """Configuration de l'installation deja presente, si elle est lisible.

    Un `stack.yml` illisible n'arrete pas une installation neuve : on repart de
    zero, ce qui est exactement ce que l'utilisateur a demande. Une version
    FUTURE, en revanche, remonte — la refuser est tout l'interet du garde-fou.
    """
    chemin = Path(project_dir) / "stack.yml"
    if not chemin.is_file():
        return None
    try:
        cfg, _notes = migrations.lire(chemin)
    except migrations.VersionFuture:
        raise
    except (ValueError, OSError):
        return None
    return cfg


#: Reglages repris tels quels, avec le libelle montre a l'utilisateur. L'ordre
#: est celui de l'affichage.
_REGLAGES: tuple[tuple[str, str], ...] = (
    ("username", "identifiant"),
    ("timezone", "fuseau horaire"),
    ("host", "adresse de la machine"),
    ("language", "langue des services"),
    ("ui_language", "langue de PlugArr"),
    ("admin_password_hash", "mot de passe de la console"),
    ("recyclarr_templates", "profils de qualite"),
)


def appliquer(
    neuve: StackConfig, ancienne: StackConfig, *, imposes: set[str] | None = None
) -> Reprise:
    """Reporte les reglages de l'ancienne installation dans la nouvelle.

    `imposes` nomme les reglages donnes EXPLICITEMENT sur la ligne de commande
    ou dans l'assistant : une option ecrite a la main prime toujours sur ce
    qu'on herite, sinon elle serait sans effet et personne ne comprendrait
    pourquoi.
    """
    imposes = imposes or set()
    reprise = Reprise()

    for champ, libelle in _REGLAGES:
        if champ in imposes:
            continue
        valeur = getattr(ancienne, champ, None)
        if not valeur or valeur == getattr(type(neuve).model_fields[champ], "default", None):
            continue
        setattr(neuve, champ, valeur)
        reprise.reglages.append(t(libelle))

    # Le VPN en bloc : reprendre le fournisseur sans la cle donnerait une
    # configuration incomplete, que Gluetun refuserait au demarrage.
    if "vpn" not in imposes and ancienne.vpn.enabled:
        neuve.vpn = ancienne.vpn.model_copy(deep=True)
        reprise.reglages.append(t("VPN ({fournisseur})", fournisseur=ancienne.vpn.provider))

    # Les identifiants, service par service. C'est ce qui evite d'annoncer un
    # mot de passe que le service refusera.
    for sid, instance in neuve.services.items():
        precedent = ancienne.services.get(sid)
        if precedent is None:
            continue
        repris = False
        for champ in ("username", "password", "api_key"):
            valeur = getattr(precedent, champ, "")
            if valeur:
                setattr(instance, champ, valeur)
                repris = True
        # Le port aussi : quelqu'un qui a decale qBittorrent pour eviter un
        # conflit ne veut pas le retrouver sur 8080.
        if precedent.host_port and precedent.host_port != instance.host_port:
            instance.host_port = precedent.host_port
            repris = True
        if repris:
            reprise.services.append(sid)

    return reprise
