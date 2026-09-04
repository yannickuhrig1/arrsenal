# Feuille de route

Où en est PlugArr, ce qui vient ensuite, et pourquoi. Tenue à jour à chaque
séance de travail.

**Dernière mise à jour : 4 septembre 2026** — version publiée : **0.2.1**

---

## Ce qui marche aujourd'hui

Douze services installés et **câblés** en une passe, vérifiés contre des
instances réelles à chaque livraison.

| | |
|---|---|
| **Téléchargement** | Transmission, qBittorrent |
| **Bibliothèque** | Sonarr, Radarr, Lidarr |
| **Indexeurs** | Prowlarr |
| **Média** | Jellyfin, Silo *(expérimental)* |
| **Automatisation** | autobrr, Recyclarr |
| **Interfaces** | Flood, qui |
| **Réseau** | Gluetun *(VPN optionnel)* |

L'assistant couvre **toutes** les options de la ligne de commande : un test
compare la signature d'`install` à ce que l'assistant sait poser, et échoue si
un écart apparaît.

La langue des interfaces se demande une fois et s'applique à toutes les
applications qui en acceptent une.

**Huit bibliothèques** sont créées et rangées : films, séries, **anime**,
musique, spectacles, livres, livres audio et logiciels. Chacune a son dossier de
téléchargement, son dossier de rangement et sa catégorie qBittorrent qui envoie
l'un vers l'autre. Sonarr reçoit un dossier racine séparé pour l'anime, comme le
recommandent les TRaSH Guides. Les quatre dernières n'ont pas encore
d'application qui les pilote : elles rangent les téléchargements manuels, et
attendent Audiobookshelf, Shelfarr et les autres.

**La configuration complète se sauvegarde et se restaure.** `plugarr backup`
archive le répertoire du projet, `CONFIG_ROOT` et **les volumes Docker** — la
base de Silo n'est pas sous `CONFIG_ROOT` et une sauvegarde qui n'archive que
des dossiers la manquerait en silence. Les conteneurs sont arrêtés pendant la
copie : une base SQLite copiée à chaud donne un fichier valide en apparence et
inutilisable en pratique. `DATA_ROOT` n'est jamais touché. `plugarr restore`
repose le tout, y compris ailleurs, en réécrivant les chemins.

Le **lecteur RSS de qBittorrent** est activé, téléchargement automatique
compris. PlugArr n'ajoute ni flux ni règle : ils dépendent de vos traqueurs,
exactement comme les indexeurs.

La page d'administration (`plugarr serve`) donne l'état des services, les
démarre, les arrête, les redémarre, signale les mises à jour et les applique,
affiche les identifiants, **renouvelle un mot de passe ou une clé API en
recâblant tout ce qui en dépend**, et **installe un service absent de
l'installation initiale**.

---

## Empreintes relevées pour les cinq services à venir

Vérifiées contre les registres le 4 septembre 2026, prêtes à être épinglées. Ce
n'est pas le travail, c'en est la condition préalable : un service n'entre au
catalogue que **câblé et vérifié** contre une instance réelle.

| | image épinglée |
|---|---|
| Seerr | `ghcr.io/seerr-team/seerr:v3.4.1@sha256:f4768de5…` |
| Audiobookshelf | `ghcr.io/advplyr/audiobookshelf:2.36.0@sha256:180acad3…` |
| Shelfarr | `ghcr.io/pedro-revez-silva/shelfarr:2026.08.31.1@sha256:08e06f5b…` |
| Shelfmark | `ghcr.io/calibrain/shelfmark:v1.3.15@sha256:96022903…` |
| DroppedNeedle | `ghcr.io/droppedneedle/droppedneedle:v2.9.0@sha256:4687b391…` |

---

## Prochaine étape

**Mise à jour du pack.** Aujourd'hui PlugArr sait dire qu'une image a une
version plus récente et l'appliquer. Il ne sait pas mettre à jour **sa propre
installation** quand c'est PlugArr qui change.

