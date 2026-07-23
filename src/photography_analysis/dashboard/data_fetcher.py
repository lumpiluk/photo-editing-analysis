import asyncio
import logging

from immichpy import AsyncClient
import pandas as pd

from photography_analysis.dashboard.config import settings
from photography_analysis.immich_data import (
    get_all_people,
    get_all_photo_dates,
    get_person_date_ranges,
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

                person_date_ranges = await get_person_date_ranges(
                    client=client,
                    people=people,
                    skip_unnamed=True,
                )
                df_ranges = pd.DataFrame(
                    person_date_ranges,
                    columns=["name", "id", "first", "last", "num_assets"],
                )
                df_ranges.to_csv(
                    f"{settings.data_cache_dir}/person-date-ranges.csv",
                    index=False,
                )

                photo_dates = await get_all_photo_dates(
                    client=client,
                    people=people,
                    skip_unnamed=True,
                )
                df_photos = pd.DataFrame(photo_dates, columns=["person_id", "name", "date"])
                df_photos.to_csv(
                    f"{settings.data_cache_dir}/person-photo-dates.csv",
                    index=False,
                )
            except Exception as e:
                logger.exception(f"Failed fetching Immich data: {e}")
                raise e

    asyncio.run(_run())
