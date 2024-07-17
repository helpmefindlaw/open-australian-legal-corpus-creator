import pytest
from src.oalc_creator.data import Entry, Request
from src.oalc_creator.scrapers.nsw_legislation import NswLegislation

@pytest.mark.asyncio()
async def test_scrape_sections():
    scraper = NswLegislation()
    entry = Entry(
       request=Request(
            path="https://legislation.nsw.gov.au/view/whole/html/inforce/2024-05-31/act-1994-045",
            method="get",
            encoding="utf-8"
        ),
        version_id="nsw_legislation:2024-05-31/act-1994-045",
        source="nsw_legislation",
        type="primary_legislation",
        jurisdiction="new_south_wales",
        date="2024-05-31",
        title="Native Title (New South Wales) Act 1994 No 45"
    )
    sections = await scraper.get_sections(entry)
    print(sections)
    assert sections == []