Le trou est concret et vérifiable : `stack.yml` porte un champ `version: 1`, et
**rien ne le lit** — aucune occurrence dans le code. Cette semaine seule, quatre
champs y sont apparus (`admin_password_hash`, `language`, `secret_key`,
`extra_ports`). Les valeurs par défaut de pydantic absorbent l'écart en silence,
ce qui marche tant qu'un champ ne fait qu'apparaître. Le jour où l'un change de
sens, une installation faite en 0.1.7 se relira sans erreur et sera fausse.

| | |
|---|---|
| Migrations de `stack.yml`, indexées sur son numéro de version | à faire |
| Appliquer les digests épinglés d'un nouveau catalogue à une installation ancienne | à faire |
| Rejouer les étapes de câblage qui ont changé depuis la version installée | à faire |

**Pas de fichier de secrets chiffré**, et la raison est mécanique plutôt que
philosophique : c'est **Docker Compose** qui lit le `.env`, pas plugarr.
`POSTGRES_PASSWORD`, `SILO_SECRET_KEY` et les identifiants VPN doivent être en
clair sur le disque au moment du `up`, sinon la stack ne démarre pas. Chiffrer
`stack.yml` pendant que `.env` est en clair à côté serait décoratif. Un vrai
chiffrement suppose une phrase de passe tapée à chaque démarrage, ce qui
supprime le démarrage automatique livré en 0.1.9. Ce qui protège aujourd'hui :
`chmod 600`, `.gitignore` généré, et masquage des secrets dans le journal.

---

## Livré récemment

| | État | Note |
|---|---|---|
| **Rotation des mots de passe** | ✅ livré en 0.1.7 | qBittorrent, Transmission et les *arr. Vérifié sur une stack de onze services : 25 liaisons sur 25 réalignées. |
| **Rotation des clés API** | ✅ livré en 0.1.8 | Sur les *arr. Piège vérifié contre Sonarr 4.0.19 : `PUT config/host` répond **202 Accepted** et ne change rien — la clé relue vaut toujours l'ancienne une minute plus tard. Seule la réécriture de `config.xml` suivie d'un redémarrage fonctionne. |
| **Ajouter un service après coup** | ✅ livré en 0.1.8 | Section « Ajouter un service » sur la page d'administration. Vérifié en vrai : stack Sonarr seul, puis ajout de Prowlarr — 4 liaisons câblées, clé et mot de passe de Sonarr intacts. |
| **Silo** | ✅ livré en 0.1.11 | Serveur média compatible API Jellyfin, **marqué expérimental**. Trois conteneurs — `pgvector/pgvector:pg18`, `redis:alpine` et `silo-server`, épinglés au digest ; Meilisearch est optionnel et n'est pas installé. Compte, **profil** et trois bibliothèques posés et relus. Deux pièges mesurés, pas supposés : sa base doit vivre dans un **volume Docker** (montage vers l'hôte : migrations en **2935 s** contre **5 s**), et son mot de passe de base doit être alphanumérique — un `?` dans une `postgres://` et le conteneur redémarre en boucle. |
| **Langue des interfaces** | ✅ livré en 0.1.11 | Demandée une fois dans l'assistant, appliquée partout. Chaque application exprime la même idée autrement : Sonarr et Radarr veulent un entier, **Prowlarr veut le code** (`fr`), Jellyfin une culture et un pays, Silo un code **par bibliothèque**. La table des 29 langues des *arr n'est publiée nulle part : relevée valeur par valeur contre un Sonarr 4.0.19. Au passage, une incohérence corrigée — PlugArr imposait le français à Jellyfin, en dur, et laissait tout le reste en anglais. |
| **Liste des pays du VPN** | ✅ livré en 0.1.8 | Liste cliquable, extraite de l'image **épinglée**. Piège trouvé au passage : cinq fournisseurs n'exposent aucun pays — quatre classent par région, un par ville. `SERVER_COUNTRIES` ne filtrait rien chez eux. |

---

