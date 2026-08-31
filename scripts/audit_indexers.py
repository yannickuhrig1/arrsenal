"""Audite l'heuristique de detection des identifiants sur TOUTES les definitions.

Deux trackers reels ne prouveraient rien : ce script confronte l'heuristique aux
626 definitions que Prowlarr embarque, et cherche ses angles morts.

    python scripts/audit_indexers.py <schema.json>

Le fichier s'obtient avec :
    curl -H "X-Api-Key: <cle>" http://<prowlarr>/api/v1/indexer/schema -o schema.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# La console Windows est en cp1252 : les noms d'indexeurs contiennent de l'UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from arrsenal.clients.prowlarr import (
    CREDENTIAL_NAMES,
    IndexerDefinition,
    is_credential,
    is_tuning,
)

#: Fragments de noms qui trahissent un identifiant. Sert uniquement a chercher ce
#: que l'heuristique aurait pu manquer, jamais a decider.
SUSPICIOUS = ("key", "pass", "user", "token", "cookie", "auth", "login", "secret", "uid", "id_")

#: Index prives qui n'exigent REELLEMENT aucun identifiant : moteurs DHT et index
#: semi-prives ouverts. Examines a la main, juges corrects.
REVIEWED_NO_CREDENTIAL = frozenset(
    {"BitMagnet (Local DHT)", "comicat", "MioBT", "ConCen"}
)

#: Champs dont le nom evoque un identifiant mais qui sont des reglages de
#: comportement (cases a cocher, listes). Examines a la main, juges corrects.
REVIEWED_NOT_CREDENTIAL = frozenset(
    {
        "useFreeleechToken",
        "usetoken",
        "use_fl_tokens",
        "authorisedOnly",
        "add_hybrid_features_to_filename",
        "passid",
    }
)


def load(path: Path) -> list[IndexerDefinition]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        IndexerDefinition(
            name=e.get("name", "?"),
            implementation=e.get("implementation", "?"),
            privacy=e.get("privacy", "unknown"),
            protocol=e.get("protocol", "unknown"),
            language=e.get("language", ""),
            description=e.get("description", "") or "",
            raw=e,
        )
        for e in raw
    ]


def main(path: Path) -> int:
    defs = load(path)
    print(f"{len(defs)} definitions analysees\n")
    problems = 0

    # 1. Un indexeur prive sans aucun identifiant detecte est suspect : on ne
    #    pourrait pas s'y connecter.
    print("=== 1. Indexeurs prives sans identifiant detecte ===")
    blind = [
        d
        for d in defs
        if d.is_private
        and d.name not in REVIEWED_NO_CREDENTIAL
        and not [f for f in d.editable_fields() if f.name != "baseUrl"]
    ]
    if blind:
        problems += len(blind)
        for d in blind[:15]:
            names = [f.get("name") for f in d.raw.get("fields", []) if not is_tuning(f.get("name", ""))]
            print(f"  MANQUE {d.name:<26} champs presents: {names[:6]}")
        if len(blind) > 15:
            print(f"  ... et {len(blind) - 15} autres")
    else:
        print(
            f"  aucun de nouveau ({len(REVIEWED_NO_CREDENTIAL)} cas connus et juges corrects)"
        )

    # 2. Champs au nom suspect que l'heuristique ne retient pas.
    print("\n=== 2. Champs au nom suspect NON retenus ===")
    missed: Counter = Counter()
    for d in defs:
        for f in d.raw.get("fields", []):
            name = f.get("name", "")
            if is_tuning(name) or f.get("type") == "info" or name == "baseUrl":
                continue
            if is_credential(f):
                continue
            if name in REVIEWED_NOT_CREDENTIAL:
                continue
            if any(frag in name.lower() for frag in SUSPICIOUS):
                missed[name] += 1
    if missed:
        for name, count in missed.most_common(20):
            print(f"  {name:<28} {count:>4} definitions")
        problems += len(missed)
    else:
        print(f"  aucun de nouveau ({len(REVIEWED_NOT_CREDENTIAL)} cas connus et juges corrects)")

    # 3. Faux positifs : un formulaire a rallonge est inutilisable.
    print("\n=== 3. Definitions avec beaucoup de champs a saisir ===")
    heavy = sorted(defs, key=lambda d: -len(d.editable_fields()))[:8]
    for d in heavy:
        fields = [f.name for f in d.editable_fields()]
        flag = "  <-- a verifier" if len(fields) > 6 else ""
        print(f"  {len(fields):>2} champs  {d.name:<24} {fields}{flag}")

    # 3bis. Ce que la regle structurelle (textbox sans defaut) ajoute a elle seule.
    print("\n=== 3bis. Champs retenus par la SEULE regle structurelle ===")
    structural: Counter = Counter()
    for d in defs:
        for f in d.raw.get("fields", []):
            name = f.get("name", "")
            if is_tuning(name) or f.get("type") == "info" or name == "baseUrl":
                continue
            if not is_credential(f):
                continue
            explicit = (
                f.get("privacy") in ("apiKey", "password", "userName")
                or f.get("type") == "password"
                or name.lower() in CREDENTIAL_NAMES
            )
            if not explicit:
                structural[name] += 1
    for name, count in structural.most_common(25):
        print(f"  {name:<28} {count:>4} definitions")
    print(f"  total : {sum(structural.values())} champs sur {len(defs)} definitions")

    # 4. Couverture des URL.
    print("\n=== 4. Definitions sans URL exploitable ===")
    no_url = [
        d
        for d in defs
        if not [f for f in d.editable_fields() if f.name == "baseUrl" and f.prefill]
    ]
    print(f"  {len(no_url)} : {[d.name for d in no_url]}")

    # 5. Distribution generale.
    print("\n=== 5. Repartition du nombre de champs a saisir ===")
    dist = Counter(len([f for f in d.editable_fields() if f.name != "baseUrl"]) for d in defs)
    for count in sorted(dist):
        print(f"  {count} identifiant(s) : {dist[count]:>4} definitions")

    print(f"\nnoms d'identifiants connus : {len(CREDENTIAL_NAMES)}")
    if problems:
        print(f"\nNOUVEAUX CAS A EXAMINER : {problems}")
        print("Examinez-les, puis ajoutez-les a REVIEWED_* ou etendez l'heuristique.")
    else:
        print(f"\nAucun cas non examine : l'heuristique couvre les {len(defs)} definitions.")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(Path(sys.argv[1])))
