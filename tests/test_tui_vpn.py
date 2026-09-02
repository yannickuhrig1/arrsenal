"""Tests de l'ecran VPN de l'assistant.

Signale a l'usage : « pourquoi tout n'est pas dans l'assistant ? ». Les sept
options `--vpn*` n'existaient qu'en ligne de commande, et le recapitulatif se
contentait d'AVERTIR qu'aucun VPN n'etait configure — sans offrir le moindre
moyen d'en mettre un.
"""

from __future__ import annotations

import pytest
from textual.widgets import Button, Input, RadioButton, Select, SelectionList, Static

from arrsenal.models import VPN_PROVIDERS, VpnConfig
from arrsenal.tui.app import ArrsenalApp
from arrsenal.tui.screens import PathsScreen, SummaryScreen, TemplatesScreen, VpnScreen


@pytest.fixture
def app(tmp_path):
    return ArrsenalApp(project_dir=tmp_path)


async def _vpn(pilot, selection=("sonarr", "qbittorrent")) -> VpnScreen:
    pilot.app.selection = list(selection)
    pilot.app.push_screen(VpnScreen())
    await pilot.pause()
    return pilot.app.screen


# --------------------------------------------------------------- apparition


@pytest.mark.asyncio
async def test_l_ecran_apparait_avec_un_client_de_telechargement(app):
    async with app.run_test() as pilot:
        pilot.app.selection = ["sonarr", "transmission"]
        pilot.app.push_screen(PathsScreen())
        await pilot.pause()
        pilot.app.screen.query_one("#next", Button).press()
        await pilot.pause()

        assert isinstance(pilot.app.screen, VpnScreen)


@pytest.mark.asyncio
async def test_il_est_saute_sans_client_de_telechargement(app):
    """Sans trafic BitTorrent, Gluetun ne protegerait rien."""
    async with app.run_test() as pilot:
        pilot.app.selection = ["sonarr", "jellyfin"]
        pilot.app.push_screen(PathsScreen())
        await pilot.pause()
        pilot.app.screen.query_one("#next", Button).press()
        await pilot.pause()

        assert isinstance(pilot.app.screen, SummaryScreen)


@pytest.mark.asyncio
async def test_les_profils_suivent_toujours_le_vpn(app):
    async with app.run_test() as pilot:
        screen = await _vpn(pilot, ("sonarr", "qbittorrent", "recyclarr"))
        screen.query_one("#next", Button).press()
        await pilot.pause()

        assert isinstance(pilot.app.screen, TemplatesScreen)


# ------------------------------------------------------------------- saisie


@pytest.mark.asyncio
async def test_sans_vpn_par_defaut(app):
    """Le VPN reste un choix : on ne l'impose pas, on le propose."""
    async with app.run_test() as pilot:
        screen = await _vpn(pilot)

        assert screen.vpn_voulu() is False
        assert screen.config().enabled is False
        assert screen.query_one("#next", Button).disabled is False


@pytest.mark.asyncio
async def test_les_25_fournisseurs_sont_proposes(app):
    """Ils viennent de Gluetun lui-meme, pas d'une liste recopiee."""
    async with app.run_test() as pilot:
        screen = await _vpn(pilot)
        liste = screen.query_one("#vpn-provider", Select)

        assert [v for _l, v in liste._options] == list(VPN_PROVIDERS)


@pytest.mark.asyncio
async def test_une_configuration_incomplete_bloque(app):
    """Gluetun refuse de demarrer s'il manque la cle, et le client de
    telechargement reste alors injoignable."""
    async with app.run_test() as pilot:
        screen = await _vpn(pilot)
        screen.query_one("#vpn-oui", RadioButton).value = True
        await pilot.pause()

        assert screen.query_one("#next", Button).disabled is True
        assert "manque" in str(screen.query_one("#vpn-status", Static).content)


@pytest.mark.asyncio
async def test_une_configuration_wireguard_complete_passe(app):
    async with app.run_test() as pilot:
        screen = await _vpn(pilot)
        screen.query_one("#vpn-oui", RadioButton).value = True
        await pilot.pause()
        screen.query_one("#vpn-provider", Select).value = "mullvad"
        screen.query_one("#vpn-key", Input).value = "cle-privee-wireguard"
        await pilot.pause()

        assert screen.query_one("#next", Button).disabled is False
        screen.query_one("#next", Button).press()
        await pilot.pause()

        vpn = pilot.app.vpn
        assert vpn.enabled and vpn.provider == "mullvad"
        assert vpn.wireguard_private_key == "cle-privee-wireguard"


