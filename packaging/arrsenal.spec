# Recette PyInstaller de l'executable Windows.
#
#     pyinstaller packaging/arrsenal.spec --noconfirm
#
# Trois points qu'il a fallu trouver, aucun devinable :
#
# - le point d'entree ne peut pas etre `src/arrsenal/__main__.py` : il fait un
#   import RELATIF, et PyInstaller execute son script d'entree sans paquet
#   parent. D'ou `packaging/launcher.py` ;
# - `app.tcss` doit etre embarque explicitement. Sans lui, Textual leve
#   `StylesheetError` au demarrage et l'assistant ne s'ouvre pas du tout ;
# - Textual charge des ressources et des widgets par nom : `collect_all` evite
#   d'avoir a lister ses modules internes un par un.
#
# Verifie sur l'executable produit : 137 regles de style chargees, les 11
# services affiches, et une installation complete de bout en bout.

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src"

textual_datas, textual_binaries, textual_hidden = collect_all("textual")

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(SRC)],
    binaries=textual_binaries,
    datas=[(str(SRC / "arrsenal" / "tui" / "app.tcss"), "arrsenal/tui"), *textual_datas],
    hiddenimports=[
        *textual_hidden,
        # Importes tardivement dans le code : PyInstaller ne peut pas les voir.
        "arrsenal.tui.app",
        "arrsenal.tui.indexers",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Uniquement utiles au developpement : ils pesent sans rien apporter.
        "pytest",
        "_pytest",
        "PyInstaller",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="arrsenal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # L'assistant est une application de TERMINAL : sans console, il n'aurait
    # nulle part ou s'afficher.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
