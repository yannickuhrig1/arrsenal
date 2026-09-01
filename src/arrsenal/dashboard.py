"""Page d'acces generee a la fin de l'installation.

Le tableau du terminal disparait des qu'on ferme la fenetre. Cette page reste, et
evite d'avoir a retrouver quel service ecoute sur quel port.

Trois pieges traites ici :

- **Les secrets.** La page contient mots de passe et cles API. Elle est ecrite en
  chmod 600 et couverte par le .gitignore genere, et les valeurs sensibles sont
  masquees jusqu'au clic : une page qu'on montre a quelqu'un ne doit pas afficher
  une cle API d'entree.
- **`localhost` ment.** Installee sur un NAS et ouverte depuis un portable, une URL
  en localhost pointe vers le portable. On detecte l'adresse du LAN.
- **Les liens `file://` ne marchent qu'en local.** Sur un NAS ils sont morts. Le
  chemin est donc donne en texte copiable AVANT d'etre donne en lien, et la limite
  est ecrite noir sur blanc.
"""

from __future__ import annotations

import html
import socket
import sys
from datetime import datetime
from pathlib import Path

from . import __version__, catalog
from .layout import CONTAINER_PATHS
from .models import Category, StackConfig

FILENAME = "acces-arrsenal.html"

#: Couleur d'accent par categorie, pour distinguer les cartes d'un coup d'oeil.
_ACCENTS = {
    Category.ARR: "#4c8dff",
    Category.DOWNLOAD: "#31c48d",
    Category.MEDIA: "#a855f7",
    Category.UI: "#f59e0b",
}


def primary_lan_ip() -> str | None:
    """Adresse de la machine sur le reseau local.

    Le connect UDP n'envoie aucun paquet : il se contente de demander au noyau par
    quelle interface il sortirait. 192.0.2.0/24 est TEST-NET-1, jamais routee.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.5)
            sock.connect(("192.0.2.1", 80))
            address = sock.getsockname()[0]
    except OSError:
        return None
    return None if address.startswith("127.") else address


def resolve_host(cfg: StackConfig) -> tuple[str, str | None]:
    """Hote a utiliser dans les liens, et note explicative eventuelle."""
    if cfg.host not in ("localhost", "127.0.0.1"):
        return cfg.host, None
    lan = primary_lan_ip()
    if lan:
        return lan, (
            f"Les liens utilisent {lan}, l'adresse de cette machine sur le reseau local, "
            f"et non localhost : la page reste donc valable depuis un autre appareil."
        )
    return cfg.host, (
        "Les liens pointent vers localhost. Depuis un autre appareil, remplacez-le par "
        "l'adresse de cette machine sur le reseau."
    )


def _secret(value: str | None, label: str) -> str:
    if not value:
        return '<span class="none">—</span>'
    safe = html.escape(value)
    return (
        f'<span class="secret" data-value="{safe}" title="Cliquer pour afficher {label}">'
        f"<span class=\"dots\">••••••••</span></span>"
        f'<button class="copy" data-value="{safe}" title="Copier">copier</button>'
    )


_CONTROLS = """        <div class="state" data-service="{sid}">
          <span class="dot" title="etat inconnu"></span><span class="label">verification…</span>
          <span class="upd" data-service="{sid}" hidden></span>
          <span class="actions">
            <button class="act" data-service="{sid}" data-action="start">demarrer</button>
            <button class="act" data-service="{sid}" data-action="restart">redemarrer</button>
            <button class="act danger" data-service="{sid}" data-action="stop">arreter</button>
          </span>
        </div>
