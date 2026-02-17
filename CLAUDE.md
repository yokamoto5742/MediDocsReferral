# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## House Rules:
- 文章ではなくパッチの差分を返す。
- コードの変更範囲は最小限に抑える。
- コードの修正は直接適用する。
- Pythonのコーディング規約はPEP8に従います。
- KISSの原則に従い、できるだけシンプルなコードにします。
- 可読性を優先します。一度読んだだけで理解できるコードが最高のコードです。
- Pythonのコードのimport文は以下の適切な順序に並べ替えてください。
標準ライブラリ
サードパーティライブラリ
カスタムモジュール 
それぞれアルファベット順に並べます。importが先でfromは後です。

## Automatic Notifications (Hooks)
自動通知は`.claude/settings.local.json` で設定済：
- **PreToolUse Hook (AskUserQuestion)**: Claude Codeがユーザーに質問する前に「Claude Codeがユーザーに質問しています」と通知
- **Stop Hook**: ユーザーがClaude Codeを停止した時に「作業が完了しました」と通知
- **SessionEnd Hook**: セッション終了時に「セッションが終了しました」と通知

## クリーンコードガイドライン
- 関数のサイズ：関数は50行以下に抑えることを目標にしてください。関数の処理が多すぎる場合は、より小さな関数に分割してください。
- 単一責任：各関数とモジュールには明確な目的が1つあるようにします。無関係なロジックをまとめないでください。
- 命名：説明的な名前を使用してください。`tmp` 、`data`、`handleStuff`のような一般的な名前は避けてください。例えば、`doCalc`よりも`calculateInvoiceTotal` の方が適しています。
- DRY原則：コードを重複させないでください。類似のロジックが2箇所に存在する場合は、共有関数にリファクタリングしてください。それぞれに独自の実装が必要な場合はその理由を明確にしてください。
- コメント:分かりにくいロジックについては説明を加えます。説明不要のコードには過剰なコメントはつけないでください。
- コメントとdocstringは必要最小限に日本語で記述します。文末に"。"や"."をつけないでください。
- このアプリのUI画面で表示するメッセージはすべて日本語にします。constants.pyで一元管理します。

## Project Overview

Medical referral document generator using AI (Claude/Gemini) to create structured medical documents. FastAPI backend with PostgreSQL database, Vite/TypeScript/Tailwind frontend.

## Development Commands

### Backend Development

**Run development server:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Run all tests:**
```bash
python -m pytest tests/ -v --tb=short
```

**Run specific test file:**
```bash
python -m pytest tests/services/test_summary_service.py -v
```

**Run specific test:**
```bash
python -m pytest tests/services/test_summary_service.py::test_generate_summary -v
```

**Run with coverage:**
```bash
python -m pytest tests/ -v --tb=short --cov=app --cov-report=html
```

**Type checking:**
```bash
pyright
```

### Frontend Development

**Start development server (with HMR):**
```bash
cd frontend
npm run dev
```

**Type check:**
```bash
cd frontend
npm run typecheck
```

**Production build:**
```bash
cd frontend
npm run build
```

Build output goes to `app/static/dist/`.

### Database Migrations

**Create new migration:**
```bash
alembic revision --autogenerate -m "説明"
```

**Apply migrations:**
```bash
alembic upgrade head
```

**Rollback migration:**
```bash
alembic downgrade -1
```

Database URL is configured in `alembic/env.py` from `app.core.config`.

## Architecture

### Layered Architecture

```
API Layer (FastAPI routes)
    ↓
Service Layer (business logic)
    ↓
External API Layer (Claude/Gemini clients)
    ↓
Model Layer (SQLAlchemy ORM)
```

### Factory Pattern for API Clients

The system dynamically selects API clients based on configuration:

```python
from app.external.api_factory import create_client, APIProvider

# Automatically selects Cloudflare vs Direct client based on env vars
client = create_client(APIProvider.CLAUDE)  # or APIProvider.GEMINI
result = client.generate_summary(...)
```

**Client selection logic** (`app/external/api_factory.py`):
- If all Cloudflare env vars set (`CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_GATEWAY_ID`, `CLOUDFLARE_AIG_TOKEN`): use `CloudflareGeminiAPIClient` or `CloudflareClaudeAPIClient`
- Otherwise: use `GeminiAPIClient` or `ClaudeAPIClient`

### Automatic Model Switching

**Location:** `app/services/model_selector.py`

The `determine_model()` function automatically switches from Claude to Gemini when:
- Input exceeds `MAX_TOKEN_THRESHOLD` (default 100,000 chars)
- User selected Claude
- Gemini is configured

If Gemini not configured, returns error instead of switching.

### Hierarchical Prompt System

