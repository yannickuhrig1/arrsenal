"""La base de Silo vit dans un VOLUME Docker, jamais sur le disque de l'hote.

Ce n'est pas une preference de style. Mesure sur la meme machine, meme image
`pgvector/pgvector:pg18`, base vide dans les deux cas, Docker Desktop sous
Windows 11 :

    montage vers un dossier de l hote  -> « database migrations applied » apres 2935 s
    volume Docker nomme  -> les memes migrations apres 5 s

Silo enchaine des milliers de petites ecritures synchrones pendant ses
migrations de premier demarrage, et chacune traverse la couche de partage de
fichiers de Docker Desktop. Le premier essai reel a expire au bout de 300 s
alors que PostgreSQL fonctionnait tres bien : il etait 590 fois plus lent.

Ce fichier existe pour qu'un futur passage « uniformisons tous les montages »
casse un test plutot que l'installation de quelqu'un.
"""

from __future__ import annotations

from plugarr import catalog, compose, layout, orchestrator


def _cfg(*services: str):
    return orchestrator.build_config(
        services=list(services), config_root="/c", data_root="/d"
    )


def test_la_base_de_silo_est_un_volume_docker():
    bloc = compose.build_compose(_cfg("silo"))["services"]["silo-postgres"]

    assert bloc["volumes"] == [f"{compose.PG_VOLUME}:/var/lib/postgresql"]


def test_aucun_montage_vers_l_hote_pour_la_base():
    """Le detail qui coute 49 minutes : un `${CONFIG_ROOT}` de trop."""
    bloc = compose.build_compose(_cfg("silo"))["services"]["silo-postgres"]

    assert not any("CONFIG_ROOT" in v for v in bloc["volumes"])


def test_le_volume_est_declare():
    """Compose refuse un volume nomme qui n'est pas declare en tete de fichier."""
    doc = compose.build_compose(_cfg("silo"))

    assert compose.PG_VOLUME in doc["volumes"]


def test_pas_de_section_volumes_sans_silo():
    """Une section vide dans chaque compose serait du bruit."""
    assert "volumes" not in compose.build_compose(_cfg("sonarr"))


def test_aucun_dossier_de_configuration_pour_la_base(tmp_path):
    """Un dossier vide `config/silo-postgres` laisserait croire a une sauvegarde
    possible. Il n'y en a pas : la base est dans le volume."""
    config = tmp_path / "config"
    layout.create_tree(tmp_path / "data", config, ["silo", "silo-postgres", "silo-redis"])

    assert not (config / "silo-postgres").exists()
    assert catalog.CATALOG["silo-postgres"].config_dir is None


def test_le_dossier_cree_est_celui_que_le_compose_monte(tmp_path):
    """`silo-redis` monte `${CONFIG_ROOT}/silo/redis`. Creer `config/silo-redis`
    a cote laissait un dossier vide et Docker fabriquait le vrai tout seul."""
    config = tmp_path / "config"
    layout.create_tree(tmp_path / "data", config, ["silo", "silo-redis"])

    assert (config / "silo" / "redis").is_dir()
    assert not (config / "silo-redis").exists()


def test_une_desinstallation_totale_emporte_le_volume():
    """`--remove-config` promet de tout effacer. Sans `-v`, la base survivait :
    la promesse serait fausse depuis qu'elle a quitte CONFIG_ROOT."""
    import inspect

    from plugarr import cli

    source = inspect.getsource(cli.uninstall)
    assert "down(volumes=True)" in source
