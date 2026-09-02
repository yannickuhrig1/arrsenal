"""Controle de l'executable : l'assistant vit-il vraiment dedans ?

Compile en un second executable jetable, puis lance. C'est le seul moyen de
verifier ce qui casse le plus facilement a l'empaquetage : un fichier non-Python
absent de l'archive.

Deux cas rencontres pour de vrai :

- `app.tcss` manquant : Textual leve `StylesheetError` et l'assistant ne s'ouvre
  pas du tout. Panne bruyante, mais invisible tant que personne ne lance
  l'executable produit ;
- `data/vpn_countries.json` manquant en 0.1.8 : l'assistant s'ouvrait
  parfaitement, affichait ses onze services, et plantait plus loin — sur l'ecran
  VPN, c'est-a-dire des qu'un client de telechargement etait coche. Ce controle
  s'arretait a l'ecran des services : il ne voyait rien.

D'ou la regle : ce controle doit PARCOURIR l'assistant, pas seulement l'ouvrir.

Sortie non nulle si l'assistant ne se rend pas correctement.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import sys

#: En dessous, la feuille de style n'a pas ete chargee.
MIN_REGLES = 50


async def probe() -> int:
    from textual.widgets import Button, RadioButton, SelectionList

    from arrsenal import catalog
    from arrsenal.tui.app import ArrsenalApp
    from arrsenal.tui.screens import PathsScreen, ServicesScreen, VpnScreen

    app = ArrsenalApp()
    app.auto_open_page = False
    lieux = -1
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        regles = len(app.stylesheet.rules)
        app.push_screen(ServicesScreen())
        await pilot.pause()
        cases = len(app.screen.query("Checkbox"))

        # Jusqu'a l'ecran VPN, en passant par les chemins : c'est le trajet
        # reel, et celui qui a plante en 0.1.8.
        app.selection = ["sonarr", "qbittorrent"]
        app.push_screen(PathsScreen())
        await pilot.pause()
        app.screen.query_one("#next", Button).press()
        await pilot.pause()
        atteint = type(app.screen).__name__
        if isinstance(app.screen, VpnScreen):
            app.screen.query_one("#vpn-oui", RadioButton).value = True
            await pilot.pause()
            lieux = len(app.screen.query_one("#vpn-lieux", SelectionList)._options)

    print(f"  feuille de style : {regles} regles")
    print(f"  services affiches : {cases} / {len(catalog.CATALOG)}")
    print(f"  ecran apres les chemins : {atteint}")
    print(f"  lieux VPN proposes : {lieux}")

    problemes = []
    if regles < MIN_REGLES:
        problemes.append(f"feuille de style absente ou vide ({regles} regles)")
    if cases != len(catalog.CATALOG):
        problemes.append(f"{cases} services affiches au lieu de {len(catalog.CATALOG)}")
    if atteint != "VpnScreen":
        problemes.append(f"l'ecran VPN n'est pas atteint ({atteint})")
    elif lieux <= 0:
        problemes.append("aucun lieu VPN propose : data/vpn_countries.json est-il embarque ?")

    for probleme in problemes:
        print(f"  ECHEC : {probleme}")
    if not problemes:
        print("  OK : l'assistant se rend correctement depuis l'executable")
    return 1 if problemes else 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(asyncio.run(probe()))
