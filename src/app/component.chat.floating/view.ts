import { OnInit, OnDestroy, ViewChild, ElementRef, ChangeDetectorRef } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { Router } from '@angular/router';

declare const wiz: any;

export class Component implements OnInit, OnDestroy {
    private readonly collectionStorageKey: string = 'plasma.selectedCollection';

    // Chat state
    public isOpen: boolean = false;
    public chatInput: string = '';
    public chatLoading: boolean = false;
    public chatMessages: any[] = [];
    public chatHistory: any[] = [];
    private chatAbortController: AbortController | null = null;
    private chatAssistantIdx: number = -1;

    // Milvus collection state
    public collections: any[] = [];
    public selectedCollection: string = '';
    public collectionsLoading: boolean = false;
    public collectionSelected: boolean = false;

    // Suggested prompts
    public suggestions = [
        { icon: '🔬', text: '플라즈마 에칭 관련 최신 논문 찾아줘', category: 'research' },
        { icon: '⚙️', text: 'ICP 에칭 공정에서 RF 파워 효과 예측해줘', category: 'prediction' },
        { icon: '📊', text: 'OES 진단과 랭뮤어 프로브 비교해줘', category: 'diagnosis' },
        { icon: '📐', text: '디바이 길이를 계산해줘', category: 'calculator' },
    ];

    @ViewChild('chatBody') chatBodyRef!: ElementRef<HTMLDivElement>;
    @ViewChild('chatInputEl') chatInputRef!: ElementRef<HTMLTextAreaElement>;

    constructor(
        public service: Service,
        private router: Router,
        private cdr: ChangeDetectorRef
    ) {}

    public async ngOnInit() {
        await this.service.init();
        this.selectedCollection = this.getStoredCollection();
    }

    public ngOnDestroy() {
        this.cancelChat();
    }

    // ===== Toggle =====
    public async toggleChat() {
        this.isOpen = !this.isOpen;
        if (this.isOpen) {
            const storedCollection = this.getStoredCollection();
            if (storedCollection) {
                this.selectedCollection = storedCollection;
            }
            // Load collections when opening for the first time
            if (this.collections.length === 0) {
                await this.loadCollections();
            } else {
                this.collectionSelected = !!this.selectedCollection;
            }
            setTimeout(() => {
                if (this.chatInputRef?.nativeElement) {
                    this.chatInputRef.nativeElement.focus();
                }
            }, 200);
        }
    }

    // ===== Collection Management =====
    private getStoredCollection(): string {
        try {
            return localStorage.getItem(this.collectionStorageKey) || '';
        } catch (e) { }
        return '';
    }

    private persistCollection(name: string) {
        try {
            if (name && name.trim()) {
                localStorage.setItem(this.collectionStorageKey, name);
            } else {
                localStorage.removeItem(this.collectionStorageKey);
            }
        } catch (e) { }
    }

    public async loadCollections() {
        this.collectionsLoading = true;
        this.cdr.detectChanges();
        try {
            let code = 0;
            let data: any = {};

            try {
                const response = await fetch(`/wiz/api/page.embedding/collections`, {
                    method: 'POST',
                    credentials: 'same-origin'
                });
                const payload = await response.json();
                code = payload.code;
                data = payload.data || {};
            } catch (e) {
                const res = await wiz.call("collections");
                code = res.code;
                data = res.data || {};
            }

            if (code === 200) {
                this.collections = (data.collections || []).sort((a: any, b: any) => {
                    return (b.total_docs || 0) - (a.total_docs || 0);
                });

                const storedCollection = this.getStoredCollection();
                if (storedCollection && this.collections.find((item: any) => item.name === storedCollection)) {
                    this.selectedCollection = storedCollection;
                }

                if (this.selectedCollection && !this.collections.find((item: any) => item.name === this.selectedCollection)) {
                    this.selectedCollection = '';
                }

                if (this.collections.length > 0 && !this.selectedCollection) {
                    this.selectedCollection = this.collections[0].name;
                }

                if (this.selectedCollection) {
                    this.persistCollection(this.selectedCollection);
                }

                if (this.collections.length === 1 && this.selectedCollection) {
                    this.collectionSelected = true;
                } else {
                    this.collectionSelected = !!this.selectedCollection;
                }
            }
        } catch (e) { }
        this.collectionsLoading = false;
        this.cdr.detectChanges();
    }

    public selectCollection(name: string) {
        this.selectedCollection = name;
        this.collectionSelected = true;
        this.persistCollection(name);
        // Clear history when switching collection
        this.chatMessages = [];
        this.chatHistory = [];
        this.chatAssistantIdx = -1;
        this.cdr.detectChanges();
    }

    public getSelectedCollectionInfo(): any {
        return this.collections.find((c: any) => c.name === this.selectedCollection) || null;
    }

    public changeCollection() {
        this.collectionSelected = false;
        this.cdr.detectChanges();
    }

