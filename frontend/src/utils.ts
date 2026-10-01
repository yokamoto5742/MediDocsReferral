// 一覧テーブルの並べ替え状態（column が空文字なら未ソート）
export interface SortState {
    column: string;
    direction: 'asc' | 'desc';
}

export function formatDateTime(dateStr: string | null | undefined): string {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('ja-JP', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 同じ列なら昇順/降順を切り替え、別の列なら昇順から始める
export function toggleSort(sort: SortState, column: string): void {
    if (sort.column === column) {
        sort.direction = sort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        sort.column = column;
        sort.direction = 'asc';
    }
}

export function sortIcon(sort: SortState, column: string): string {
    if (sort.column !== column) return '⇅';
    return sort.direction === 'asc' ? '↑' : '↓';
}

// 数値同士は数値として、それ以外は大文字小文字を無視した文字列として比較する（null は空文字扱い）
function compareValues(a: unknown, b: unknown): number {
    if (typeof a === 'number' && typeof b === 'number') {
        return a - b;
    }
    const aText = String(a ?? '').toLowerCase();
    const bText = String(b ?? '').toLowerCase();
    if (aText < bText) return -1;
    if (aText > bText) return 1;
    return 0;
}

// sort の列と方向で rows をその場で並べ替える。dateColumn に指定した列は日時として比較する
export function sortRows<T extends object>(rows: T[], sort: SortState, dateColumn?: string): void {
    const sign = sort.direction === 'asc' ? 1 : -1;
    const valueOf = (row: T): unknown => {
        const value = (row as Record<string, unknown>)[sort.column];
        return sort.column === dateColumn ? new Date(value as string).getTime() : value;
    };
    rows.sort((a, b) => sign * compareValues(valueOf(a), valueOf(b)));
}
