from datetime import datetime
from dateutil import parser
import json

class OrderedSet:
    """An ordered set implementation over a dict"""

    def __init__(self, iterable):
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

    def add(self, item, time = None):
        if item not in self._dict:
            if(time is None):
                self._dict[item] = datetime.now(datetime.now().astimezone().tzinfo)
            else:
                self._dict[item] = time

    def pop(self, item):
        self._dict.pop(item)

    def get(self, item):
        return self._dict[item]

    def update(self, iterable):
        for item in iterable:
            self.add(item)

    def __contains__(self, item):
        return item in self._dict

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def toJSON(self):
        return json.dump(self._dict, f, default=str)