## Services à venir

Un service n'entre au catalogue que lorsqu'il est **câblé et vérifié** contre
une instance réelle. L'ordre ci-dessous est celui de l'étude.

| | Ce qu'il reste à faire |
|---|---|
| **Plex** | Second serveur média. Son jeton s'obtient par `plex.tv`, pas par l'API locale : c'est le point à vérifier avant de l'inscrire. |
| **Seerr** | Demandes de médias. Jellyseerr et Overseerr ont fusionné sous ce nom, confirmé par le projet lui-même. Image `ghcr.io/seerr-team/seerr`, **v3.4.1**, 11 versions publiées — épinglable. Le câblage vise Sonarr, Radarr et le serveur média. |
| **Notifiarr** | Notifications centralisées. Chaque *arr s'y déclare par une clé API. |
| **Bazarr** | Sous-titres. Sa configuration passe par un fichier YAML et non par une API — rien n'est encore vérifié. |
| **SABnzbd** | Client Usenet, à côté des deux clients torrent. |
| **DroppedNeedle** | `ghcr.io/droppedneedle/droppedneedle`, **v2.9.0**. Musique, anciennement *MusicSeerr*. **Remplace Lidarr** plutôt que de le compléter. Un conteneur, `PUID`/`PGID` et un montage `/data` à parent commun : nos conventions exactes. Deux obstacles : il télécharge par slskd ou SABnzbd, aucun des deux au catalogue, et son premier compte administrateur se crée par l'interface web. |
| **Wizarr** | Invitations et gestion des comptes pour Jellyfin, Plex et Emby. Le plus autonome de la liste : un conteneur, et le câblage se réduit au serveur média et à sa clé. |
| **Tautulli** | Suivi et statistiques **Plex**. Ne peut pas précéder Plex. |
| **Jellystat** | Statistiques Jellyfin. Exige une base **PostgreSQL** dans un second conteneur, là où tout le catalogue tient en un seul. |
| **Tracearr** | Suivi des lectures et détection de partage de comptes. L'image `latest` réclame une base et un Redis externes ; le tag `supervised` réunit le tout en un conteneur. |
| **Audiobookshelf** | `ghcr.io/advplyr/audiobookshelf:2.36.0`, épinglé au digest. Les répertoires `books` et `audiobooks` l'attendent déjà. **Obstacle relevé contre une instance réelle, non résolu :** sur une installation neuve, `/status` répond `isInit: true` alors que la table `users` de sa base est **vide**, et `POST /init` — la voie documentée pour créer le premier compte — répond **405**. L'interface web n'est pas servie non plus (`/` en 404), avec ou sans le volume `/metadata`. L'API vit pourtant (`/api/libraries` répond 401). Tant que la création du premier compte n'est pas comprise, le câblage est impossible. À noter : l'image taguée `2.36.0` rapporte `serverVersion: 2.35.0`. |
| **Shelfarr** | `ghcr.io/pedro-revez-silva/shelfarr`, **2026.08.31.1**. Demandes de livres pour l'écosystème *arr — un Seerr des livres. Cherche dans Prowlarr, télécharge par qBittorrent, livre à Audiobookshelf. Comble le trou laissé par Readarr, archivé depuis le 27 juin 2025. |
| **Shelfmark** | `ghcr.io/calibrain/shelfmark`, **v1.3.15**, 60 versions. Interface de recherche et de demande de livres, sources et clients apportés par vous. |

**Readarr n'est pas au programme** : le projet est archivé depuis le 27 juin 2025.

---

## La console PlugArr

Le seul chantier qui ne soit pas un service de plus. Aujourd'hui l'assistant
installe puis s'efface ; `plugarr serve` comble une partie du manque, mais
reste une commande à lancer.

