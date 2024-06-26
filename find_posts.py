#!/usr/bin/env python3
"""FediFetcher - a tool to fetch posts from the fediverse."""

import asyncio

from argparser import parse_arguments
from fedifetcher import main

if __name__ == "__main__":
    asyncio.run(main(parse_arguments()))
