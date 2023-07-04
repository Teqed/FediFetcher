"""An ordered set implementation over a dict."""
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path


class OrderedSet:
    """An ordered set implementation over a dict.

    Attributes
    ----------
    _dict (dict[str, datetime]): The dict that stores the ordered set.
    """

    def __init__(self,
        iterable: set[str] | list[str] | dict[str, datetime] | None = None) -> None:
        """Initialize the ordered set.

        Args:
        ----
        iterable (set[str] | list[str] | dict[str, datetime] | None, optional): \
            The iterable to initialize the ordered set with. \
            Defaults to None.
        """
        self._dict = {}
        if iterable is not None:
            if isinstance(iterable, set | list):
                for item in iterable:
                    self.add(item)
            elif isinstance(iterable, dict):
                for item, time in iterable.items():
                    self.add(item, time)
            else:
                msg = "Invalid type for iterable. Expected set, list, dict, or None."
                raise TypeError(msg)

    def add(self, item: str, time: datetime | None = None) -> None:
        """Add the given item to the ordered set.

        Args:
        ----
        item (str): The item to add.
        time (datetime | None): The time to add the item at. \
            If None, the current time will be used.
        """
        if item not in self._dict:
            self._dict[item] = time or datetime.now(UTC)

    def remove(self, item: str) -> None:
        """Remove the given item from the ordered set.

        Args:
        ----
        item (str): The item to remove.

        Raises:
        ------
        KeyError: If the item does not exist in the ordered set.
        """
        self._dict.pop(item)

    def get_time(self, item: str) -> datetime:
        """Get the time the given item was added to the ordered set.

        Args:
        ----
        item (str): The item to get.

        Returns:
        -------
        datetime: The time the item was added to the ordered set.

        Raises:
        ------
        KeyError: If the item does not exist in the ordered set.
        """
        return self._dict[item]

    def update(self, iterable: set[str] | list[str]) -> None:
        """Update the ordered set with the given iterable.

        Args:
        ----
        iterable (Union[set[str], list[str]]): \
            The iterable to update the ordered set with.
        """
        for item in iterable:
            self.add(item)

    def __contains__(self, item: str) -> bool:
        """Check if the given item is in the ordered set.

        Args:
        ----
        item (str): The item to check.

        Returns:
        -------
        bool: Whether the item is in the ordered set.
        """
        return item in self._dict

    def __iter__(self) -> Iterator[str]:
        """Get an iterator over the ordered set.

        Returns
        -------
        Iterator[str]: An iterator over the ordered set.
        """
        return iter(self._dict)

    def __len__(self) -> int:
        """Get the length of the ordered set.

        Returns
        -------
        int: The length of the ordered set.
        """
        return len(self._dict)

    def to_json(self, filename: str) -> None:
        """Dump the ordered set to a JSON file.

        Args:
        ----
        filename (str): The name of the file to dump the ordered set to.
        """
        with Path(filename).open("w") as file:
            json.dump(self._dict, file, default=str)
