#!/usr/bin/env python3
"""FediFetcher - a tool to fetch posts from the fediverse."""

import asyncio

from fedifetcher.main import main

asyncio.run(main())
