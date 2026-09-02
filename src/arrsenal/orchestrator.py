"""Orchestration : preflight, pre-semis, generation, demarrage, cablage.

Ce module ne connait NI Typer NI Textual. La CLI et le TUI l'appellent tous les
deux, et ne font que rendre les evenements qu'il emet. C'est ce qui garantit que
le wizard et la ligne de commande ne divergeront jamais.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from . import catalog, compose, dashboard, seed
from .clients.arr import ArrClient
from .layout import PROFILE_DEFAULTS, create_tree, resolve_ids
from .models import PlatformProfile, ServiceInstance, StackConfig
from .runner import (
    Check,
    Compose,
    check_disk_space,
    check_docker,
    check_hardlinks,
    check_port_free,
)
from .wiring import StepResult, Wirer


class InstallAborted(RuntimeError):
    """Echec bloquant : le message est destine a l'utilisateur tel quel."""


@dataclass
class Progress:
    """Evenement d'avancement, rendu differemment par la CLI et par le TUI."""

    phase: str
    message: str
    ok: bool = True
    done: bool = False


ProgressFn = Callable[[Progress], None]


def _noop(_: Progress) -> None:
    return None


# ----------------------------------------------------------------- construction


def build_config(
    *,
    services: list[str],
    config_root: str | None = None,
    data_root: str | None = None,
    platform: PlatformProfile = PlatformProfile.GENERIC_LINUX,
    host: str = "localhost",
    timezone: str = "Etc/UTC",
    username: str = "arrsenal",
) -> StackConfig:
    """Construit une StackConfig complete, secrets generes.

    Les prerequis manquants sont ajoutes automatiquement : cocher Flood tire
    Transmission.
    """
    defaults = PROFILE_DEFAULTS[platform]
    uid, gid, source, certain = resolve_ids(platform)

    cfg = StackConfig(
        platform=platform,
        config_root=config_root or defaults.config_root,
        data_root=data_root or defaults.data_root,
        puid=uid,
        pgid=gid,
        timezone=timezone,
        host=host,
        ids_source=source,
        ids_certain=certain,
        username=username,
    )
    for sid in catalog.resolve_dependencies(services):
        cfg.services[sid] = new_instance(cfg, sid)
    return cfg


#: Familles qui recoivent un identifiant et un mot de passe.
_AVEC_COMPTE = ("arr", "transmission", "qbittorrent", "jellyfin", "autobrr", "qui")


def new_instance(cfg: StackConfig, service_id: str) -> ServiceInstance:
    """Instance neuve d'un service, secrets generes.

    Extrait de `build_config` pour que l'ajout d'un service APRES l'installation
    produise exactement la meme chose qu'une installation initiale. Deux
    fabriques auraient fini par diverger, et la difference ne se serait vue que
    chez quelqu'un dont la stack a grandi.
    """
    spec = catalog.get(service_id)
    inst = ServiceInstance(
        spec_id=service_id,
        host_port=spec.default_host_port,
        image=spec.image,
        # Par defaut, le port hote vaut le port interne. Le decalage se decide
        # au moment ou un conflit apparait, pas ici.
        extra_ports={interne: interne for _libelle, interne in spec.extra_ports},
    )
    if spec.api_family == "arr":
        inst.api_key = seed.generate_api_key()
    if spec.api_family in _AVEC_COMPTE:
        inst.username = cfg.username
        inst.password = seed.generate_password()
    return inst


def our_published_ports(cfg: StackConfig, project_dir: Path | None) -> set[int]:
    """Ports deja publies par NOTRE propre pile.

    Reinstaller la meme stack n'est pas un conflit : ces ports nous appartiennent
    et seront liberes par l'arret prealable. Sans cette distinction, le preflight
    refusait de rejouer une installation sur une stack en marche — c'est-a-dire
    le cas le plus courant apres un premier essai.
    """
    if project_dir is None:
        return set()
    ports: set[int] = set()
    for row in Compose(project_dir, cfg.project_name).ps_json():
        for publie in row.get("Publishers") or []:
            port = publie.get("PublishedPort")
            if isinstance(port, int) and port:
                ports.add(port)
    return ports


