"""Tests des mots de passe generes.

Ces valeurs traversent un `.env` lu par Docker Compose, une ligne de commande de
conteneur, un XML, un INI et plusieurs charges JSON. Un caractere mal choisi ne
casse pas la generation : il casse l'installation, plusieurs minutes plus tard,
avec un message incomprehensible.
"""

from __future__ import annotations

import re
import string

import pytest

from arrsenal import compose, seed
from arrsenal.orchestrator import build_config


def test_le_mot_de_passe_change_a_chaque_appel():
    tirages = {seed.generate_password() for _ in range(200)}
    assert len(tirages) == 200


def test_longueur_par_defaut_confortable():
    """Bien au-dela des 12 caracteres usuels : personne n'a a les retenir."""
    assert seed.PASSWORD_LENGTH >= 20
    assert len(seed.generate_password()) == seed.PASSWORD_LENGTH


@pytest.mark.parametrize("longueur", [4, 12, 20, 64])
def test_chaque_classe_est_garantie(longueur):
    """« Presque toujours » ne suffit pas : certains services exigent un chiffre.

    Sur 200 tirages, un seul manquement se verrait ici.
    """
    for _ in range(200):
        pwd = seed.generate_password(longueur)
        assert len(pwd) == longueur
        assert any(c in string.ascii_lowercase for c in pwd), pwd
        assert any(c in string.ascii_uppercase for c in pwd), pwd
        assert any(c in string.digits for c in pwd), pwd
        assert any(c in seed.PASSWORD_SPECIALS for c in pwd), pwd


def test_une_longueur_impossible_est_refusee():
    with pytest.raises(ValueError):
        seed.generate_password(3)


def test_aucun_caractere_dangereux_n_est_tire():
    """Le detail qui compte.

    `$` serait interprete par Compose comme une interpolation de variable, et le
    mot de passe arriverait vide dans le conteneur. L'apostrophe fermerait la
    valeur du .env. Les metacaracteres de shell casseraient un script qui source
    ce fichier — la CI de ce depot en fait partie.
    """
    interdits = set("$'\"\\`# &;|<>()[]{}/~") | {" "}
    tirages = "".join(seed.generate_password() for _ in range(300))

    assert not (set(tirages) & interdits), sorted(set(tirages) & interdits)


def test_l_alphabet_reste_assez_large():
    """75 caracteres possibles, soit environ 125 bits sur 20 tirages."""
    alphabet = set("".join(seed.PASSWORD_CLASSES))
    assert len(alphabet) >= 70
    # Toutes les classes sont distinctes : aucun caractere compte deux fois.
    assert len(alphabet) == sum(len(groupe) for groupe in seed.PASSWORD_CLASSES)


def test_la_cle_api_reste_hexadecimale():
    """Les *arr refusent une cle qui n'est pas hexadecimale : pas de special ici."""
    for _ in range(50):
        key = seed.generate_api_key()
        assert len(key) == 32
        assert all(c in string.hexdigits for c in key)


# ----------------------------------------------------------------- fichier .env


def test_les_valeurs_du_env_sont_entre_apostrophes(tmp_path):
    cfg = build_config(
        services=["sonarr"], config_root=str(tmp_path / "c"), data_root=str(tmp_path / "d")
    )
    cfg.services["sonarr"].password = "Aa1" + seed.PASSWORD_SPECIALS

    env = compose.render_env(cfg)
    ligne = re.search(r"^SONARR_PASS=(.*)$", env, re.MULTILINE).group(1)

    assert ligne == f"'Aa1{seed.PASSWORD_SPECIALS}'"


def test_une_apostrophe_venue_d_ailleurs_est_neutralisee(tmp_path):
    """Elle est exclue de l'alphabet, mais une valeur peut venir d'un stack.yml
    edite a la main."""
    cfg = build_config(
        services=["sonarr"], config_root=str(tmp_path / "c"), data_root=str(tmp_path / "d")
    )
    cfg.services["sonarr"].password = "avant'apres"

    ligne = re.search(r"^SONARR_PASS=(.*)$", compose.render_env(cfg), re.MULTILINE).group(1)

    # Forme POSIX : on ferme, on echappe, on rouvre.
    assert ligne == "'avant'\\''apres'"


def test_le_env_se_relit_sans_perte(tmp_path):
    """Un analyseur de .env doit retrouver la valeur exacte, apostrophes retirees."""
    cfg = build_config(
        services=["sonarr", "prowlarr"],
        config_root=str(tmp_path / "c"),
        data_root=str(tmp_path / "d"),
    )
    env = compose.render_env(cfg)

    valeurs = dict(re.findall(r"^(\w+)='(.*)'$", env, re.MULTILINE))
    assert valeurs["SONARR_PASS"] == cfg.services["sonarr"].password
    assert valeurs["PROWLARR_API_KEY"] == cfg.services["prowlarr"].api_key


def test_le_hachage_qbittorrent_supporte_les_caracteres_speciaux():
    """Le mot de passe n'est jamais ecrit en clair : seule son empreinte l'est."""
    import base64
    import hashlib

    pwd = "Aa1" + seed.PASSWORD_SPECIALS
    value = seed.qbittorrent_password_hash(pwd)

    assert value.startswith("@ByteArray(") and value.endswith(")")
    salt_b64, digest_b64 = value[len("@ByteArray(") : -1].split(":")
    recompute = hashlib.pbkdf2_hmac(
        "sha512", pwd.encode(), base64.b64decode(salt_b64), 100000, dklen=64
    )
    assert recompute == base64.b64decode(digest_b64)
    assert pwd not in value


def test_le_config_xml_echappe_ce_qu_il_faut():
    """`&` et `<` ne sont pas dans l'alphabet, mais l'XML doit rester valide."""
    import xml.etree.ElementTree as ET

    xml = seed.render_arr_config(
        api_key="a" * 32,
        port=8989,
        instance_name="Sonarr",
        username="arrsenal",
        password="Aa1" + seed.PASSWORD_SPECIALS,
    )
    root = ET.fromstring(xml)

    assert root.findtext("Password") == "Aa1" + seed.PASSWORD_SPECIALS
