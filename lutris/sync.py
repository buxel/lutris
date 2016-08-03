"""Synchronization of the game library with server and local data."""
import os

from lutris import api, pga
from lutris.runners.steam import steam
from lutris.runners.winesteam import winesteam
from lutris.util.steam import get_appmanifests, AppManifest
from lutris.util import resources
from lutris.util.log import logger


class Sync(object):
    def __init__(self):
        self.library = pga.get_games()

    def sync_all(self):
        added, updated = self.sync_from_remote()
        installed, uninstalled = self.sync_local()
        return added, updated, installed, uninstalled

    def sync_local(self):
        """Synchronize games state with local third parties."""
        installed, uninstalled = self.sync_steam_local()
        return installed, uninstalled

    def sync_from_remote(self):
        """Synchronize from remote to local library.

        :return: The added and updated games (slugs)
        :rtype: tuple of sets
        """
        logger.debug("Syncing game library")
        # Get local library
        local_slugs = set([game['slug'] for game in self.library])
        logger.debug("%d games in local library", len(local_slugs))
        # Get remote library
        try:
            remote_library = api.get_library()
        except Exception as e:
            logger.debug("Error while downloading the remote library: %s" % e)
            remote_library = {}
        remote_slugs = set([game['slug'] for game in remote_library])
        logger.debug("%d games in remote library (inc. unpublished)",
                     len(remote_slugs))

        not_in_local = remote_slugs.difference(local_slugs)

        added = self.sync_missing_games(not_in_local, remote_library)
        updated = self.sync_game_details(remote_library)
        if added:
            self.library = pga.get_games()
        return (added, updated)

    @staticmethod
    def sync_missing_games(not_in_local, remote_library):
        """Get missing games in local library from remote library.

        :return: The slugs of the added games
        :rtype: set
        """
        if not not_in_local:
            return set()

        missing = []
        for game in remote_library:
            slug = game['slug']
            if slug in not_in_local:
                logger.debug("Adding to local library: %s", slug)
                missing.append({
                    'name': game['name'],
                    'slug': slug,
                    'year': game['year'],
                    'updated': game['updated'],
                    'steamid': game['steamid']
                })
        missing_ids = pga.add_games_bulk(missing)
        logger.debug("%d games added", len(missing))
        return set(missing_ids)

    @staticmethod
    def sync_game_details(remote_library):
        """Update local game details,

        :return: The slugs of the updated games.
        :rtype: set
        """
        if not remote_library:
            return set()
        updated = set()

        # Get remote games (TODO: use this when switched API to DRF)
        # remote_games = get_games(sorted(local_slugs))
        # if not remote_games:
        #     return set()

        for game in remote_library:
            slug = game['slug']
            sync = False
            sync_icons = True
            local_game = pga.get_game_by_field(slug, 'slug')
            if not local_game:
                continue

            # Sync updated
            if game['updated'] > local_game['updated']:
                sync = True
            # Sync new DB fields
            else:
                for key, value in local_game.iteritems():
                    if value or key not in game:
                        continue
                    if game[key]:
                        sync = True
                        sync_icons = False
            if not sync:
                continue

            logger.debug("Syncing details for %s" % slug)
            game_id = pga.add_or_update(
                name=local_game['name'],
                runner=local_game['runner'],
                slug=slug,
                year=game['year'],
                updated=game['updated'],
                steamid=game['steamid']
            )

            # Sync icons (TODO: Only update if icon actually updated)
            if sync_icons:
                resources.download_icon(slug, 'banner', overwrite=True)
                resources.download_icon(slug, 'icon', overwrite=True)
                updated.add(game_id)

        logger.debug("%d games updated", len(updated))
        return updated

    def sync_steam_local(self):
        """Sync Steam games in library with Steam and Wine Steam

        FIXME: This is the guilty method that causes grief to everyone, most of it should
        probably disappear
        """
        steamrunner = steam()
        winesteamrunner = winesteam()
        installed = set()
        uninstalled = set()

        # Get installed steamapps
        installed_steamapps = self.get_installed_steamapps(steamrunner)
        installed_winesteamapps = self.get_installed_steamapps(winesteamrunner)

        for game_info in self.library:
            runner = game_info['runner']
            steamid = str(game_info['steamid'])
            installed_in_steam = steamid in installed_steamapps
            installed_in_winesteam = steamid in installed_winesteamapps

            # Set installed
            if not game_info['installed']:
                if installed_in_steam:
                    runner_name = 'steam'
                elif installed_in_winesteam:
                    runner_name = 'winesteam'
                    if not game_info['configpath']:
                        continue
                else:
                    continue
                game_id = steam.mark_as_installed(steamid, runner_name, game_info)
                installed.add(game_id)

            # Set uninstalled
            elif not (installed_in_steam or installed_in_winesteam):
                if runner not in ['steam', 'winesteam']:
                    continue
                if runner == 'steam' and not steamrunner.is_installed():
                    continue
                if runner == 'winesteam' and not winesteamrunner.is_installed():
                    continue
                logger.debug("Setting %(name)s (%(steamid)s) as uninstalled", game_info)
                game_id = steam.mark_as_uninstalled(game_info)
                uninstalled.add(game_id)
        return (installed, uninstalled)

    @staticmethod
    def get_installed_steamapps(runner):
        """Return a list of appIDs of the installed Steam games."""
        if not runner.is_installed():
            return []
        installed = []
        steamapps_paths = runner.get_steamapps_dirs()
        for steamapps_path in steamapps_paths:
            for filename in get_appmanifests(steamapps_path):
                appmanifest_path = os.path.join(steamapps_path, filename)
                appmanifest = AppManifest(appmanifest_path)
                if appmanifest.is_installed():
                    installed.append(appmanifest.steamid)
        return installed
