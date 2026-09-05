*[Français](PRIOR-ART.md) · **English***

# What already exists

Written before the first line of code, so as not to redo what is already done, and kept
up to date since. Every project was read, not assumed.

## The summary

| Project | Deploys | Wires the apps together | Quality profiles | Wizard | Language |
|---|---|---|---|---|---|
| [DockSTARTer](https://github.com/GhostWriters/DockSTARTer) | yes | no | no | `ncurses` menu | English |
| [Saltbox](https://github.com/saltyorg/Saltbox) | yes | partial | no | no | English |
| [geekau/mediastack](https://github.com/geekau/mediastack) | yes (files) | no | no | no | English |
| [Recyclarr](https://github.com/recyclarr/recyclarr) | no | no | **yes** | no | English |
| [Configarr](https://github.com/raydak-labs/configarr) | no | no | **yes** | no | English |
| [TRaSH Guides](https://trash-guides.info/) | no | no | manual | no | English |
| **PlugArr** | **yes** | **yes** | **yes** (delegated to Recyclarr) | **yes** | **fr + en** |

The column that matters is the second one. That is the one almost nobody goes to.

### How that last column was checked

Claiming a project speaks only English is a claim about somebody else's work: it
gets verified. Three probes, on 5 September 2026, against each of the five
repositories:

| | Result |
|---|---|
| `.po` files (`filename:*.po`) | 0 everywhere |
| Occurrences of `gettext`, `i18n` or `localization` in the code | 0 everywhere |
| An `i18n/`, `locale/`, `locales/`, `lang/` or `translations/` directory at the root | none |

This is not proof of absence — a translation could go through another
mechanism, and GitHub's search index can lag. It is enough to write it down, and
the method is here so it can be redone.

PlugArr, for its part, carries **548 phrases** in its catalogue and an audit that
fails if one is missing: `scripts/audit_traductions.py`.

## Project by project

### DockSTARTer

The closest in intent: a menu that lets you pick applications and generates a
`docker-compose.yml`. Very mature, very broad, more than a hundred applications.

**What it does not do**: once the containers are running, everything is still left to do.
No API key is exchanged, no root folder is created, no download client is attached. That is
exactly the three hours of work PlugArr removes.

### Saltbox (and Cloudbox before it)

A very complete Ansible deployment, down to the reverse proxy and the certificates. It
does wire some things together.

**The mismatch**: it is a distribution, not a tool. It expects a dedicated server, imposes
its choices, and is aimed at serious, long-lived use rather than at an installation you try
out on a Sunday.

### geekau/mediastack

Excellent Compose files, very well documented, with several variants depending on whether
you want a VPN or not.

**The limit**: they are files. The wiring stays manual, and the documentation is there to
guide you through it, not to do it for you.

### Recyclarr and Configarr

They sync the TRaSH Guides' quality profiles and *custom formats* into Sonarr and Radarr.
Each does that job very well.

**They do not overlap with PlugArr**: they assume a stack that is already installed and
already wired. They come afterwards.

That is exactly why Recyclarr is now **integrated, not replaced**. PlugArr asks it to
generate its configuration from an official template, then writes into it only the URL and
the API key, the two things it alone knows, and the only two lines the user would have had
to go and find by hand. The content of the profiles stays the guide's.

### TRaSH Guides and the Servarr wiki

The documentary reference for this field. That is where the single `/data` mount principle
comes from, and the reason PlugArr enforces it.

Nothing to compete with: these are guides. PlugArr aims to apply their recommendations
automatically, and credits them.

## Where PlugArr sits

The gap is clear: **deployment and complete wiring, in a single tool, with a wizard**.

Three choices follow from that analysis.

**The wiring is the reason to exist, not a bonus.** Generating a `docker-compose.yml` is a
means. If PlugArr did only that, it would have no reason to exist next to DockSTARTer.

**The wiring must be verified, not assumed.** That is what separates a tool from a script.
Every link is validated by the target application's *Test* button.

**The quality profiles come from Recyclarr.** Reimplementing the TRaSH Guides would be a
pointless duplication that goes stale fast. PlugArr provides the wiring, TRaSH provides the
profiles.

## The autobrr ecosystem

Pointed out along the way, and it changes two things.

### dashbrr: the admin page is not a new idea

[`autobrr/dashbrr`](https://github.com/autobrr/dashbrr) (227 stars, Go) is a monitoring and
management dashboard for a media stack. Which is, to a large extent, what `plugarr serve`
does.

Better to say so than to pretend otherwise. What is left to PlugArr: the page comes out of
the installation, with no extra container and no configuration. dashbrr is richer and more
polished for anyone who wants a permanent dashboard.

### autobrr and qui: two additions, not two competitors

[`autobrr`](https://github.com/autobrr/autobrr) (2,991 stars) listens to trackers' IRC
announce channels instead of waiting for the next RSS poll. It plugs into the *arr **and**
into the download client: it is a wiring node, exactly what this project automates. Added to
the catalogue.

[`qui`](https://github.com/autobrr/qui) (4,430 stars) is a single-binary qBittorrent UI,
more starred than Flood and more recent. Added as an option, without replacing Flood, which
also covers Transmission.

Left aside: `netronome` (network speed testing) and `mkbrr` (torrent file creation) fall
outside the scope of a consumption stack. `upbrr` prepares uploads to private trackers: it
is a legitimate tool, but its purpose diverges from this project's position, which provides
neither trackers nor facilitation.

## What none of them do, and neither do we (yet)

- **Verifying that hardlinks actually work** before the installation. PlugArr does that,
  and it may be its most useful addition after the wiring.
- **A "diagnostic" mode for an installation you did not perform yourself.** `plugarr doctor`
  only covers part of that.

## Method

This document is re-read at every phase. A project that starts wiring applications together
changes PlugArr's positioning, and it is better to know that early than to discover it in a
Reddit comment.

Last re-read: 2026-08-31.

*Since it was first written, `plugarr adopt` covers taking over an existing stack, which was
listed here as a gap across the whole ecosystem.*
