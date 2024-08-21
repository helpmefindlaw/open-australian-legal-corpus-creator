import pytest
from src.oalc_creator.scrapers.queensland_caselaw import QueenslandCaselaw

@pytest.mark.asyncio()
async def test_scrape_get_index_req():
    scraper = QueenslandCaselaw()
    request = await scraper.get_index_reqs()
    assert isinstance(request, set)