    // ===== Send Message =====
    public async sendChat(text?: string) {
        const message = (text || this.chatInput || '').trim();
        if (!message || this.chatLoading) return;

        // Add user message
        this.chatMessages.push({ role: 'user', content: message });
        this.chatInput = '';
        this.chatLoading = true;

        // Add empty assistant message
        const assistantMsg: any = { role: 'assistant', content: '', toolCalls: [], collapsed: false };
        this.chatMessages.push(assistantMsg);
        this.chatAssistantIdx = this.chatMessages.length - 1;
        this.scrollToBottom();
        this.cdr.detectChanges();

        // SSE fetch
        this.chatAbortController = new AbortController();
        const params = new URLSearchParams();
        params.append('message', message);
        params.append('history', JSON.stringify(this.chatHistory));
        if (this.selectedCollection) {
            params.append('collection', this.selectedCollection);
        }

        try {
            const response = await fetch(
                `/wiz/api/page.agent/agent_chat`,
                { method: 'POST', body: params, signal: this.chatAbortController.signal }
            );

            const reader = response.body!.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const event = JSON.parse(line.slice(6));
                            this.handleChatEvent(event);
                        } catch (e) { }
                    }
                }
            }
        } catch (e: any) {
            if (e.name !== 'AbortError') {
                this.chatMessages[this.chatAssistantIdx].content += '\n\n**오류가 발생했습니다.**';
            }
        }

        this.chatLoading = false;
        this.cdr.detectChanges();
    }

    // ===== SSE Event Handler =====
    private handleChatEvent(event: any) {
        const msg = this.chatMessages[this.chatAssistantIdx];
        if (!msg) return;

        switch (event.type) {
            case 'text':
                msg.content += event.content || '';
                break;
            case 'tool_use':
                msg.toolCalls.push({
                    type: 'use',
                    id: event.id,
                    name: event.name,
                    input: event.input,
                    collapsed: true
                });
                break;
            case 'tool_result':
                // Check for navigation command
                this.handleToolResult(event);
                msg.toolCalls.push({
                    type: 'result',
                    id: event.id,
                    name: event.name,
                    result: event.result,
                    collapsed: true
                });
                break;
            case 'history':
                this.chatHistory = event.messages || [];
                break;
            case 'done':
                if (!msg.content?.trim() && this.pendingNavigation) {
                    msg.content = this.buildAgentNavigationSummary(this.pendingNavigation);
                }
                // Auto-collapse previous turns
                for (let i = 0; i < this.chatMessages.length - 1; i++) {
                    if (this.chatMessages[i].role === 'assistant') {
                        this.chatMessages[i].collapsed = true;
                    }
                }
                break;
            case 'error':
                msg.content += `\n\n**Error:** ${event.message}`;
                break;
        }
        this.scrollToBottom();
        this.cdr.detectChanges();
    }

    // ===== Navigation Handler =====
    public pendingNavigation: any = null;

    private buildAgentNavigationSummary(nav: any): string {
        if (!nav) return '';

        const lines = [
            `### 에이전트 실행 요약`,
            `- 분류 결과: **${nav.title || nav.page}**`,
            `- 선택 컬렉션: **${nav.collection || this.selectedCollection || '-'}**`
        ];

        if (nav.query) {
            lines.push(`- 핵심 키워드: **${nav.query}**`);
        }

        const entries = Object.entries(nav.params || {}).filter(([key, value]) => {
            return key !== 'collection' && value !== null && value !== undefined && String(value).trim().length > 0;
        });

        if (entries.length > 0) {
            lines.push(`- 전달 파라미터: ${entries.map(([key, value]) => `${key}=${value}`).join(', ')}`);
        }

        lines.push(`- 다음 단계: 해당 페이지로 이동해 동일한 컬렉션으로 바로 실행합니다.`);
        return lines.join('\n');
    }

    private handleToolResult(event: any) {
        if (event.name !== 'navigate_to_page') return;
        try {
            const data = JSON.parse(event.result);
            if (data.action === 'navigate') {
                const navigationCollection = data.collection || data.params?.collection || this.selectedCollection || '';
                if (navigationCollection) {
                    this.persistCollection(navigationCollection);
                }
                // 네비게이션 카드 상태 저장 (UI에서 표시용)
                this.pendingNavigation = {
                    page: data.page,
                    title: data.title_ko || data.page,
                    url: data.url,
                    tab: data.tab,
                    query: data.query,
                    params: data.params || {},
                    collection: navigationCollection
                };
                this.cdr.detectChanges();

                // queryParams 객체 구성
                const queryParams: any = {};
                if (data.tab) queryParams['tab'] = data.tab;
                if (data.query) queryParams['q'] = data.query;
                if (navigationCollection) queryParams['collection'] = navigationCollection;
                if (data.params) {
                    for (const [k, v] of Object.entries(data.params)) {
                        if (v !== null && v !== undefined && String(v).trim()) {
                            queryParams[k] = String(v);
                        }
                    }
                }
                const targetPath = data.url ? data.url.split('?')[0] : '/' + data.page;

                // Force fresh navigation: 루트로 갔다가 목표 페이지로 이동
                // → 같은 페이지에서도 ngOnInit이 다시 실행되어 파라미터가 적용됨
                setTimeout(async () => {
                    try {
                        await this.router.navigateByUrl('/', { skipLocationChange: true });
                        await this.router.navigate([targetPath], { queryParams });
                    } catch (e) {
                        // fallback: 직접 URL 이동
                        this.router.navigateByUrl(data.url || targetPath);
                    }
                    this.pendingNavigation = null;
                    this.cdr.detectChanges();
                }, 1800);
            }
        } catch (e) { }
    }

    public navigateNow() {
        if (!this.pendingNavigation) return;
        const nav = this.pendingNavigation;
        const queryParams: any = {};
        if (nav.tab) queryParams['tab'] = nav.tab;
        if (nav.query) queryParams['q'] = nav.query;
        if (nav.collection) queryParams['collection'] = nav.collection;
        if (nav.params) {
            for (const [k, v] of Object.entries(nav.params)) {
                if (v !== null && v !== undefined && String(v).trim()) {
                    queryParams[k] = String(v);
                }
            }
        }
        const targetPath = nav.url ? nav.url.split('?')[0] : '/' + nav.page;
        this.router.navigateByUrl('/', { skipLocationChange: true }).then(() => {
            this.router.navigate([targetPath], { queryParams });
        });
        this.pendingNavigation = null;
        this.cdr.detectChanges();
    }

    // ===== Cancel =====
    public cancelChat() {
        if (this.chatAbortController) {
            this.chatAbortController.abort();
            this.chatAbortController = null;
        }
        this.chatLoading = false;
    }

    // ===== Clear =====
    public clearChat() {
        this.chatMessages = [];
        this.chatHistory = [];
        this.chatAssistantIdx = -1;
        this.pendingNavigation = null;
    }

    // ===== Helpers =====
    public onKeydown(event: KeyboardEvent) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendChat();
        }
    }

    private scrollToBottom() {
        setTimeout(() => {
            if (this.chatBodyRef?.nativeElement) {
                this.chatBodyRef.nativeElement.scrollTop = this.chatBodyRef.nativeElement.scrollHeight;
            }
        }, 50);
    }

    public toggleCollapse(msg: any) {
        msg.collapsed = !msg.collapsed;
    }

    public toggleToolCollapse(tc: any) {
        tc.collapsed = !tc.collapsed;
    }

    public getToolIcon(name: string): string {
        const icons: any = {
            search_papers: '📄', recommend_topics: '💡', detect_research_gaps: '🔍',
            generate_hypothesis: '🧪', analyze_keywords: '🏷️', predict_process: '⚙️',
            analyze_parameter_effect: '📈', inverse_search: '🔄', surrogate_predict: '🎯',
            compare_diagnostics: '⚖️', search_anomaly: '⚠️', failure_reasoning: '🔧',
            extract_equations: '📐', search_equations: '🔢', extract_assumptions: '📋',
            build_theory_graph: '🌐', navigate_to_page: '🧭', get_collections: '📦'
        };
        return icons[name] || '🔨';
    }

    public getToolLabel(name: string): string {
        const labels: any = {
            search_papers: '논문 검색', recommend_topics: '주제 추천',
            detect_research_gaps: '연구 공백 탐지', generate_hypothesis: '가설 생성',
            analyze_keywords: '키워드 분석', predict_process: '공정 예측',
            analyze_parameter_effect: '파라미터 효과', inverse_search: '역탐색',
            surrogate_predict: '수치 예측', compare_diagnostics: '진단 비교',
            search_anomaly: '이상 검색', failure_reasoning: '고장 추론',
            extract_equations: '수식 추출', search_equations: '수식 검색',
            extract_assumptions: '가정 분석', build_theory_graph: '이론 그래프',
            navigate_to_page: '페이지 이동', get_collections: '컬렉션 목록'
        };
        return labels[name] || name;
    }

    public formatToolInput(input: any): string {
        if (!input) return '';
        const keys = Object.keys(input);
        return keys.map(k => `${k}: ${typeof input[k] === 'string' ? input[k] : JSON.stringify(input[k])}`).join(', ');
    }

    public parseToolResult(result: string): string {
        if (!result) return '';
        try {
            const parsed = JSON.parse(result);
            if (parsed.action === 'navigate') {
                const params = parsed.params || {};
                const paramStr = Object.keys(params).length > 0
                    ? ' | ' + Object.entries(params).map(([k, v]) => `${k}=${v}`).join(', ')
                    : '';
                return `📍 ${parsed.title_ko || parsed.page} → ${parsed.tab || ''}${paramStr}`;
            }
            if (typeof parsed === 'object') {
                // Summarize nicely
                if (parsed.total !== undefined) return `${parsed.total}건의 결과를 찾았습니다.`;
                if (parsed.results) return `${parsed.results.length || 0}건의 결과`;
                if (parsed.error) return `❌ ${parsed.error}`;
            }
        } catch (e) { }
        // Truncate long text
        if (result.length > 200) return result.slice(0, 200) + '...';
        return result;
    }
}
