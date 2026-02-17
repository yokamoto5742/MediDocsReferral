# 変更履歴

診療情報提供書作成アプリのすべての重要な変更は、このファイルに記録されます。

このフォーマットは [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) に基づいており、
このプロジェクトは [Semantic Versioning](https://semver.org/spec/v2.0.0.html) に準拠しています。

## [Unreleased]

## [1.5.1] - 2026-02-14

### 追加
- **選択モデル取得API**: 現在選択されているAIモデルを取得するエンドポイント
  - `app/api/settings.py`: `/api/settings/models/selected`エンドポイントを追加
  - 選択されたモデル情報をJSON形式で返却
  - `tests/api/test_settings.py`: エンドポイント動作検証テストを追加

### 変更
- **例外ハンドラーのリファクタリング**: 汎用的な例外処理に統一
  - `app/utils/error_handlers.py`: エラーハンドリングロジックを簡潔化
  - `app/utils/exceptions.py`: 未使用の`DatabaseError`を削除
  - `tests/test_utils/test_input_sanitizer.py`: テストを修正

## [1.5.0] - 2026-02-12

### セキュリティ
- **プロンプトインジェクション対策**: 悪意のある入力パターンを検出・ブロック
  - `app/utils/input_sanitizer.py`: 多層防御アプローチによる検出機能
  - 疑わしいパターン（システムプロンプト上書き、命令注入等）を検出
  - 検出時は即座にエラーレスポンスを返却
  - `tests/test_utils/test_input_sanitizer.py`: 包括的なテストケース
- **CORS設定**: クロスオリジンリクエストの制御を強化
  - 環境変数による許可オリジンの設定（`CORS_ORIGINS`）
  - 資格情報付きリクエストの制御（`CORS_ALLOW_CREDENTIALS`）
  - `tests/core/test_cors.py`: CORS設定の検証テスト
- **監査ログ機能**: セキュリティイベントの記録
  - `app/utils/audit_logger.py`: JSON形式でのログ出力
  - プロンプトインジェクション検出、認証失敗等のイベントを記録
- **CSP設定の改善**: Content Security Policyに`unsafe-eval`を追加
  - Alpine.jsの動的評価機能に対応

### 変更
- **CSRF設定**: シークレットキーにデフォルト値を追加
  - 開発環境での初期セットアップを簡素化
  - 本番環境では必ず環境変数で上書きすることを推奨

### 修正
- **プロンプトインジェクション検出ロジック**: 不要な変数を削除
  - コードの可読性とメンテナンス性を向上

## [1.4.0] - 2026-02-09

### 追加
- **ログ機能**: アプリケーション動作をCSV形式で記録
  - `app/main.py`: ロギング設定を追加（INFO/ERROR/WARNING）
  - ログはコンソールに出力
- **SSEストリーミングAPI**: リアルタイム文書生成・評価
  - `app/api/summary.py`: `/generate/stream`エンドポイントを追加
  - `app/api/evaluation.py`: `/evaluate/stream`エンドポイントを追加
  - `app/services/sse_helpers.py`: SSEハートビート処理の共通ヘルパー関数
- **Cloudflare AI Gateway統合**: API呼び出しの最適化
  - `app/external/cloudflare_claude_api.py`: Cloudflare経由のClaude API
  - `app/external/cloudflare_gemini_api.py`: Cloudflare経由のGemini API
  - `app/core/config.py`: `use_cloudflare_gateway`, `cloudflare_account_id`, `cloudflare_gateway_id`設定を追加
  - `app/external/api_factory.py`: Cloudflare有効時のクライアント自動選択
- **評価プロンプト管理機能**:
  - `app/services/evaluation_prompt_service.py`: 評価プロンプトCRUDサービス
  - `app/api/evaluation.py`: `/prompts/*`評価プロンプト管理エンドポイント
  - 評価ロジックをプロンプト管理から分離し、モジュール性を向上
- **テストカバレッジ拡張**:
  - `tests/services/test_evaluation_prompt_service.py`: 評価プロンプトサービステスト
  - `tests/services/test_sse_helpers.py`: SSEヘルパー関数テスト
  - `tests/api/test_summary_stream.py`: SSEストリーミングAPIテスト

### 変更
- **環境変数名の変更**: Google Cloud設定の一貫性向上
  - `GOOGLE_CLOUD_LOCATION` → `GOOGLE_LOCATION`
  - `app/core/config.py`: `validation_alias`で後方互換性を維持
- **APIクライアント選択ロジック**: Cloudflare設定に基づく動的切り替え
  - `app/external/api_factory.py`: `APIFactory`クラスを`create_client`関数に変更
  - Cloudflare設定時は自動的にCloudflareクライアントを選択
  - ログ出力で使用するクライアントを明示
- **メッセージのローカライゼーション**: UI表示メッセージを日本語化
  - `app/core/constants.py`: エラーメッセージ、ステータスメッセージを日本語に統一
  - `frontend/src/app.ts`: エラーハンドリングでメッセージ定数を使用
  - `tests/*`: テストケースのエラーメッセージを日本語に修正

### リファクタリング
- **評価サービスの分離**:
  - `app/services/evaluation_service.py`: 評価実行ロジックのみに集中
  - `app/services/evaluation_prompt_service.py`: プロンプト管理ロジックを分離
  - SSEハートビート処理を`sse_helpers.py`に抽出
- **コードの整理とモジュール分割**:
  - `app/services/model_selector.py`: モデル選択ロジックを独立
  - 関数とクラスの責任を明確化
  - 定数とメッセージを`constants.py`に集約
- **ドキュメントコメントの簡潔化**:
  - `app/services/prompt_service.py`, `summary_service.py`, `external/*`: 冗長なコメントを削除
  - 自明な処理には最小限のコメントのみ
- **プロジェクト構造の更新**:
  - `scripts/project_structure.txt`: 新規サービスとAPIモジュールを反映

### 修正
- **フロントエンドエラー処理**: エラーメッセージのフォールバック改善
  - `frontend/src/app.ts`: APIエラーレスポンスの構造に対応
- **統計表示**: モデル名表示ロジックの簡略化
  - `app/api/statistics.py`: "Gemini_Pro" → "Gemini" 表示名マッピング
- **SSE処理の非同期対応**:
  - `app/api/evaluation.py`, `app/api/summary.py`: async/await構文の修正
  - CSRF対応ヘッダーの追加

### 技術的改善
- Vite: 7.3.1に更新
- pytest設定: `asyncio_default_fixture_loop_scope = "function"`を追加
- CSRF対策: SSEエンドポイントでトークン検証を適用

## [1.3.3] - 2026-01-31

### 変更
- **環境変数名の変更**: APIキー認証用の環境変数を`API_KEY`から`MEDIDOCS_API_KEY`に変更
  - `app/core/config.py`: フィールド名を`medidocs_api_key`に変更し、後方互換性のため`api_key`プロパティを追加
  - `app/core/security.py`: コメント内の環境変数名を更新
  - `tests/conftest.py`: テスト設定のコメントを更新
  - `tests/core/test_security.py`: テストのコメントを更新
  - `tests/api/test_api_authentication.py`: テストのコメントを更新
  - HTTPヘッダー名（`X-API-Key`）は変更なし

### 追加
- **APIキー認証機能**: `/api/*`配下のエンドポイントに`X-API-Key`ヘッダーによる認証を実装
  - `app/core/config.py`: `api_key`フィールドを追加
  - `app/core/security.py`: `verify_api_key`依存関数を実装
  - `app/api/router.py`: ルーターレベルで認証を適用
  - 環境変数`MEDIDOCS_API_KEY`でキーを設定
  - `MEDIDOCS_API_KEY`未設定時は認証をスキップ（開発モード）
  - `.env.example`: APIキー設定例を追加
  - `tests/core/test_security.py`: 認証関数のユニットテスト
  - `tests/api/test_api_authentication.py`: 統合テスト

### 修正
- **APIキー認証の適用範囲を最適化**: Web UI（ブラウザアクセス）と外部API呼び出しを区別
  - `app/api/router.py`: 管理用ルーター（認証不要）と公開APIルーター（認証必須）に分離
  - `app/api/summary.py`: `/models`エンドポイントを認証不要、`/generate`エンドポイントを認証必須に変更
  - `app/api/evaluation.py`: `/prompts/*`エンドポイントを認証不要、`/evaluate`エンドポイントを認証必須に変更
  - 管理機能（プロンプト管理、統計、設定）はWeb UIから認証なしでアクセス可能
  - 文書生成・評価APIは外部アクセス時にAPIキー認証が必要
  - `tests/api/test_api_authentication.py`: テストを更新し、管理APIと公開APIの認証動作を検証
- `app/templates/base.html`: Alpine.jsの`init()`メソッドが実行されるように`x-init="init()"`を追加し、医師名リストが正しく表示されるよう修正
- **APIキー設定時の医師名表示不具合を修正**: 設定エンドポイント（`/api/settings/*`）を認証対象外に変更
  - `app/api/router.py`: 認証が必要なルーターと不要なルーターを分離し、`settings.router`のみ認証をスキップ
  - `frontend/src/app.ts`: `updateDoctors()`にエラーハンドリングを追加し、APIエラー時の挙動を改善
  - `tests/api/test_api_authentication.py`: 認証テストを更新し、設定エンドポイントが認証不要であることを確認するテストを追加

## [1.3.2] - 2026-01-29

### リファクタリング
- **DRY原則の適用**: `app/services/summary_service.py`にエラーレスポンス生成ヘルパー関数`_error_response`を導入し、重複コードを削減
- **マジックストリング削除**: `app/core/constants.py`に`ModelType` Enumを追加し、"Claude"、"Gemini_Pro"などの文字列リテラルを統一
  - `app/services/summary_service.py`: `ModelType`と`APIProvider` Enumを使用
  - `app/schemas/summary.py`: デフォルト値を`ModelType.CLAUDE.value`に変更
  - `app/core/config.py`: `selected_ai_model`のデフォルト値を`ModelType.CLAUDE.value`に変更
  - `app/main.py`: `get_available_models`関数で`ModelType` Enumを使用
  - `app/api/summary.py`: `get_available_models`関数で`ModelType` Enumを使用
- **冗長コード削除**: `app/api/summary.py`の`generate_summary`エンドポイントで、`SummaryResponse`の冗長な再構築を削除
- **型ヒント追加**: `app/utils/text_processor.py`の`format_output_summary`と`parse_output_summary`関数に型ヒントを追加
- **ロジック集約**: モデル名取得ロジックを`app/services/prompt_service.py`の`get_selected_model`関数に集約
  - `app/services/summary_service.py`の`determine_model`関数で使用
  - `app/external/base_api.py`の`get_model_name`関数で使用
  - 重複していたデータベース呼び出しを統一

### 修正
- テストファイルの更新: リファクタリングに合わせてモックのパスとテストロジックを修正
  - `tests/api/test_settings.py`: `test_get_doctors_default_department`の期待値を修正
  - `tests/external/test_base_api.py`: `@patch`のパスを更新、`get_selected_model`を使用

## [1.3.1] - 2026-01-29

### 追加
- `package.json`: Alpine.jsをdependenciesに追加
- `package.json`: heroku-postbuildスクリプトに `--include=dev` オプションを追加
- `frontend/DEVELOPMENT.md`: フロントエンド開発ガイド（README.mdからリネーム）

### 変更
- `README.md`: プロジェクトルートに移動（docs/README.mdから）
- `app/templates/base.html`: Vite版を有効化、CDN版をコメントアウト
- `.claude/agents/readme-generator.md`: パス指定を修正（docs/README.md → README.md）
- `scripts/project_structure.txt`: プロジェクト構造と生成日時を更新

### 削除
- `docs/FRONTEND_MIGRATION.md`: フロントエンド移行ガイドを削除（情報統合済み）
- `app/static/js/app.js`: 未使用のJavaScriptファイルを削除（Vite版に統合済み）
- `app/static/css/style.css`: 未使用のCSSファイルを削除（Vite版に統合済み）

### リファクタリング
- フロントエンド関連ファイルをVite版に完全移行
- 開発関連ドキュメントを整理統合

## [1.3.0] - 2026-01-28

### 追加
- **フロントエンド環境構築**: Vite + TypeScript + Tailwind CSSのモダンなビルド環境を導入
  - `frontend/`: フロントエンド専用ディレクトリ作成
  - `frontend/src/types.ts`: バックエンドスキーマと対応する型定義
  - `frontend/src/app.ts`: 型安全なAlpine.jsアプリケーション
  - `frontend/src/main.ts`: エントリーポイント
  - `frontend/src/styles/main.css`: Tailwind CSS + カスタムスタイル（@apply使用）
  - `frontend/src/alpinejs.d.ts`: Alpine.js型定義
  - `frontend/vite.config.ts`: Vite設定（プロキシ、ビルド設定）
  - `frontend/tailwind.config.js`: Tailwind設定
  - `frontend/postcss.config.js`: PostCSS設定
  - `frontend/tsconfig.json`: TypeScript設定
  - `frontend/package.json`: フロントエンド依存関係管理
  - `frontend/README.md`: フロントエンドセットアップガイド
- **Jinja2コンポーネント**: 画面ごとの分割
  - `app/templates/components/input_screen.html`: 入力画面
  - `app/templates/components/output_screen.html`: 出力画面
  - `app/templates/components/evaluation_screen.html`: 評価画面
- **Jinja2マクロ**: 共通UIコンポーネント
  - `app/templates/macros.html`: テキストエリア、ボタン、アラートのマクロ
- **ヘルパー関数**: Alpine.jsロジック整理
  - `app/static/js/app.js`: `getCurrentTabContent()`, `copyCurrentTab()`, `isActiveTab()`, `getTabClass()`追加
- **ドキュメント**:
  - `html_refactoring_plan.md`: HTMLリファクタリング計画書
  - `FRONTEND_MIGRATION.md`: フロントエンド移行ガイド

### 変更
- `app/templates/index.html`: 187行→9行に削減（includeのみ）
- `app/static/css/style.css`: 共通CSSクラス追加（`.form-textarea`, `.btn-primary`等）
- `app/templates/base.html`: Vite版とCDN版の切り替えコメント追加
- `.gitignore`: フロントエンドビルド成果物を除外（`app/static/dist/`, `node_modules/`）

### リファクタリング
- **HTML整理**: Tailwind CSSクラスの重複を削減（10箇所以上→0）
- **ロジック分離**: HTML内の三項演算子をJavaScript関数に移動
- **型安全性**: TypeScriptによる型チェック導入

### 技術スタック更新
- TypeScript 5.3.0
- Vite 5.0.0
- Tailwind CSS 3.4.0
- Alpine.js 3.13.0（型定義追加）

### 備考
- CDN版（フェーズ1-3）が現在稼働中
- Vite版（フェーズ4）はビルド済み、いつでも切り替え可能
- HMR対応の開発環境が利用可能

## [1.2.0] - 2026-01-27

### 追加
- `app/models/prompt.py`: 型ヒントを追加
- `app/models/evaluation_prompt.py`: 型ヒントを追加
- `app/services/evaluation_service.py`: prompt_data.contentに型キャストを追加

### 変更
- `app/services/summary_service.py`: SummaryResultをSummaryResponseに置き換え
- `app/services/evaluation_service.py`: プロンプト構築の退院時処方を現在の処方に変更
- `docs/README.md`: APIクライアントアーキテクチャ、開発コマンド、型チェック（Pyright）、コントリビューションガイドを更新

### 修正
- `app/static/js/app.js`: コメントの表記ゆれを修正
- `tests/api/test_base_api.py`: 空文字列のテストケースを修正
- `tests/services/test_evaluation_service.py`: 退院時処方の表記を修正

### リファクタリング
- `tests/`: 不要な引数を削除し、テストを簡潔にする
- `app/utils/text_processor.py`, `app/utils/error_handlers.py`: 不要なコメントを削除

## [1.1.0] - 2026-01-23

### 修正
- すべての失敗していたユニットテストを修正（120のテスト全てがパス）
- `app/utils/text_processor.py`: テキスト処理機能を強化
  - `format_output_summary`: `#`記号と半角スペースの削除機能を追加
  - `section_aliases`: マッピング構造を簡素化（複雑な括弧を削除）
  - `parse_output_summary`: コロン/非コロンパターンを適切に処理するための完全な書き直し
- `app/utils/env_loader.py`: 出力メッセージをテスト期待値に合わせて修正
- `tests/test_prompt_manager.py`: 文書タイプ参照を定数に合わせて更新
- `tests/test_summary_service.py`: キューベースのエラー処理に対応した例外処理テストを修正

## [1.0.0] - 2026-01-21

### 追加
- 診療情報提供書作成アプリの初回安定版リリース
- 複数のAIプロバイダーサポート（ClaudeとGemini）
- 入力長に基づく自動モデル切り替え（40,000文字を超える入力の場合、Claude → Gemini）
- プロンプト、使用統計、設定のためのPostgreSQLデータベース統合
- AIプロバイダー管理のためのFactoryパターン実装
- 階層的プロンプトシステム（診療科 → 医師 → 文書タイプ）
- すべてのAI API呼び出しの使用状況追跡と統計
- より良い出力フォーマットのためのテキスト処理の強化
- すべてのAPIクライアントでのエラー処理の改善
