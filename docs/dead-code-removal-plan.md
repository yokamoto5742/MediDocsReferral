# デッドコード削除計画

本アプリケーション（バックエンド `app/`、開発スクリプト `scripts/`、フロントエンド `frontend/src` + `app/templates`）を対象に、デッドコードを洗い出した結果と削除計画をまとめる。

## 調査方法

- `ruff` の未使用検出 (F401/F811/F841/F823) → 全件パス（モジュール内の未使用 import/変数は無し）
- `vulture`（信頼度60%）→ 候補抽出。ただしFastAPIルート・Pydanticフィールド・SQLAlchemyカラムは大量に誤検出されるため、全候補を手動で参照確認した
- テンプレートは `TemplateResponse` 呼び出し・`include`/`extends` を全件突合
- TypeScript は `export` シンボルの参照を全件突合

## 優先順位の基準

**「明確に未使用 かつ 削除が安全な順」** に並べる。

1. 参照ゼロ・単一ファイル完結・動作への結合なし（即削除可）
2. 設定値・テストと結合（影響範囲の確認が必要）
3. 開発専用スクリプト（本番非依存・pyright対象外）

---

## 優先度1: 即削除可（参照ゼロ・リスクなし）

| # | 対象 | 場所 | 根拠 |
|---|------|------|------|
| 1 | クラス `PromptUpdate` | `app/schemas/prompt.py:17-19` | `app`/`tests`/`templates`/`frontend` のどこからも import・参照されていない。完全に未使用 |
| 2 | 定数 `DEFAULT_DOCTOR = ["default"]` | `app/core/constants.py:11` | どこからも参照なし。grep でヒットするのは別物の `DEFAULT_DOCTOR_LABEL` のみ |
| 3 | テンプレート `fragments/statistics_records_tbody.html` | `app/templates/fragments/` | `TemplateResponse`・`include`・`extends` のいずれからもレンダリングされない。削除後 `fragments/` が空になれば併せて削除 |

これらは他コードへの影響がなく、削除によるテスト・動作変更は発生しない。

---

## 優先度2: 未使用の設定フィールド（要判断）

`Settings`（`app/core/config.py`）の以下フィールドはコード内で一度も参照されていない。`model_config` は `extra="ignore"` のため `.env` に値が残っていても無害だが、削除前に意図を確認する。Settingsは昔使っていたが、今は使っていないので削除してOK 。

| # | 対象 | 場所 | 備考 |
|---|------|------|------|
| 4 | `app_type: str = "default"` | `app/core/config.py:53` | 設定値自体は未使用。`usage` モデルの `app_type` カラムは別物で、`usage_service.py:73` が `"dischargesummary"` をハードコードしている。**カラム/スキーマは残す**こと |

| 5 | `selected_ai_model: str` | `app/core/config.py:54` | どこからも参照なし。モデル選択は各プロンプトの `selected_model` と `anthropic_model`/`gemini_model` 経由で行われている |

| 6 | `db_pool_recycle: int = 1800` | `app/core/config.py:29` | `database.py:16` がエンジンに `pool_recycle=3600` をハードコードしているため未使用。削除せずエンジンに配線する。

> 注: `db_max_overflow`（line 27）は `database.py:14` で使用されているため**削除しない**。

---

## 優先度3: 本番未使用だがテストと結合

| # | 対象 | 場所 | 根拠・手順 |
|---|------|------|-----------|
| 7 | 関数 `sanitize_prompt_text` | `app/utils/input_sanitizer.py:84-89` | `sanitize_medical_text` の薄いラッパー。本番コードからの呼び出しは無く、参照は自身のテストのみ。削除時は `tests/test_utils/test_input_sanitizer.py` の import（4行目）と `test_sanitize_prompt_text`（60行目）も併せて削除する |

---

## 誤検出 — 削除してはいけないもの

vulture が候補として挙げたが、実際にはフレームワーク経由で使用されている。**「未使用に見える」だけで削除すると動作が壊れる**ため明記する。

- **FastAPI ルートハンドラ** — `app/api/*.py` の各関数、`app/main.py` の `index` / `health_check` / 各ページ関数。デコレータでルート登録され、直接呼び出しは無い
- **Pydantic フィールド / `model_config`** — `app/schemas/*.py` の各フィールド（`evaluation_result`, `model_used`, `total_count`, `is_default` 等）と `model_config`。シリアライズで使用される
- **SQLAlchemy カラム** — `app/models/*.py` の `Column` 定義（`app_type` カラム含む）
- **`SecurityHeadersMiddleware.dispatch`** — `app/core/security.py:83`。Starlette のミドルウェア基底クラスがフレームワークから呼ぶ
- **`AppError`** — `app/utils/exceptions.py:1`。`APIError` の基底クラス。例外階層の拡張点であり、直接使用されないのは設計上正常。**残す**
- **TypeScript の `types.ts` 全 interface** — 11個すべて `app.ts` で import・使用済み

---

## 推奨実施順序

1. 優先度1（#1〜#3）を一括削除 → `pyright` と `python -m pytest tests/ -v --tb=short` で検証
2. 優先度3（#7）を削除（テストも併せて削除）→ pytest で検証
3. 優先度2（#4〜#6）はユーザーに意図を確認後に削除（特に #6 は「削除 / 配線」の判断）

各ステップ後に全テストがパスすることを確認する。
