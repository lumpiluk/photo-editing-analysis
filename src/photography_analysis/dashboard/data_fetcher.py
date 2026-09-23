import asyncio
import logging
import pathlib

from immichpy import AsyncClient
import pandas as pd

from photography_analysis.dashboard.config import settings
from photography_analysis.immich_data import (
    get_all_people,
    get_all_photo_dates,
    get_person_date_ranges,
    fetch_all_asset_people,
)


logger = logging.getLogger(__name__)


def fetch_and_save_immich_data() -> None:
    async def _run() -> None:
        async with AsyncClient(
                api_key=settings.immich_api_key,
                base_url=settings.immich_host
        ) as client:
            logger.info("Fetching Immich data")
            try:
                people = await get_all_people(client)

                await fetch_all_asset_people(
                    client=client,
                    cache_file=pathlib.Path(settings.data_cache_dir)
                        / "asset-people.json",
                )
                await get_person_date_ranges(
                    client=client,
                    people=people,
                    cache_file=pathlib.Path(settings.data_cache_dir)
                        / "person-date-ranges.csv",
                    skip_unnamed=True,
                )
                await get_all_photo_dates(
                    client=client,
                    people=people,
                    cache_file=pathlib.Path(settings.data_cache_dir)
                        / "person-photo-dates.csv",
                    skip_unnamed=True,
                )
            except Exception as e:
                logger.exception(f"Failed fetching Immich data: {e}")
                raise e

    asyncio.run(_run())



