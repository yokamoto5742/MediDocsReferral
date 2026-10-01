import { getHeaders, postJson } from '../api';
import type { EvaluationPrompt, EvaluationPromptSaveResponse } from '../types';
import { formatDateTime } from '../utils';

// 評価プロンプト管理ページ (evaluation_prompts.html)
export function evaluationPromptsPage() {
    return {
        prompts: [] as EvaluationPrompt[],
        documentTypes: window.DOCUMENT_TYPES,
        isLoading: false,
        error: null as string | null,
        successMessage: null as string | null,

        async init() {
            this.checkQueryParams();
            await this.loadPrompts();
        },

        // 編集画面から戻ってきたときの完了メッセージを表示する
        checkQueryParams() {
            const params = new URLSearchParams(window.location.search);
            if (params.get('saved') === '1') {
                this.successMessage = window.MESSAGES.SUCCESS.PROMPT_SAVED;
            } else if (params.get('deleted') === '1') {
                this.successMessage = window.MESSAGES.SUCCESS.PROMPT_DELETED;
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
                const response = await fetch('/api/evaluation/prompts');
                const data = await response.json() as { prompts?: EvaluationPrompt[] };
                this.prompts = data.prompts || [];
            } catch (e) {
                this.error = window.MESSAGES.ERROR.PROMPT_LOAD_FAILED;
            } finally {
                this.isLoading = false;
            }
        },

        getPrompt(docType: string): EvaluationPrompt | undefined {
            return this.prompts.find(p => p.document_type === docType);
        },

        hasPrompt(docType: string): boolean {
            return !!this.getPrompt(docType);
        },

        getPromptPreview(docType: string): string {
            const content = this.getPrompt(docType)?.content;
            if (!content) return '未設定';
            return content.length > 50 ? content.substring(0, 50) + '...' : content;
        },

        getUpdatedAt(docType: string): string {
            return formatDateTime(this.getPrompt(docType)?.updated_at);
        },

        async deletePrompt(docType: string) {
            const confirmMessage = window.MESSAGES.CONFIRM.DELETE_EVALUATION_PROMPT
                .replace('{document_type}', docType);
            if (!confirm(confirmMessage)) return;

            try {
                const response = await fetch(`/api/evaluation/prompts/${encodeURIComponent(docType)}`, {
                    method: 'DELETE',
                    headers: getHeaders()
                });
                const data = await response.json() as EvaluationPromptSaveResponse;
                if (data.success) {
                    this.successMessage = data.message;
                    await this.loadPrompts();
                } else {
                    this.error = data.message || window.MESSAGES.ERROR.EVALUATION_PROMPT_DELETE_FAILED;
                }
            } catch (e) {
                this.error = window.MESSAGES.ERROR.API_ERROR;
            }
        }
    };
}

// 評価プロンプト編集ページ (evaluation_prompts_edit.html)
export function evaluationPromptEditPage(documentType: string) {
    return {
        documentType,
        content: '',
        isSaving: false,
        error: null as string | null,

        async init() {
            await this.loadPrompt();
        },

        async loadPrompt() {
            try {
                const response = await fetch(`/api/evaluation/prompts/${encodeURIComponent(this.documentType)}`);
                const data = await response.json() as EvaluationPrompt;
                if (data.content) {
                    this.content = data.content;
                }
            } catch (e) {
                this.error = window.MESSAGES.ERROR.EVALUATION_PROMPT_LOAD_FAILED;
            }
        },

        async savePrompt() {
            if (!this.content.trim()) {
                this.error = window.MESSAGES.VALIDATION.PROMPT_CONTENT_REQUIRED;
                return;
            }

            this.isSaving = true;
            this.error = null;

            try {
                const response = await postJson('/api/evaluation/prompts', {
                    document_type: this.documentType,
                    content: this.content
                });

                const data = await response.json() as EvaluationPromptSaveResponse;
                if (data.success) {
                    window.location.href = '/evaluation-prompts?saved=1';
                } else {
                    this.error = data.message || window.MESSAGES.ERROR.EVALUATION_PROMPT_SAVE_FAILED;
                }
            } catch (e) {
                this.error = window.MESSAGES.ERROR.API_ERROR;
            } finally {
                this.isSaving = false;
            }
        }
    };
}