def preflight(cfg: StackConfig, project_dir: Path | None = None) -> list[Check]:
    checks = check_docker()
    nos_ports = our_published_ports(cfg, project_dir)
    for sid in catalog.STARTUP_ORDER:
        # Un service sans interface web ne publie rien : Recyclarr tourne sur une
        # planification. Le controler afficherait « port 0 : libre », une ligne
        # qui n'apprend rien et fait douter du reste du tableau.
        if not cfg.enabled(sid):
            continue
        inst = cfg.services[sid]
        # TOUS les ports publies, pas seulement le principal : un service peut
        # en ouvrir plusieurs, et un seul conflit fait echouer `compose up`
        # pour la pile entiere.
        for port in [inst.host_port, *sorted(inst.extra_ports.values())]:
            if not port:
                continue
            if port in nos_ports:
                checks.append(
                    Check(f"port {port} ({sid})", True, "occupe par votre propre pile arrsenal")
                )
            else:
                checks.append(check_port_free(port, sid))
    checks.append(check_disk_space(cfg.data_root))
    checks.append(check_hardlinks(cfg.data_root))
    checks.append(check_existing_config(cfg))
    return checks


def existing_configs(cfg: StackConfig) -> list[str]:
    """Services dont la configuration existe DEJA sous config_root."""
    present = []
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        directory = Path(cfg.config_path(sid))
        if directory.is_dir() and any(directory.iterdir()):
            present.append(sid)
    return present


def check_existing_config(cfg: StackConfig) -> Check:
    """Une configuration precedente est-elle reutilisee ?

    Le cas est piegeux et a ete rencontre a l'usage. arrsenal reprend la cle API
    des *arr dans leur `config.xml` existant, mais il ne PEUT pas retrouver les
    mots de passe de qBittorrent, Jellyfin, autobrr ou qui : ils n'y sont
    stockes que haches. Il en genere donc de nouveaux, les annonce dans le
    rapport... et les services refusent les identifiants.

    Le symptome est incomprehensible : « reponse illisible », « HTTP 401 »,
    « l'API a peut-etre change de forme ». La cause tient en une phrase, autant
    la dire avant de commencer.
    """
    present = existing_configs(cfg)
    hachants = [s for s in present if catalog.get(s).api_family in _HASHED_PASSWORDS]
    if not hachants:
        return Check(
            "configuration existante",
            True,
            "aucune, installation neuve" if not present else f"reprise : {', '.join(present)}",
            blocking=False,
        )
    return Check(
        "configuration existante",
        False,
        f"{', '.join(hachants)} ont deja une configuration dans {cfg.config_root}. "
        f"Leurs mots de passe y sont haches : arrsenal ne peut pas les relire, et ceux "
        f"qu'il vient de generer seront refuses. Reprenez l'installation d'origine avec "
        f"--project-dir, ou supprimez ces dossiers pour repartir a zero.",
        blocking=False,
    )


#: Services dont le mot de passe n'est stocke que sous forme hachee : impossible
#: a relire, donc impossible a reprendre.
_HASHED_PASSWORDS = ("qbittorrent", "transmission", "jellyfin", "autobrr", "qui")


def unusable_configs(cfg: StackConfig) -> list[str]:
    """Services dont la configuration existante empeche une reprise propre.

    Ceux-la seulement : les *arr se reprennent tres bien, leur cle API se relit
    dans leur `config.xml`.
    """
    return [
        sid for sid in existing_configs(cfg) if catalog.get(sid).api_family in _HASHED_PASSWORDS
    ]


