from sqlalchemy import MetaData

from .models import AnalysisArea

METADATA = MetaData()
AnalysisArea.__table__.to_metadata(METADATA)

__all__ = ["METADATA", "AnalysisArea"]
