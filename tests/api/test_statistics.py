from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import status

from app.models.usage import SummaryUsage


def test_get_summary_empty(client, test_db):
    """統計サマリー取得 - データなし"""
    response = client.get("/api/statistics/summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_count"] == 0
    assert data["total_input_tokens"] == 0
    assert data["total_output_tokens"] == 0
    assert data["average_processing_time"] == 0


def test_get_summary_with_data(client, sample_usage_records):
    """統計サマリー取得 - データあり"""
    response = client.get("/api/statistics/summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_count"] == 2
    assert data["total_input_tokens"] == 3000
    assert data["total_output_tokens"] == 1300
    assert 2.0 < data["average_processing_time"] < 3.5


def test_get_summary_filtered_by_model(client, sample_usage_records):
    """統計サマリー取得 - モデルフィルター"""
    response = client.get("/api/statistics/summary?model=Claude")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_count"] == 1
    assert data["total_input_tokens"] == 1000
    assert data["total_output_tokens"] == 500


def test_get_summary_filtered_by_date(client, sample_usage_records):
    """統計サマリー取得 - 日付フィルター"""
    start_date = datetime.now().isoformat()
    response = client.get(f"/api/statistics/summary?start_date={start_date}")
    assert response.status_code == status.HTTP_200_OK


def test_get_aggregated_csv_empty(client, test_db):
    """集計統計CSV出力 - データなしはヘッダー行のみ"""
    response = client.get("/api/statistics/aggregated/csv")
    assert response.status_code == status.HTTP_200_OK
    assert response.content.decode("utf-8-sig").splitlines() == [
        "文書名,診療科,医師名,作成件数,入力トークン,出力トークン"
    ]


def test_get_aggregated_csv_with_data(client, sample_usage_records):
    """集計統計CSV出力 - BOM付きUTF-8の添付ファイルとして返る"""
    response = client.get("/api/statistics/aggregated/csv")
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="aggregated_statistics_')
    assert disposition.endswith('.csv"')
    assert response.content.startswith(b"\xef\xbb\xbf")

    lines = response.content.decode("utf-8-sig").splitlines()
    assert len(lines) == 3
    assert "他院への紹介,眼科,橋本義弘,1,1000,500" in lines
    assert "返書,全科共通,医師共通,1,2000,800" in lines


def test_get_aggregated_csv_filtered_by_model(client, sample_usage_records):
    """集計統計CSV出力 - モデルフィルター"""
    response = client.get("/api/statistics/aggregated/csv?model=Claude")
    assert response.status_code == status.HTTP_200_OK
    lines = response.content.decode("utf-8-sig").splitlines()
    assert lines[1:] == ["他院への紹介,眼科,橋本義弘,1,1000,500"]


def test_get_records_empty(client, test_db):
    """使用統計レコード取得 - データなし"""
    response = client.get("/api/statistics/records")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_get_records_with_data(client, sample_usage_records):
    """使用統計レコード取得 - データあり"""
    response = client.get("/api/statistics/records")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2
    assert data[0]["department"] in ["眼科", "default"]


def test_get_records_with_pagination(client, sample_usage_records):
    """使用統計レコード取得 - ページネーション"""
    response = client.get("/api/statistics/records?limit=1&offset=0")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1

    response = client.get("/api/statistics/records?limit=1&offset=1")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1


def test_get_records_respects_limit(client, sample_usage_records):
    """使用統計レコード取得 - limit制限"""
    response = client.get("/api/statistics/records?limit=10")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) <= 10


USAGE_HISTORY_CSV_HEADER = (
    "作成日,文書名,診療科,医師名,AIモデル,入力トークン,出力トークン,作成時間(秒)"
)


def test_get_records_csv_empty(client, test_db):
    """使用履歴CSV出力 - データなしはヘッダー行のみ"""
    response = client.get("/api/statistics/records/csv")
    assert response.status_code == status.HTTP_200_OK
    assert response.content.decode("utf-8-sig").splitlines() == [
        USAGE_HISTORY_CSV_HEADER
    ]


def test_get_records_csv_with_data(client, sample_usage_records):
    """使用履歴CSV出力 - BOM付きUTF-8の添付ファイルとして返る"""
    response = client.get("/api/statistics/records/csv")
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="usage_history_')
    assert disposition.endswith('.csv"')
    assert response.content.startswith(b"\xef\xbb\xbf")

    lines = response.content.decode("utf-8-sig").splitlines()
    assert lines[0] == USAGE_HISTORY_CSV_HEADER
    # 作成日は実行時刻で変わるため、2列目以降を比較する
    rows = sorted(line.split(",", 1)[1] for line in lines[1:])
    assert rows == [
        "他院への紹介,眼科,橋本義弘,Claude,1000,500,3",
        "返書,全科共通,医師共通,Gemini,2000,800,3",
    ]


def test_get_records_csv_filtered_by_model(client, sample_usage_records):
    """使用履歴CSV出力 - モデルフィルター"""
    response = client.get("/api/statistics/records/csv?model=Claude")
    assert response.status_code == status.HTTP_200_OK
    lines = response.content.decode("utf-8-sig").splitlines()
    assert len(lines) == 2
    assert lines[1].endswith("他院への紹介,眼科,橋本義弘,Claude,1000,500,3")


def test_get_records_csv_outputs_all_records(client, test_db):
    """使用履歴CSV出力 - 一覧APIの上限 (500件) を超えても全件出力される"""
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    test_db.add_all(
        SummaryUsage(date=now, document_type="返書", model="Claude")
        for _ in range(501)
    )
    test_db.commit()

    response = client.get("/api/statistics/records/csv")
    assert response.status_code == status.HTTP_200_OK
    assert len(response.content.decode("utf-8-sig").splitlines()) == 502