**Location:** `app/services/prompt_service.py`

Prompts are resolved in this order:
1. Doctor + document type specific prompt
2. Department + document type specific prompt
3. Document type default prompt
4. System default

This allows per-department and per-doctor customization of document generation.

### Service Layer Pattern

Business logic is separated from API routes:

- **`summary_service.py`**: Document generation orchestration
  - Input validation
  - Model selection logic
  - API client orchestration
  - Usage statistics tracking
- **`prompt_service.py`**: Prompt CRUD and hierarchical resolution
- **`evaluation_service.py`**: AI-based output evaluation
- **`evaluation_prompt_service.py`**: Evaluation prompt management
- **`statistics_service.py`**: Usage statistics aggregation
- **`model_selector.py`**: Model selection and switching logic
- **`usage_service.py`**: Usage tracking persistence
- **`sse_helpers.py`**: Server-Sent Events utilities (heartbeat, event formatting)

### Constants Management

**Location:** `app/core/constants.py`

All constants are centralized here:
- `ModelType` Enum: "Claude", "Gemini_Pro"
- `APIProvider` Enum: CLAUDE, GEMINI
- Department/doctor mappings
- Document types: ["他院への紹介", "紹介元への逆紹介", "返書", "最終返書"]
- User-facing messages (Japanese)

**CRITICAL:** Always use constants, never magic strings. Use `get_message(category, key, **kwargs)` for user messages.

### Data Flow

1. User submits medical text via web UI
2. FastAPI endpoint receives and validates input
3. `SummaryService` orchestrates generation
4. Factory pattern instantiates appropriate API client
5. Model auto-selected based on input length
6. AI generates structured medical document
7. Text processor parses output into sections
8. Usage stats (tokens, time, cost) saved to PostgreSQL
9. Structured document returned to UI

### SSE Streaming Endpoints

**Location:** `app/api/summary.py`, `app/api/evaluation.py`

Endpoints with `/stream` suffix provide real-time streaming:
- `/api/generate/stream`: Streams document generation
- `/api/evaluate/stream`: Streams evaluation results

Use `app/services/sse_helpers.py` utilities:
- `sse_event()`: Format SSE messages
- `stream_with_heartbeat()`: Add periodic heartbeat to prevent timeout

### CSRF Protection

**Location:** `app/core/security.py`

- All state-changing endpoints require CSRF token validation
- Token generated using `CSRF_SECRET_KEY`
- Token expires after `CSRF_TOKEN_EXPIRE_MINUTES` (default 60)
- SSE endpoints also validate CSRF tokens

## Code Style

### Python

- Follow PEP 8
- Use type hints for all function parameters and return values
- Import order: standard library → third-party → local modules
  - Sort alphabetically within each group
  - `import` statements first, then `from` imports
- Keep functions under 50 lines
- Comments only for complex logic, in Japanese, no period at end
- Use constants from `app/core/constants.py`, never magic strings

### TypeScript (Frontend)

- All types defined in `frontend/src/types.ts`
- Keep types in sync with Pydantic schemas
- Use strict type checking (`typeCheckingMode: "standard"`)

### Commit Messages

Use conventional commit format with emoji prefixes:
- `✨ feat`: New feature
- `🐛 fix`: Bug fix
- `📝 docs`: Documentation
- `♻️ refactor`: Code refactoring
- `✅ test`: Tests

Write commit message content in Japanese explaining what and why.

Example:
```
✨ feat(evaluation): 評価プロンプト管理機能を追加

文書タイプごとに評価プロンプトをカスタマイズできるよう、
評価プロンプトCRUDエンドポイントとサービスレイヤーを実装
```

## Testing

**Location:** `tests/`

### Test Structure

- **API tests** (`tests/api/`): Endpoint integration tests
- **Service tests** (`tests/services/`): Business logic unit tests
- **External API tests** (`tests/external/`): Provider integration tests (mocked)
- **Core tests** (`tests/core/`): Config, security, database tests
- **Utility tests** (`tests/test_utils/`): Text processing, error handling

### Test Configuration

- `pytest.ini`: Test discovery settings
- `pyrightconfig.json`: Type checking excludes tests
- Fixtures in `tests/conftest.py`

### Adding Tests

When adding new features:
1. Write service layer tests first (TDD recommended)
2. Add API integration tests
3. Add external API tests with `pytest-mock` if needed

Mock external API calls using `pytest-mock`:
```python
def test_example(mocker):
    mock_client = mocker.patch("app.external.api_factory.create_client")
    # test logic
```

## Environment Variables

**Critical variables** (see README.md for complete list):

