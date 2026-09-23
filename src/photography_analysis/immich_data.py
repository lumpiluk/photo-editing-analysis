import datetime
import json
import logging
import os
import pathlib

from dotenv import load_dotenv
from immichpy import AsyncClient
from immichpy.client.generated.models.metadata_search_dto import (
    MetadataSearchDto,
)
import pandas as pd

logger = logging.getLogger(__name__)


async def get_all_people(client, size: int = 1000, with_hidden: bool = False):
    all_people = []
    page = 1

    while True:
        response = await client.people.get_all_people(
            page=page,
            size=size,
            with_hidden=with_hidden,
        )
        all_people.extend(response.people)

        if not response.has_next_page:
            break
        page += 1

    return all_people


async def get_person_date_ranges(
        client,
        people,
        cache_file: pathlib.Path | None = None,
        skip_unnamed=True,
):
    records = []

    for person in people:
        if skip_unnamed and person.name == "":
            continue
        first_page = await client.search.search_assets(
            MetadataSearchDto(
                person_ids=[person.id],
                order="asc",
                size=1,
                page=1,
            )
        )
        last_page = await client.search.search_assets(
            MetadataSearchDto(
                person_ids=[person.id],
                order="desc",
                size=1,
                page=1,
            )
        )
        stats = await client.people.get_person_statistics(
            id=person.id,
        )

        first_items = first_page.assets.items
        last_items = last_page.assets.items

        records.append({
            "name": person.name or None,
            "id": str(person.id),
            "first": first_items[0].local_date_time if first_items else None,
            "last": last_items[0].local_date_time if last_items else None,
            "num_assets": stats.assets,
        })

    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        df_ranges = pd.DataFrame(
            records,
            columns=["name", "id", "first", "last", "num_assets"],
        )
        df_ranges.to_csv(cache_file, index=False)

    return records


async def get_person_photo_dates(client, person_id, size: int = 1000) -> list[datetime.datetime]:
    """Return every photo date (local_date_time) for a given person."""
    dates = []
    page = 1

    while page is not None:
        response = await client.search.search_assets(
            MetadataSearchDto(
                person_ids=[person_id],
                order="asc",
                size=size,
                page=int(page),
            )
        )
        dates.extend(item.local_date_time for item in response.assets.items)

        next_page = response.assets.next_page
        page = int(next_page) if next_page else None

    return dates


async def get_all_photo_dates(
        client,
        people,
        cache_file: pathlib.Path | None = None,
        skip_unnamed=True,
):
    """Return one row per photo: person_id, name, date."""
    records = []

    for person in people:
        if skip_unnamed and person.name == "":
            continue

        dates = await get_person_photo_dates(client, person.id)
        for d in dates:
            records.append({
                "person_id": str(person.id),
                "name": person.name or None,
                "date": d,
            })

    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        df_photos = pd.DataFrame(records, columns=["person_id", "name", "date"])
        df_photos.to_csv(cache_file, index=False)

    return records


async def fetch_all_asset_people(
        client,
        cache_file: pathlib.Path | None = None,
        size=1000,
):
    records = []
    page = 1
    while page is not None:
        response = await client.search.search_assets(
            MetadataSearchDto(
                order="asc",
                size=size,
                page=int(page),
                with_people=True,
            )
        )
        num_assets_with_people = 0
        for asset in response.assets.items:
            if asset.people:
                num_assets_with_people += 1
                records.append([str(p.id) for p in asset.people])
        logger.info(f"Page {page}: {num_assets_with_people} / {len(response.assets.items)} assets have people")

        next_page = response.assets.next_page
        page = int(next_page) if next_page else None

    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Writing cache to {cache_file}")
        with open(cache_file, "w") as f:
            json.dump(records, f)

    return records


async def main():
    # Read variables from .env and set them in os.environ:
    load_dotenv()

    async with AsyncClient(
            api_key=os.environ["IMMICH_API_KEY"],
            base_url=os.environ["IMMICH_HOST"],
    ) as client:
        people = await get_all_people(client)

        person_date_ranges = await get_person_date_ranges(client, people, skip_unnamed=True)
        df_ranges = pd.DataFrame(
            person_date_ranges,
            columns=["name", "id", "first", "last", "num_assets"],
        )
        df_ranges.to_csv("person-date-ranges.csv", index=False)

        photo_dates = await get_all_photo_dates(client, people, skip_unnamed=True)
        df_photos = pd.DataFrame(photo_dates, columns=["person_id", "name", "date"])
        df_photos.to_csv("person-photo-dates.csv", index=False)