def reset_configs(cfg: StackConfig, services: list[str]) -> list[Path]:
    """Supprime la configuration des services indiques. Renvoie ce qui a ete efface.

    Fonction destructrice, donc bornee de trois facons, et il faut que ces trois
    verrous se lisent d'un coup d'oeil :

    1. seuls des services du CATALOGUE sont acceptes, jamais un chemin libre ;
    2. le dossier doit se trouver sous `config_root`, verifie APRES resolution
       des liens symboliques et des `..` ;
    3. `data_root` n'est jamais parcouru : les medias ne sont pas en jeu, meme
       si l'appelant se trompe.
    """
    racine = Path(cfg.config_root).resolve()
    efface: list[Path] = []
    for sid in services:
        catalog.get(sid)  # leve une erreur lisible si le service est inconnu
        dossier = Path(cfg.config_path(sid)).resolve()
        if not dossier.is_dir():
            continue
        if racine not in dossier.parents:
            raise ValueError(f"{dossier} n'est pas sous {racine} : suppression refusee")
        shutil.rmtree(dossier)
        efface.append(dossier)
    return efface


def blocking_failures(checks: list[Check]) -> list[Check]:
    return [c for c in checks if not c.ok and c.blocking]


def seed_all(cfg: StackConfig) -> list[str]:
    """Pre-seme les configurations. Renvoie les actions effectuees.

    Un fichier existant fait toujours autorite : on adopte sa cle plutot que de
    lui imposer la notre.
    """
    actions: list[str] = []
    for sid in seeded_services(cfg):
        spec, inst = catalog.get(sid), cfg.services[sid]
        cfg_dir = Path(cfg.config_path(sid))

        if spec.api_family == "arr":
            effective, written = seed.seed_arr(
                cfg_dir,
                api_key=inst.api_key or "",
                port=spec.internal_port,
                instance_name=spec.display_name,
                username=inst.username or "arrsenal",
                password=inst.password or "",
            )
            if not written:
                inst.api_key = effective
            actions.append(
                f"{sid} : config.xml {'pre-seme' if written else 'existant, cle reprise'}"
            )
        elif spec.api_family == "qbittorrent":
            _written, message = seed.seed_qbittorrent(
                cfg_dir,
                username=inst.username or "arrsenal",
                password=inst.password or "",
                port=spec.internal_port,
            )
            actions.append(f"{sid} : {message}")
        elif spec.api_family == "transmission":
            _written, message = seed.seed_transmission(
                cfg_dir,
                rpc_username=inst.username or "arrsenal",
                rpc_password=inst.password or "",
            )
            actions.append(f"{sid} : {message}")
    return actions


def wait_for_download_clients(cfg: StackConfig, on_progress: ProgressFn = _noop) -> None:
    """Attend que les clients de telechargement repondent.

    On attendait les *arr, pas eux. Or c'est le *arr qui VALIDE la connexion au
    moment d'enregistrer le client : si qBittorrent n'a pas fini de demarrer, il
    refuse avec « Authentication Failure », un message qui accuse les
    identifiants alors qu'ils sont bons. Constate apres une reinstallation, ou
    le conteneur redemarre juste avant le cablage.

    N'importe quelle reponse HTTP suffit : elle prouve que le service ecoute.
    """
    import httpx

    from .clients.base import wait_until

    for sid in catalog.DOWNLOAD_CLIENTS:
        if not cfg.enabled(sid) or cfg.services[sid].adopted:
            continue
        url = cfg.services[sid].url(cfg.host)

        def probe(adresse: str = url) -> bool:
            try:
                httpx.get(adresse, timeout=5.0, follow_redirects=False)
            except httpx.HTTPError:
                return False
            return True

        resultat = wait_until(probe, label=sid, timeout=180.0)
        message = (
            f"{catalog.get(sid).display_name} pret"
            if resultat.ready
            else f"{catalog.get(sid).display_name} ne repond pas : {resultat.detail}"
        )
        if resultat.ready and sid == "qbittorrent":
            leve = _lift_qbittorrent_ban(cfg)
            if leve:
                message += ", bannissement leve"
        on_progress(Progress("attente", message, ok=resultat.ready))


