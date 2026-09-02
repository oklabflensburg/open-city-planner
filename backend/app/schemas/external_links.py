from pydantic import BaseModel


class WikipediaExternalLink(BaseModel):
    title: str
    url: str


class ExternalLinks(BaseModel):
    wikipedia: WikipediaExternalLink | None = None
