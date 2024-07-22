import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel
from pydantic import Field
from pydantic import AnyUrl
from pydantic import validator
from pydantic import AnyHttpUrl
from dateutil import parser


class ChunkType(str, Enum):
    ORIGINAL = "ORIGINAL"
    SUMMARY = "SUMMARY"

class Instrument(Enum):
    Legislation = "legislation"
    Regulation = "regulation"
    EnvironmentalPlanningInstrument = "epi"
    Constiution = "constitution"
    CaseLaw = "caselaw"
    Standard = "standard"


# ////////////////////////////////////////////
# // NEW DATA MODEL //////////////////////////
# ////////////////////////////////////////////

class Document(BaseModel):
    id: str
    jurisdiction_id: str
    court_id: Optional[str] = None

    instrument: Instrument
    instrument_subtype: Optional[str] = None

    title: str
    summary: Optional[str]
    headnotes: Optional[str]
    history: Optional[str]
    disposition: Optional[str]

    source_url: AnyUrl
    html_url: Optional[AnyUrl]
    pdf_url: Optional[AnyUrl]
    xml_url: Optional[AnyUrl]
    docx_url: Optional[AnyUrl]
    rtf_url: Optional[AnyUrl]
    pdf_path: Optional[str]

    citation: Optional[str]
    number: Optional[str]
    year: Optional[int]

    effective_date: Optional[datetime.date]
    date_scraped: datetime.datetime
    other: Optional[dict] = None

    @validator("effective_date", "date_scraped", pre=True)
    def parse_datetime(cls, v):
        if isinstance(v, str):
            try:
                v = parser.parse(v)
            except (ValueError, TypeError):
                pass
        return v

class DocumentSection(BaseModel):
    id: str
    document_id: str

    text: str
    
    title: Optional[str] = None
    citation: Optional[str] = None
    number: Optional[str] = None

    source_url: AnyUrl
    html_url: Optional[AnyUrl] = None

    other: Optional[dict] = None

class DocumentOpinion(BaseModel):
    id: str
    document_id: str

    type: str
    text: str # some opinions are empty and you need to go to the download_url
    author: Optional[str] = None
    per_curiam: bool
    download_url: Optional[str] = None
    ocr: bool
    other: dict

class DocumentMetadata(BaseModel):
    document_id: str
    document_title: Optional[str] = None  # will change when fixed legacy
    document_citation: Optional[str] = None
    document_source_url: Optional[str] = None
    document_pdf_url: Optional[str] = None

    section_id: Optional[str] = None
    section_title: Optional[str] = None
    section_citation: Optional[str] = None
    section_source_url: Optional[str] = None

    opinion_id: Optional[str] = None
    opinion_author: Optional[str] = None
    opinion_type: Optional[str] = None

    court: Optional[str] = None

    instrument: Instrument
    instrument_subtype: Optional[str] = None

    jurisdiction_id: str
    jurisdiction: str
    country: str
    province: Optional[str]

    other: Optional[dict] = None
    created_at: Optional[datetime.datetime] = None

    class Config:
        use_enum_values = True

class DocumentText(BaseModel):
    id: str
    text: str
    metadata: DocumentMetadata