"""


def _cards(cfg: StackConfig, host: str, live: bool = False) -> str:
    blocks = []
    for sid in catalog.STARTUP_ORDER:
        if not cfg.enabled(sid):
            continue
        spec, inst = catalog.get(sid), cfg.services[sid]
        url = f"http://{host}:{inst.host_port}"
        accent = _ACCENTS.get(spec.category, "#64748b")
        rows = ""
        if inst.username:
            rows += (
                f'<div class="row"><span class="k">Identifiant</span>'
                f'<span class="v mono">{html.escape(inst.username)}</span></div>'
            )
        if inst.password:
            rows += (
                f'<div class="row"><span class="k">Mot de passe</span>'
                f'<span class="v">{_secret(inst.password, "le mot de passe")}</span></div>'
            )
        if inst.api_key:
            rows += (
                f'<div class="row"><span class="k">Cle API</span>'
                f'<span class="v">{_secret(inst.api_key, "la cle API")}</span></div>'
            )
        controls = _CONTROLS.format(sid=spec.id) if live else ""
        # Un service sans port publie n'a pas d'interface a ouvrir. Recyclarr
        # tourne sur une planification. Lui donner un lien vers le port 0 offrirait
        # une carte cliquable qui n'aboutit nulle part : le lecteur en conclurait
        # que l'installation a echoue, alors qu'elle a reussi.
        if inst.has_web_ui:
            title = (
                f'<a class="title" href="{url}" target="_blank" rel="noopener">'
                f'<span class="badge">{html.escape(spec.display_name[0])}</span>'
                f"<span><strong>{html.escape(spec.display_name)}</strong>"
                f'<span class="url">{html.escape(url)}</span></span></a>'
            )
        else:
            title = (
                '<div class="title headless">'
                f'<span class="badge">{html.escape(spec.display_name[0])}</span>'
                f"<span><strong>{html.escape(spec.display_name)}</strong>"
                '<span class="url">tache de fond, sans interface</span></span></div>'
            )
        blocks.append(
            f"""      <article class="card" style="--accent:{accent}">
        {title}
        <p class="note">{html.escape(spec.notes)}</p>
{controls}        <div class="creds">{rows}</div>
      </article>"""
        )
    return "\n".join(blocks)


def _has_download_client(cfg: StackConfig) -> bool:
    return any(cfg.enabled(sid) for sid in catalog.DOWNLOAD_CLIENTS)


def _paths(cfg: StackConfig) -> str:
    entries = [
        ("Films", f"{cfg.data_root}/media/movies", CONTAINER_PATHS["media_movies"]),
        ("Series", f"{cfg.data_root}/media/tv", CONTAINER_PATHS["media_tv"]),
        ("Telechargements", f"{cfg.data_root}/torrents", CONTAINER_PATHS["torrents_root"]),
        ("Configurations", cfg.config_root, "—"),
    ]
    if cfg.enabled("lidarr"):
        entries.insert(2, ("Musique", f"{cfg.data_root}/media/music", "/data/media/music"))

    rows = ""
    for label, host_path, container_path in entries:
        safe = html.escape(host_path)
        link = html.escape("file:///" + host_path.lstrip("/").replace("\\", "/"))
        rows += f"""        <tr>
          <td>{html.escape(label)}</td>
          <td class="mono">{safe} <button class="copy" data-value="{safe}">copier</button></td>
          <td class="mono dim">{html.escape(container_path)}</td>
          <td><a href="{link}">ouvrir</a></td>
        </tr>"""
    return rows


def render(cfg: StackConfig, *, failed: int = 0, live: bool = False) -> str:
    """Rend la page.

    `live=False` produit le fichier statique ecrit apres l'installation.
    `live=True` ajoute l'etat des services et les boutons de controle ; cette
    forme n'est servie que par `arrsenal serve`, qui apporte le serveur capable
    de repondre aux appels.
    """
    host, host_note = resolve_host(cfg)
    generated = datetime.now().astimezone().strftime("%d/%m/%Y a %H:%M")
    count = sum(1 for sid in catalog.STARTUP_ORDER if cfg.enabled(sid))

    banner = ""
    if failed:
        banner = (
            f'<div class="banner warn"><strong>{failed} lien(s) n\'ont pas pu etre '
            f"etablis.</strong> Lancez <code>arrsenal doctor</code> pour un diagnostic.</div>"
        )
    if host_note:
        banner += f'<div class="banner info">{html.escape(host_note)}</div>'
    if not cfg.vpn_enabled and _has_download_client(cfg):
        banner += (
            '<div class="banner warn"><strong>Aucun VPN.</strong> Le trafic BitTorrent '
            "sort sur l'adresse IP publique de cette machine.</div>"
        )
    if not cfg.ids_certain:
        banner += (
            f'<div class="banner warn"><strong>PUID/PGID {cfg.puid}:{cfg.pgid}</strong> — '
            f"{html.escape(cfg.ids_source)}. Cette valeur decide de qui possede vos medias."
            "</div>"
        )

    if not live:
        banner += (
            "<div class=\"banner info\">Cette page est un <b>fichier fige</b> : elle ne "
            "montre ni l'etat des services, ni les mises a jour disponibles, et ses "
            "boutons n'existent pas ici.<br>Pour tout cela, ouvrez "
            f"<code>{LAUNCHER_NAME}</code>, depose a cote de cette page.</div>"
        )

    return _TEMPLATE.format(
        generated=generated,
        count=count,
        cards=_cards(cfg, host, live=live),
        paths=_paths(cfg),
        banner=banner,
        data_root=html.escape(cfg.data_root),
        version=__version__,
        live_script=_LIVE_SCRIPT if live else "",
        title="Administration" if live else "Acces",
    )


def write(cfg: StackConfig, target_dir: Path, *, failed: int = 0) -> Path:
    """Ecrit la page. Renvoie son chemin."""
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / FILENAME
    path.write_text(render(cfg, failed=failed), encoding="utf-8")
    try:
        # Meme regime que le .env : la page contient les memes secrets.
        path.chmod(0o600)
    except (OSError, NotImplementedError):
        pass
    return path


def open_in_browser(path: Path) -> bool:
    """Ouvre la page. Renvoie False sans bruit sur une machine sans navigateur,
    ce qui est le cas normal d'un NAS."""
    import webbrowser

    try:
        return webbrowser.open(path.resolve().as_uri())
    except Exception:  # noqa: BLE001 - un echec ici ne doit jamais interrompre
        return False


