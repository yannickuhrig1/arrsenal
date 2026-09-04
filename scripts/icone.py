"""Fabrique l'icone Windows de PlugArr depuis le visuel d'origine.

    python scripts/icone.py [source.jpg]

Le dessin vient de l'illustration fournie par l'auteur du projet ; ce script ne
le redessine pas, il l'ISOLE et le decline aux tailles que Windows attend.

Deux choix, et il faut les justifier.

**Fond transparent, pas la tuile sombre.** L'illustration pose la marque sur un
carre anthracite. Une icone porte ce carre partout : sur une barre des taches
claire il devient une tache noire au milieu d'icones qui, elles, savent
s'adapter. La marque seule se pose sur n'importe quel fond.

**Le canal alpha vient de la CHROMA, pas de la luminosite.** Le fond de
l'illustration est un gris neutre et la marque est entierement saturee : la
distance a l'axe des gris separe les deux proprement, y compris dans les
degrades sombres du violet. Un seuil de luminosite, lui, mangeait le bas du
jambage violet — essaye et constate.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

RACINE = Path(__file__).resolve().parent.parent
SOURCE = Path("C:/Users/darkl/Downloads/Gemini_Generated_Image_dsw6igdsw6igdsw6.jpg")
CIBLE = RACINE / "assets" / "plugarr.ico"

#: Tailles qu'un .ico Windows doit porter : explorateur, barre des taches,
#: menu demarrer, et l'affichage « grandes icones ».
TAILLES = (16, 24, 32, 48, 64, 128, 256)

#: Marge autour de la marque, en fraction du cote. Sans elle l'icone touche les
#: bords et parait plus grande que ses voisines.
MARGE = 0.06

#: En dessous de cette chroma, on est sur le fond. Releve sur l'illustration :
#: le fond plafonne a 0.10, le point le plus terne de la marque est a 0.42.
CHROMA_FOND = 0.20
CHROMA_PLEINE = 0.40


def _chroma(r: int, g: int, b: int) -> float:
    haut = max(r, g, b)
    return 0.0 if haut == 0 else (haut - min(r, g, b)) / haut


def extraire(source: Path) -> Image.Image:
    """Isole la marque sur fond transparent, recadree au carre."""
    image = Image.open(source).convert("RGB")
    largeur, hauteur = image.size
    px = image.load()

    xs: list[int] = []
    ys: list[int] = []
    for y in range(0, hauteur, 3):
        for x in range(0, largeur, 3):
            if _chroma(*px[x, y]) > CHROMA_PLEINE and max(px[x, y]) > 90:
                xs.append(x)
                ys.append(y)
    if not xs:
        raise SystemExit(f"aucune marque trouvee dans {source}")

    cote = max(max(xs) - min(xs), max(ys) - min(ys))
    marge = round(cote * MARGE)
    cote += 2 * marge
    gauche = (min(xs) + max(xs) - cote) // 2
    haut = (min(ys) + max(ys) - cote) // 2

    decoupe = image.crop((gauche, haut, gauche + cote, haut + cote)).convert("RGBA")
    dpx = decoupe.load()
    for y in range(cote):
        for x in range(cote):
            r, g, b, _ = dpx[x, y]
            c = _chroma(r, g, b)
            if c <= CHROMA_FOND:
                dpx[x, y] = (r, g, b, 0)
            elif c < CHROMA_PLEINE:
                # Bord : on adoucit au lieu de trancher, sinon l'icone est
                # dentelee a 256 px et illisible a 16.
                part = (c - CHROMA_FOND) / (CHROMA_PLEINE - CHROMA_FOND)
                dpx[x, y] = (r, g, b, round(255 * part))
    return decoupe


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE
    if not source.exists():
        raise SystemExit(f"source introuvable : {source}")

    marque = extraire(source)
    CIBLE.parent.mkdir(parents=True, exist_ok=True)
    marque.resize((512, 512), Image.LANCZOS).save(CIBLE.parent / "plugarr.png")
    calques = [marque.resize((t, t), Image.LANCZOS) for t in TAILLES]
    calques[-1].save(CIBLE, format="ICO", sizes=[(t, t) for t in TAILLES])
    for t, c in zip(TAILLES, calques):
        c.save(CIBLE.parent / f"plugarr-{t}.png")
    print(f"marque isolee : {marque.size[0]} px")
    print(f"{CIBLE.name} — {len(TAILLES)} tailles, {CIBLE.stat().st_size} octets")


if __name__ == "__main__":
    main()
