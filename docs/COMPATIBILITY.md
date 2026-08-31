# Compatibilité

Tout ce qui figure ici a été **vérifié contre une instance réelle**, pas déduit de la
documentation. Les tags d'image sont épinglés dans `src/arrsenal/catalog.py`.

Dernière campagne de vérification : **2026-08-31**, Docker Engine 29.6.1,
Docker Compose v5.3.0, Docker Desktop sous Windows 11 (backend WSL2).

## Versions testées

| Service | Image | Tag | Version rapportée par l'API |
|---|---|---|---|
| Sonarr | `lscr.io/linuxserver/sonarr` | `4.0.19` | 4.0.19.2979 |
| Radarr | `lscr.io/linuxserver/radarr` | `6.3.0` | vérifié au démarrage |
| Prowlarr | `lscr.io/linuxserver/prowlarr` | `2.5.2` | vérifié au démarrage |
| Transmission | `lscr.io/linuxserver/transmission` | `4.1.3` | — |
| Jellyfin | `lscr.io/linuxserver/jellyfin` | `10.11.11` | 10.11.11 |
| Lidarr | `lscr.io/linuxserver/lidarr` | `3.1.0` | 3.1.0.4875 |
| qBittorrent | `lscr.io/linuxserver/qbittorrent` | `5.2.3` | v5.2.3 |
| Flood | `jesec/flood` | `4.16.1` | pas encore testé |

## Constats vérifiés expérimentalement

### Le pré-semis de `config.xml` fonctionne

Un `config.xml` écrit **avant** le premier démarrage est adopté par l'application.
Sonarr conserve nos champs et se contente d'ajouter les siens (`EnableSsl`).
Notre clé API répond immédiatement sur `/api/v3/system/status`.