def _lift_qbittorrent_ban(cfg: StackConfig) -> bool:
    """Leve un bannissement d'adresse dans qBittorrent, s'il y en a un.

    qBittorrent bannit une adresse apres cinq echecs d'authentification, pour une
    heure. Une installation qui s'est trompee de mot de passe — apres une
    reinstallation, par exemple — fait donc bannir l'adresse de Sonarr. Le
    symptome ensuite est cruel : le mot de passe est devenu correct, mais le
    *arr recoit un 403 et refuse d'enregistrer le client sur
    « Authentication Failure », en accusant les identifiants.

    Verifie : depuis l'hote la connexion repondait 204, depuis le conteneur
    Sonarr 403. Un redemarrage vide la liste des bannis, et la meme requete
    repond 204.
    """
    import httpx

    from .clients.base import wait_until

    inst = cfg.services["qbittorrent"]
    try:
        reponse = httpx.post(
            f"{inst.url(cfg.host)}/api/v2/auth/login",
            data={"username": inst.username or "", "password": inst.password or ""},
            headers={"Referer": inst.url(cfg.host)},
            timeout=15.0,
        )
    except httpx.HTTPError:
        return False
    if reponse.status_code != 403 or cfg.project_dir is None:
        return False

    ok, _message = Compose(Path(str(cfg.project_dir)), cfg.project_name).control(
        "restart", "qbittorrent"
    )
    if not ok:
        return False
    wait_until(
        lambda: httpx.get(f"{inst.url(cfg.host)}/api/v2/app/version", timeout=5.0).is_success,
        label="qbittorrent",
        timeout=120.0,
    )
    return True


def wait_for_arrs(cfg: StackConfig, on_progress: ProgressFn = _noop) -> None:
    """Attend que chaque *arr reponde AVEC NOTRE CLE, pas juste qu'il ecoute."""
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        spec, inst = catalog.get(sid), cfg.services[sid]
        if spec.api_family != "arr":
            continue
        with ArrClient(
            inst.url(cfg.host), inst.api_key or "", api_version=spec.api_version, name=sid
        ) as client:
            client.wait_ready()
            on_progress(Progress("attente", f"{spec.display_name} {client.version}"))


# -------------------------------------------------------------------- pipeline


def install(
    cfg: StackConfig,
    project_dir: Path,
    *,
    on_progress: ProgressFn = _noop,
    on_step: Callable[[StepResult], None] | None = None,
) -> list[StepResult]:
    """Deroule l'installation complete et renvoie le resultat du cablage.

    Leve InstallAborted avec un message actionnable en cas d'echec bloquant.
    """
    cfg.project_dir = project_dir
    created = create_tree(cfg.data_root, cfg.config_root, list(cfg.services))
    on_progress(Progress("arborescence", f"{len(created)} dossiers crees"))

    written = compose.write_artifacts(cfg, project_dir)
    on_progress(Progress("artefacts", ", ".join(p.name for p in written)))
    runner = Compose(project_dir, cfg.project_name)

    # Arreter AVANT de pre-semer, si une stack du meme nom tourne deja. Deux
    # raisons, toutes deux constatees a l'usage :
    #
    # - qBittorrent garde sa configuration en memoire. Reecrire son mot de passe
    #   pendant qu'il tourne ne change rien pour lui, et le *arr refuse ensuite
    #   d'enregistrer le client sur « Authentication Failure » ;
    # - Transmission REECRIT son settings.json a l'arret. Notre modification
    #   serait purement et simplement effacee quelques minutes plus tard.
    arretes, _ = runner.stop()
    on_progress(
        Progress(
            "arret",
            "conteneurs existants arretes avant pre-semis"
            if arretes
            else "aucun conteneur a arreter",
        )
    )

    for action in seed_all(cfg):
        on_progress(Progress("pre-semis", action))

    # Le pre-semis peut adopter la cle API d'un config.xml existant : les
    # artefacts doivent refleter ce qui sera reellement utilise.
    compose.write_artifacts(cfg, project_dir)

    valid, message = runner.config_valid()
    if not valid:
        raise InstallAborted(f"Le fichier compose genere est invalide : {message}")

    on_progress(Progress("demarrage", "docker compose up (peut prendre plusieurs minutes)"))
    ok, message = runner.up()
    if not ok:
        raise InstallAborted(f"docker compose up a echoue : {message}")

    wait_for_arrs(cfg, on_progress)
    wait_for_download_clients(cfg, on_progress)

    wirer = Wirer(cfg)
    try:
        results = wirer.execute(on_step=on_step)
    finally:
        wirer.close()

    # Le cablage enrichit la config : la cle API Jellyfin n'existe qu'apres son
    # assistant de demarrage. On repersiste pour que .env et stack.yml soient
    # complets et que `wire` reste rejouable seul.
    compose.write_artifacts(cfg, project_dir)

    page = dashboard.write(cfg, project_dir, failed=sum(1 for r in results if not r.ok))
    # La page d'acces est un fichier fige : ni etat des services, ni mises a
    # jour, ni boutons. Tout cela vient de `arrsenal serve` — encore faut-il
    # pouvoir le lancer. Un utilisateur qui a double-clique un executable n'a pas
    # `arrsenal` dans son PATH : on lui depose donc un lanceur cliquable.
    lanceur = dashboard.write_admin_launcher(project_dir)
    on_progress(Progress("page d'acces", f"{page} (+ {lanceur.name})"))

    on_progress(Progress("cablage", "termine", ok=all(r.ok for r in results), done=True))
    return results


