import re
import asyncio

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import pytz
import aiohttp
import lxml.html
from typing import List

from inscriptis.css_profiles import CSS_PROFILES
from inscriptis.html_properties import Display
from inscriptis.model.html_element import HtmlElement

from ..ocr import pdf2txt
from ..data import Entry, Request, Document, make_doc, Section, make_section, Response
from ..helpers import log, warning
from ..scraper import Scraper
from ..custom_inscriptis import CustomInscriptis, CustomParserConfig

BASE_URL = "https://www.legislation.vic.gov.au"

class VicLegislation(Scraper):
    """A scraper for the VIC Legislation database."""
    
    def __init__(self,
                 indices_refresh_interval: bool | timedelta = None,
                 index_refresh_interval: bool | timedelta = None,
                 semaphore: asyncio.Semaphore = None,
                 session: aiohttp.ClientSession = None,
                 thread_pool_executor: ThreadPoolExecutor = None,
                 ocr_semaphore: asyncio.Semaphore = None,
                 ) -> None:
        super().__init__(
            source='vic_legislation',
            indices_refresh_interval=indices_refresh_interval,
            index_refresh_interval=index_refresh_interval,
            semaphore=semaphore,
            session=session,
            thread_pool_executor=thread_pool_executor,
            ocr_semaphore=ocr_semaphore,
        )

        self._jurisdiction = 'victoria'
        
        # Create a custom Inscriptis CSS profile.
        inscriptis_profile = CSS_PROFILES['strict'].copy()
        
        # Ensure that blockquotes are indented.
        inscriptis_profile['blockquote'] = HtmlElement(display=Display.block, padding_inline=4)
        
        # Create an Inscriptis parser config using the custom CSS profile.
        self._inscriptis_config = CustomParserConfig(inscriptis_profile)

    @log
    async def get_index_reqs(self) -> set[Request]:
        # Get the current date in NSW.
        pit = datetime.now(tz=pytz.timezone("Australia/VIC")).strftime(r"%d/%m/%Y")
        
        return {
            Request(f'{BASE_URL}/in-force/{instrument}?page={0}')
            for instrument in ('acts', 'statutory-rules')
        }

    @log
    async def get_index(self, req: Request) -> set[Entry]:        
        # Determine the document type of the index.
        type = 'primary_legislation' if 'acts' in req.path else 'secondary_legislation'


        
        # Retrieve the index.
        resp = (await self.get(req)).text
        
        # Extract document paths and titles from the index.
        paths_and_titles = re.findall(r'<a(?: class="indent")? href="/view/(?:html|pdf)/([^"]+)">((?:.|\n)*?)</a>', resp)
        
        # Create entries from the paths and titles.
        entries = await asyncio.gather(*[self._get_entry(path, title, type) for path, title in paths_and_titles])
        
        # Filter out entries that are `None`.
        # NOTE It is possible for some documents to simply be missing which is why we filter out `s` rather than raising an exception.
        entries = {entry for entry in entries if entry}
        
        return entries
    
    @log
    async def _get_entry(self, path: str, title: str, type: str) -> Entry | None:
        date = None
        
        # If the document's path begins with 'asmade/' then we already have its version id.
        if path.startswith('asmade/'):
            version_id = path
        
        # Otherwise, we must retrieve the document's status page to determine its latest version id.
        else:
            # Extract the document id from the path.
            doc_id = path.split('/')[-1]

            # Retrieve the document's status page.
            resp = await self.get(f"https://legislation.nsw.gov.au/view/html/inforce/current/{doc_id}")

            # If error 404 is encountered, return `None`.
            # NOTE It is possible for some documents to simply be missing which is why we return `None` rather than raising an exception.
            if resp.status == 404:
                warning(f'Unable to retrieve document from https://legislation.nsw.gov.au/view/html/inforce/current/{doc_id}. Error 404 (Not Found) encountered. Returning `None`.')
                
                return
        
            match resp.type:
                case 'text/html':
                    # Extract the point in time of the latest version of the document.
                    pit = re.search(r'<a\s+href="/search\?pointInTime=(\d{4}-\d{2}-\d{2})&', resp.text).group(1)
                    date = pit
                
                # If a PDF version of the document is returned, then we must use the current point in time.
                case 'application/pdf':
                    pit = datetime.now(tz=pytz.timezone("Australia/VIC")).strftime(r"%Y-%m-%d")
                
                case _:
                    raise ValueError(f"Unable to retrieve entry from https://legislation.nsw.gov.au/view/html/inforce/current/{doc_id}. Invalid content type: {resp.type}.")

            # Create the version id by appending the document id to the point in time.
            version_id = f'{pit}/{doc_id}'
        
        # Create the entry.
        return Entry(
            request=Request(f'https://legislation.nsw.gov.au/view/whole/html/inforce/{version_id}'),
            version_id=version_id,
            source=self.source,
            type=type,
            jurisdiction=self._jurisdiction,
            date=date,
            title=title,
        )

    @log
    async def _get_doc(self, entry: Entry) -> Document | None:
        # Retrieve the document.
        resp: Response = await self.get(entry.request)
        
        # If error 404 is encountered, return `None`.
        # NOTE It is possible for some documents to simply be missing which is why we return `None` rather than raising an exception.
        if resp.status == 404:
            warning(f'Unable to retrieve document from {entry.request.path}. Error 404 (Not Found) encountered, indicating that the document is missing from the NSW Legislation database. Returning `None`.')
            
            return
        
        match resp.type:
            case 'text/html':
                # If the response contains the substring 'No fragments found.', then return `None` as there is a bug in the NSW Legislation database preventing the retrieval of certain documents (see, eg, https://legislation.nsw.gov.au/view/whole/html/inforce/2021-03-25/act-1944-031).
                if 'No fragments found.' in resp.text:
                    warning(f"Unable to retrieve document from {entry.request.path}. 'No fragments found.' encountered in the response, indicating that the document is missing from the NSW Legislation database. Returning `None`.")
                    return
                
                # Create an etree from the response.
                etree = lxml.html.fromstring(resp.text)
                
                # Select the element containing the text of the document.
                text_elm = etree.xpath('//div[@id="frag-col"]')[0]
                
                # Remove the toolbar.
                text_elm.xpath('//div[@id="fragToolbar"]')[0].drop_tree()
                
                # Remove the search results (they are supposed to be hidden by Javascript).
                text_elm.xpath('//div[@class="nav-result display-none"]')[0].drop_tree()

                # Remove footnotes (they are supposed to be hidden by Javascript).
                for elm in text_elm.xpath("//*[contains(concat(' ', normalize-space(@class), ' '), ' view-history-note ')]"): elm.drop_tree()

                # Extract the text of the document.
                text = CustomInscriptis(text_elm, self._inscriptis_config).get_text()
            
            case 'application/pdf':
                # Extract the text of the document from the PDF with OCR.
                text = await pdf2txt(resp.stream, self.ocr_batch_size, self.thread_pool_executor, self.ocr_semaphore)
            
            case _:
                raise ValueError(f'Unable to retrieve document from {entry.request.path}. Invalid content type: {resp.type}.')
        
        # Return the document.
        return make_doc(
            version_id=entry.version_id,
            type=entry.type,
            jurisdiction=entry.jurisdiction,
            source=entry.source,
            mime=resp.type,
            date=entry.date,
            citation=entry.title,
            url=entry.request.path,
            text=text
        )