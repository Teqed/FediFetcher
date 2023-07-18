"""Manage cache storage and retrieval.

This module contains a class for handling operations related to cache management.
The operations include writing and loading from cache. The cache referred to is defined
and managed using SeenFilesManager class.
"""
import json
import logging
from pathlib import Path

from fedifetcher.ordered_set import OrderedSet


class SeenFilesManager:
    """A class to manage files seen.

    Methods
    -------
    __init__(self, base_dir: str) -> None
        Constructor to initialize SeenFilesManager.
        replied_toot_server_ids: dict[str, str | None],
        known_followings: OrderedSet, recently_checked_users: OrderedSet,
        Write the seen files to the storage.
    get_seen_data(self) -> tuple[OrderedSet, dict[str, str| None], OrderedSet,
        OrderedSet, dict[str, str], dict[str, str]]:
    Load and return seen files data from the storage.
    """

    def __init__(self, base_dir: str) -> None:
        """Initialize the SeenFilesManager.

        Parameters
        ----------
        base_dir : str
            The base directory for storing the cache files.

        """
        self.base_dir = base_dir

    def _get_file_path(self, file_name: str) -> Path:
        """Get the full file path.

        Parameters
        ----------
        file_name : str
            The name of the file.

        Returns
        -------
        Path
            The full file path.

        """
        return Path(self.base_dir) / file_name

    def _write_file(self, file_name: str, data: dict | OrderedSet) -> None:
        """Write data to a file.

        Parameters
        ----------
        file_name : str
            The name of the file.
        data : dict | OrderedSet
            The data to write to the file.

        """
        file_path = self._get_file_path(file_name)
        with file_path.open("w", encoding="utf-8") as file:
            if isinstance(data, OrderedSet):
                file.write("\n".join(list(data)[-50000:]))
                logging.debug(f"Wrote {len(data)} {file_name}")
            else:
                json.dump(dict(list(data.items())[-50000:]), file)
                logging.debug(f"Wrote {len(data)} {file_name}")

    def write_seen_files(
        self,
        replied_toot_server_ids: dict[str, str | None],
        known_followings: OrderedSet,
        recently_checked_users: OrderedSet,
    ) -> None:
        """Write the seen files to disk.

        Parameters
        ----------
            The set of seen URLs.
        replied_toot_server_ids : dict[str, str | None]
            The dictionary mapping toot server IDs to replied toot IDs.
        known_followings : OrderedSet
            The set of known followings.
        recently_checked_users : OrderedSet
            The set of recently checked users.
            The dictionary mapping status IDs to URLs.

        """
        self._write_file("known_followings", known_followings)
        self._write_file("replied_toot_server_ids", replied_toot_server_ids)
        self._write_file("recently_checked_users", recently_checked_users)

    def get_seen_data(
        self,
    ) -> tuple[
        dict[str, str | None], OrderedSet, OrderedSet,
    ]:
        """Load seen files from disk.

        Returns
        -------
        tuple
            A tuple containing the loaded seen files data.

        """
        replied_toot_server_ids = {}
        known_followings = OrderedSet()
        recently_checked_users = OrderedSet()

        file_data = [
            ("known_followings", known_followings),
            ("replied_toot_server_ids", replied_toot_server_ids),
            ("recently_checked_users", recently_checked_users),
        ]

        for file_name, data in file_data:
            file_path = self._get_file_path(file_name)
            if file_path.exists():
                with file_path.open(encoding="utf-8") as file:
                    if isinstance(data, OrderedSet):
                        data.update(file.read().splitlines())
                        logging.debug(f"Loaded {len(data)} {file_name}")
                    else:
                        data.update(json.load(file))
                        logging.debug(f"Loaded {len(data)} {file_name}")

        return (
            replied_toot_server_ids,
            known_followings,
            recently_checked_users,
        )
