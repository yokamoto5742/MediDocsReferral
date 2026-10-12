import csv
import io
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func
from sqlalchemy.orm import Query, Session

from app.core.constants import (
    AGGREGATED_CSV_COLUMNS,
    AGGREGATED_CSV_FILENAME,
    DEFAULT_STATISTICS_PERIOD_DAYS,
    MESSAGES,
    USAGE_HISTORY_CSV_COLUMNS,
    USAGE_HISTORY_CSV_DATE_FORMAT,
    USAGE_HISTORY_CSV_FILENAME,
)
from app.models.usage import SummaryUsage

JST = ZoneInfo("Asia/Tokyo")


def _apply_default_period(
    start_date: datetime | None,
    end_date: datetime | None,
) -> tuple[datetime, datetime]:
    """期間未指定時にデフォルト期間を適用"""
    now = datetime.now(JST)
    if end_date is None:
        end_date = now
    if start_date is None:
        start_date = now - timedelta(days=DEFAULT_STATISTICS_PERIOD_DAYS)
    return start_date, end_date


def _apply_filters[T](
    query: Query[T],
    start_date: datetime | None,
    end_date: datetime | None,
    model: str | None,
    document_type: str | None = None,
) -> Query[T]:
    """期間 (未指定時はデフォルト期間)・モデル・文書タイプの絞り込みをクエリに適用"""
    start_date, end_date = _apply_default_period(start_date, end_date)
    query = query.filter(SummaryUsage.date >= start_date, SummaryUsage.date <= end_date)
    if model:
        query = query.filter(SummaryUsage.model == model)
    if document_type:
        query = query.filter(SummaryUsage.document_type == document_type)
    return query


def _label(value: str | None, default_label: str) -> str:
    """共通設定 ("default") と未設定の値を表示用ラベルに置き換える"""
    return default_label if not value or value == "default" else value


def get_usage_summary(
    db: Session,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    model: str | None = None,
) -> dict:
    """使用統計サマリを取得"""
    query = db.query(
        func.count(SummaryUsage.id),
        func.sum(SummaryUsage.input_tokens),
        func.sum(SummaryUsage.output_tokens),
        func.avg(SummaryUsage.processing_time),
    )
    # 集計関数のみのクエリは、対象0件でも必ず1行返す (その場合 sum / avg は None)
    count, input_tokens, output_tokens, average_time = _apply_filters(
        query, start_date, end_date, model
    ).one()

    return {
        "total_count": count,
        "total_input_tokens": int(input_tokens or 0),
        "total_output_tokens": int(output_tokens or 0),
        "average_processing_time": round(float(average_time or 0), 2),
    }


def get_aggregated_records(
    db: Session,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    model: str | None = None,
    document_type: str | None = None,
) -> list[dict]:
    """文書別集計統計データを取得"""
    query = db.query(
        SummaryUsage.document_type,
        SummaryUsage.department,
        SummaryUsage.doctor,
        func.count(SummaryUsage.id).label("count"),
        func.sum(SummaryUsage.input_tokens).label("input_tokens"),
        func.sum(SummaryUsage.output_tokens).label("output_tokens"),
    )

    results = (
        _apply_filters(query, start_date, end_date, model, document_type)
        .group_by(
            SummaryUsage.document_type, SummaryUsage.department, SummaryUsage.doctor
        )
        .order_by(desc("count"))
        .all()
    )

    return [
        {
            "document_type": r.document_type or "-",
            "department": _label(r.department, MESSAGES["INFO"]["DEFAULT_DEPARTMENT_LABEL"]),
            "doctor": _label(r.doctor, MESSAGES["INFO"]["DEFAULT_DOCTOR_LABEL"]),
            "count": r.count,
            "input_tokens": r.input_tokens or 0,
            "output_tokens": r.output_tokens or 0,
        }
        for r in results
    ]


def _build_csv(columns: dict[str, str], rows: list[dict]) -> str:
    """行データを列定義 (キー → ヘッダー名) の順でヘッダー行付きのCSV文字列に変換"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns.values())
    for row in rows:
        writer.writerow(row[key] for key in columns)
    return buffer.getvalue()


def _csv_filename(filename_template: str) -> str:
    """出力日 (JST) を埋め込んだCSVのファイル名を返す"""
    return filename_template.format(date=datetime.now(JST).strftime("%Y%m%d"))


def build_aggregated_csv(records: list[dict]) -> str:
    """集計統計データをヘッダー行付きのCSV文字列に変換"""
    return _build_csv(AGGREGATED_CSV_COLUMNS, records)


def get_aggregated_csv_filename() -> str:
    """出力日 (JST) を含む集計統計CSVのファイル名を返す"""
    return _csv_filename(AGGREGATED_CSV_FILENAME)


def _usage_history_row(record: SummaryUsage) -> dict:
    """使用履歴レコードを画面表示と同じ値のCSV行に変換"""
    return {
        "date": (
            record.date.astimezone(JST).strftime(USAGE_HISTORY_CSV_DATE_FORMAT)
            if record.date
            else "-"
        ),
        "document_type": record.document_type or "-",
        "department": _label(
            record.department, MESSAGES["INFO"]["DEFAULT_DEPARTMENT_LABEL"]
        ),
        "doctor": _label(record.doctor, MESSAGES["INFO"]["DEFAULT_DOCTOR_LABEL"]),
        "model": record.model or "-",
        "input_tokens": record.input_tokens or 0,
        "output_tokens": record.output_tokens or 0,
        # round() は偶数丸めのため、画面 (toFixed(0)) と同じ四捨五入にする
        "processing_time": int((record.processing_time or 0) + 0.5),
    }


def build_usage_history_csv(records: list[SummaryUsage]) -> str:
    """使用履歴データをヘッダー行付きのCSV文字列に変換"""
    return _build_csv(
        USAGE_HISTORY_CSV_COLUMNS, [_usage_history_row(record) for record in records]
    )


def get_usage_history_csv_filename() -> str:
    """出力日 (JST) を含む使用履歴CSVのファイル名を返す"""
    return _csv_filename(USAGE_HISTORY_CSV_FILENAME)


def get_usage_records(
    db: Session,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    model: str | None = None,
    document_type: str | None = None,
    limit: int | None = 100,
    offset: int = 0,
) -> list[SummaryUsage]:
    """使用統計レコードを取得 (limit=None で全件)"""
    query = _apply_filters(
        db.query(SummaryUsage), start_date, end_date, model, document_type
    )
    return query.order_by(SummaryUsage.date.desc()).offset(offset).limit(limit).all()