| | État |
|---|---|
| État des services | ✅ |
| Démarrer, arrêter, redémarrer | ✅ |
| Voir et appliquer les mises à jour | ✅ |
| Lancer le diagnostic | ✅ 0.1.11 |
| Forcer la recherche de mises à jour | ✅ 0.1.11 |
| Renouveler un mot de passe, avec recâblage | ✅ |
| Renouveler une clé API, avec recâblage | ✅ |
| Ajouter un service absent de l'installation | ✅ |
| Démarrage automatique, sans lancer de commande | ✅ 0.1.9 |

**Pourquoi pas un conteneur.** La question a été tranchée en la mesurant. La
console doit créer, démarrer et recréer des conteneurs — soit
`POST /containers/create` puis `/start` dans l'API Docker. Or un conteneur qu'on
crée peut monter la racine de l'hôte et tourner en root : un proxy de socket qui
autorise ces deux appels n'enferme rien, et sans eux la console ne sert plus à
rien. L'y enfermer reviendrait donc à exposer sur le réseau un service aux
pleins pouvoirs, sans rien gagner.

Elle tourne donc sur l'hôte, sous le compte de l'utilisateur, sur `127.0.0.1`,
et démarre toute seule avec `plugarr autostart`. Le confort recherché est le
même. Et parce qu'une console qui change des mots de passe doit s'authentifier
sérieusement, `plugarr admin-password` pose un mot de passe : empreinte seule
dans `stack.yml`, sessions expirables, tentatives limitées.

---

## Ce qu'on ne fera pas

**Choisir plusieurs profils Recyclarr par service.** Recyclarr groupe ses
instances par `base_url` et **écarte tout groupe qui en compte plus d'une** —
c'est `SplitInstancesFilter`, lu dans son code source. Deux profils visant le
même Sonarr, et ce ne sont pas deux profils posés : c'est **zéro**. Les
templates racine sont autonomes et ne se composent pas ; la seule voie serait de
fusionner leur YAML nous-mêmes, exactement ce que le projet refuse — tout
l'intérêt est que le contenu vienne des TRaSH Guides et pas de nous.

PlugArr détecte désormais cette situation et n'en garde qu'un, en renommant les
autres plutôt qu'en les effaçant.

---

## Journal des corrections notables

