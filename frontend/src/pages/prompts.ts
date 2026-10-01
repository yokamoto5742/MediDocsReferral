import { fetchDoctors, getHeaders } from '../api';
import type { PromptListItem } from '../types';
import { formatDateTime, sortIcon, sortRows, toggleSort, type SortState } from '../utils';

// プロンプト管理ページ (prompts.html)
export function promptsPage() {
    return {
        prompts: [] as PromptListItem[],
        filteredPrompts: [] as PromptListItem[],
        doctors: ['default'],
        filter: {
            department: 'default',
            doctor: 'default',
            documentType: window.DOCUMENT_TYPES[0]
        },
        isLoading: false,
        error: null as string | null,
        successMessage: null as string | null,
        sort: { column: '', direction: 'asc' } as SortState,

        async init() {
            this.checkQueryParams();
            await this.updateDoctors();
            await this.loadPrompts();
        },

        async updateDoctors() {
            if (!this.filter.department) {
                this.doctors = ['default'];
                return;
            }
            try {
                this.doctors = await fetchDoctors(this.filter.department);
                if (this.filter.doctor && !this.doctors.includes(this.filter.doctor)) {
                    this.filter.doctor = '';
                }
            } catch (e) {
                this.doctors = ['default'];
            }
        },

        // 作成・編集画面から戻ってきたときの完了メッセージを表示する
        checkQueryParams() {
            const params = new URLSearchParams(window.location.search);
            const messages = window.MESSAGES.SUCCESS;
            if (params.get('created') === '1') {
                this.successMessage = messages.PROMPT_CREATED;
            } else if (params.get('updated') === '1') {
                this.successMessage = messages.PROMPT_UPDATED;
            } else if (params.get('deleted') === '1') {
                this.successMessage = messages.PROMPT_DELETED;
            } else {
                return;
            }
            // 再読み込みで同じメッセージが出ないようクエリを消す
            window.history.replaceState({}, document.title, window.location.pathname);
        },

        async loadPrompts() {
            this.isLoading = true;
            this.error = null;
            try {
                const response = await fetch('/api/prompts/');
                this.prompts = await response.json() as PromptListItem[];
                this.applyFilters();
            } catch (e) {
                this.error = window.MESSAGES.ERROR.PROMPT_LOAD_FAILED;
            } finally {
                this.isLoading = false;
            }
        },

        applyFilters() {
            this.filteredPrompts = this.prompts.filter(p => {
                if (this.filter.department && p.department !== this.filter.department) return false;
                if (this.filter.doctor && p.doctor !== this.filter.doctor) return false;
                if (this.filter.documentType && p.document_type !== this.filter.documentType) return false;
                return true;
            });
        },

        async deletePrompt(promptId: number) {
            if (!confirm(window.MESSAGES.CONFIRM.DELETE_PROMPT)) return;

            try {
                const response = await fetch(`/api/prompts/${promptId}`, {
                    method: 'DELETE',
                    headers: getHeaders()
                });
                if (response.ok) {
                    this.successMessage = window.MESSAGES.SUCCESS.PROMPT_DELETED;
                    await this.loadPrompts();
                } else {
                    this.error = window.MESSAGES.ERROR.PROMPT_DELETE_FAILED;
                }
            } catch (e) {
                this.error = window.MESSAGES.ERROR.API_ERROR;
            }
        },

        formatDate: formatDateTime,

        sortPrompts(column: string) {
            toggleSort(this.sort, column);
            sortRows(this.filteredPrompts, this.sort, 'updated_at');
        },

        getSortIcon(column: string): string {
            return sortIcon(this.sort, column);
        }
    };
}
