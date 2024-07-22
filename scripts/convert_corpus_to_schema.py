import json
import dateparser
import pandas as pd
from uuid import uuid4
from pathlib import Path
import shutil
from schema import Instrument, Document, DocumentText, DocumentMetadata

def type_to_instrument(x):
    if x == 'primary_legislation':
        return Instrument.Legislation
    if x == 'secondary_legislation':
        return Instrument.Regulation
    if x == 'decision':
        return Instrument.CaseLaw

def jurisdiction_normalise(x):
    return {
        "south_australia": "J0105",
        "western_australia": "J0105",
        "tasmania": "J0106",
        "new_south_wales": "J0103",
        "commonwealth": "J0100",
        "queensland": "J0102",
        "victoria": "J0101",
        "norfolk_island": "J0109"
    }[x]

def federal_court_mappings(x):
    mapping = {
        "federal_court_of_australia:fca/single": 'C0100001',
        "federal_court_of_australia:fca/full": "C0100001",
        "federal_court_of_australia:irc": "C0100002",
        'federal_court_of_australia:tribunals/acompt': "C0100003",
        "federal_court_of_australia:nfsc": "C0109001",
        "federal_court_of_australia:tribunals/acopyt": "C0100004",
        "federal_court_of_australia:tribunals/fpdt": "C0100005",
        "federal_court_of_australia:tribunals/atpt": "C0100006",
        "federal_court_of_australia:tribunals/adfdat": "C0100007"
    }
    for key in mapping.keys():
        if key in x:
            return mapping[key]
    print(x)
    raise ValueError


courts = pd.read_csv("./data/courts.csv").set_index("id")
jurisdiction = pd.read_csv("./data/jurisdiction.csv").set_index("id")

def get_court_given_id(id):
    if id:
        return courts.loc[id, "full_name"]
    return None

def get_jurisdiction_given_id(id):
    return jurisdiction.loc[id, ["name", "country", "province"]].to_dict()

def process(row):
    court_id = None
    if row["type"] == 'decision':
        if row["source"] == "federal_court_of_australia":
            court_id = federal_court_mappings(row["version_id"])
        if row["source"] == "high_court_of_australia":
            court_id = "C0100008"
    date = dateparser.parse(row["date"]) if row["date"] else None
    data = dict(
        id=row['version_id'],
        jurisdiction_id=jurisdiction_normalise(row["jurisdiction"]),
        court_id=court_id,
        instrument=type_to_instrument(row["type"]),
        instrument_subtype=None,
        title=row["citation"],
        headnotes=None,
        history=None,
        summary=None,
        disposition=None,
        number=None,
        source_url=row["url"],
        pdf_url=row["url"] if row["mime"] == "application/pdf" else None,
        html_url=row["url"] if row["mime"] == "text/html" else None,
        xml_url=None,
        rtf_url=row["url"] if row["mime"] == "application/rtf" else None,
        docx_url=row["url"] if row["mime"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" else None,
        pdf_path=None,
        citation=row["citation"],
        year=date.year if date else None,
        effective_date=date,
        date_scraped=row["when_scraped"]
    )
    doc = Document(**data)
    jurisdiction = get_jurisdiction_given_id(doc.jurisdiction_id)
    metadata = DocumentMetadata(
        document_id=doc.id,
        document_title=doc.title,
        document_citation=doc.citation,
        document_source_url=str(doc.source_url),
        document_pdf_url=str(doc.pdf_url),
        section_id=None,
        section_title=None,
        section_citation=None,
        opinion_id=None,
        opinion_author=None,
        opinion_type=None,
        court=get_court_given_id(doc.court_id),
        instrument=doc.instrument,
        instrument_subtype=doc.instrument_subtype,
        jurisdiction_id=doc.jurisdiction_id,
        jurisdiction=jurisdiction["name"],
        country=jurisdiction["country"],
        province=None if pd.isna(jurisdiction["province"]) else jurisdiction["province"],
        other=None,
    )
    text = DocumentText(
        id=doc.id,
        text=row["text"],
        metadata=metadata
    )
    return doc, text

def write_batch(dir: Path, batch):
    with open(dir.joinpath(uuid4().hex + ".jsonl"), 'w') as f:
        for item in batch:
            f.write(item.json() + "\n")

def main():
    with open('./data/document_records.jsonl', 'w') as document_file:
        text_batch = []
        _dir = Path('./data/documents')
        if _dir.exists():
           shutil.rmtree(_dir)
        _dir.mkdir()

        with open('./data/corpus.jsonl', 'r') as f:
            for line in f.readlines():
                row = json.loads(line)
                if row['type'] in ['bill']:
                    continue
                doc, text = process(row)

                document_file.write(doc.json() + "\n")
                text_batch.append(text)
                if len(text_batch) == 10000:
                    write_batch(_dir, text_batch)
                    text_batch = []
    write_batch(_dir, text_batch)
    text_batch = []
            



if __name__ == "__main__":
    main()