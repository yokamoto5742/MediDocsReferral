import { errorMessageOf, fetchDoctors, postJson, readSSE } from './api';
import type {
    Settings,
    ReferralForm,
    GenerationResult,
    EvaluationResult,
    SelectedModelResponse,
    SSECompleteEvent,
    SSEErrorEvent,
    SSEEvaluationCompleteEvent
} from './types';

type ScreenType = 'input' | 'output' | 'evaluation';

interface AppState {
    settings: Settings;
    doctors: string[];
    form: ReferralForm;
    result: GenerationResult;
    isGenerating: boolean;
    elapsedTime: number;
    timerInterval: ReturnType<typeof setInterval> | null;
    showCopySuccess: boolean;
    error: string | null;
    activeTab: number;
    tabs: readonly string[];
    currentScreen: ScreenType;
    evaluationResult: EvaluationResult;
    isEvaluating: boolean;
    init(): Promise<void>;
    updateReferralPurpose(): void;
    updateDoctors(): Promise<void>;
    updateSelectedModel(): Promise<void>;
    startTimer(): void;
    stopTimer(): void;
    buildSummaryRequestBody(refine: boolean): Record<string, unknown>;
    generateSummary(refine?: boolean): Promise<void>;
    handleSummaryEvent(eventType: string, data: unknown): void;
    clearForm(): void;
    backToInput(): void;
    backToOutput(): void;
    showEvaluation(): void;
    buildEvaluationRequestBody(): Record<string, unknown>;
    evaluateOutput(): Promise<void>;
    handleEvaluationEvent(eventType: string, data: unknown): void;
    copyToClipboard(text: string): Promise<void>;
    getCurrentTabContent(): string;
    copyCurrentTab(): void;
    getTabClass(index: number): string;
}

function emptyResult(): GenerationResult {
    return {
        outputSummary: '',
        parsedSummary: {},
        processingTime: null,
        modelUsed: '',
        modelSwitched: false
    };
}

function emptyEvaluation(): EvaluationResult {
    return { result: '', processingTime: null };
}

