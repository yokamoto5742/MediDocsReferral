---
description: テスト実行コマンドとテスト方針
---

## テスト実行コマンド

テストは pytest を uv 経由で実行する(`.venv` を直接指定しない)。

```bash
# 全件
uv run pytest tests/ -v --tb=short

# 単一ファイル
uv run pytest tests/<パッケージ>/test_<モジュール>.py -v

# 単一テスト
uv run pytest tests/<パッケージ>/test_<モジュール>.py::test_<テスト名> -v

# カバレッジ付き(pytest-cov を一時的に使う。依存には追加しない)
uv run --with pytest-cov pytest tests/ --cov --cov-report=term-missing
```

## テストの配置

- `tests/` 配下はソースのパッケージ構成に合わせる(例: `service/foo.py` → `tests/service/test_foo.py`)。
- コードを変更したら、コミット前に全件を実行してパスを確認する。
