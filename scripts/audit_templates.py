"""Confronte les templates par defaut au manifeste publie par Recyclarr.

Les deux noms codes dans `DEFAULT_TEMPLATES` sont les seuls elements du projet
qui designent du contenu TRaSH. Ils vivent chez quelqu'un d'autre : un template
renomme ou retire ferait echouer `config create` chez tous les utilisateurs, et
la panne n'apparaitrait qu'a la toute fin d'une installation.

    python scripts/audit_templates.py

Sortie non nulle des qu'un defaut n'existe plus, ou que la structure du
manifeste change. A lancer avant une publication.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plugarr.clients import recyclarr


def main() -> int:
    names, problem = recyclarr.fetch_manifest(timeout=30)
    if problem:
        print(f"ECHEC : {problem}")
        return 2

    print(f"Manifeste : {recyclarr.MANIFEST_URL}")
    for service in sorted(names):
        print(f"  {service:8} {len(names[service])} templates racine")

    problems = 0
    for service, template in sorted(recyclarr.DEFAULT_TEMPLATES.items()):
        available = names.get(service, [])
        if not available:
            print(f"\nECHEC : le manifeste ne connait plus le service {service}")
            problems += 1
        elif template not in available:
            close = [n for n in available if template.split("-")[0] in n][:5]
            print(f"\nECHEC : le defaut {service} = {template!r} n'existe plus.")
            print(f"        Noms proches : {', '.join(close) or 'aucun'}")
            problems += 1
        else:
            print(f"\nOK : {service} = {template}")

    # Un identifiant n'est pas un nom de fichier. Le verifier ici evite de
    # retomber dans le piege si quelqu'un « simplifie » la lecture du manifeste.
    prefixed = [n for service in names for n in names[service] if n.startswith(f"{service}-")]
    print(f"\n{len(prefixed)} identifiants prefixes par leur service")
    print("(ils ne correspondent PAS au nom du fichier : lire le manifeste, pas le dossier)")

    if problems:
        print(f"\n{problems} defaut(s) a corriger dans DEFAULT_TEMPLATES.")
    else:
        print("\nTous les templates par defaut existent toujours.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
