import { errorMessageOf, fetchDoctors, getHeaders, postJson } from '../api';
import type { PromptDetail } from '../types';

interface PromptForm {
    department: string;
    doctor: string;
    documentType: string;
    selectedModel: string;
    content: string;
}

// プロンプトを保存する（作成と更新は同じAPI）。成功時は null、失敗時は表示するエラーメッセージを返す
async function savePrompt(form: PromptForm, fallbackMessage: string): Promise<string | null> {
    try {
        const response = await postJson('/api/prompts/', {
            department: form.department,
            doctor: form.doctor,
            document_type: form.documentType,
            selected_model: form.selectedModel || null,
            content: form.content
        });
        return response.ok ? null : await errorMessageOf(response, fallbackMessage);
    } catch (e) {
        return window.MESSAGES.ERROR.API_ERROR;
    }
}

// プロンプト新規作成ページ (prompts_new.html)
export function promptNewPage() {
    return {
        form: {
            department: 'default',
            doctor: 'default',
            documentType: window.DOCUMENT_TYPES[0],
            selectedModel: '',
            content: ''
        } as PromptForm,
        doctors: ['default'],
        isSaving: false,
        error: null as string | null,

        async init() {
            await this.updateDoctors();
        },

        async updateDoctors() {
            try {
                this.doctors = await fetchDoctors(this.form.department);
                if (!this.doctors.includes(this.form.doctor)) {
                    this.form.doctor = this.doctors[0];
                }
            } catch (e) {
                this.doctors = ['default'];
            }
        },

        async savePrompt() {
            const form = this.form;
            if (!form.department || !form.doctor || !form.documentType || !form.content.trim()) {
                this.error = window.MESSAGES.VALIDATION.ALL_REQUIRED_FIELDS;
                return;
            }

            this.isSaving = true;
            this.error = null;
            this.error = await savePrompt(form, window.MESSAGES.ERROR.PROMPT_CREATE_FAILED);
            if (!this.error) {
                window.location.href = '/prompts?created=1';
            }
            this.isSaving = false;
        }
    };
}

// プロンプト編集ページ (prompts_edit.html)
export function promptEditPage(promptId: number) {
    return {
        promptId,
        form: {
            department: '',
            doctor: '',
            documentType: '',
            selectedModel: '',
            content: ''
        } as PromptForm,
        isLoading: true,
        isSaving: false,
        error: null as string | null,
        loadError: null as string | null,

        async init() {
            await this.loadPrompt();
        },

        async loadPrompt() {
            this.isLoading = true;
            this.loadError = null;

            try {
                const response = await fetch(`/api/prompts/${this.promptId}`);
                if (response.ok) {
                    const data = await response.json() as PromptDetail;
                    this.form = {
                        department: data.department,
                        doctor: data.doctor,
                        documentType: data.document_type,
                        selectedModel: data.selected_model || '',
                        content: data.content
                    };
                } else if (response.status === 404) {
                    this.loadError = window.MESSAGES.ERROR.PROMPT_NOT_FOUND;
                } else {
                    this.loadError = window.MESSAGES.ERROR.PROMPT_LOAD_FAILED;
                }
            } catch (e) {
                this.loadError = window.MESSAGES.ERROR.API_ERROR;
            } finally {
                this.isLoading = false;
            }
        },

        async updatePrompt() {
            if (!this.form.content.trim()) {
                this.error = window.MESSAGES.VALIDATION.PROMPT_CONTENT_REQUIRED;
                return;
            }

            this.isSaving = true;
            this.error = null;
            this.error = await savePrompt(this.form, window.MESSAGES.ERROR.PROMPT_UPDATE_FAILED);
            if (!this.error) {
                window.location.href = '/prompts?updated=1';
            }
            this.isSaving = false;
        },

        async deletePrompt() {
            if (!confirm(window.MESSAGES.CONFIRM.DELETE_PROMPT)) return;

            this.isSaving = true;
            this.error = null;

            try {
                const response = await fetch(`/api/prompts/${this.promptId}`, {
                    method: 'DELETE',
                    headers: getHeaders()
                });

                if (response.ok) {
                    window.location.href = '/prompts?deleted=1';
                } else {
                    this.error = await errorMessageOf(response, window.MESSAGES.ERROR.PROMPT_DELETE_FAILED);
                }
            } catch (e) {
                this.error = window.MESSAGES.ERROR.API_ERROR;
            } finally {
                this.isSaving = false;
            }
        }
    };
}
