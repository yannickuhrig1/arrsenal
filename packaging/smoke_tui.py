"""Controle de l'executable : l'assistant vit-il vraiment dedans ?

Compile en un second executable jetable, puis lance. C'est le seul moyen de
verifier ce qui casse le plus facilement a l'empaquetage : `app.tcss` absent de
l'archive. Textual leve alors `StylesheetError` et l'assistant ne s'ouvre pas —
panne bruyante, mais invisible tant que personne ne lance l'executable produit.

Sortie non nulle si l'assistant ne se rend pas correctement.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import sys

#: En dessous, la feuille de style n'a pas ete chargee.
MIN_REGLES = 50


async def probe() -> int:
    from arrsenal import catalog
    from arrsenal.tui.app import ArrsenalApp
    from arrsenal.tui.screens import ServicesScreen

    app = ArrsenalApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        regles = len(app.stylesheet.rules)
        app.push_screen(ServicesScreen())
        await pilot.pause()
        cases = len(app.screen.query("Checkbox"))

    print(f"  feuille de style : {regles} regles")
    print(f"  services affiches : {cases} / {len(catalog.CATALOG)}")

    problemes = []
    if regles < MIN_REGLES:
        problemes.append(f"feuille de style absente ou vide ({regles} regles)")
    if cases != len(catalog.CATALOG):
        problemes.append(f"{cases} services affiches au lieu de {len(catalog.CATALOG)}")

    for probleme in problemes:
        print(f"  ECHEC : {probleme}")
    if not problemes:
        print("  OK : l'assistant se rend correctement depuis l'executable")
    return 1 if problemes else 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(asyncio.run(probe()))
