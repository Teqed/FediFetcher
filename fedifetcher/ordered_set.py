"""An ordered set implementation over a dict."""
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from dateutil import parser


class OrderedSet:
    """An ordered set implementation over a dict."""

    def __init__(
            self : "OrderedSet",
            iterable: list,
            ) -> None:
        """Initialize the ordered set.

        Args:
        ----
        self: The ordered set to initialize.
        iterable: The iterable to initialize the ordered set with.
        """
        self._dict = {}
        if isinstance(iterable, dict):
            for item in iterable:
                if isinstance(iterable[item], str):
                    self.add(item, parser.parse(iterable[item]))
                else:
                    self.add(item, iterable[item])
        else:
            for item in iterable:
                self.add(item)

    def add(
            self : "OrderedSet",
            item : str,
            time : datetime | None = None,
            ) -> None:
        """Add the given item to the ordered set.

        Args:
        ----
        self: The ordered set to add the item to.
        item: The item to add.
        time: The time to add the item at.
        """
        if item not in self._dict:
            if(time is None):
                self._dict[item] = datetime.now(datetime.now(UTC).astimezone().tzinfo)
            else:
                self._dict[item] = time

    def pop(
            self : "OrderedSet",
            item : str,
            ) -> None:
        """Remove the given item from the ordered set.

        Args:
        ----
        self: The ordered set to remove the item from.
        item: The item to remove.
        """
        self._dict.pop(item)

    def get(
            self : "OrderedSet",
            item : str,
            ) -> datetime:
        """Get the time the given item was added to the ordered set.

        Args:
        ----
        self: The ordered set to get the item from.
        item: The item to get.

        Returns:
        -------
        The time the item was added to the ordered set.
        """
        return self._dict[item]

    def update(
            self : "OrderedSet",
            iterable : list,
            ) -> None:
        """Update the ordered set with the given iterable.

        Args:
        ----
        self: The ordered set to update.
        iterable: The iterable to update the ordered set with.
        """
        for item in iterable:
            self.add(item)

    def __contains__(
            self : "OrderedSet",
            item : str,
            ) -> bool:
        """Check if the given item is in the ordered set.

        Args:
        ----
        self: The ordered set to check.
        item: The item to check.

        Returns:
        -------
        Whether the item is in the ordered set.
        """
        return item in self._dict

    def __iter__(
            self : "OrderedSet",
            ) -> Iterable:
        """Get an iterator over the ordered set.

        Args:
        ----
        self: The ordered set to iterate over.

        Returns:
        -------
        An iterator over the ordered set.
        """
        return iter(self._dict)

    def __len__(self : "OrderedSet") -> int:
        """Get the length of the ordered set.

        Args:
        ----
        self: The ordered set to get the length of.

        Returns:
        -------
        The length of the ordered set.
        """
        return len(self._dict)

    def to_json(self: "OrderedSet", filename: str) -> None:
        """Dump the ordered set to a JSON file.

        Args:
        ----
        self: The ordered set to dump.
        filename: The name of the file to dump the ordered set to.
        """
        with Path(filename).open("w") as file:
            json.dump(self._dict, file, default=str)