Le premier démarrage prend **environ 110 s** (extraction de l'image + initialisation).
C'est ce qui fixe le délai d'attente par défaut à 300 s.

### `Forms` + `Enabled` est le bon réglage d'authentification

Trois comportements confirmés sur Sonarr 4.0.19.2979 :

| Requête | Résultat |
|---|---|
| `GET /` sans session | `302` vers `/login` — l'UI est protégée |
| `GET /api/v3/system/status` sans clé | `401` |
| `GET /api/v3/system/status` avec `X-Api-Key` | `200`, `"authentication": "forms"` |

L'alternative `External` + `DisabledForLocalAddresses` câble aussi bien mais laisse
les interfaces web ouvertes à tout le réseau local. **Rejetée.**

Bonus : l'application consomme `<Username>`/`<Password>` au premier démarrage, les
migre en base, puis les **efface du fichier**. Le mot de passe en clair ne survit pas
sur le disque.

### `Category` et `Directory` sont mutuellement exclusifs

Renseigner les deux fait échouer la création du client de téléchargement :

```
HTTP 400 — propertyName: "TvCategory", errorMessage: "Cannot use Category and Directory"
```

**Piège** : le gabarit renvoyé par `/schema` arrive avec une catégorie **par défaut
déjà remplie** (`tv-sonarr` pour Sonarr, `radarr` pour Radarr). Il ne suffit pas
d'omettre le champ, il faut le **vider explicitement**.

`arrsenal` retient `Directory`, qui pointe vers un chemin explicite sous
`/data/torrents` et garde les hardlinks possibles.

### La notification Jellyfin exige une clé API

L'implémentation `MediaBrowser` de Sonarr et Radarr refuse un `apiKey` vide :

```
HTTP 400 — propertyName: "ApiKey", errorMessage: "'Api Key' must not be empty."
```

`arrsenal` crée donc une clé Jellyfin via `POST /Auth/Keys?app=arrsenal` (répond `204`)
pendant l'étape d'assistant, puis la relit par `GET /Auth/Keys`, et l'injecte dans les
notifications. C'est ce qui impose l'ordre : Jellyfin avant les notifications.

### Assistant de démarrage Jellyfin 10.11.11

| Appel | Code |
|---|---|
| `POST /Startup/Configuration` | `204` |
| `GET /Startup/User` | `200` |
| `POST /Startup/User` | `204` |
| `POST /Startup/RemoteAccess` | `204` |
| `POST /Startup/Complete` | `204` |
| `POST /Users/AuthenticateByName` | `200` + `AccessToken` |
| `POST /Library/VirtualFolders` | `204` |

Après quoi `StartupWizardCompleted` passe à `true` et la bibliothèque apparaît avec le
bon `CollectionType` et le bon chemin.

Jellyfin démarre en **environ 25 s**, nettement plus vite que les *arr.

## Vérification finale du câblage

Chaque lien est validé par le bouton **Test** de l'application concernée, pas par le
code de retour du POST :

| Test | Résultat |
|---|---|
| `POST /api/v3/downloadclient/test` (Sonarr → Transmission) | `200` |
| `POST /api/v1/applications/test` (Prowlarr → Sonarr) | `200` |
| `POST /api/v3/notification/test` (Sonarr → Jellyfin) | `200` |
| `GET /api/v3/rootfolder` | `accessible: true` |

Installation propre depuis zéro : **10/10 liens établis**.

## Phase 2 — constats vérifiés

Campagne du **2026-08-31**, même environnement. Installation propre à 7 services
avec **les deux clients de téléchargement en parallèle** : **18/18 liens établis**.

### Le pré-semis du mot de passe qBittorrent fonctionne

Depuis la 4.6.1, qBittorrent génère au premier démarrage un mot de passe temporaire
aléatoire écrit sur sa sortie standard — impossible à câbler automatiquement.

Écrire `WebUI\Password_PBKDF2` dans `/config/qBittorrent/qBittorrent.conf` avant le
premier démarrage résout le problème. Format confirmé contre 5.2.3 :

```
@ByteArray(<sel base64>:<empreinte base64>)
PBKDF2-HMAC-SHA512, 100000 itérations, clé 64 octets, sel 16 octets
```

Résultat : `POST /api/v2/auth/login` répond `204` avec un cookie `QBT_SID`, et aucun
mot de passe temporaire n'apparaît dans les logs.

**Attention au code de retour** : qBittorrent 5.x renvoie `204` en cas de succès et
`200` avec le corps `Fails.` en cas d'échec. C'est donc la présence du cookie qui fait
foi, jamais le code HTTP seul.

### `HostHeaderValidation` doit être désactivé

Sonarr et Radarr appellent qBittorrent par son nom de conteneur
(`http://qbittorrent:8080`), pas par une adresse IP. Sans
`WebUI\HostHeaderValidation=false`, qBittorrent rejette ces requêtes.

### qBittorrent route par catégorie, Transmission par répertoire

Transmission n'a pas de vraies catégories : on lui passe un `Directory`.
qBittorrent a des catégories natives avec chemin de sauvegarde par catégorie : on lui
passe une `Category`, créée en amont via `POST /api/v2/torrents/createCategory`.

Ordre imposé : les catégories doivent exister **avant** que les *arr n'y pointent,
sinon qBittorrent les crée lui-même sans chemin de sauvegarde. Prowlarr fait de même
avec une catégorie `prowlarr` : elle est donc pré-créée aussi.

Vérifié après installation :

```
movies   -> /data/torrents/movies
music    -> /data/torrents/music
prowlarr -> /data/torrents
tv       -> /data/torrents/tv
```

### Lidarr n'est pas un Sonarr comme les autres

Trois différences qui cassent le code écrit pour Sonarr et Radarr :

1. **Son API est en `v1`**, pas `v3`.
2. **Son dossier racine exige plus de champs.** Là où Sonarr accepte `{"path": ...}`,
   Lidarr répond `400` :

   ```
   Name                     : 'Name' must not be empty.
   DefaultQualityProfileId  : must be greater than '0'.
   DefaultMetadataProfileId : must be greater than '0'.
   ```

   Il n'existe pas de `/schema` pour `rootfolder`. Les identifiants de profils ne sont
   pas stables entre versions : ils sont résolus **par nom** (`Standard`), avec repli
   sur le premier profil disponible.

3. Lidarr n'expose **pas** l'implémentation de notification `MediaBrowser` : aucun lien
   Lidarr vers Jellyfin n'est tenté.

## PUID / PGID par plateforme — vérifié

Le point de départ était un `TODO(verify)`. La vérification a montré que **la question
était mal posée** : ce ne sont pas les mêmes valeurs qu'il fallait trouver, mais deux
comportements différents.

| Profil | Comportement | Pourquoi |
|---|---|---|
| `generic-linux` | détection (`os.getuid`) | l'utilisateur courant est le bon |
| `unraid` | **constante 99:100** | Unraid fait tourner ses conteneurs en `nobody:users` à l'échelle de la plateforme, et son `appdata` appartient à 99:100 |
| `synology` | détection | **les UID DSM varient selon l'ordre de création des utilisateurs** : 1026 pour le premier, mais on rencontre couramment bien plus haut |

Coder `1026` en dur pour Synology était donc **faux par conception**, pas seulement non
vérifié. Une constante ne peut pas être juste quand la valeur dépend de l'installation.

Deux conséquences dans le code :

- `detect_ids()` renvoie `None` quand la plateforme n'expose pas `os.getuid` (Windows),
  au lieu d'inventer `1000:1000` en silence. Une valeur fabriquée sans le dire empêche
  d'avertir l'utilisateur.
- `StackConfig` porte `ids_source` et `ids_certain`. Le récapitulatif affiche d'où
  viennent les valeurs (« détecté », « constante Unraid », « repli »), et l'assistant
  avertit explicitement quand la détection a échoué.

Sources : [forums Unraid](https://forums.unraid.net/topic/117661-docker-user-puid-and-group-pgid-settings/)
· [Marius Hosting, UID/GID sur Synology](https://mariushosting.com/synology-how-to-find-uid-userid-and-gid-groupid/)

## Coexistence avec une stack existante — vérifié

Observation faite sur un Unraid réel faisant tourner 75 conteneurs, dont un
`sonarr` sur le port 8989 avec `/mnt/user/appdata/sonarr` en configuration :
**arrsenal codait `container_name` en dur**, donc il ne pouvait ni cohabiter avec une
stack existante, ni être déployé deux fois sur la même machine.

Les noms de conteneurs sont désormais préfixés par le nom de projet
(`arrsenal-sonarr`). Vérifié contre Docker Compose v5.3 que cela ne casse rien :

```
depuis le service "sonarr" :
  getent hosts prowlarr           -> 172.18.0.3  prowlarr
  getent hosts dnsprobe-prowlarr  -> 172.18.0.3  dnsprobe-prowlarr
```

Le **nom de service** résout indépendamment de `container_name`. Le câblage vise le
service (`http://sonarr:8989`), il n'est donc pas affecté.

Les collisions de **ports** restent possibles (8989 est un défaut très répandu) : le
préflight les détecte et refuse avant toute écriture.

## Linux natif — vérifié le 2026-08-31

Toutes les campagnes précédentes tournaient sous Docker Desktop / WSL2, où les
permissions sont plus permissives qu'un vrai serveur. Vérification faite sur un **LXC
Proxmox Debian 12.2** (PVE 9.2.6), ext4, Docker 29.7.2.

| | |
|---|---|
| Installation complète (5 services) | **11/11 liens établis**, tous validés par le bouton Test |
| Second passage | aucune création, tout « déjà présent » |
| Hardlink `/data/torrents/tv` → `/data/media/tv`, **depuis l'intérieur du conteneur Sonarr** | `stat -c %h` = **2** |

Le hardlink est la preuve qui manquait : sous Windows, seul `os.link` côté hôte avait
été testé. Ici c'est Sonarr lui-même, dans son conteneur, sur ext4, qui partage l'inode
entre les téléchargements et la médiathèque. C'est exactement ce que le montage `/data`
unique doit garantir.

### Docker dans un LXC : `nesting=1` suffit

Contrairement à ce qui est souvent écrit, `keyctl=1` n'a pas été nécessaire — et il
n'est de toute façon pas réglable via un jeton d'API Proxmox, seulement en `root@pam`
direct. Avec `nesting=1` seul, `docker run hello-world` et la stack complète
fonctionnent.

### Le bug que seul Linux pouvait révéler

`sudo arrsenal install` détectait `0:0` et faisait tourner **toute la stack en root**,
en silence. Les médias téléchargés appartiennent alors à root, et l'utilisateur ne peut
plus y toucher sans `sudo`.

`resolve_ids` signale désormais explicitement le cas root, au même titre qu'une
détection impossible. La valeur reste proposée — c'est un choix légitime sur certains
NAS — mais elle n'est plus silencieuse.

## Non vérifié à ce jour

- Bazarr est **volontairement absent du catalogue** : sa configuration passe par un
  fichier YAML et non par une API, et rien n'a encore été vérifié. Le projet ne livre
  pas de service qu'il ne sait pas câbler.
- Flood n'a pas encore été démarré dans une campagne de test.

## Indexeurs — constats vérifiés (Prowlarr 2.5.2)

### Ce que Prowlarr embarque

`GET /api/v1/indexer/schema` renvoie **626 définitions**, soit **5,7 Mo** — à charger une
seule fois et à mettre en cache, jamais à chaque frappe.

| | |
|---|---|
| privées | 475 |
| publiques | 88 |
| semi-privées | 63 |
| torrent / usenet | 605 / 21 |

### Repérer les champs d'identifiants

Le marqueur `privacy` au niveau champ (`apiKey`, `password`, `userName`) ne couvre que
**115 champs sur plus de 9500** : la majorité des définitions Cardigann laissent leurs
clés en `privacy: normal`. Une heuristique combinée est nécessaire :

1. `privacy` ∈ (`apiKey`, `password`, `userName`)
2. ou `type == "password"`
3. ou nom connu (`apikey`, `passkey`, `cookie`, `rsskey`, …)
4. ou — **règle structurelle** — `type == "textbox"` avec une valeur par défaut vide
5. en excluant les préfixes de réglage (`baseSettings.`, `torrentBaseSettings.`,
   `usenetBaseSettings.`), les 882 champs `type: "info"` purement décoratifs, et une
   courte liste de zones de texte libres qui n'en sont pas (`vipExpiration`,
   `additionalParameters`, préférences de langue)

### L'audit qui a produit la règle 4

Les règles 1 à 3 ont été confrontées aux **626 définitions** par
[`scripts/audit_indexers.py`](../scripts/audit_indexers.py). Elles laissaient passer
six identifiants : `mamId` (MyAnonamouse), `twoFactorAuthCode`, `alt2fatoken`, `passan`,
`staffpass`, `csrf_token`.

Tous étaient des **zones de texte sans valeur par défaut**. D'où la règle structurelle,
qui vaut mieux qu'une liste de noms à rallonge : une textbox vide est, par construction,
quelque chose que seul l'utilisateur peut fournir. Les réglages de comportement sont des
cases à cocher ou des listes, jamais des textbox vides.

Effet mesuré : **58 champs** rattrapés sur les 626 définitions, tous de vrais
identifiants (26 codes 2FA, 17 `useragent`, 8 `pin`, `mamId`, `passan`, `staffpass`…).
Aucun formulaire ne dépasse **3 identifiants**.

Deux familles de cas ont été examinées puis jugées correctes :

- **4 index privés sans aucun identifiant** — `BitMagnet (Local DHT)`, `comicat`,
  `MioBT`, `ConCen`. Ce sont des moteurs de recherche qui n'exigent pas de compte.
- **6 champs au nom trompeur** — `useFreeleechToken`, `usetoken`, `passid`… tous des
  cases à cocher ou des listes, donc des réglages.

L'audit tourne en CI contre le Prowlarr de la stack de test : **il échoue si une future
version introduit un champ d'identifiant d'une forme non prévue.**

### Les URL ne sont pas dans le champ `baseUrl`

**600 des 626** définitions exposent un `baseUrl` de type `select` **sans valeur et sans
`selectOptions`**. Les adresses vivent au niveau de la définition, dans `indexerUrls`.
Sans cette reprise, l'utilisateur devrait deviner l'adresse du tracker. Seules 3
définitions n'ont légitimement aucune URL : les génériques (`Generic Newznab`,
`Generic Torznab`, `Torrent RSS Feed`).

### L'ajout contacte forcément l'indexeur

`appProfileId` doit être `> 0`, comme le dossier racine de Lidarr. Résolu par nom
(`Standard`), jamais codé en dur.

Surtout : **`forceSave=true` ne saute pas la validation.** Vérifié sur deux cas d'échec :

| Situation | Résultat |
|---|---|
| indexeur injoignable | `400 — Unable to connect to indexer` |
| recherche de test sans résultat | `400 — Query successful, but no results were returned` |
| faux indexeur Torznab local renvoyant un résultat | enregistré |

Il n'existe donc **aucun moyen d'enregistrer un indexeur hors ligne**. Ce n'est pas un
choix d'arrsenal. La contrepartie est utile : la validation *est* le test, donc un ajout
réussi prouve que les identifiants fonctionnent.

Vérification menée contre un **faux serveur Torznab local**, jamais contre un vrai
tracker.