| Version | |
|---|---|
| **0.2.1** | **Sauvegarde et restauration complètes.** Vérifié sur une pile réelle et non simulé : un témoin posé dans Sonarr, sauvegarde, **destruction totale** — conteneurs, volumes, dossiers — puis restauration ailleurs. Le témoin est revenu, Silo est reparti *healthy* du premier coup, et le recâblage a compté **12 liaisons sur 12, zéro créée** : tout existait déjà. Un bouton sur la console ; la restauration reste en ligne de commande, car elle écrase une configuration en place. |
| **0.2.0** | **arrsenal devient PlugArr.** Le nom disait « un tas d'outils », ce que propose n'importe quel dépôt de compose *arr ; ce qui distingue ce projet est qu'il les **branche ensemble**. 125 fichiers. Le point dur n'était aucun des noms visibles : `discovery.py` reconnaît les piles installées par un **label**, jamais par leur nom, et renommer ce label aurait rendu invisible chaque installation existante — donc candidate à être recréée par-dessus. Les deux marqueurs sont lus, `plugarr.managed` et `arrsenal.managed` ; seul le premier est écrit. Le renommage mécanique avait aussi cassé vingt-cinq élisions françaises : « qu'arrsenal sait faire » devenait « qu'PlugArr sait faire ». |
| **0.2.0** | **L'exécutable n'avait aucune icône** — Windows lui collait celle, générique, de tout binaire console. Sept tailles de 16 à 256 px, engendrées par `scripts/icone.py` plutôt que commitées en binaire opaque : fond transparent, car une tuile sombre gravée devient une tache noire sur une barre des tâches claire ; canal alpha tiré de la **chroma** et non de la luminosité, qui mangeait le bas du jambage violet. L'assistant porte les couleurs de la marque. |
| **0.1.12** | **Une bibliothèque ajoutée au catalogue n'atteignait pas les installations existantes.** `install` crée l'arborescence, `wire` non — et Sonarr refuse net un dossier racine absent : « Path '/data/media/anime' does not exist ». Trouvé en réparant une pile réelle juste après l'ajout de l'anime. `wire` garantit désormais les dossiers avant de câbler ; l'opération est idempotente et silencieuse sur une installation à jour. |
| **0.1.12** | **`plugarr wire` n'attendait pas que les services soient prêts, et répondait par une trace Python.** Un Sonarr neuf passe une minute ou plus dans ses migrations : son port est publié mais rien n'écoute derrière, et le câblage tombait sur « Server disconnected without sending a response » — un message qui envoie chercher une panne réseau là où il n'y a qu'une attente. Quand l'attente expirait, la commande finissait sur « Failed to execute script 'launcher' ». `install` traitait déjà les deux cas ; `wire`, qui est la commande qu'on lance justement pour réparer un câblage incomplet, non. |
| **0.1.12** | **Flood ne pouvait pas joindre son client de téléchargement sous VPN.** Même cause que Prowlarr : Flood n'est pas dans le tunnel, le client y est et perd son alias DNS. Son mot de passe quitte au passage `docker-compose.yml`, où il était en clair — dernier secret à y rester après la clé WireGuard. |
| **0.1.12** | **Un tunnel qui ressort chez vous est maintenant détecté.** Les deux premiers contrôles le déclaraient bon — le conteneur *est* dans le tunnel. Trouvé sur le banc d'essai : un serveur WireGuard local qui traduisait les adresses vers la sortie du domicile passait au vert. L'adresse du tunnel est donc comparée à celle de la machine. Aucune des deux n'est journalisée. |
| **0.1.12** | **PlugArr vérifie désormais que le trafic torrent sort par le tunnel.** Il écrivait `network_mode: service:gluetun` et considérait l'affaire close ; or ce réglage se perd, et rien ne l'aurait signalé. Deux contrôles dans `doctor` et sur le bouton diagnostic : la structure du conteneur, puis la sortie réelle, demandée au serveur de contrôle de Gluetun **depuis l'intérieur du client**. Ce test ne peut pas réussir par accident — seul un conteneur partageant la pile réseau de Gluetun voit ce `127.0.0.1`, vérifié dans les deux sens. Aucun service extérieur n'est contacté, et l'adresse IP n'est jamais journalisée. |
| **0.1.12** | **Prowlarr ne pouvait pas joindre les clients de téléchargement quand le VPN était actif.** Un client torrent sous VPN passe en `network_mode: service:gluetun` et perd son nom sur le réseau : c'est `gluetun` qu'il faut viser. `step_download_client` le savait, `step_prowlarr_download_client` posait le nom du service en dur. Sonarr, Radarr et Lidarr se câblaient très bien sur les mêmes clients au même instant, ce qui rendait la panne illisible. **Troisième divergence** entre ces deux étapes après le mot de passe et la clé : elles lisent désormais la même fonction. |
| **0.1.11** | **La console d'administration n'avait plus aucun JavaScript depuis la 0.1.8.** Le message de confirmation de « ajouter un service » contenait une chaine ouverte sur deux lignes et trois apostrophes francaises non echappees — du JavaScript invalide, qui emportait le script entier. Demarrer, arreter, redemarrer, faire tourner une cle, appliquer une mise a jour : rien ne repondait. Le HTML etait pourtant parfaitement bien forme, et tous les tests Python passaient. Trouve en ouvrant la page dans un vrai navigateur ; un test verifie desormais que chaque bloc `<script>` a ses apostrophes appariees. |
| **0.1.11** | **Diagnostic et recherche de mises a jour depuis la console.** Deux boutons, demandes a l'usage. La verification des mises a jour tournait deja toutes les quinze minutes, mais en silence : impossible de la declencher ni de savoir quand elle avait eu lieu. Le diagnostic, lui, n'existait qu'en ligne de commande. |
| **0.1.11** | **Une seconde installation ecrasait la premiere.** Docker identifie une pile par son nom, jamais par son repertoire, et ce nom etait fige a `plugarr` : installer une pile d'essai a cote d'une pile en service recreait les six conteneurs de celle-ci en les pointant ailleurs. Le preflight rassurait meme — « port occupe par votre propre pile PlugArr » — ce qui etait vrai du nom et faux de l'installation. `--project-name` existe maintenant, l'assistant le demande, et le preflight avertit. |
| **0.1.11** | **Le volume de la base de Silo survivait a une reinstallation.** PostgreSQL n'applique `POSTGRES_PASSWORD` qu'a la creation de sa base ; sur un volume deja rempli il l'ignore en silence. Reinstaller generait un nouveau mot de passe, le volume gardait l'ancien, et Silo redemarrait en boucle sur « password authentication failed ». La verification ne regardait que le disque. |
| **0.1.11** | **PlugArr promettait un `.gitignore` qu'il n'ecrivait pas.** Le rapport et la page d'acces annoncaient que les identifiants etaient « deja dans .gitignore » ; aucun fichier n'etait depose. Il l'est desormais. |
| **0.1.11** | **La cle privee WireGuard etait ecrite en clair dans `docker-compose.yml`**, seul secret a echapper au `.env` protege. Elle passe par le `.env` comme les autres. |
| **0.1.11** | **Le conseil de fin citait Prowlarr meme absent.** « Ajoutez vos indexeurs dans Prowlarr, ils descendront vers Sonarr et Radarr » s'affichait apres une installation de Silo seul, ou aucune des trois applications n'existait. Il depend maintenant de ce qui est installe. |
| **0.1.11** | La base de Silo passait par un montage vers le disque Windows : ses migrations de premier démarrage prenaient **49 minutes** au lieu de 5 secondes, et l'installation abandonnait au bout de 300 s alors que PostgreSQL fonctionnait très bien. Un volume Docker règle les deux. Au passage, `config/silo-redis` restait vide à côté du `config/silo/redis` que Docker fabriquait lui-même. |
| **0.1.10** | **0.1.8 et 0.1.9 etaient ininstallables** : le fichier des pays VPN n'entrait ni dans l'exécutable ni dans le paquet, et l'assistant mourait sur l'écran VPN. Un test compare désormais les fichiers non-Python réels aux deux déclarations d'empaquetage, et le contrôle de l'exe parcourt l'assistant au lieu de l'ouvrir. |
| **0.1.9** | La console démarre toute seule, sur l'hôte, et se protège par un mot de passe. Un cookie contenant un caractère accentué tuait la requête sans authentification. |
| **0.1.8** | Rotation des clés API, ajout d'un service depuis la page d'administration, et filtre géographique du VPN en liste cliquable. Un même défaut trouvé trois fois : un service qui garde l'ancien secret sans que rien ne le dise — autobrr, puis l'entrée Application de Prowlarr. |
| **0.1.7** | Recyclarr ne posait plus aucun profil, silencieusement, dès qu'un service se retrouvait avec deux fichiers de configuration. Renouvellement d'un mot de passe depuis la page d'administration. autobrr gardait l'ancien mot de passe d'un client de téléchargement. |
| **0.1.6** | Trois plantages de l'assistant : deuxième indexeur sélectionné (`DuplicateIds`), message d'erreur d'un indexeur contenant un crochet ouvert, et champs devenus inaccessibles sur une fenêtre courte. La clé d'un indexeur ne fuit plus à l'écran ni au journal. |
| **0.1.5** | Le VPN et l'adresse de la machine entrent dans l'assistant. Jellyfin gardait un index vide : rien ne lançait d'analyse après la création des bibliothèques. Une étape qui plante n'emporte plus tout le câblage. |
| **0.1.4** | Identifiant au choix, page d'administration accessible. |
| **0.1.3** | Choix explicite sur une configuration existante, page d'accès ouverte automatiquement. |

Le détail complet est dans les [notes de version](https://github.com/yannickuhrig1/plugarr/releases).
