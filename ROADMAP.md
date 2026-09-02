# Feuille de route

Où en est arrsenal, ce qui vient ensuite, et pourquoi. Tenue à jour à chaque
séance de travail.

**Dernière mise à jour : 2 septembre 2026** — version publiée : **0.1.6**

---

## Ce qui marche aujourd'hui

Onze services installés et **câblés** en une passe, vérifiés contre des
instances réelles à chaque livraison.

| | |
|---|---|
| **Téléchargement** | Transmission, qBittorrent |
| **Bibliothèque** | Sonarr, Radarr, Lidarr |
| **Indexeurs** | Prowlarr |
| **Média** | Jellyfin |
| **Automatisation** | autobrr, Recyclarr |
| **Interfaces** | Flood, qui |
| **Réseau** | Gluetun *(VPN optionnel)* |

L'assistant couvre **toutes** les options de la ligne de commande : un test
compare la signature d'`install` à ce que l'assistant sait poser, et échoue si
un écart apparaît.

La page d'administration (`arrsenal serve`) donne l'état des services, les
démarre, les arrête, les redémarre, signale les mises à jour et les applique,
affiche les identifiants, et **renouvelle un mot de passe en recâblant tout ce
qui en dépend**.

---

## En cours

| | État | Note |
|---|---|---|
| **Rotation des mots de passe** | ✅ livré, non publié | qBittorrent, Transmission et les *arr. Vérifié sur une stack de onze services : 25 liaisons sur 25 réalignées. |
| **Rotation des clés API** | à faire | Plus délicat : la clé vit dans `config.xml`, changer demande un redémarrage, et tout ce qui la référence doit suivre. |
| **Ajouter un service après coup** | à faire | `arrsenal wire` sait déjà le faire ; il manque le bouton et la reprise du compose. |
| **Liste des pays du VPN** | à faire | Source identifiée : `qdm12/gluetun-servers`, un JSON par fournisseur. À extraire à la génération pour ne pas dépendre du réseau pendant l'assistant. |

---

## Services à venir

Un service n'entre au catalogue que lorsqu'il est **câblé et vérifié** contre
une instance réelle. L'ordre ci-dessous est celui de l'étude.

| | Ce qu'il reste à faire |
|---|---|
| **Plex** | Second serveur média. Son jeton s'obtient par `plex.tv`, pas par l'API locale : c'est le point à vérifier avant de l'inscrire. |
| **Seerr** | Demandes de médias. Jellyseerr et Overseerr ont fusionné sous ce nom ; le câblage vise Sonarr, Radarr et le serveur média. |
| **Notifiarr** | Notifications centralisées. Chaque *arr s'y déclare par une clé API. |
| **Bazarr** | Sous-titres. Sa configuration passe par un fichier YAML et non par une API — rien n'est encore vérifié. |
| **SABnzbd** | Client Usenet, à côté des deux clients torrent. |
| **DroppedNeedle** | Musique, anciennement *MusicSeerr*. **Remplace Lidarr** plutôt que de le compléter. Un conteneur, `PUID`/`PGID` et un montage `/data` à parent commun : nos conventions exactes. Deux obstacles : il télécharge par slskd ou SABnzbd, aucun des deux au catalogue, et son premier compte administrateur se crée par l'interface web. |
| **Wizarr** | Invitations et gestion des comptes pour Jellyfin, Plex et Emby. Le plus autonome de la liste : un conteneur, et le câblage se réduit au serveur média et à sa clé. |
| **Tautulli** | Suivi et statistiques **Plex**. Ne peut pas précéder Plex. |
| **Jellystat** | Statistiques Jellyfin. Exige une base **PostgreSQL** dans un second conteneur, là où tout le catalogue tient en un seul. |
| **Tracearr** | Suivi des lectures et détection de partage de comptes. L'image `latest` réclame une base et un Redis externes ; le tag `supervised` réunit le tout en un conteneur. |
| **Silo** | Serveur média compatible API Jellyfin. Pile de quatre conteneurs, et aucune version publiée — seulement des SHA de commit. |
| Audiobookshelf, Shelfmark, Shelfarr | Livres et livres audio. |

**Readarr n'est pas au programme** : le projet est archivé depuis le 27 juin 2025.

---

## La console arrsenal

Le seul chantier qui ne soit pas un service de plus. Aujourd'hui l'assistant
installe puis s'efface ; `arrsenal serve` comble une partie du manque, mais
reste une commande à lancer.

| | État |
|---|---|
| État des services | ✅ |
| Démarrer, arrêter, redémarrer | ✅ |
| Voir et appliquer les mises à jour | ✅ |
| Renouveler un mot de passe, avec recâblage | ✅ |
| Renouveler une clé API, avec recâblage | à faire |
| Ajouter un service absent de l'installation | à faire |
| Conteneur autonome plutôt que commande | à faire |

Deux questions à trancher avant d'en faire un conteneur : il devra piloter
Docker, donc accéder au socket Docker — ce qui revient à donner les pleins
pouvoirs sur la machine, et doit être dit clairement. Et une console qui change
des mots de passe doit s'authentifier elle-même, sérieusement.

---

## Ce qu'on ne fera pas

**Choisir plusieurs profils Recyclarr par service.** Recyclarr groupe ses
instances par `base_url` et **écarte tout groupe qui en compte plus d'une** —
c'est `SplitInstancesFilter`, lu dans son code source. Deux profils visant le
même Sonarr, et ce ne sont pas deux profils posés : c'est **zéro**. Les
templates racine sont autonomes et ne se composent pas ; la seule voie serait de
fusionner leur YAML nous-mêmes, exactement ce que le projet refuse — tout
l'intérêt est que le contenu vienne des TRaSH Guides et pas de nous.

arrsenal détecte désormais cette situation et n'en garde qu'un, en renommant les
autres plutôt qu'en les effaçant.

---

## Journal des corrections notables

| Version | |
|---|---|
| **0.1.6** | Trois plantages de l'assistant : deuxième indexeur sélectionné (`DuplicateIds`), message d'erreur d'un indexeur contenant un crochet ouvert, et champs devenus inaccessibles sur une fenêtre courte. La clé d'un indexeur ne fuit plus à l'écran ni au journal. |
| **0.1.5** | Le VPN et l'adresse de la machine entrent dans l'assistant. Jellyfin gardait un index vide : rien ne lançait d'analyse après la création des bibliothèques. Une étape qui plante n'emporte plus tout le câblage. |
| **0.1.4** | Identifiant au choix, page d'administration accessible. |
| **0.1.3** | Choix explicite sur une configuration existante, page d'accès ouverte automatiquement. |

Le détail complet est dans les [notes de version](https://github.com/yannickuhrig1/arrsenal/releases).
