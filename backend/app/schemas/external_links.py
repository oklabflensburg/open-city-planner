from pydantic import BaseModel


class WikidataExternalLink(BaseModel):
    id: str
    url: str


class WikipediaExternalLink(BaseModel):
    title: str
    url: str


class ExternalLinks(BaseModel):
    wikidata: WikidataExternalLink | None = None
    wikipedia: WikipediaExternalLink | None = None