# ------------------------------------------------------------------ inspection


def has_download_client(cfg: StackConfig) -> bool:
    """Un client de telechargement est-il installe ?

    Sans lui, l'avertissement VPN n'a aucun sens : il n'y a pas de trafic
    BitTorrent a proteger.
    """
    return any(cfg.enabled(sid) for sid in catalog.DOWNLOAD_CLIENTS)


def planned_links(cfg: StackConfig) -> int:
    """Nombre de liens que le cablage va poser. Sert au recapitulatif."""
    return len(Wirer(cfg).build_plan())


#: Evenements emis par install() en dehors du pre-semis, de l'attente et du
#: cablage : arborescence, artefacts, arret prealable, demarrage, page d'acces,
#: fin. Un test deroule un vrai install() pour confronter ce compte aux
#: evenements reellement emis : il a rattrape cette valeur des son changement.
_FIXED_EVENTS = 6


def seeded_services(cfg: StackConfig) -> list[str]:
    """Services pour lesquels seed_all emet une action.

    Cette liste et celle de `seed_all` doivent decrire les memes services : c'est
    `seed_all` qui l'utilise, precisement pour qu'elles ne puissent pas diverger.
    """
    return [
        sid
        for sid in catalog.STARTUP_ORDER
        if cfg.enabled(sid)
        and catalog.get(sid).api_family in ("arr", "qbittorrent", "transmission")
    ]


def expected_events(cfg: StackConfig) -> int:
    """Nombre total d'evenements que l'installation va emettre.

    Sert a la barre de progression. Un affichage qui n'atteint jamais 100 %, ou
    qui le depasse, fait douter de tout le reste : les consommateurs bornent donc
    l'avancement, et cette valeur reste une estimation honnete plutot qu'une
    promesse.
    """
    arrs = [sid for sid in catalog.STARTUP_ORDER if cfg.enabled(sid) and _is_arr(sid)]
    clients = [
        sid
        for sid in catalog.DOWNLOAD_CLIENTS
        if cfg.enabled(sid) and not cfg.services[sid].adopted
    ]
    return (
        _FIXED_EVENTS
        + len(seeded_services(cfg))
        + len(arrs)
        + len(clients)
        + planned_links(cfg)
    )


def _is_arr(service_id: str) -> bool:
    return catalog.get(service_id).api_family == "arr"


def iter_selected(cfg: StackConfig) -> Iterator[tuple[str, ServiceInstance]]:
    for sid in catalog.STARTUP_ORDER:
        if cfg.enabled(sid):
            yield sid, cfg.services[sid]


