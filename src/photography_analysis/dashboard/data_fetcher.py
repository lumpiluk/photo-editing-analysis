import asyncio
import json
import logging
import pathlib

from immichpy import AsyncClient
import pandas as pd

from photography_analysis.dashboard.config import settings
from photography_analysis.pseudonyms import pseudonym_for_id
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


def load_ranges(demo_mode: bool):
    path = pathlib.Path(settings.data_cache_dir) / "person-date-ranges.csv"
    df = pd.read_csv(path)
    df["last"] = pd.to_datetime(df["last"], format="ISO8601")
    if demo_mode:
        df["name"] = df["id"].apply(pseudonym_for_id)
    return df


def load_photos(demo_mode: bool):
    path = pathlib.Path(settings.data_cache_dir) / "person-photo-dates.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], format="ISO8601")  # .dt.normalize()? from events_detail.py
    if demo_mode:
        df["name"] = df["person_id"].apply(pseudonym_for_id)
    return df


def load_asset_people():
    path = pathlib.Path(settings.data_cache_dir) / "asset-people.json"
    with open(path, "r") as f:
        return json.load(f)