export function appState(): AppState {
    return {
        // Settings
        settings: {
            department: 'default',
            doctor: 'default',
            documentType: window.DOCUMENT_TYPES[0],
            model: 'Claude'
        },
        doctors: ['default'],

        // Form
        form: {
            referralPurpose: '',
            currentPrescription: '',
            medicalText: '',
            additionalInfo: ''
        },

        // Result
        result: emptyResult(),

        // UI state
        isGenerating: false,
        // 生成と評価は同時に走らないため、経過時間のタイマーは共有する
        elapsedTime: 0,
        timerInterval: null,
        showCopySuccess: false,
        error: null,
        activeTab: 0,
        tabs: window.TAB_NAMES,
        currentScreen: 'input',

        // Evaluation state
        evaluationResult: emptyEvaluation(),
        isEvaluating: false,

        async init() {
            await this.updateDoctors();
            this.updateReferralPurpose();
            await this.updateSelectedModel();
        },

        updateReferralPurpose() {
            if (window.DOCUMENT_PURPOSE_MAPPING && window.DOCUMENT_PURPOSE_MAPPING[this.settings.documentType]) {
                this.form.referralPurpose = window.DOCUMENT_PURPOSE_MAPPING[this.settings.documentType];
            }
        },

        async updateDoctors() {
            try {
                this.doctors = await fetchDoctors(this.settings.department);
                if (!this.doctors.includes(this.settings.doctor)) {
                    this.settings.doctor = this.doctors[0];
                }
            } catch (error) {
                console.error('医師リストの取得中にエラーが発生しました:', error);
            }
        },

        async updateSelectedModel() {
            try {
                const params = new URLSearchParams({
                    department: this.settings.department,
                    document_type: this.settings.documentType,
                    doctor: this.settings.doctor
                });
                const response = await fetch(`/api/settings/selected-model?${params}`);
                if (!response.ok) {
                    console.error('選択モデルの取得に失敗しました:', response.status, response.statusText);
                    return;
                }
                const data = await response.json() as SelectedModelResponse;
                if (data.selected_model) {
                    this.settings.model = data.selected_model;
                }
            } catch (error) {
                console.error('選択モデルの取得中にエラーが発生しました:', error);
            }
        },

        startTimer() {
            this.elapsedTime = 0;
            this.timerInterval = setInterval(() => {
                this.elapsedTime++;
            }, 1000);
        },

        stopTimer() {
            if (this.timerInterval !== null) {
                clearInterval(this.timerInterval);
                this.timerInterval = null;
            }
        },

        buildSummaryRequestBody(refine: boolean): Record<string, unknown> {
            const body: Record<string, unknown> = {
                referral_purpose: this.form.referralPurpose,
                current_prescription: this.form.currentPrescription,
                medical_text: this.form.medicalText,
                additional_info: this.form.additionalInfo,
                department: this.settings.department,
                doctor: this.settings.doctor,
                document_type: this.settings.documentType,
                model: this.settings.model,
                model_explicitly_selected: true
            };
            // 評価結果を反映した再生成の場合、前回の出力と評価結果を送信
            if (refine) {
                body.previous_summary = this.result.outputSummary;
                body.evaluation_feedback = this.evaluationResult.result;
            }
            return body;
        },

        async generateSummary(refine = false) {
            if (!this.form.medicalText.trim()) {
                this.error = window.MESSAGES.VALIDATION.NO_INPUT;
                return;
            }

            this.isGenerating = true;
            this.error = null;
            this.startTimer();

            try {
                const response = await postJson('/api/summary/generate-stream', this.buildSummaryRequestBody(refine));
                if (!response.ok) {
                    this.error = await errorMessageOf(response, window.MESSAGES.ERROR.API_ERROR);
                    return;
                }
                await readSSE(response, (eventType, data) => this.handleSummaryEvent(eventType, data));
            } catch (e) {
                console.error('SSEストリーミング中にエラーが発生:', e);
                this.error = window.MESSAGES.ERROR.API_ERROR;
            } finally {
                this.stopTimer();
                this.isGenerating = false;
            }
        },

        // progress イベントはハートビートのため何もしない
        handleSummaryEvent(eventType: string, data: unknown) {
            if (eventType === 'complete') {
                const completeData = data as SSECompleteEvent;
                this.result = {
                    outputSummary: completeData.output_summary || '',
                    parsedSummary: completeData.parsed_summary || {},
                    processingTime: completeData.processing_time || null,
                    modelUsed: completeData.model_used || '',
                    modelSwitched: completeData.model_switched || false
                };
                this.evaluationResult = emptyEvaluation();
                this.activeTab = 0;
                this.currentScreen = 'output';
            } else if (eventType === 'error') {
                this.error = (data as SSEErrorEvent).error_message || window.MESSAGES.ERROR.GENERIC_ERROR;
            }
        },

        clearForm() {
            this.form = {
                referralPurpose: '',
                currentPrescription: '',
                medicalText: '',
                additionalInfo: ''
            };
            this.result = emptyResult();
            this.evaluationResult = emptyEvaluation();
            this.error = null;
        },

        backToInput() {
            this.clearForm();
            this.currentScreen = 'input';
            this.error = null;
        },

        backToOutput() {
            this.currentScreen = 'output';
        },

        showEvaluation() {
            this.currentScreen = 'evaluation';
        },

        buildEvaluationRequestBody(): Record<string, unknown> {
            return {
                document_type: this.settings.documentType,
                input_text: this.form.medicalText,
                current_prescription: this.form.currentPrescription,
                additional_info: this.form.additionalInfo,
                output_summary: this.result.outputSummary
            };
        },

        async evaluateOutput() {
            if (!this.result.outputSummary) {
                this.error = window.MESSAGES.VALIDATION.EVALUATION_NO_OUTPUT;
                return;
            }

            // 既に評価結果がある場合は確認ダイアログを表示
            if (this.evaluationResult.result) {
                if (!confirm(window.MESSAGES.CONFIRM.RE_EVALUATE)) {
                    return;
                }
            }

            this.isEvaluating = true;
            this.error = null;
            this.startTimer();

            try {
                const response = await postJson('/api/evaluation/evaluate-stream', this.buildEvaluationRequestBody());
                if (!response.ok) {
                    this.error = await errorMessageOf(response, window.MESSAGES.ERROR.EVALUATION_ERROR);
                    return;
                }
                await readSSE(response, (eventType, data) => this.handleEvaluationEvent(eventType, data));
            } catch (e) {
                console.error('SSEストリーミング中にエラーが発生:', e);
                this.error = window.MESSAGES.ERROR.API_ERROR;
            } finally {
                this.stopTimer();
                this.isEvaluating = false;
            }
        },

        handleEvaluationEvent(eventType: string, data: unknown) {
            if (eventType === 'complete') {
                const completeData = data as SSEEvaluationCompleteEvent;
                this.evaluationResult = {
                    result: completeData.evaluation_result || '',
                    processingTime: completeData.processing_time || null
                };
                this.currentScreen = 'evaluation';
            } else if (eventType === 'error') {
                this.error = (data as SSEErrorEvent).error_message || window.MESSAGES.ERROR.GENERIC_ERROR;
            }
        },

        async copyToClipboard(text: string) {
            try {
                await navigator.clipboard.writeText(text);
                this.showCopySuccess = true;
                setTimeout(() => {
                    this.showCopySuccess = false;
                }, 2000);
            } catch (e) {
                this.error = window.MESSAGES.ERROR.COPY_FAILED;
            }
        },

        // ヘルパー関数
        getCurrentTabContent(): string {
            if (this.activeTab === 0) {
                return this.result.outputSummary;
            }
            return this.result.parsedSummary[this.tabs[this.activeTab]] || '';
        },

        copyCurrentTab() {
            this.copyToClipboard(this.getCurrentTabContent());
        },

        getTabClass(index: number): string {
            return this.activeTab === index
                ? 'border-blue-500 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                : 'border-transparent text-white hover:text-gray-700 dark:hover:text-gray-300';
        }
    };
}