# --------------------------------------------------------------- rotation


#: Familles dont le mot de passe peut etre change sans reinstaller. La liste vit
#: dans catalog : la page d'administration en a besoin, et elle ne peut pas
#: importer orchestrator, qui l'importe deja.
ROTATABLE = catalog.ROTATABLE_FAMILIES


def rotate_password(
    cfg: StackConfig,
    project_dir: Path,
    service_id: str,
    *,
    on_progress: ProgressFn = _noop,
) -> tuple[bool, str, str]:
    """Change le mot de passe d'un service, puis RECABLE ce qui en depend.

    Renvoie (succes, message, nouveau mot de passe). Le mot de passe n'est
    renvoye que pour etre affiche a qui vient de le demander ; il n'est
    journalise nulle part.

    Le recablage est le coeur du sujet, et la raison pour laquelle cette
    fonction existe. Un mot de passe de client de telechargement change a la
    main casse SIX liaisons en silence : les quatre *arr et Prowlarr gardent
    l'ancien, leur bouton Test echoue, et rien ne l'explique. `Wirer.execute`
    est idempotent et `sync_fields` met a jour les entrees existantes : rejouer
    le cablage suffit donc a tout realigner.

    Chaque famille a son chemin, et un seul est verifie par famille :

    - **arr** : `PUT config/host`, l'application hache elle-meme ;
    - **qBittorrent** : `setPreferences`, a chaud. Reecrire son fichier serait
      inutile — il garde sa configuration en memoire et la reecrit a l'arret ;
    - **Transmission** : son settings.json, conteneur ARRETE. Son RPC ne sait
      pas changer `rpc-password` ; c'est la voie prevue, et il rehache au
      demarrage suivant.
    """
    from .clients.arr import ArrClient
    from .clients.qbittorrent import QBittorrentClient
    from .runner import Compose
    from .wiring import Wirer

    if not cfg.enabled(service_id):
        return False, f"service inconnu : {service_id}", ""
    spec, inst = catalog.get(service_id), cfg.services[service_id]
    if spec.api_family not in ROTATABLE:
        return False, f"{spec.display_name} ne sait pas changer son mot de passe ici", ""

    cfg.project_dir = project_dir
    nouveau = seed.generate_password()
    ancien = inst.password or ""
    runner = Compose(project_dir, cfg.project_name)
    url = inst.url(cfg.host)

    try:
        if spec.api_family == "arr":
            client = ArrClient(
                url, inst.api_key or "", api_version=spec.api_version, name=service_id
            )
            try:
                client.ensure_web_user(inst.username or cfg.username, nouveau)
            finally:
                client.close()
        elif spec.api_family == "qbittorrent":
            with QBittorrentClient(url, inst.username or cfg.username, ancien) as client:
                client.login()
                client.set_password(nouveau)
        else:
            # Transmission REECRIT son settings.json a l'arret : le modifier
            # pendant qu'il tourne reviendrait a l'effacer quelques minutes plus
            # tard. On l'arrete donc avant, comme le fait l'installation.
            arrete, message = runner.control("stop", service_id)
            if not arrete:
                return False, f"arret impossible : {message[:200]}", ""
            seed.seed_transmission(
                Path(cfg.config_path(service_id)),
                rpc_username=inst.username or cfg.username,
                rpc_password=nouveau,
            )
            demarre, message = runner.control("start", service_id)
            if not demarre:
                return False, f"redemarrage impossible : {message[:200]}", ""
    except Exception as exc:  # noqa: BLE001 - remonte a l'appelant, jamais au terminal
        return False, f"{type(exc).__name__} : {exc}", ""

    inst.password = nouveau
    on_progress(Progress("rotation", f"{spec.display_name} : mot de passe change"))

    # Persister AVANT de recabler : si le cablage echoue, le nouveau mot de passe
    # est deja celui du service, et .env doit le refleter — sinon arrsenal
    # afficherait un mot de passe qui n'ouvre plus rien.
    compose.write_artifacts(cfg, project_dir)

    wait_for_download_clients(cfg, on_progress)
    wirer = Wirer(cfg)
    try:
        results = wirer.execute()
    finally:
        wirer.close()
    compose.write_artifacts(cfg, project_dir)
    echecs = [r.name for r in results if not r.ok]
    dashboard.write(cfg, project_dir, failed=len(echecs))

    if echecs:
        return True, f"mot de passe change, mais {len(echecs)} liaison(s) en echec", nouveau
    return True, f"mot de passe change et {len(results)} liaisons recablees", nouveau


