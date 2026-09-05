"""Catalogue anglais, indexe sur la phrase francaise.

Ecrit a la main, verifie mecaniquement : `scripts/audit_traductions.py` echoue
si une phrase affichable n'a pas d'entree ici, **et** si une entree ne
correspond a aucune phrase du code. Les deux sens comptent — une entree morte
signale une phrase supprimee du code et oubliee ici, c'est-a-dire un catalogue
qui commence a mentir.

Le fichier est volontairement plat et sans logique : c'est une table de
correspondance, elle doit se relire en diagonale.

Les balises de mise en forme (`[b]`, `[dim]`, `[/green]`) sont celles de Rich.
Elles doivent etre reportees telles quelles : une balise ouverte et jamais
fermee s'affiche en clair au milieu du texte.
"""

from __future__ import annotations

EN: dict[str, str] = {
    # -- navigation et socle --------------------------------------------------
    "Retour": "Back",
    "Quitter": "Quit",
    "Continuer": "Continue",
    "Commencer": "Start",
    "Passer": "Skip",
    "Terminer": "Finish",
    "Fermer": "Close",
    "Restaurer": "Restore",
    "ECHEC": "FAILED",
    # -- accueil --------------------------------------------------------------
    "Deploie ET cable une stack media complete": (
        "Deploys AND wires a complete media stack"
    ),
    "Cet assistant va deployer les services que vous choisissez, puis "
    "[b]les cabler entre eux[/b] : cles API echangees, indexeurs synchronises, "
    "dossiers racine crees, bibliotheques scannees.\n\n"
    "Rien n'est ecrit avant l'ecran de recapitulatif.": (
        "This wizard will deploy the services you choose, then "
        "[b]wire them together[/b]: API keys exchanged, indexers synced, root "
        "folders created, libraries scanned.\n\n"
        "Nothing is written before the summary screen."
    ),
    "Langue de PlugArr": "PlugArr language",
    "Restaurer une sauvegarde": "Restore a backup",
    "Diagnostic impossible": "Diagnostic failed",
    # -- restauration ---------------------------------------------------------
    "Restaurer une installation sauvegardee": "Restore a saved installation",
    "Reposez une archive produite par [b]plugarr backup[/b] ou par le bouton "
    "[b]Sauvegarder la configuration[/b] de la page d'administration.\n\n"
    "Elle contient vos services, vos identifiants et tout ce que vous aviez "
    "saisi : indexeurs, profils, bibliotheques. [b]Vos medias ne sont pas "
    "dedans[/b] et ne seront pas touches.": (
        "Restore an archive produced by [b]plugarr backup[/b] or by the "
        "[b]Back up the configuration[/b] button on the admin page.\n\n"
        "It holds your services, your credentials and everything you entered: "
        "indexers, profiles, libraries. [b]Your media is not in it[/b] and will "
        "not be touched."
    ),
    "Fichier de sauvegarde (.zip)": "Backup file (.zip)",
    "Ou reposer la configuration [dim](vide = l'emplacement d'origine)[/dim]": (
        "Where to restore the configuration [dim](empty = its original "
        "location)[/dim]"
    ),
    "Examiner l'archive": "Inspect the archive",
    # -- selection des services ----------------------------------------------
    "Etape 1/3 - Quels services installer ?": "Step 1/3 - Which services to install?",
    "Mediatheque": "Media library",
    "Telechargement": "Downloads",
    "Serveur media": "Media server",
    "Interfaces": "Web UIs",
    "[yellow]Selectionnez au moins un service.[/yellow]": (
        "[yellow]Select at least one service.[/yellow]"
    ),
    # -- chemins et plateforme ------------------------------------------------
    "Etape 2/3 - Chemins et plateforme": "Step 2/3 - Paths and platform",
    "Profil de plateforme": "Platform profile",
    "Racine des configurations": "Configuration root",
    "Racine des donnees [dim](montee sur /data dans TOUS les conteneurs)[/dim]": (
        "Data root [dim](mounted on /data in EVERY container)[/dim]"
    ),
    "Identifiant [dim](le meme pour tous les services installes)[/dim]": (
        "Username [dim](the same one for every installed service)[/dim]"
    ),
    "Langue des services installes [dim](Sonarr, Jellyfin... ; celle de PlugArr "
    "se choisit sur l'ecran d'accueil)[/dim]": (
        "Language of the installed services [dim](Sonarr, Jellyfin...; PlugArr's "
        "own language is chosen on the welcome screen)[/dim]"
    ),
    "Nom de la pile Docker [dim](a changer pour en installer une SECONDE a "
    "cote)[/dim]": (
        "Docker stack name [dim](change it to install a SECOND one "
        "alongside)[/dim]"
    ),
    "Fuseau horaire": "Time zone",
    "Adresse de cette machine [dim](a changer si vous naviguerez depuis un "
    "autre poste)[/dim]": (
        "This machine's address [dim](change it if you will browse from another "
        "computer)[/dim]"
    ),
    "Verifier les chemins": "Check the paths",
    "[red]La racine des donnees ne peut pas etre vide.[/red]": (
        "[red]The data root cannot be empty.[/red]"
    ),
    # -- profils de qualite ---------------------------------------------------
    "Etape optionnelle - profils de qualite": "Optional step - quality profiles",
    "Sans profil de qualite, un *arr accepte [b]n'importe quel[/b] encodage : "
    "le premier resultat venu, pas le meilleur.\n"
    "[dim]Les profils viennent des TRaSH Guides. plugarr ne fait que poser "
    "l'adresse et la cle API dans le template que vous choisissez ici.[/dim]": (
        "Without a quality profile, an *arr accepts [b]any[/b] encoding: the "
        "first result that comes along, not the best one.\n"
        "[dim]The profiles come from the TRaSH Guides. plugarr only writes the "
        "URL and the API key into the template you pick here.[/dim]"
    ),
    "[dim]Chargement de la liste officielle…[/dim]": (
        "[dim]Loading the official list…[/dim]"
    ),
    # -- vpn -------------------------------------------------------------------
    "Etape optionnelle - VPN du client de telechargement": (
        "Optional step - download client VPN"
    ),
    "Sans VPN, le trafic BitTorrent sort sur [b]l'adresse IP publique de cette "
    "machine[/b], visible par tous les autres pairs.\n"
    "[dim]Avec Gluetun, le client de telechargement perd son propre reseau : il "
    "ne demarre pas tant que le tunnel n'est pas etabli, donc aucun paquet ne "
    "peut sortir en clair.[/dim]": (
        "Without a VPN, BitTorrent traffic leaves through [b]this machine's "
        "public IP address[/b], visible to every other peer.\n"
        "[dim]With Gluetun, the download client loses its own network: it does "
        "not start until the tunnel is up, so no packet can leave in the "
        "clear.[/dim]"
    ),
    "Sans VPN": "No VPN",
    "Faire passer le client par un VPN": "Route the client through a VPN",
    "Fournisseur": "Provider",
    "Protocole": "Protocol",
    "Cle privee WireGuard": "WireGuard private key",
    "Identifiant OpenVPN": "OpenVPN username",
    "Mot de passe OpenVPN": "OpenVPN password",
    "[dim]Ce fournisseur ne propose pas de filtre geographique : les serveurs "
    "viennent de votre propre configuration.[/dim]": (
        "[dim]This provider offers no geographic filter: the servers come from "
        "your own configuration.[/dim]"
    ),
    "[green]Configuration complete.[/green]": "[green]Configuration complete.[/green]",
    # -- recapitulatif ---------------------------------------------------------
    "Etape 3/3 - Recapitulatif (rien n'est encore ecrit)": (
        "Step 3/3 - Summary (nothing is written yet)"
    ),
    "Service": "Service",
    "Image": "Image",
    "URL": "URL",
    "Conserver ces configurations": "Keep these configurations",
    "Supprimer et repartir de zero": "Delete them and start over",
    "Installer et cabler": "Install and wire",
    # -- installation ----------------------------------------------------------
    "Installation et cablage": "Installing and wiring",
    "Preparation...": "Preparing...",
    # -- rapport ----------------------------------------------------------------
    "Acces": "Access",
    "Identifiant": "Username",
    "Mot de passe": "Password",
    "Cle API": "API key",
    "Ouvrir la page d'acces": "Open the access page",
    # -- indexeurs ---------------------------------------------------------------
    "Etape optionnelle - vos indexeurs": "Optional step - your indexers",
    "plugarr ne fournit et ne recommande [b]aucun[/b] indexeur. La liste "
    "ci-dessous est celle que votre propre Prowlarr embarque.\n"
    "[dim]Ajouter un indexeur le contacte pour valider vos identifiants : c'est "
    "Prowlarr qui l'impose, il n'existe pas d'enregistrement hors ligne.[/dim]": (
        "plugarr provides and recommends [b]no[/b] indexer. The list below is "
        "the one your own Prowlarr ships.\n"
        "[dim]Adding an indexer contacts it to validate your credentials: that "
        "is Prowlarr's rule, there is no offline registration.[/dim]"
    ),
    "Choisissez un indexeur a gauche.": "Pick an indexer on the left.",
    "[dim]Aucun identifiant requis.[/dim]": "[dim]No credentials required.[/dim]",
    "Ajouter cet indexeur": "Add this indexer",
    "Passer cette etape": "Skip this step",
    # -- notes du catalogue ------------------------------------------------------
    # Affichees sous chaque service a l'ecran de selection. Elles arrivent au
    # widget par une variable : c'est leur declaration dans `catalog.py` que
    # l'audit releve.
    "Pivot du cablage : alimente les autres en indexeurs.": (
        "The wiring hub: it feeds indexers to all the others."
    ),
    "Series TV.": "TV shows.",
    "Films.": "Movies.",
    "Client torrent par defaut.": "Default torrent client.",
    "Musique. Son API est en v1, pas en v3.": "Music. Its API is v1, not v3.",
    "Categories natives avec chemin dedie.": (
        "Native categories with a dedicated path."
    ),
    "Serveur media. Bibliotheques creees pour vous.": (
        "Media server. Libraries created for you."
    ),
    "Demandes de medias. Successeur de Jellyseerr et d'Overseerr.": (
        "Media requests. Successor to Jellyseerr and Overseerr."
    ),
    "Client Usenet. Complete les torrents, il ne les remplace pas.": (
        "Usenet client. It complements torrents, it does not replace them."
    ),
    "Musique, de la demande au rangement. REMPLACE Lidarr, ne le complete pas.": (
        "Music, from request to filing. REPLACES Lidarr, does not complement it."
    ),
    "Livres et livres audio. Remplit les bibliotheques books et audiobooks.": (
        "Books and audiobooks. Fills the books and audiobooks libraries."
    ),
    "Base de donnees de Silo. Installee avec lui, jamais seule.": (
        "Silo's database. Installed with it, never on its own."
    ),
    "Cache de Silo. Installe avec lui, jamais seul.": (
        "Silo's cache. Installed with it, never on its own."
    ),
    "Serveur media, API compatible Jellyfin. Meilisearch est optionnel et n'est "
    "pas installe.": (
        "Media server with a Jellyfin-compatible API. Meilisearch is optional and "
        "is not installed."
    ),
    "Ecoute les annonces IRC. Plus rapide que le sondage RSS.": (
        "Listens to IRC announces. Faster than RSS polling."
    ),
    "UI web pour qBittorrent. N'est pas un client.": (
        "Web UI for qBittorrent. Not a client."
    ),
    "Profils de qualite TRaSH. Aucune interface web.": (
        "TRaSH quality profiles. No web UI."
    ),
    "UI web pour qBittorrent ou Transmission. N'est pas un client.": (
        "Web UI for qBittorrent or Transmission. Not a client."
    ),
    # -- origine des PUID/PGID ---------------------------------------------------
    "utilisateur courant": "current user",
    "utilisateur courant (les UID DSM varient selon l'utilisateur cree)": (
        "current user (DSM UIDs vary with the user that was created)"
    ),
    "constante Unraid : nobody:users = 99:100": (
        "Unraid constant: nobody:users = 99:100"
    ),
    "sans effet sous Docker Desktop : Windows ne porte pas ces droits": (
        "no effect under Docker Desktop: Windows does not carry these permissions"
    ),
    # -- phrases a champs nommes ------------------------------------------------
    # Assemblees a l'affichage : leur valeur change a chaque appel, seul le
    # gabarit peut servir de cle. Les champs doivent etre reportes tels quels.
    '[b]{services} services[/b] - [b]{liens} liens[/b] seront cables': '[b]{services} services[/b] - [b]{liens} links[/b] will be wired',
    '\n[cyan]Ajoute automatiquement (prerequis) : {noms}[/cyan]': '\n[cyan]Added automatically (prerequisites): {noms}[/cyan]',
    "[dim]PUID/PGID = l'utilisateur Linux, a l'interieur des conteneurs, qui possedera vos fichiers.[/dim]": '[dim]PUID/PGID = the Linux user, inside the containers, that will own your files.[/dim]',
    ' [yellow]- non detectables ici, valeur de repli.[/yellow]\n': ' [yellow]- not detectable here, falling back.[/yellow]\n',
    '\n[dim]Sur un NAS, lancez `id` et corrigez ces valeurs.[/dim]': '\n[dim]On a NAS, run `id` and correct these values.[/dim]',
    '[dim]Dossier vise : {chemin}[/dim]': '[dim]Target folder: {chemin}[/dim]',
    '[red]Impossible de le creer : {erreur}[/red]': '[red]Cannot create it: {erreur}[/red]',
    'liste indisponible : {erreur}': 'list unavailable: {erreur}',
    '[dim]Les noms ne seront pas verifies ici. Les defauts restent valables.[/dim]': '[dim]Names will not be checked here. The defaults still apply.[/dim]',
    '[dim]{nombre} profils proposes par les TRaSH Guides. Cliquez pour derouler la liste.[/dim]': '[dim]{nombre} profiles offered by the TRaSH Guides. Click to open the list.[/dim]',
    '[red]Template inconnu — {noms}[/red]\n[dim]Recyclarr refuserait de generer la configuration.[/dim]': '[red]Unknown template — {noms}[/red]\n[dim]Recyclarr would refuse to generate the configuration.[/dim]',
    '[dim](facultatif)[/dim]': '[dim](optional)[/dim]',
    '[dim]{nombre} choix proposes par Gluetun {version}. Sans selection, le VPN choisit pour vous.[/dim]': '[dim]{nombre} choices offered by Gluetun {version}. With none selected, the VPN picks for you.[/dim]',
    '[yellow]Il manque {champs}.[/yellow]\n[dim]Sans cela Gluetun refuse de demarrer, et le client de telechargement reste injoignable.[/dim]': '[yellow]Missing: {champs}.[/yellow]\n[dim]Without them Gluetun refuses to start, and the download client stays unreachable.[/dim]',
    'tache de fond': 'background task',
    '[b]Configurations[/b]  {chemin}': '[b]Configuration[/b]   {chemin}',
    '[b]Donnees[/b]        {chemin}  -> /data dans tous les conteneurs': '[b]Data[/b]            {chemin}  -> /data in every container',
    '[b]Liens a cabler[/b] {nombre}': '[b]Links to wire[/b]  {nombre}',
    '[b]VPN[/b]            gluetun - {fournisseur} [dim]({protocole}) ; le client de telechargement ne demarrera pas sans le tunnel[/dim]': '[b]VPN[/b]             gluetun - {fournisseur} [dim]({protocole}); the download client will not start without the tunnel[/dim]',
    '[yellow]PUID/PGID non detectables ici : repli sur {uid}:{gid}.[/yellow]\n[dim]Des identifiants faux font ecrire toute la stack avec de mauvaises permissions. Sur un NAS, lancez `id`.[/dim]': '[yellow]PUID/PGID not detectable here: falling back to {uid}:{gid}.[/yellow]\n[dim]Wrong ids make the whole stack write with the wrong permissions. On a NAS, run `id`.[/dim]',
    "[yellow]Une configuration existe deja pour {services}.[/yellow]\n[dim]Leurs mots de passe n'y sont stockes que haches : plugarr ne peut pas les reprendre, et ceux qu'il va vous annoncer seront refuses.[/dim]\n": '[yellow]A configuration already exists for {services}.[/yellow]\n[dim]Their passwords are stored hashed only: plugarr cannot take them over, and the ones it is about to show you will be refused.[/dim]\n',
    '[dim]Vos medias ne sont jamais touches.[/dim]': '[dim]Your media is never touched.[/dim]',
    '[yellow]Prise A CHAUD, conteneurs en marche : ses bases peuvent etre corrompues.[/yellow]': '[yellow]Taken HOT, with containers running: its databases may be corrupt.[/yellow]',
    '[green]Restauration terminee.[/green]\n\n{nombre} services reposes. Demarrez la pile, puis [b]plugarr wire[/b] pour verifier que tout repond.': '[green]Restore complete.[/green]\n\n{nombre} services restored. Start the stack, then run [b]plugarr wire[/b] to check that everything answers.',
    '[dim]Journal detaille : {chemin}[/dim]': '[dim]Detailed log: {chemin}[/dim]',
    '[dim]Detail complet dans {chemin}[/dim]': '[dim]Full detail in {chemin}[/dim]',
    '[green]Termine : {faits}/{total} liens etablis[/green]': '[green]Done: {faits}/{total} links established[/green]',
    '[yellow]Termine : {faits}/{total} liens etablis[/yellow]': '[yellow]Done: {faits}/{total} links established[/yellow]',
    '[red]Liens en echec :[/red]\n': '[red]Failed links:[/red]\n',
    '\n\n[dim]Diagnostic : plugarr doctor[/dim]': '\n\n[dim]Diagnostic: plugarr doctor[/dim]',
    "Prochaine etape : ouvrez chaque service depuis la page d'acces.": 'Next step: open each service from the access page.',
    '\n\n[dim]Ces identifiants sont aussi dans {chemin} (chmod 600).[/dim]': '\n\n[dim]These credentials are also in {chemin} (chmod 600).[/dim]',
    "Rouvrir la page d'acces": 'Reopen the access page',
    '[yellow]Page introuvable : {chemin}[/yellow]': '[yellow]Page not found: {chemin}[/yellow]',
    '[green]Page ouverte dans votre navigateur.[/green]\n': '[green]Page opened in your browser.[/green]\n',
    '[yellow]Aucun navigateur disponible ici.[/yellow]\n[dim]Ouvrez ce fichier depuis un autre appareil : {chemin}[/dim]': '[yellow]No browser available here.[/yellow]\n[dim]Open this file from another device: {chemin}[/dim]',
    '[red]Prowlarr injoignable : {erreur}[/red]': '[red]Prowlarr unreachable: {erreur}[/red]',
    ' - deja configures : {noms}': ' - already configured: {noms}',
    '[dim]{nombre} definitions fournies par votre Prowlarr{deja}[/dim]': '[dim]{nombre} definitions shipped by your Prowlarr{deja}[/dim]',
    '[dim]Validation de {nom} par Prowlarr...[/dim]': '[dim]Prowlarr is validating {nom}...[/dim]',
    # -- rendu console -----------------------------------------------------------
    # Ce que voit quelqu'un qui lance `plugarr install --yes` : preflight,
    # recapitulatif, etapes de cablage et rapport final.
    'Preflight': 'Preflight',
    'Controle': 'Check',
    'Detail': 'Detail',
    'ATTENTION': 'WARNING',
    "Recapitulatif - rien n'a encore ete ecrit": 'Summary - nothing written yet',
    'Chemins': 'Paths',
    'CONFIG_ROOT : {config}\nDATA_ROOT   : {data}  (monte sur /data dans TOUS les conteneurs)\nPUID:PGID   : {uid}:{gid}  ({origine})\nUMASK / TZ  : {umask}   {tz}\nPlateforme  : {plateforme}': 'CONFIG_ROOT : {config}\nDATA_ROOT   : {data}  (mounted on /data in EVERY container)\nPUID:PGID   : {uid}:{gid}  ({origine})\nUMASK / TZ  : {umask}   {tz}\nPlatform    : {plateforme}',
    'Avertissement VPN': 'VPN warning',
    "Aucun VPN n'est configure pour le client torrent.\nLe trafic BitTorrent sortira sur l'adresse IP publique de cette machine, visible par les autres pairs.\nPour ajouter un VPN, relancez avec --vpn.": "No VPN is configured for the torrent client.\nBitTorrent traffic will leave through this machine's public IP address, visible to other peers.\nTo add one, re-run with --vpn.",
    'attention': 'warning',
    'preparation': 'preparing',
    'termine': 'done',
    'Resultat': 'Result',
    '[dim]Ces identifiants sont aussi dans .env (chmod 600, deja dans .gitignore).[/dim]': '[dim]These credentials are also in .env (chmod 600, already in .gitignore).[/dim]',
    '{faits}/{total} liens etablis, {crees} crees a ce passage.': '{faits}/{total} links established, {crees} created on this pass.',
    '\nEchecs :': '\nFailures:',
    '\nDiagnostic : `plugarr doctor`': '\nDiagnostic: `plugarr doctor`',
    # -- conseil de fin d'installation -------------------------------------------
    # La derniere chose que lit quelqu'un qui vient d'installer, et la seule qui
    # lui dise quoi faire ensuite.
    'Prochaine etape : ajoutez vos indexeurs dans Prowlarr.': 'Next step: add your indexers in Prowlarr.',
    'Ils descendront automatiquement vers {noms}.': 'They will flow down to {noms} automatically.',
    'plugarr ne fournit aucun indexeur : ce choix vous appartient.': 'plugarr provides no indexer: that choice is yours.',
    'Prochaine etape : ajoutez vos indexeurs dans {noms}.': 'Next step: add your indexers in {noms}.',
    "Prowlarr les aurait distribues a votre place : il n'est pas installe.": 'Prowlarr would have distributed them for you: it is not installed.',
    'Prochaine etape : deposez vos medias sous {racine}.': 'Next step: drop your media under {racine}.',
    '{noms} les trouvera a la prochaine analyse.': '{noms} will find it on the next scan.',
    # -- page d'acces et console d'administration ---------------------------------
    # L'artefact que l'utilisateur GARDE : il la rouvre pour retrouver un port,
    # un mot de passe, ou pour arreter un service.
    'Administration': 'Administration',
    'Votre stack media': 'Your media stack',
    '{nombre} services installes et cables le {date}.': '{nombre} services installed and wired on {date}.',
    'Services': 'Services',
    'Dossiers': 'Folders',
    'Ajouter un service': 'Add a service',
    "{nombre} lien(s) n'ont pas pu etre etablis.": '{nombre} link(s) could not be established.',
    'Lancez <code>plugarr doctor</code> pour un diagnostic.': 'Run <code>plugarr doctor</code> for a diagnostic.',
    'Aucun VPN.': 'No VPN.',
    "Le trafic BitTorrent sort sur l'adresse IP publique de cette machine.": "BitTorrent traffic leaves through this machine's public IP address.",
    'Cette valeur decide de qui possede vos medias.': 'This value decides who owns your media.',
    "Cette page est un <b>fichier fige</b> : elle ne montre ni l'etat des services, ni les mises a jour disponibles, et ses boutons n'existent pas ici.<br>Pour tout cela, ouvrez <code>{lanceur}</code>, depose a cote de cette page.": 'This page is a <b>frozen file</b>: it shows neither service status nor available updates, and its buttons do not exist here.<br>For all that, open <code>{lanceur}</code>, written next to this page.',
    "Les liens utilisent {adresse}, l'adresse de cette machine sur le reseau local, et non localhost : la page reste donc valable depuis un autre appareil.": "The links use {adresse}, this machine's address on the local network, rather than localhost: the page therefore stays valid from another device.",
    "Les liens pointent vers localhost. Depuis un autre appareil, remplacez-le par l'adresse de cette machine sur le reseau.": "The links point at localhost. From another device, replace it with this machine's address on the network.",
    'tache de fond, sans interface': 'background task, no web UI',
    'Cliquer pour afficher {quoi}': 'Click to reveal {quoi}',
    'Copier': 'Copy',
    'copier': 'copy',
    'copie': 'copied',
    'pas encore installe': 'not installed yet',
    'installer et cabler': 'install and wire',
    '— tirera aussi {noms}': '— will also pull in {noms}',
    "Le service est installe puis <b>cable dans les deux sens</b> : il apprend a parler aux autres, et les autres apprennent a lui parler. Rien n'est arrete, et aucun mot de passe existant n'est touche.": 'The service is installed then <b>wired both ways</b>: it learns to talk to the others, and the others learn to talk to it. Nothing is stopped, and no existing password is touched.',
    'Contenu': 'Content',
    'Sur cette machine': 'On this machine',
    'Vu par les conteneurs': 'As seen by the containers',
    'Films': 'Movies',
    'Series': 'Shows',
    'Musique': 'Music',
    'Telechargements': 'Downloads',
    'Configurations': 'Configuration',
    'ouvrir': 'open',
    "Les liens « ouvrir » ne fonctionnent que si ce navigateur tourne sur la machine d'installation. Depuis un autre appareil, utilisez le chemin copiable, ou passez par un partage reseau.": 'The “open” links only work if this browser runs on the installation machine. From another device, use the copyable path, or go through a network share.',
    'Cette page contient vos mots de passe et vos cles API. Elle est en lecture seule pour vous (<code>chmod 600</code>) et exclue du depot git. Ne la partagez pas.': 'This page holds your passwords and API keys. It is readable by you only (<code>chmod 600</code>) and excluded from the git repository. Do not share it.',
    'Genere par plugarr {version} — donnees dans <code>{racine}</code>.': 'Generated by plugarr {version} — data in <code>{racine}</code>.',
    'diagnostic': 'diagnostic',
    'chercher les mises a jour': 'check for updates',
    'sauvegarder la configuration': 'back up the configuration',
    # -- chemins et permissions ----------------------------------------------------
    # Origine des PUID/PGID et verdict du controle de hardlink, affiches par
    # l'assistant, le preflight et la page d'acces.
    'detecte ({origine})': 'detected ({origine})',
    'valeur par defaut : detection impossible sur cette plateforme': 'default value: detection impossible on this platform',
    'lance en root : conteneurs et medias appartiendront a root': 'running as root: containers and media will belong to root',
    'hardlink OK entre torrents/ et media/': 'hardlink OK between torrents/ and media/',
    "hardlink impossible ({erreur}). Les imports recopieront les fichiers au lieu de les lier. Verifiez que {source} et {cible} sont sur le MEME systeme de fichiers, et que DATA_ROOT est monte d'un seul bloc.": 'hardlink impossible ({erreur}). Imports will copy files instead of linking them. Check that {source} and {cible} are on the SAME filesystem, and that DATA_ROOT is mounted as a single block.',
    # -- format de date --------------------------------------------------------------
    # Ce n'est pas une phrase mais un gabarit `strftime` : « 05/09 » se lit
    # « 9 mai » pour un anglophone, et le mot de liaison change aussi.
    '%d/%m/%Y a %H:%M': '%Y-%m-%d at %H:%M',
    # -- aide de la ligne de commande --------------------------------------------
    # Lue par Typer a l'IMPORT : la langue est donc resolue avant, en regardant
    # `sys.argv` puis le systeme. Voir `_langue_a_l_import` dans cli.py.
    'Deploie ET cable automatiquement une stack media *arr.': 'Deploys AND automatically wires an *arr media stack.',
    "Lance l'assistant interactif plein ecran.": 'Launches the full-screen interactive wizard.',
    'Deploie et cable la stack de bout en bout, sans interaction.': 'Deploys and wires the stack end to end, without interaction.',
    "Liste les services deja installes sur cette machine. N'ecrit rien.": 'Lists the services already installed on this machine. Writes nothing.',
    'Cable une stack DEJA installee, sans la recreer.': 'Wires an ALREADY installed stack, without recreating it.',
    'Regenere docker-compose.yml et .env depuis stack.yml, sans rien demarrer.': 'Regenerates docker-compose.yml and .env from stack.yml, starting nothing.',
    'Rejoue uniquement le cablage sur une stack deja demarree. Idempotent.': 'Replays only the wiring on an already running stack. Idempotent.',
    "Page d'administration : etat des services, demarrer / arreter / redemarrer.": 'Admin page: service status, start / stop / restart.',
    "Pose le mot de passe de la page d'administration.": 'Sets the admin page password.',
    "Lance la console d'administration a chaque ouverture de session.": 'Starts the admin console with every login session.',
    'Archive la configuration complete : projet, CONFIG_ROOT et volumes.': 'Archives the whole configuration: project, CONFIG_ROOT and volumes.',
    "Repose une sauvegarde. N'ecrit RIEN dans DATA_ROOT.": 'Restores a backup. Writes NOTHING into DATA_ROOT.',
    'Diagnostique une installation existante.': 'Diagnoses an existing installation.',
    'Arrete la stack. Ne touche JAMAIS a DATA_ROOT.': 'Stops the stack. NEVER touches DATA_ROOT.',
    "Langues d'interface acceptees.": 'Accepted interface languages.',
    'Liste les fournisseurs VPN acceptes par Gluetun.': 'Lists the VPN providers Gluetun accepts.',
    'Liste le catalogue.': 'Lists the catalogue.',
    'Liste les profils de qualite TRaSH proposables a Recyclarr.': 'Lists the TRaSH quality profiles that can be given to Recyclarr.',
    'Affiche la version et quitte.': 'Shows the version and exits.',
    'Langue de PlugArr : fr, en. Par defaut, celle du systeme.': 'PlugArr language: fr, en. Defaults to the system one.',
    'Ne pas demander confirmation.': 'Do not ask for confirmation.',
    'Montrer le plan, ne rien faire.': 'Show the plan, do nothing.',
    "N'ecrit rien, montre tout.": 'Writes nothing, shows everything.',
    'Liste separee par des virgules. Connus: ': 'Comma-separated list. Known: ',
    'Ou ecrire les artefacts.': 'Where to write the artefacts.',
    'Ou ecrire stack.yml.': 'Where to write stack.yml.',
    'Ou reposer le projet.': 'Where to restore the project.',
    'Repertoire du stack.yml.': 'Directory holding stack.yml.',
    'Racine des configurations.': 'Configuration root.',
    'Racine des configurations existantes.': 'Root of the existing configurations.',
    'Racine des configurations, pour lire le manifeste deja clone.': 'Configuration root, to read the already cloned manifest.',
    'Racine des donnees (monte sur /data).': 'Data root (mounted on /data).',
    'Racine des medias de la stack existante.': 'Media root of the existing stack.',
    'Profil de plateforme.': 'Platform profile.',
    'Identifiant commun a tous les services installes.': 'Username shared by every installed service.',
    'Hote pour les URL du rapport final.': "Host to use in the final report's URLs.",
    'Adresse de cette machine, joignable DEPUIS les conteneurs.': "This machine's address, reachable FROM the containers.",
    'Langue des interfaces (code ISO : fr, en, es...). Voir `plugarr langues`.': 'Language of the service interfaces (ISO code: fr, en, es...). See `plugarr langues`.',
    'Faire passer le client torrent par un VPN.': 'Route the torrent client through a VPN.',
    'Fournisseur VPN. Voir `plugarr vpn-providers`.': 'VPN provider. See `plugarr vpn-providers`.',
    'wireguard ou openvpn.': 'wireguard or openvpn.',
    'Cle privee WireGuard.': 'WireGuard private key.',
    'Identifiant OpenVPN.': 'OpenVPN username.',
    'Mot de passe OpenVPN.': 'OpenVPN password.',
    'Pays souhaites, separes par des virgules.': 'Wanted countries, comma-separated.',
    'Template TRaSH pour Sonarr. Voir `plugarr templates`. Vide = defaut.': 'TRaSH template for Sonarr. See `plugarr templates`. Empty = default.',
    'Template TRaSH pour Radarr. Voir `plugarr templates`. Vide = defaut.': 'TRaSH template for Radarr. See `plugarr templates`. Empty = default.',
    'Lever une ambiguite : service=conteneur. Repetable.': 'Resolve an ambiguity: service=container. Repeatable.',
    'Identifiant du client de telechargement existant.': 'Username of the existing download client.',
    'Mot de passe du client existant. Illisible depuis sa configuration.': 'Password of the existing client. Unreadable from its configuration.',
    "Adresse d'ecoute.": 'Listen address.',
    "Adresse d'ecoute de la console.": 'Console listen address.',
    "Port d'ecoute.": 'Listen port.',
    "Port d'ecoute de la console.": 'Console listen port.',
    'Ouvrir le navigateur.': 'Open the browser.',
    "Ouvrir la page d'acces a la fin.": 'Open the access page at the end.',
    "Ouvrir la page d'acces dans le navigateur.": 'Open the access page in the browser.',
    'Retirer le mot de passe.': 'Remove the password.',
    'Retirer le lancement automatique.': 'Remove the automatic startup.',
    "Fichier d'archive a ecrire.": 'Archive file to write.',
    'Archive produite par `plugarr backup`.': 'Archive produced by `plugarr backup`.',
    'Ne PAS arreter les conteneurs. Plus rapide, et la sauvegarde peut etre corrompue.': 'Do NOT stop the containers. Faster, and the backup may be corrupt.',
    "Restaurer AILLEURS que l'origine. Les chemins sont reecrits.": 'Restore SOMEWHERE ELSE than the original. Paths are rewritten.',
    'Inclure les arretes.': 'Include stopped ones.',
    'Supprime CONFIG_ROOT.': 'Deletes CONFIG_ROOT.',
    # -- messages de la ligne de commande ------------------------------------------
    # Poses par la console traduisante de `report.py`, qui joue pour la ligne de
    # commande le role de `tui/widgets.py` pour l'assistant.
    '[dim]Ouverte dans votre navigateur.[/dim]': '[dim]Opened in your browser.[/dim]',
    '[dim]Aucun navigateur disponible ici : ouvrez ce fichier a la main.[/dim]': '[dim]No browser available here: open this file by hand.[/dim]',
    "\n[dim]Vos medias ne sont jamais touches : seul l'etat ci-dessus le serait.[/dim]": '\n[dim]Your media is never touched: only the state above would be.[/dim]',
    '[dim]Configurations conservees.[/dim]': '[dim]Configurations kept.[/dim]',
    '[dim]Conservee (--yes ne supprime rien). Utilisez --reset-config pour repartir de zero.[/dim]': '[dim]Kept (--yes deletes nothing). Use --reset-config to start over.[/dim]',
    "[yellow]Un template a ete choisi mais Recyclarr n'est pas dans la selection : il ne sera pas applique.[/yellow]": '[yellow]A template was chosen but Recyclarr is not in the selection: it will not be applied.[/yellow]',
    '[yellow]--vpn sans client de telechargement : Gluetun ne protegerait rien.[/yellow]': '[yellow]--vpn with no download client: Gluetun would protect nothing.[/yellow]',
    '[cyan]--dry-run : aucune ecriture. Compose qui serait genere :[/cyan]': '[cyan]--dry-run: nothing written. The Compose that would be generated:[/cyan]',
    '[red]Des controles bloquants ont echoue.[/red]': '[red]Blocking checks failed.[/red]',
    '[dim]Diagnostic : `plugarr doctor`[/dim]': '[dim]Diagnostic: `plugarr doctor`[/dim]',
    'Aucun service connu detecte sur cette machine.': 'No known service detected on this machine.',
    "[red]Rien d'adoptable. Lancez `plugarr scan` pour comprendre.[/red]": '[red]Nothing to adopt. Run `plugarr scan` to find out why.[/red]',
    "[red]Impossible de determiner l'adresse de cette machine sur le reseau.[/red]\n[dim]Les conteneurs doivent pouvoir se joindre entre eux : `localhost` ne convient pas. Passez --host <adresse>.[/dim]": "[red]Cannot determine this machine's address on the network.[/red]\n[dim]The containers must be able to reach each other: `localhost` will not do. Pass --host <address>.[/dim]",
    '[dim]Le jeton change a chaque demarrage. Ctrl+C pour arreter.[/dim]': '[dim]The token changes on every start. Ctrl+C to stop.[/dim]',
    "[dim]Aucun navigateur : ouvrez l'URL ci-dessus.[/dim]": '[dim]No browser: open the URL above.[/dim]',
    'Serveur arrete.': 'Server stopped.',
    '[red]Huit caracteres au minimum.[/red]': '[red]Eight characters minimum.[/red]',
    'Mot de passe enregistre. La console demandera desormais ce mot de passe, et acceptera toujours le jeton affiche par `plugarr serve`.': 'Password saved. The console will now ask for it, and will still accept the token printed by `plugarr serve`.',
    'Mot de passe retire. Seul le jeton de session ouvre desormais la console.': 'Password removed. Only the session token opens the console now.',
    "[yellow]Aucun mot de passe n'est pose sur la console.[/yellow]": '[yellow]No password is set on the console.[/yellow]',
    "[dim]Lancee automatiquement, elle n'afficherait son jeton dans aucun terminal : personne ne pourrait y entrer. Posez-en un d'abord :[/dim]": '[dim]Started automatically, it would print its token in no terminal: nobody could get in. Set one first:[/dim]',
    '  plugarr admin-password': '  plugarr admin-password',
    "[dim]Une unite utilisateur s'arrete a la deconnexion. Pour qu'elle survive :[/dim]": '[dim]A user unit stops at logout. To make it survive:[/dim]',
    '  loginctl enable-linger $USER': '  loginctl enable-linger $USER',
    "[yellow]Sauvegarde a chaud.[/yellow] Une base SQLite copiee pendant qu'on ecrit dedans donne un fichier valide en apparence et inutilisable en pratique. Sans --live, PlugArr arrete les conteneurs le temps de la copie.": '[yellow]Hot backup.[/yellow] A SQLite database copied while it is being written to gives a file that looks valid and is unusable in practice. Without --live, PlugArr stops the containers for the duration of the copy.',
    '[yellow]Cette archive contient vos mots de passe et vos cles API en clair.[/yellow]\n[dim]Elle est en lecture seule pour vous (chmod 600). Rangez-la comme un secret.[/dim]': '[yellow]This archive holds your passwords and API keys in cleartext.[/yellow]\n[dim]It is readable by you only (chmod 600). Store it like a secret.[/dim]',
    '[yellow]Cette archive a ete prise A CHAUD, conteneurs en marche.[/yellow] Ses bases peuvent etre corrompues.': '[yellow]This archive was taken HOT, with containers running.[/yellow] Its databases may be corrupt.',
    '[green]Restauration terminee.[/green]': '[green]Restore complete.[/green]',
    '\nEtat des conteneurs :': '\nContainer status:',
    'Joignabilite des API :': 'API reachability:',
    '\nProtection VPN du trafic torrent :': '\nVPN protection of torrent traffic:',
    "[bold]Proposees dans l'assistant[/bold]": '[bold]Offered in the wizard[/bold]',
    '[dim]Jellyfin et Silo acceptent tout code ISO ; la liste ci-dessus est celle que les *arr savent afficher.[/dim]': '[dim]Jellyfin and Silo accept any ISO code; the list above is the one the *arr can display.[/dim]',
    '[dim]Liste obtenue de Gluetun v3.41.3 lui-meme, pas recopiee.[/dim]\n': '[dim]List obtained from Gluetun v3.41.3 itself, not copied.[/dim]\n',
    "[dim]Choix a l'installation : `plugarr install --recyclarr-sonarr <nom> --recyclarr-radarr <nom>`.[/dim]": '[dim]Chosen at install time: `plugarr install --recyclarr-sonarr <name> --recyclarr-radarr <name>`.[/dim]',
    "Aucun indexeur configure.\n[dim]plugarr n'en fournit aucun : ajoutez les votres avec `plugarr indexers add`.[/dim]": 'No indexer configured.\n[dim]plugarr provides none: add your own with `plugarr indexers add`.[/dim]',
    # -- messages a champs nommes de la ligne de commande --------------------------
    "\n[yellow]Etat existant detecte[/yellow] pour [bold]{services}[/bold].\n[dim]Leurs mots de passe ne se relisent pas : plugarr ne peut pas les reprendre, et ceux qu'il va annoncer seront refuses.[/dim]": '\n[yellow]Existing state detected[/yellow] for [bold]{services}[/bold].\n[dim]Their passwords cannot be read back: plugarr cannot take them over, and the ones it is about to announce will be refused.[/dim]',
    'Supprimer cet etat et repartir de zero ?': 'Delete this state and start over?',
    '[red]Template inconnu pour {service} : {nom}[/red]\n[dim]`plugarr templates` liste les noms acceptes.[/dim]': '[red]Unknown template for {service}: {nom}[/red]\n[dim]`plugarr templates` lists the accepted names.[/dim]',
    '[yellow]Noms de templates non verifies : {cause}[/yellow]': '[yellow]Template names not verified: {cause}[/yellow]',
    "[red]VPN active mais incomplet : il manque {champs}.[/red]\n[dim]Sans cela Gluetun refuse de demarrer, et le client torrent reste injoignable puisqu'il partage sa pile reseau.[/dim]": '[red]VPN enabled but incomplete: missing {champs}.[/red]\n[dim]Without them Gluetun refuses to start, and the torrent client stays unreachable since it shares its network stack.[/dim]',
    "[yellow]PUID/PGID {uid}:{gid} - {origine}.[/yellow]\n[dim]C'est l'utilisateur Linux, a l'interieur des conteneurs, qui possedera vos fichiers. Sur un NAS, lancez `id` en tant que l'utilisateur voulu.[/dim]": '[yellow]PUID/PGID {uid}:{gid} - {origine}.[/yellow]\n[dim]That is the Linux user, inside the containers, that will own your files. On a NAS, run `id` as the user you want.[/dim]',
    'Ecrire les fichiers et demarrer la stack ?': 'Write the files and start the stack?',
    '\n[dim]Journal detaille : {chemin}[/dim]': '\n[dim]Detailed log: {chemin}[/dim]',
    '[yellow]{service} est present {nombre} fois ({noms}).[/yellow]\n[dim]Precisez lequel cabler : --pick {identifiant}=<conteneur>[/dim]': '[yellow]{service} is present {nombre} times ({noms}).[/yellow]\n[dim]Say which one to wire: --pick {identifiant}=<container>[/dim]',
    '[dim]Adresse retenue pour le cablage : {hote}[/dim]': '[dim]Address used for the wiring: {hote}[/dim]',
    '[red]{identifiant} est ambigu : {noms}.[/red] [dim]Ajoutez --pick {identifiant}=<conteneur>[/dim]': '[red]{identifiant} is ambiguous: {noms}.[/red] [dim]Add --pick {identifiant}=<container>[/dim]',
    '[cyan]{nombre} lien(s) seraient poses sur ces conteneurs existants. Aucun ne sera recree.[/cyan]': '[cyan]{nombre} link(s) would be set up on these existing containers. None will be recreated.[/cyan]',
    'Cabler ces services ?': 'Wire these services?',
    "[yellow]Ecoute sur {hote} : la page sera joignable depuis le reseau.[/yellow]\n[dim]Elle permet d'arreter vos services et affiche vos identifiants. Le jeton est la seule protection ; ne partagez pas l'URL.[/dim]": '[yellow]Listening on {hote}: the page will be reachable from the network.[/yellow]\n[dim]It can stop your services and shows your credentials. The token is the only protection; do not share the URL.[/dim]',
    "[red]Impossible d'ecouter sur {hote}:{port} : {erreur}[/red]": '[red]Cannot listen on {hote}:{port}: {erreur}[/red]',
    'Nouveau mot de passe': 'New password',
    '[dim]Deja installe : {chemin}. Reecriture.[/dim]': '[dim]Already installed: {chemin}. Rewriting.[/dim]',
    '[dim]Console : http://{hote}:{port} — au prochain demarrage de session.[/dim]': '[dim]Console: http://{hote}:{port} — at your next login session.[/dim]',
    "[dim]Vos medias dans {racine} ne sont PAS dedans, et c'est voulu.[/dim]": '[dim]Your media in {racine} is NOT in it, and that is deliberate.[/dim]',
    'Ecraser la configuration dans {config} et le projet dans {projet} ?': 'Overwrite the configuration in {config} and the project in {projet}?',
    '[dim]Demarrez la pile, puis `plugarr wire --project-dir {repertoire}` pour verifier que tout repond.[/dim]': '[dim]Start the stack, then run `plugarr wire --project-dir {repertoire}` to check that everything answers.[/dim]',
    'Supprimer definitivement {chemin} (bases, historiques, reglages) ?': 'Permanently delete {chemin} (databases, history, settings)?',
    'Confirmez une seconde fois : cette action est irreversible.': 'Confirm a second time: this action cannot be undone.',
    "[dim]Vos medias dans {racine} n'ont pas ete touches.[/dim]": '[dim]Your media in {racine} was not touched.[/dim]',
    '[dim]Aussi acceptees par --langue : {codes}[/dim]': '[dim]Also accepted by --langue: {codes}[/dim]',
    # -- preflight ---------------------------------------------------------------
    # Le premier tableau qu'on voit, en ligne de commande comme dans l'assistant.
    'binaire `docker` introuvable dans le PATH. Installez Docker Engine ou Docker Desktop, puis relancez.': '`docker` binary not found on PATH. Install Docker Engine or Docker Desktop, then run again.',
    'trouve : {chemin}': 'found: {chemin}',
    'daemon docker': 'docker daemon',
    'le binaire repond mais le daemon est injoignable ou trop lent. Demarrez Docker (Desktop, ou `systemctl start docker`). Detail : {detail}': 'the binary answers but the daemon is unreachable or too slow. Start Docker (Desktop, or `systemctl start docker`). Detail: {detail}',
    'version serveur {version}': 'server version {version}',
    'plugin `docker compose` absent. Installez docker-compose-plugin.': '`docker compose` plugin missing. Install docker-compose-plugin.',
    'libre': 'free',
    'deja utilise. Changez le port de {service} dans stack.yml.': "already in use. Change {service}'s port in stack.yml.",
    'occupe par votre propre pile plugarr': 'used by your own plugarr stack',
    'espace disque': 'disk space',
    'impossible de lire {chemin} : {erreur}': 'cannot read {chemin}: {erreur}',
    '{libres:.1f} Go libres': '{libres:.1f} GB free',
    ' - moins que le minimum conseille de {minimum} Go': ' - below the recommended minimum of {minimum} GB',
    'configuration existante': 'existing configuration',
    'aucune, installation neuve': 'none, fresh installation',
    'reprise : {services}': 'taking over: {services}',
    'dans {chemin}': 'in {chemin}',
    'dans le volume Docker {volumes}': 'in the Docker volume {volumes}',
    'dans {chemin}, et dans les volumes Docker {volumes}': 'in {chemin}, and in the Docker volumes {volumes}',
    "{services} ont deja un etat {ou}. Leurs mots de passe ne se relisent pas, et ceux que plugarr vient de generer seront refuses. Reprenez l'installation d'origine avec --project-dir, ou remettez ces services a zero.": '{services} already have state {ou}. Their passwords cannot be read back, and the ones plugarr has just generated will be refused. Resume the original installation with --project-dir, or reset those services.',
    'nom de projet': 'project name',
    'des conteneurs nommes {nom} tournent deja depuis {ailleurs}. Installer ici les REMPLACERA : Docker identifie une pile par son nom, pas par son repertoire. Les fichiers de {ailleurs} ne seront pas touches, mais ses services repartiront sur la configuration de {ici}.': 'containers named {nom} are already running from {ailleurs}. Installing here will REPLACE them: Docker identifies a stack by its name, not by its directory. The files in {ailleurs} will not be touched, but its services will restart on the configuration in {ici}.',
    # -- resultat de chaque etape de cablage ---------------------------------------
    # Ces fragments composent chaque ligne du rapport final : ce sont les plus
    # lus de tout le catalogue.
    'cree': 'created',
    'deja present': 'already present',
    'deja configure ({dossiers}), respecte': 'already configured ({dossiers}), respected',
    'aucun dossier racine configure': 'no root folder configured',
    'identifiants inconnus': 'credentials unknown',
    'identifiants mis a jour ({champs})': 'credentials updated ({champs})',
    'realigne ({champs})': 'realigned ({champs})',
    'client existant, categories laissees telles quelles': 'existing client, categories left as they are',
    'client existant, reglages laisses tels quels': 'existing client, settings left as they are',
    'creees : {noms}': 'created: {noms}',
    'aucune (deja presentes)': 'none (already present)',
    'posees : {noms}': 'set: {noms}',
    'aucune (deja completes)': 'none (already complete)',
    'assistant execute': 'wizard run',
    'assistant deja termine': 'wizard already completed',
    'accueil execute': 'setup run',
    'accueil deja termine': 'setup already completed',
    'utilisateur existant': 'existing user',
    'compte cree': 'account created',
    'compte cree, connexion toujours refusee meme apres redemarrage': 'account created, login still refused even after a restart',
    'aucun template choisi, rien a generer': 'no template chosen, nothing to generate',
    # -- boutons de chaque service sur la console ----------------------------------
    'etat inconnu': 'status unknown',
    'verification…': 'checking…',
    'demarrer': 'start',
    'redemarrer': 'restart',
    'arreter': 'stop',
    'renouveler': 'rotate',
    'Tirer un nouveau mot de passe et recabler': 'Draw a new password and re-wire',
    'Tirer une nouvelle cle API et recabler': 'Draw a new API key and re-wire',
}