@pytest.mark.asyncio
async def test_openvpn_demande_deux_champs_differents(app):
    """WireGuard veut une cle, OpenVPN un couple : les champs affiches changent."""
    async with app.run_test() as pilot:
        screen = await _vpn(pilot)
        screen.query_one("#vpn-oui", RadioButton).value = True
        await pilot.pause()
        screen.query_one("#vpn-type", Select).value = "openvpn"
        await pilot.pause()

        assert screen.query_one("#vpn-openvpn").has_class("hidden") is False
        assert screen.query_one("#vpn-wireguard").has_class("hidden") is True
        assert screen.query_one("#next", Button).disabled is True

        screen.query_one("#vpn-user", Input).value = "moi"
        screen.query_one("#vpn-pass", Input).value = "secret"
        await pilot.pause()

        assert screen.query_one("#next", Button).disabled is False


@pytest.mark.asyncio
async def test_le_choix_atteint_la_configuration(app):
    async with app.run_test() as pilot:
        screen = await _vpn(pilot)
        screen.query_one("#vpn-oui", RadioButton).value = True
        await pilot.pause()
        screen.query_one("#vpn-provider", Select).value = "protonvpn"
        screen.query_one("#vpn-key", Input).value = "ma-cle"
        # La liste est repeuplee par le changement de fournisseur : il faut
        # laisser passer l'evenement avant de pouvoir y choisir quoi que ce soit.
        await pilot.pause()
        screen.query_one("#vpn-lieux", SelectionList).select("Switzerland")
        await pilot.pause()
        screen.query_one("#next", Button).press()
        await pilot.pause()

        cfg = pilot.app.build_config()
        assert cfg.vpn.enabled and cfg.vpn.provider == "protonvpn"
        assert cfg.vpn.countries == "Switzerland"


# -------------------------------------------------------------------- l'hote


@pytest.mark.asyncio
async def test_l_hote_du_rapport_se_saisit_dans_l_assistant(app):
    """Derniere option qui n'existait qu'en ligne de commande (`--host`).

    Sur un NAS pilote en SSH, `localhost` designe le NAS et non le poste qui
    lit le rapport : toutes les URL de la page finale seraient mortes.
    """
    async with app.run_test() as pilot:
        pilot.app.selection = ["sonarr"]
        pilot.app.push_screen(PathsScreen())
        await pilot.pause()
        screen = pilot.app.screen

        assert screen.query_one("#host", Input).value == "localhost"
        screen.query_one("#host", Input).value = "192.168.1.42"
        screen.query_one("#next", Button).press()
        await pilot.pause()

        assert pilot.app.build_config().host == "192.168.1.42"


@pytest.mark.asyncio
async def test_un_hote_vide_retombe_sur_localhost(app):
    async with app.run_test() as pilot:
        pilot.app.selection = ["sonarr"]
        pilot.app.push_screen(PathsScreen())
        await pilot.pause()
        screen = pilot.app.screen
        screen.query_one("#host", Input).value = "   "
        screen.query_one("#next", Button).press()
        await pilot.pause()

        assert pilot.app.build_config().host == "localhost"


# ------------------------------------------------------------ recapitulatif


async def _recap(pilot, vpn: VpnConfig) -> SummaryScreen:
    pilot.app.selection = ["sonarr", "qbittorrent"]
    pilot.app.config_root, pilot.app.data_root = "/c", "/d"
    pilot.app.vpn = vpn
    pilot.app.push_screen(SummaryScreen())
    await pilot.pause()
    return pilot.app.screen


def _texte(screen: SummaryScreen) -> str:
    return " ".join(str(w.content) for w in screen.query(Static))


@pytest.mark.asyncio
async def test_sans_vpn_le_recapitulatif_avertit(app):
    async with app.run_test() as pilot:
        screen = await _recap(pilot, VpnConfig())

        assert "Aucun VPN" in _texte(screen)


@pytest.mark.asyncio
async def test_avec_un_vpn_le_recapitulatif_se_tait(app):
    """Il annoncait « aucun VPN » a qui venait d'en saisir un : l'avertissement
    ne regardait que la presence d'un client de telechargement."""
    async with app.run_test() as pilot:
        screen = await _recap(
            pilot,
            VpnConfig(enabled=True, provider="mullvad", wireguard_private_key="cle"),
        )

        assert "Aucun VPN" not in _texte(screen)


@pytest.mark.asyncio
async def test_le_recapitulatif_annonce_gluetun(app):
    """Gluetun n'est pas un service du catalogue : il n'apparait pas dans le
    tableau. Sans cette ligne, rien ne confirmerait le choix qui vient d'etre
    fait."""
    async with app.run_test() as pilot:
        screen = await _recap(
            pilot,
            VpnConfig(enabled=True, provider="mullvad", wireguard_private_key="cle"),
        )
        texte = _texte(screen)

        assert "gluetun" in texte and "mullvad" in texte
        assert "wireguard" in texte


@pytest.mark.asyncio
async def test_sans_vpn_le_recapitulatif_ne_parle_pas_de_gluetun(app):
    async with app.run_test() as pilot:
        screen = await _recap(pilot, VpnConfig())

        assert "gluetun" not in _texte(screen)