def rotate_api_key(
    cfg: StackConfig,
    project_dir: Path,
    service_id: str,
    *,
    on_progress: ProgressFn = _noop,
) -> tuple[bool, str, str]:
    """Change la cle API d'un *arr, puis RECABLE ce qui la porte.

    Renvoie (succes, message, nouvelle cle).

    Une cle API n'est pas un mot de passe : elle ne sert pas a se connecter, elle
    sert a ce que les AUTRES services parlent a celui-ci. La changer sans
    recabler ne casse donc pas une connexion — elle casse le cablage entier, en
    silence, du cote de ceux qui l'utilisaient.

    Trois choses la portent, et les trois sont realignees par le cablage :
    l'entree Application de Prowlarr, la notification de rafraichissement
    Jellyfin, et la page d'acces.

    Le chemin passe par `config.xml` et un redemarrage, PAS par l'API. Verifie
    contre Sonarr 4.0.19 : `PUT config/host` avec une nouvelle cle repond
    **202 Accepted** et ne change rien — soixante secondes plus tard la cle
    relue est toujours l'ancienne, et la nouvelle repond 401. Seuls les *arr
    sont concernes ; les autres familles n'ont pas de cle qu'arrsenal choisisse.
    """
    from .runner import Compose
    from .wiring import Wirer

    if not cfg.enabled(service_id):
        return False, f"service inconnu : {service_id}", ""
    spec, inst = catalog.get(service_id), cfg.services[service_id]
    if spec.api_family != "arr":
        return False, f"{spec.display_name} n'a pas de cle API geree par arrsenal", ""

    cfg.project_dir = project_dir
    nouvelle = seed.generate_api_key()

    if not seed.replace_arr_api_key(Path(cfg.config_path(service_id)), nouvelle):
        return False, f"config.xml de {spec.display_name} introuvable ou inattendu", ""

    inst.api_key = nouvelle
    # Persister AVANT le redemarrage : la cle est deja celle de l'application,
    # et un .env resté sur l'ancienne rendrait la stack injoignable.
    compose.write_artifacts(cfg, project_dir)

    runner = Compose(project_dir, cfg.project_name)
    ok, message = runner.control("restart", service_id)
    if not ok:
        return False, f"cle changee mais redemarrage impossible : {message[:200]}", nouvelle
    on_progress(Progress("rotation", f"{spec.display_name} : cle API changee"))

    wait_for_arrs(cfg, on_progress)
    wirer = Wirer(cfg)
    try:
        results = wirer.execute()
    finally:
        wirer.close()
    compose.write_artifacts(cfg, project_dir)
    echecs = [r.name for r in results if not r.ok]
    dashboard.write(cfg, project_dir, failed=len(echecs))

    if echecs:
        return True, f"cle API changee, mais {len(echecs)} liaison(s) en echec", nouvelle
    return True, f"cle API changee et {len(results)} liaisons recablees", nouvelle


# ------------------------------------------------------- ajout apres coup


def installable(cfg: StackConfig) -> list[str]:
    """Services du catalogue absents de l'installation, dans l'ordre d'affichage."""
    return [
        sid
        for sid in catalog.STARTUP_ORDER
        if not cfg.enabled(sid) and not catalog.get(sid).internal
    ]


