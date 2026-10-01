import asyncio
import json
import time
from typing import Any, AsyncGenerator

# プロキシによるバッファリングを避け、イベントを即時に届けるためのヘッダー
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse_event(event_type: str, data: dict[str, Any]) -> str:
    """SSEイベント文字列を生成"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_error(error_message: str) -> str:
    """SSEのerrorイベント文字列を生成"""
    return sse_event("error", {"success": False, "error_message": error_message})


async def heartbeat_events(
    task: asyncio.Future[Any],
    start_message: str,
    running_status: str,
    running_message: str,
    elapsed_message_template: str,
    heartbeat_interval: float = 5,
) -> AsyncGenerator[str, None]:
    """
    taskが完了するまで一定間隔でprogressイベントを生成

    接続を維持するためのハートビート。taskの結果と例外はここでは扱わず、
    呼び出し側が task.result() で受け取る
    """
    yield sse_event("progress", {"status": "starting", "message": start_message})
    yield sse_event("progress", {"status": running_status, "message": running_message})

    start_time = time.time()
    while True:
        done, _ = await asyncio.wait({task}, timeout=heartbeat_interval)
        if done:
            return
        elapsed = int(time.time() - start_time)
        yield sse_event(
            "progress",
            {
                "status": running_status,
                "message": elapsed_message_template.format(elapsed=elapsed),
            },
        )