### Database
- `DATABASE_URL` or individual `POSTGRES_*` vars
- `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, etc.

### Claude API
- AWS Bedrock: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `ANTHROPIC_MODEL`

### Gemini API
- `GOOGLE_CREDENTIALS_JSON`, `GOOGLE_PROJECT_ID`, `GOOGLE_LOCATION`
- `GEMINI_MODEL`, `GEMINI_THINKING_LEVEL`

### Cloudflare (optional)
- `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_GATEWAY_ID`, `CLOUDFLARE_AIG_TOKEN`

### Application
- `MAX_TOKEN_THRESHOLD`: Auto-switch threshold (default 100,000)
- `SELECTED_AI_MODEL`: Default model ("Claude" or "Gemini_Pro")
- `CSRF_SECRET_KEY`, `CSRF_TOKEN_EXPIRE_MINUTES`

## Common Patterns

### Adding a New Endpoint

1. Create Pydantic schema in `app/schemas/`
2. Add service function in `app/services/`
3. Add route in `app/api/`
4. Add tests in `tests/api/` and `tests/services/`
5. Update frontend types in `frontend/src/types.ts` if needed

### Adding a New AI Provider

1. Create client class inheriting from `BaseAPIClient` in `app/external/`
2. Add provider to `APIProvider` enum in `app/external/api_factory.py`
3. Update `create_client()` factory function
4. Add tests in `tests/external/`

### Adding Constants

Add to `app/core/constants.py`:
```python
# For enums
class NewEnum(str, Enum):
    VALUE1 = "value1"
    VALUE2 = "value2"

# For messages
MESSAGES["CATEGORY"]["KEY"] = "メッセージ内容"
```

Then use:
```python
from app.core.constants import NewEnum, get_message

value = NewEnum.VALUE1
msg = get_message("CATEGORY", "KEY", placeholder="value")
```

## Frontend Architecture

**Location:** `frontend/`

- **Vite** for fast development and building
- **TypeScript** for type safety
- **Tailwind CSS** for styling
- **Alpine.js** for reactive components
- **Jinja2** for server-side templates

### Development

- Frontend dev server runs on port 5173
- API requests proxy to `http://localhost:8000`
- HMR (Hot Module Replacement) enabled
- Build outputs to `app/static/dist/`

### File Structure

- `frontend/src/main.ts`: Entry point
- `frontend/src/app.ts`: Alpine.js application logic
- `frontend/src/types.ts`: TypeScript type definitions
- `frontend/src/styles/main.css`: Tailwind + custom styles
- `app/templates/`: Jinja2 templates
- `app/templates/components/`: Reusable components
- `app/templates/macros.html`: UI component macros

## Common Tasks

### Adding a New Document Type

1. Add to `DOCUMENT_TYPES` in `app/core/constants.py`
2. Add purpose mapping to `DOCUMENT_TYPE_TO_PURPOSE_MAPPING`
3. Update frontend dropdown in templates
4. Add default prompt if needed
5. Update tests

### Adding a New Department/Doctor

1. Update `DEPARTMENT_DOCTORS_MAPPING` in `app/core/constants.py`
2. Update `DEFAULT_DEPARTMENT` and `DEFAULT_DOCTOR` if needed
3. Frontend will auto-populate from settings endpoint

### Modifying Model Switching Logic

Edit `app/services/model_selector.py`:
- `determine_model()`: Auto-switching logic
- `get_provider_and_model()`: Provider/model mapping

### Changing Prompt Resolution

Edit `app/services/prompt_service.py`:
- `get_prompt()`: Hierarchical prompt resolution
- `get_selected_model()`: Model name resolution

## Troubleshooting

### Tests Failing

- Check `.env.test` file is configured
- Ensure database migrations are up to date
- Verify external API calls are mocked
- Look for error messages in Japanese in `app/core/constants.py`

### Frontend Not Building

- Run `npm install` in `frontend/` directory
- Check `vite.config.ts` paths are correct
- Ensure TypeScript types match backend schemas

### API Errors

- Check environment variables are set
- Verify API keys are valid
- Check Cloudflare settings if using AI Gateway
- Review logs for specific error messages

### Database Connection Issues

- Verify PostgreSQL is running
- Check `DATABASE_URL` or individual `POSTGRES_*` variables
- Ensure database exists: `createdb medidocs`
- Run migrations: `alembic upgrade head`

## Important Notes

- **Medical Application:** All AI-generated content must be reviewed by medical professionals
- **Security:** Never commit `.env` files, rotate API keys regularly
- **Language:** User-facing messages are in Japanese, code comments in Japanese only for complex logic
- **Testing:** Maintain comprehensive test coverage (120+ tests)
- **Type Safety:** Use type hints everywhere, run `pyright` before committing