def add_service(
    cfg: StackConfig,
    project_dir: Path,
    service_id: str,
    *,
    on_progress: ProgressFn = _noop,
) -> tuple[bool, str, list[str]]:
    """Installe et cable un service absent de l'installation initiale.

    Renvoie (succes, message, services reellement ajoutes) — au pluriel, parce
    qu'un service peut en tirer d'autres : cocher Flood tire Transmission, et
    l'ajouter sans son prerequis produirait une interface qui ne pilote rien.

    Deux garde-fous avant d'ecrire quoi que ce soit :

    - le port doit etre LIBRE. Ajouter un service dont le port est deja pris par
      autre chose ferait echouer `docker compose up` pour toute la pile, pas
      seulement pour le nouveau venu ;
    - on ne pre-seme QUE les nouveaux. Repasser sur les anciens reecrirait des
      configurations en marche, ce que l'installation evite deja en arretant
      tout d'abord — un ajout, lui, ne doit rien arreter.

    Le cablage est ensuite rejoue en entier. Il est idempotent, et c'est la
    seule facon de relier le nouveau venu aux anciens dans les deux sens : un
    client de telechargement ajoute doit apparaitre dans les quatre *arr, et un
    *arr ajoute doit apparaitre dans Prowlarr et dans autobrr.
    """
    from .wiring import Wirer

    try:
        catalog.get(service_id)
    except Exception:  # noqa: BLE001 - le catalogue leve un message deja lisible
        return False, f"service inconnu : {service_id}", []
    if cfg.enabled(service_id):
        return False, f"{catalog.get(service_id).display_name} est deja installe", []

    cfg.project_dir = project_dir
    nouveaux = [
        sid for sid in catalog.resolve_dependencies([service_id, *cfg.services]) if not cfg.enabled(sid)
    ]

    # Les instances D'ABORD, le controle de port ENSUITE : c'est l'instance qui
    # decide du port publie, pas le catalogue. Verifier le defaut du catalogue
    # reviendrait a controler un port qui n'est pas celui qu'on va ouvrir.
    instances = {sid: new_instance(cfg, sid) for sid in nouveaux}

    nos_ports = our_published_ports(cfg, project_dir)
    for sid, inst in instances.items():
        port = inst.host_port
        if not port or port in nos_ports:
            continue
        if not check_port_free(port, sid).ok:
            return False, f"port {port} deja occupe ({catalog.get(sid).display_name})", []

    cfg.services.update(instances)
    on_progress(Progress("ajout", ", ".join(catalog.get(s).display_name for s in nouveaux)))

    create_tree(cfg.data_root, cfg.config_root, nouveaux)
    compose.write_artifacts(cfg, project_dir)

    # Pre-semis limite aux nouveaux : les anciens tournent, et reecrire la
    # configuration d'un service en marche est sans effet au mieux, destructeur
    # au pire — Transmission reecrit son fichier en s'arretant.
    partiel = cfg.model_copy(update={"services": {s: cfg.services[s] for s in nouveaux}})
    partiel.project_dir = project_dir
    for action in seed_all(partiel):
        on_progress(Progress("pre-semis", action))
    compose.write_artifacts(cfg, project_dir)

    runner = Compose(project_dir, cfg.project_name)
    valide, message = runner.config_valid()
    if not valide:
        return False, f"compose genere invalide : {message[:300]}", []

    on_progress(Progress("demarrage", "docker compose up"))
    ok, message = runner.up()
    if not ok:
        return False, f"docker compose up a echoue : {message[:300]}", []

    wait_for_arrs(cfg, on_progress)
    wait_for_download_clients(cfg, on_progress)

    wirer = Wirer(cfg)
    try:
        results = wirer.execute()
    finally:
        wirer.close()
    compose.write_artifacts(cfg, project_dir)
    echecs = [r.name for r in results if not r.ok]
    dashboard.write(cfg, project_dir, failed=len(echecs))

    noms = ", ".join(catalog.get(s).display_name for s in nouveaux)
    if echecs:
        return True, f"{noms} installe, mais {len(echecs)} liaison(s) en echec", nouveaux
    return True, f"{noms} installe et {len(results)} liaisons cablees", nouveaux
