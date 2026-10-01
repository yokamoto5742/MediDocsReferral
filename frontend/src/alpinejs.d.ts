declare module 'alpinejs' {
    interface Alpine {
        // x-data="name(引数)" の形でテンプレートから引数を渡せる
        data(name: string, callback: (...args: any[]) => any): void;
        start(): void;
    }

    const Alpine: Alpine;
    export default Alpine;
}
