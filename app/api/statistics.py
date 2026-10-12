from datetime import datetime
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.statistics import UsageSummary, UsageRecord, AggregatedRecord
from app.services import statistics_service

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("/summary", response_model=UsageSummary)
def get_summary(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    model: str | None = None,
    db: Session = Depends(get_db),
):
    """使用統計サマリを取得"""
    return statistics_service.get_usage_summary(db, start_date, end_date, model)


@router.get("/aggregated", response_model=list[AggregatedRecord])
def get_aggregated(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    model: str | None = None,
    document_type: str | None = None,
    db: Session = Depends(get_db),
):
    """集計統計データを取得"""
    return statistics_service.get_aggregated_records(
        db, start_date, end_date, model, document_type
    )


@router.get("/aggregated/csv")
def get_aggregated_csv(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    model: str | None = None,
    document_type: str | None = None,
    db: Session = Depends(get_db),
) -> Response:
    """集計統計データをCSVファイルとして出力"""
    records = statistics_service.get_aggregated_records(
        db, start_date, end_date, model, document_type
    )
    filename = statistics_service.get_aggregated_csv_filename()
    # Excel で文字化けしないよう BOM 付き UTF-8 で返す
    return Response(
        content=statistics_service.build_aggregated_csv(records).encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/records", response_model=list[UsageRecord])
def get_records(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    model: str | None = None,
    document_type: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """使用統計レコードを取得"""
    return statistics_service.get_usage_records(
        db, start_date, end_date, model, document_type, limit, offset
    )
