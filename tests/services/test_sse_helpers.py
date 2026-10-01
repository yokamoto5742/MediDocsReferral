import asyncio
import json

import pytest

from app.services.sse_helpers import heartbeat_events, sse_error, sse_event


class TestSseEvent:
    """sse_event 関数のテスト"""

    def test_sse_event_basic(self):
        """SSEイベント生成 - 基本"""
        result = sse_event("progress", {"status": "starting"})

        assert result.startswith("event: progress\n")
        assert "data: " in result
        assert result.endswith("\n\n")

        data_line = result.split("data: ")[1].strip()
        parsed = json.loads(data_line)
        assert parsed["status"] == "starting"

    def test_sse_event_japanese(self):
        """SSEイベント生成 - 日本語"""
        result = sse_event("error", {"message": "エラーが発生しました"})

        data_line = result.split("data: ")[1].strip()
        parsed = json.loads(data_line)
        assert parsed["message"] == "エラーが発生しました"

    def test_sse_event_complete(self):
        """SSEイベント生成 - 完了イベント"""
        data = {
            "success": True,
            "input_tokens": 1000,
            "output_tokens": 500,
        }
        result = sse_event("complete", data)

        assert "event: complete\n" in result
        data_line = result.split("data: ")[1].strip()
        parsed = json.loads(data_line)
        assert parsed["success"] is True
        assert parsed["input_tokens"] == 1000


    def test_sse_error(self):
        """SSEイベント生成 - errorイベント"""
        result = sse_error("エラーが発生しました")

        assert result.startswith("event: error\n")
        parsed = json.loads(result.split("data: ")[1].strip())
        assert parsed == {"success": False, "error_message": "エラーが発生しました"}


class TestHeartbeatEvents:
    """heartbeat_events 関数のテスト"""

    async def _collect(self, task: asyncio.Future, heartbeat_interval: float = 5) -> list[str]:
        return [
            event
            async for event in heartbeat_events(
                task,
                start_message="開始",
                running_status="processing",
                running_message="処理中",
                elapsed_message_template="処理中... {elapsed}秒",
                heartbeat_interval=heartbeat_interval,
            )
        ]

    async def test_yields_start_and_running_progress(self):
        """開始・実行中の progress イベントを生成し、task 完了で終了する"""
        task = asyncio.create_task(asyncio.to_thread(lambda: ("結果", 100, 50)))

        events = await self._collect(task)

        assert len(events) == 2
        assert "event: progress" in events[0]
        assert '"status": "starting"' in events[0]
        assert "開始" in events[0]
        assert '"status": "processing"' in events[1]
        assert "処理中" in events[1]
        # 結果はイベントに含めず、呼び出し側が task から受け取る
        assert task.result() == ("結果", 100, 50)

    async def test_yields_heartbeat_while_task_running(self):
        """task が完了するまで一定間隔で経過時間付きの progress イベントを生成する"""
        task = asyncio.create_task(asyncio.sleep(0.1))

        events = await self._collect(task, heartbeat_interval=0.02)

        assert len(events) > 2
        assert all("event: progress" in event for event in events)
        assert "処理中... 0秒" in events[2]

    async def test_task_exception_is_left_to_caller(self):
        """task の例外はイベントにせず、呼び出し側の task.result() で送出される"""

        def failing_task() -> tuple[str, int, int]:
            raise ValueError("テストエラー")

        task = asyncio.create_task(asyncio.to_thread(failing_task))

        events = await self._collect(task)

        assert all("event: progress" in event for event in events)
        with pytest.raises(ValueError, match="テストエラー"):
            task.result()