_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — stack media</title>
<style>
  :root {{
    --bg: #f6f7f9; --panel: #fff; --text: #16181d; --muted: #6b7280;
    --line: #e4e7ec; --warn-bg: #fff7ed; --warn-line: #f59e0b;
    --info-bg: #eff6ff; --info-line: #4c8dff;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #101216; --panel: #181b21; --text: #e8eaed; --muted: #9aa3af;
      --line: #272b33; --warn-bg: #2a2015; --info-bg: #15202f;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 2.5rem 1.5rem 4rem; background: var(--bg); color: var(--text);
    font: 15px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }}
  .wrap {{ max-width: 1080px; margin: 0 auto; }}
  header h1 {{ margin: 0 0 .3rem; font-size: 1.6rem; letter-spacing: -.02em; }}
  header p {{ margin: 0 0 1.6rem; color: var(--muted); }}
  .banner {{
    padding: .8rem 1rem; border-radius: 8px; margin-bottom: .7rem;
    background: var(--info-bg); border-left: 4px solid var(--info-line);
  }}
  .banner.warn {{ background: var(--warn-bg); border-left-color: var(--warn-line); }}
  h2 {{ font-size: 1rem; text-transform: uppercase; letter-spacing: .06em;
       color: var(--muted); margin: 2.2rem 0 .9rem; }}
  .grid {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr)); }}
  .card {{
    background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
    padding: 1rem 1.1rem; border-top: 3px solid var(--accent);
  }}
  .title {{ display: flex; gap: .75rem; align-items: center; text-decoration: none; color: inherit; }}
  .title:hover .url {{ text-decoration: underline; }}
  .title.headless:hover .url {{ text-decoration: none; }}
  .title.headless .url {{ color: var(--muted); font-style: italic; }}
  .badge {{
    width: 38px; height: 38px; flex: none; border-radius: 9px; background: var(--accent);
    color: #fff; display: grid; place-items: center; font-weight: 700; font-size: 1.1rem;
  }}
  .title strong {{ display: block; font-size: 1.05rem; }}
  .url {{ color: var(--accent); font-size: .87rem; font-family: ui-monospace, monospace; }}
  .note {{ color: var(--muted); font-size: .85rem; margin: .7rem 0 .5rem; }}
  .creds {{ border-top: 1px solid var(--line); padding-top: .6rem; }}
  .row {{ display: flex; justify-content: space-between; align-items: center;
          gap: .5rem; padding: .22rem 0; font-size: .87rem; }}
  .k {{ color: var(--muted); }}
  .v {{ display: flex; align-items: center; gap: .4rem; }}
  .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  .dim {{ color: var(--muted); }}
  .none {{ color: var(--muted); }}
  .secret {{ cursor: pointer; font-family: ui-monospace, monospace; }}
  .secret .dots {{ letter-spacing: .1em; }}
  button.copy {{
    font: inherit; font-size: .75rem; padding: .1rem .45rem; cursor: pointer;
    background: transparent; color: var(--muted);
    border: 1px solid var(--line); border-radius: 5px;
  }}
  button.copy:hover {{ color: var(--text); }}
  table {{ width: 100%; border-collapse: collapse; background: var(--panel);
           border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }}
  th, td {{ text-align: left; padding: .6rem .8rem; border-bottom: 1px solid var(--line);
            font-size: .88rem; }}
  th {{ color: var(--muted); font-weight: 600; font-size: .78rem;
        text-transform: uppercase; letter-spacing: .05em; }}
  tr:last-child td {{ border-bottom: none; }}
  td a {{ color: var(--info-line); }}
  footer {{ margin-top: 2.5rem; color: var(--muted); font-size: .85rem;
            border-top: 1px solid var(--line); padding-top: 1.2rem; }}
  code {{ font-family: ui-monospace, monospace; background: var(--bg);
          padding: .1rem .35rem; border-radius: 4px; }}
  .state {{ display: flex; align-items: center; gap: .45rem; flex-wrap: wrap;
            margin: .6rem 0 .2rem; font-size: .84rem; }}
  .dot {{ width: 9px; height: 9px; border-radius: 50%; background: #9ca3af; flex: none; }}
  .dot.up {{ background: #22c55e; }}
  .dot.down {{ background: #ef4444; }}
  .dot.busy {{ background: #f59e0b; }}
  .state .label {{ color: var(--muted); }}
  .state .actions {{ margin-left: auto; display: flex; gap: .3rem; }}
  button.act {{
    font: inherit; font-size: .75rem; padding: .15rem .5rem; cursor: pointer;
    background: transparent; color: var(--muted);
    border: 1px solid var(--line); border-radius: 5px;
  }}
  button.act:hover:not(:disabled) {{ color: var(--text); border-color: var(--accent); }}
  button.act.danger:hover:not(:disabled) {{ color: #ef4444; border-color: #ef4444; }}
  button.act:disabled {{ opacity: .4; cursor: not-allowed; }}
  .upd {{ display: inline-flex; align-items: center; gap: .35rem; }}
  .upd .tag {{
    font-size: .7rem; padding: .05rem .4rem; border-radius: 999px;
    background: var(--warn-bg); color: var(--warn-line);
    border: 1px solid var(--warn-line); font-weight: 600;
  }}
  button.upgrade {{
    font: inherit; font-size: .75rem; padding: .15rem .5rem; cursor: pointer;
    background: var(--warn-line); color: #1b1200; border: none; border-radius: 5px;
    font-weight: 600;
  }}
  button.upgrade:disabled {{ opacity: .5; cursor: not-allowed; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Votre stack media</h1>
    <p>{count} services installes et cables le {generated}.</p>
    {banner}
  </header>

  <h2>Services</h2>
  <div class="grid">
{cards}
  </div>

  <h2>Dossiers</h2>
  <table>
    <thead><tr><th>Contenu</th><th>Sur cette machine</th><th>Vu par les conteneurs</th><th></th></tr></thead>
    <tbody>
{paths}
    </tbody>
  </table>
  <p class="note">Les liens « ouvrir » ne fonctionnent que si ce navigateur tourne sur la
  machine d'installation. Depuis un autre appareil, utilisez le chemin copiable, ou passez
  par un partage reseau.</p>

  <footer>
    <p><strong>Prochaine etape</strong> : ajoutez vos indexeurs dans Prowlarr. Ils
    descendront automatiquement vers vos applications. arrsenal n'en fournit aucun.</p>
    <p>Cette page contient vos mots de passe et vos cles API. Elle est en lecture seule
    pour vous (<code>chmod 600</code>) et exclue du depot git. Ne la partagez pas.</p>
    <p>Genere par arrsenal {version} — donnees dans <code>{data_root}</code>.</p>
  </footer>
</div>
<script>
  document.querySelectorAll('.secret').forEach(function (el) {{
    el.addEventListener('click', function () {{
      var dots = el.querySelector('.dots');
      if (el.dataset.shown === '1') {{
        dots.textContent = '\\u2022'.repeat(8);
        el.dataset.shown = '0';
      }} else {{
        dots.textContent = el.dataset.value;
        el.dataset.shown = '1';
      }}
    }});
  }});
  document.querySelectorAll('button.copy').forEach(function (btn) {{
    btn.addEventListener('click', function () {{
      navigator.clipboard.writeText(btn.dataset.value).then(function () {{
        var before = btn.textContent;
        btn.textContent = 'copie';
        setTimeout(function () {{ btn.textContent = before; }}, 1200);
      }});
    }});
  }});
</script>
{live_script}</body>
</html>
"""

_LIVE_SCRIPT = """<script>
  // Sert uniquement quand la page vient de `arrsenal serve` : c'est ce serveur
  // qui expose /api/status et /api/action. Le jeton voyage en cookie HttpOnly,
  // pose lors du chargement de la page.
  var LIBELLES = {running: 'en marche', exited: 'arrete', created: 'cree',
                  paused: 'en pause', absent: 'conteneur absent'};

  function peindre(services) {
    services.forEach(function (s) {
      var bloc = document.querySelector('.state[data-service="' + s.id + '"]');
      if (!bloc) return;
      var dot = bloc.querySelector('.dot');
      dot.className = 'dot ' + (s.up ? 'up' : 'down');
      dot.title = s.status;
      bloc.querySelector('.label').textContent =
        (LIBELLES[s.state] || s.state) + (s.status ? ' — ' + s.status : '');
      bloc.querySelectorAll('button.act').forEach(function (b) {
        b.disabled = (b.dataset.action === 'start') ? s.up : !s.up;
      });
    });
  }

  function rafraichir() {
    fetch('/api/status', {credentials: 'same-origin'})
      .then(function (r) { return r.json(); })
      .then(function (d) { peindre(d.services); })
      .catch(function () {});
  }

  document.querySelectorAll('button.act').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var bloc = btn.closest('.state');
      bloc.querySelector('.dot').className = 'dot busy';
      bloc.querySelector('.label').textContent = 'en cours…';
      bloc.querySelectorAll('button.act').forEach(function (b) { b.disabled = true; });
      fetch('/api/action', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({service: btn.dataset.service, action: btn.dataset.action})
      }).then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d.ok) { bloc.querySelector('.label').textContent = 'echec : ' + (d.message || d.error); }
          setTimeout(rafraichir, 900);
        })
        .catch(function () { bloc.querySelector('.label').textContent = 'serveur injoignable'; });
    });
  });

  function peindreMaj(services) {
    services.forEach(function (s) {
      var zone = document.querySelector('.upd[data-service="' + s.id + '"]');
      if (!zone) return;
      if (!s.available) { zone.hidden = true; zone.innerHTML = ''; return; }
      var libelle = s.latest
        ? 'v' + s.latest.replace(/^v/, '') + ' disponible'
        : 'image reconstruite';
      var titre = s.latest
        ? 'Version ' + s.current + ' installee, ' + s.latest + ' disponible'
        : 'Meme version, image republiee en amont (correctifs de securite)';
      zone.hidden = false;
      zone.innerHTML =
        '<span class="tag" title="' + titre + '">' + libelle + '</span>' +
        '<button class="upgrade">mettre a jour</button>';
      zone.querySelector('button').addEventListener('click', function () {
        lancerMaj(s, zone);
      });
    });
  }

  function lancerMaj(s, zone) {
    var quoi = s.latest ? ('passer de ' + s.current + ' a ' + s.latest) : 'retirer la meme version';
    var question = s.name + ' : ' + quoi + ' ?'
      + '\\n\\nLe conteneur sera recree. Les autres services ne bougent pas.';
    if (!confirm(question)) return;
    zone.innerHTML = '<span class="tag">mise a jour…</span>';
    fetch('/api/update', {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({service: s.id, target: s.latest || null})
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        zone.innerHTML = '<span class="tag">' + (d.ok ? 'fait : ' + d.message : 'echec') + '</span>';
        if (!d.ok) { alert(s.name + ' : ' + (d.message || d.error)); }
        setTimeout(function () { rafraichir(); verifierMaj(); }, 1500);
      })
      .catch(function () { zone.innerHTML = '<span class="tag">serveur injoignable</span>'; });
  }

  function verifierMaj() {
    fetch('/api/updates', {credentials: 'same-origin'})
      .then(function (r) { return r.json(); })
      .then(function (d) { peindreMaj(d.services); })
      .catch(function () {});
  }

  rafraichir();
  setInterval(rafraichir, 5000);
  // Le controle interroge les registres : lent, et sans urgence.
  verifierMaj();
  setInterval(verifierMaj, 900000);
</script>
"""


#: Nom du lanceur ecrit a cote des artefacts, selon la plateforme.
LAUNCHER_NAME = "administration.cmd" if sys.platform == "win32" else "administration.sh"


def admin_command(project_dir: Path) -> str:
    """Commande capable de relancer la page d'administration.

    Un utilisateur qui a double-clique un executable n'a pas `arrsenal` dans son
    PATH : lui dire « lancez arrsenal serve » ne l'avance a rien. On note donc le
    chemin reellement utilise pour cette installation.
    """
    cible = f'"{Path(project_dir).resolve()}"'
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" serve --project-dir {cible}'
    return f'"{Path(sys.executable).resolve()}" -m arrsenal serve --project-dir {cible}'


def write_admin_launcher(project_dir: Path) -> Path:
    """Ecrit un lanceur double-cliquable pour la page d'administration.

    C'est elle qui porte l'etat des services, les boutons demarrer / arreter /
    redemarrer et les mises a jour disponibles. La page d'acces, elle, est un
    fichier fige : signale a l'usage, personne ne devine qu'il faut lancer une
    commande pour obtenir le reste.
    """
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    cible = project_dir / LAUNCHER_NAME
    commande = admin_command(project_dir)

    if sys.platform == "win32":
        contenu = (
            "@echo off\r\n"
            "rem Genere par arrsenal. Ouvre la page d'administration : etat des\r\n"
            "rem services, demarrage, arret, mises a jour.\r\n"
            "title arrsenal - administration\r\n"
            f"{commande}\r\n"
            "pause\r\n"
        )
        cible.write_text(contenu, encoding="utf-8", newline="")
    else:
        contenu = (
            "#!/bin/sh\n"
            "# Genere par arrsenal. Ouvre la page d'administration : etat des\n"
            "# services, demarrage, arret, mises a jour.\n"
            f"exec {commande}\n"
        )
        cible.write_text(contenu, encoding="utf-8")
        cible.chmod(0o755)
    return cible
