"""Capture la page d'administration, dans les deux langues.

Elle n'est pas un ecran du terminal : c'est du HTML, servi par
`plugarr serve`. `scripts/screenshots.py` ne peut donc pas la produire — il
exporte des ecrans Textual — et elle etait la seule partie visible du produit
dont il n'existait aucune image.

Deux fichiers sont produits par langue :

- **le HTML**, autonome, qu'on ouvre pour voir la page exactement telle qu'un
  utilisateur la verrait ;
- **une image**, pour le README et le site, prise par Chrome en mode sans
  interface.

L'image, elle, n'est PAS reproductible d'une machine a l'autre : elle depend
de la version de Chrome et des polices installees. Elle est donc traitee comme
une ressource, versionnee mais hors du controle de la CI — contrairement aux
captures du terminal, que `screenshots.py` regenere a l'octet pres.

    python scripts/captures_administration.py

Les memes precautions que pour les captures du terminal s'appliquent : secrets
d'illustration, chemins fixes, date figee, aucune valeur venant de la machine
qui produit le fichier.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))

from plugarr import dashboard, i18n, orchestrator, seed

SORTIE = RACINE / "docs" / "screenshots"

#: Memes valeurs d'illustration que `screenshots.py`, pour que les deux jeux
#: racontent la meme installation.
CLE_MONTREE = "0123456789abcdef0123456789abcdef"
MOT_DE_PASSE_MONTRE = "MotDePasseGenere42"

#: Une pile representative : un indexeur, deux *arr, un client, un serveur
#: media. Assez pour montrer les cartes, les boutons et le tableau des
#: dossiers, sans faire une page de trois metres.
SERVICES = ["prowlarr", "sonarr", "radarr", "qbittorrent", "jellyfin"]


def _figer() -> None:
    """Rend la page independante de la machine ET du jour qui la produit.

    La date est figee : celle du jour rendrait le fichier different a chaque
    execution, impossible a versionner, et le controle de la CI deviendrait du
    bruit.
    """
    from datetime import datetime

    class _Fige(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 5, 9, 34, tzinfo=tz)

    dashboard.datetime = _Fige  # type: ignore[assignment]
    seed.generate_api_key = lambda: CLE_MONTREE  # type: ignore[assignment]
    seed.generate_password = lambda *a, **kw: MOT_DE_PASSE_MONTRE  # type: ignore[assignment]
    # `resolve_host` interroge la machine pour trouver son adresse sur le
    # reseau local : sans cela, l'adresse privee de qui lance le script
    # finirait dans une image publiee.
    dashboard.primary_lan_ip = lambda: "192.168.1.10"  # type: ignore[assignment]


def produire(langue: str) -> Path:
    i18n.utiliser(langue)
    cfg = orchestrator.build_config(
        services=SERVICES,
        config_root="/opt/plugarr/config",
        data_root="/srv/data",
    )
    cfg.ui_language = langue
    # `live=True` : c'est la console servie par `plugarr serve`, celle qui
    # porte l'etat des services et les boutons. La page figee ecrite apres
    # l'installation est la meme sans eux, et le bandeau le dit.
    page = dashboard.render(cfg, live=True)
    dossier = SORTIE if langue == "fr" else SORTIE / langue
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / "10-administration.html"
    with cible.open("w", encoding="utf-8", newline="") as sortie:
        sortie.write(page)
    return cible


#: Largeur de l'image. Assez large pour que les cartes de service tiennent sur
#: trois colonnes, comme sur un ecran de bureau : c'est la disposition que la
#: page est faite pour montrer.
LARGEUR = 1360

#: Hauteur de la fenetre de capture. La page entiere fait pres de quatre mille
#: pixels : illisible dans un README. Cette valeur s'arrete apres la premiere
#: rangee de « ajouter un service », c'est-a-dire sur une carte entiere plutot
#: qu'au milieu de l'une d'elles.
HAUTEUR = 1258


def _chrome() -> str | None:
    """Chemin de Chrome, ou None. L'image est facultative : sans navigateur, le
    HTML reste produit, et c'est lui qui fait foi."""
    import shutil

    for nom in ("chrome", "google-chrome", "chromium", "chromium-browser"):
        trouve = shutil.which(nom)
        if trouve:
            return trouve
    windows = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    return str(windows) if windows.exists() else None


def photographier(page: Path) -> Path | None:
    """Prend l'image de la page, puis la rogne sur son contenu.

    Chrome remplit la fenetre demandee : sans le rognage, l'image se termine
    par plusieurs centaines de pixels de fond vide.
    """
    navigateur = _chrome()
    if not navigateur:
        print("  (Chrome introuvable : image non produite, le HTML suffit)")
        return None

    import subprocess

    from PIL import Image, ImageChops

    image = page.with_suffix(".png")
    subprocess.run(
        [
            navigateur,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={LARGEUR},{HAUTEUR}",
            f"--screenshot={image}",
            page.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
    )

    with Image.open(image) as prise:
        prise = prise.convert("RGB")
        # Le fond de la page, lu sur son coin superieur gauche plutot que
        # devine : le theme peut changer sans que ce script le sache.
        fond = Image.new("RGB", prise.size, prise.getpixel((0, 0)))
        boite = ImageChops.difference(prise, fond).getbbox()
        if boite:
            # On garde la marge de gauche et du haut : rogner au ras du texte
            # donnerait une image etouffee.
            prise = prise.crop((0, 0, prise.width, min(boite[3] + 24, prise.height)))
        prise.save(image, optimize=True)
    return image


if __name__ == "__main__":
    _figer()
    for code in ("fr", "en"):
        chemin = produire(code)
        print(f"  {chemin.relative_to(RACINE)}")
        image = photographier(chemin)
        if image:
            print(f"  {image.relative_to(RACINE)}")
