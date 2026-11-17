"""Translate domain read models into the versioned HTTP response contract."""

from app.domain.analyses.models import AnalysisDetail, AnalysisPage
from app.presentation.dto import AnalysisDetail as AnalysisDetailDTO
from app.presentation.dto import AnalysisPage as AnalysisPageDTO


def detail_to_dto(result: AnalysisDetail) -> AnalysisDetailDTO:
    return AnalysisDetailDTO.model_validate(result.model_dump())


def page_to_dto(result: AnalysisPage) -> AnalysisPageDTO:
    return AnalysisPageDTO.model_validate(result.model_dump())
