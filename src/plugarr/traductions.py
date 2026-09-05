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
}
