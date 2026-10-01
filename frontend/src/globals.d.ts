// base.html のインラインスクリプトでテンプレートから渡される値
interface Window {
    CSRF_TOKEN: string;
    TAB_NAMES: string[];
    MESSAGES: Record<string, Record<string, string>>;
    DOCUMENT_PURPOSE_MAPPING: Record<string, string>;
    DOCUMENT_TYPES: string[];
}
