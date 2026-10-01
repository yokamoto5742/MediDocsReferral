import type { DoctorsResponse } from './types';

// APIリクエスト用のヘッダーを取得（変更系APIに必要なCSRFトークンを付与）
export function getHeaders(additionalHeaders: Record<string, string> = {}): Record<string, string> {
    return { 'X-CSRF-Token': window.CSRF_TOKEN, ...additionalHeaders };
}

export function postJson(url: string, body: unknown): Promise<Response> {
    return fetch(url, {
        method: 'POST',
        headers: getHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(body)
    });
}

// 失敗レスポンスからサーバーのエラーメッセージを取り出す。取得できなければ fallback を返す
export async function errorMessageOf(response: Response, fallback: string): Promise<string> {
    try {
        const data = await response.json();
        // 検証エラー・未処理例外は error_message、HTTPException は detail に入る
        const message = data.error_message ?? data.detail;
        return typeof message === 'string' && message ? message : fallback;
    } catch {
        return fallback;
    }
}

export async function fetchDoctors(department: string): Promise<string[]> {
    const response = await fetch(`/api/settings/doctors/${department}`);
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json() as DoctorsResponse;
    return data.doctors;
}

// SSEレスポンスを読み取り、イベントごとに onEvent(イベント名, パース済みdata) を呼ぶ
export async function readSSE(
    response: Response,
    onEvent: (eventType: string, data: unknown) => void
): Promise<void> {
    if (!response.body) {
        throw new Error(window.MESSAGES.ERROR.RESPONSE_BODY_EMPTY);
    }

    const dispatch = (eventText: string) => {
        let eventType = '';
        let data = '';
        for (const line of eventText.split('\n')) {
            if (line.startsWith('event: ')) {
                eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
                data = line.slice(6);
            }
        }
        if (eventType && data) {
            onEvent(eventType, JSON.parse(data));
        }
    };

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            // イベントは空行区切り。末尾の未完成分は次のチャンクに持ち越す
            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split('\n\n');
            buffer = events.pop() || '';
            events.forEach(dispatch);
        }
        dispatch(buffer);
    } finally {
        reader.releaseLock();
    }
}
