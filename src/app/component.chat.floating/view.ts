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

    public robotProfile: any = {
        name: 'PLASMA-BOT PX-14',
        subtitle: '플라즈마 연구용 로봇 에이전트',
        tag: 'TRACE MODE'
    };

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

    private createAssistantMessage(question: string): any {
        return {
            role: 'assistant',
            content: '',
            toolCalls: [],
            collapsed: false,
            traceOpen: true,
            traceSteps: this.buildTraceSteps(question),
            pipelineComponents: this.buildAnswerPipeline(question),
            references: [],
            similaritySummary: '',
            currentLabel: '프롬프트 레이어를 구성하고 있습니다.',
            currentDescription: '시스템 프롬프트, 사용자 질문, 선택 컬렉션을 결합해 에이전트 실행 컨텍스트를 만들고 있습니다.',
            question,
            traceCategory: this.classifyQuestion(question),
            traceLanguage: this.detectLanguage(question),
            traceDifficulty: this.detectDifficulty(question)
        };
    }

    private buildTraceSteps(question: string): any[] {
        const category = this.classifyQuestion(question);
        const language = this.detectLanguage(question) === 'ko' ? '한국어' : '영어';
        const difficulty = this.detectDifficulty(question);
        const collection = this.selectedCollection || '미선택';

        return [
            { id: 1, title: '질문 수신', summary: '새로운 사용자 질문을 등록했습니다.', detail: this.truncate(question, 88), status: 'done' },
            { id: 2, title: '언어 판별', summary: `응답 언어를 ${language}로 결정했습니다.`, detail: `사용자 입력 기반으로 ${language} 응답을 준비합니다.`, status: 'done' },
            { id: 3, title: '도메인 분류', summary: `${category} 영역으로 분류했습니다.`, detail: '질문 유형을 8대 연구 기능 영역 중 하나로 매핑했습니다.', status: 'done' },
            { id: 4, title: '응답 수준 판정', summary: `${difficulty} 수준 응답이 필요합니다.`, detail: '질문 길이와 파라미터 밀도를 기준으로 응답 깊이를 결정했습니다.', status: 'done' },
            { id: 5, title: '검색 전략 수립', summary: '검색 전략과 도구 순서를 준비합니다.', detail: '핵심 키워드, 후속 도구, 최종 이동 페이지를 계획 중입니다.', status: 'running' },
            { id: 6, title: '컬렉션 확인', summary: `선택 컬렉션: ${collection}`, detail: '벡터 검색에 사용할 컬렉션과 문서 범위를 점검합니다.', status: this.selectedCollection ? 'done' : 'running' },
            { id: 7, title: '질의 확장', summary: '검색용 키워드로 질문을 확장합니다.', detail: '동의어, 공정명, 약어를 포함한 검색 질의를 구성합니다.', status: 'pending' },
            { id: 8, title: '참고 문헌 검색', summary: '유사 문헌을 검색합니다.', detail: '벡터 DB와 도구를 사용해 관련 논문을 찾습니다.', status: 'pending' },
            { id: 9, title: '문헌 재정렬', summary: '유사도 기준으로 결과를 재정렬합니다.', detail: '상위 후보를 정렬해 우선 검토 대상을 고릅니다.', status: 'pending' },
            { id: 10, title: '핵심 근거 추출', summary: '근거 문장과 조건을 추출합니다.', detail: '문헌 본문에서 핵심 문장, 조건, 유사도를 정리합니다.', status: 'pending' },
            { id: 11, title: '추가 도구 실행', summary: '필요 시 분석 도구를 실행합니다.', detail: '추천, 예측, 가설, 진단 등 후속 도구 실행 여부를 판단합니다.', status: 'pending' },
            { id: 12, title: '결과 통합 요약', summary: '도구 결과를 최종 답변으로 통합합니다.', detail: '문헌과 도구 결과를 사람이 읽기 쉬운 설명으로 정리합니다.', status: 'pending' },
            { id: 13, title: '검증 및 신뢰도 점검', summary: '응답 품질과 신뢰도를 점검합니다.', detail: '근거 수, 유사도, 누락 파라미터를 기준으로 응답을 검토합니다.', status: 'pending' },
            { id: 14, title: '최종 안내 및 핸드오프', summary: '관련 페이지로 연결합니다.', detail: '필요 시 적절한 페이지와 탭으로 이동을 준비합니다.', status: 'pending' }
        ];
    }

    private buildAnswerPipeline(question: string): any[] {
        const language = this.detectLanguage(question) === 'ko' ? '한국어' : '영어';
        const category = this.classifyQuestion(question);
        const difficulty = this.detectDifficulty(question);
        const historyTurns = (this.chatHistory || []).filter((item: any) => item.role === 'user' || item.role === 'assistant').length;
        const collection = this.selectedCollection || '미선택';

        return [
            {
                key: 'prompt',
                title: '프롬프트',
                icon: '🧠',
                status: 'running',
                summary: '시스템 프롬프트와 사용자 질문을 결합합니다.',
                detail: `${language} 응답 · ${category} 분류 후보 · 선택 컬렉션 ${collection}`,
                metaBadges: [language, this.selectedCollection ? `컬렉션 ${this.selectedCollection}` : '컬렉션 미선택']
            },
            {
                key: 'orchestrator',
                title: '오케스트레이터',
                icon: '🗺️',
                status: 'pending',
                summary: '실행 순서와 도구 계획을 수립합니다.',
                detail: `${difficulty} 수준으로 응답 깊이를 조정하고 후속 단계를 계획합니다.`,
                metaBadges: [category, difficulty],
                plan: []
            },
            {
                key: 'tools',
                title: '도구',
                icon: '🧰',
                status: 'pending',
                summary: '검색·분석·이동 도구를 실행합니다.',
                detail: '도구 실행을 대기 중입니다.',
                metaBadges: ['0개 실행']
            },
            {
                key: 'memory',
                title: '메모리',
                icon: '🗂️',
                status: 'pending',
                summary: '대화 이력과 선택 컬렉션을 컨텍스트에 주입합니다.',
                detail: `이전 대화 ${historyTurns}턴과 현재 컬렉션 상태를 기반으로 메모리를 구성합니다.`,
                metaBadges: [historyTurns > 0 ? `이력 ${historyTurns}턴` : '새 대화', `컬렉션 ${collection}`]
            },
            {
                key: 'streaming',
                title: '스트리밍 UI',
                icon: '📡',
                status: 'pending',
                summary: 'SSE 이벤트로 실행 과정을 화면에 표시합니다.',
                detail: '실시간 이벤트 스트림 연결을 대기 중입니다.',
                metaBadges: ['SSE 대기']
            }
        ];
    }

    // ===== Send Message =====
    public async sendChat(text?: string) {
        const message = (text || this.chatInput || '').trim();
        if (!message || this.chatLoading) return;

        this.collapsePreviousAssistantTurns();
        this.chatMessages.push({ role: 'user', content: message });
        this.chatInput = '';
        this.chatLoading = true;

        const assistantMsg: any = this.createAssistantMessage(message);
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
            case 'pipeline':
                this.applyPipelineEvent(msg, event);
                break;
            case 'text':
                msg.content += event.content || '';
                this.updatePipelineComponent(msg, 'streaming', 'running', 'LLM 응답을 스트리밍 UI로 전달하고 있습니다.', ['응답 스트리밍']);
                this.updateTraceStep(msg, 12, 'running', '도구 결과와 참고 문헌을 바탕으로 최종 답변을 작성하고 있습니다.');
                break;
            case 'tool_use':
                msg.toolCalls.push({
                    type: 'use',
                    id: event.id,
                    name: event.name,
                    input: event.input,
                    collapsed: true
                });
                this.applyToolUseTrace(msg, event);
                break;
            case 'tool_result':
                this.handleToolResult(event);
                msg.toolCalls.push({
                    type: 'result',
                    id: event.id,
                    name: event.name,
                    result: event.result,
                    collapsed: true
                });
                this.applyToolResultTrace(msg, event);
                break;
            case 'history':
                this.chatHistory = event.messages || [];
                break;
            case 'done':
                if (!msg.content?.trim() && this.pendingNavigation) {
                    msg.content = this.buildAgentNavigationSummary(this.pendingNavigation);
                }
                this.finalizeTrace(msg);
                this.collapsePreviousAssistantTurns(this.chatAssistantIdx);
                break;
            case 'error':
                msg.content += `\n\n**Error:** ${event.message}`;
                this.markTraceError(msg, event.message || '에이전트 처리 중 오류가 발생했습니다.');
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

    private collapsePreviousAssistantTurns(exceptIdx: number = -1) {
        for (let i = 0; i < this.chatMessages.length; i++) {
            const item = this.chatMessages[i];
            if (item.role !== 'assistant') continue;
            if (i === exceptIdx) continue;
            item.collapsed = true;
            item.traceOpen = false;
        }
    }

    private applyToolUseTrace(msg: any, event: any) {
        const input = event.input || {};
        const name = event.name;
        this.updatePipelineComponent(msg, 'tools', 'running', `${this.getToolLabel(name)} 도구를 실행하고 있습니다.`, [`${msg.toolCalls.filter((item: any) => item.type === 'use').length}개 실행`, this.getToolLabel(name)]);
        this.updatePipelineComponent(msg, 'orchestrator', 'done', '오케스트레이터가 필요한 도구 순서를 결정하고 실행으로 넘겼습니다.');

        if (name === 'get_collections') {
            this.updateTraceStep(msg, 6, 'running', '사용 가능한 컬렉션 목록과 문서 규모를 확인하고 있습니다.');
            return;
        }

        if (name === 'search_papers') {
            this.updateTraceStep(msg, 5, 'done', '질문 목적에 맞는 검색 전략과 후속 흐름을 수립했습니다.');
            this.updateTraceStep(msg, 7, 'running', `검색 질의를 확장하고 있습니다. ${input.query || msg.question}`);
            this.updateTraceStep(msg, 8, 'running', '벡터 데이터베이스에서 관련 참고 문헌을 검색하고 있습니다.');
            return;
        }

        if (name === 'navigate_to_page') {
            this.updateTraceStep(msg, 14, 'running', '최종 결과와 연동할 페이지/탭을 확정하고 있습니다.');
            return;
        }

        this.updateTraceStep(msg, 11, 'running', `${this.getToolLabel(name)} 도구를 실행하고 있습니다.`);
    }

    private applyToolResultTrace(msg: any, event: any) {
        const name = event.name;
        const executedCount = msg.toolCalls.filter((item: any) => item.type === 'result').length;

        if (name === 'get_collections') {
            this.updatePipelineComponent(msg, 'memory', 'done', '컬렉션 메타데이터를 메모리 컨텍스트에 반영했습니다.', [`컬렉션 ${this.selectedCollection || '미선택'}`]);
            this.updateTraceStep(msg, 6, 'done', '검색 가능한 컬렉션 메타데이터를 확보했습니다.');
            return;
        }

        if (name === 'search_papers') {
            const refs = this.parseSearchPapersResults(event.result);
            msg.references = refs;
            msg.similaritySummary = this.buildSimilaritySummary(refs);
            this.updatePipelineComponent(msg, 'tools', 'running', refs.length > 0 ? `논문 검색과 근거 추출을 완료했습니다. (${refs.length}건)` : '논문 검색 결과를 정리했습니다.', [`${executedCount}개 완료`, refs.length > 0 ? `근거 ${refs.length}건` : '근거 대기']);
            this.updatePipelineComponent(msg, 'memory', 'done', refs.length > 0 ? '검색 결과를 세션 메모리에 반영했습니다.' : '검색 결과를 메모리와 동기화했습니다.', [msg.similaritySummary || '유사도 요약 없음']);

            this.updateTraceStep(msg, 7, 'done', '질문을 연구 검색용 키워드와 도메인 표현으로 확장했습니다.');
            this.updateTraceStep(msg, 8, 'done', refs.length > 0 ? `${refs.length}건의 참고 문헌 후보를 검색했습니다.` : '검색 결과를 확보했습니다.');
            this.updateTraceStep(msg, 9, 'done', refs.length > 0 ? '유사도 기준 상위 결과를 정렬했습니다.' : '검색 결과를 정렬했습니다.');
            this.updateTraceStep(msg, 10, 'done', refs.length > 0 ? '참고 문헌, 본문 요약, 유사도 정보를 추출했습니다.' : '핵심 근거를 정리했습니다.');
            this.updateTraceStep(msg, 11, 'running', '추가 분석 도구 실행 여부를 검토하고 있습니다.');
            return;
        }

        if (name === 'navigate_to_page') {
            this.updatePipelineComponent(msg, 'orchestrator', 'done', '오케스트레이터가 후속 페이지와 실행 컨텍스트를 확정했습니다.');
            this.updatePipelineComponent(msg, 'tools', 'done', '도구 실행과 페이지 핸드오프까지 완료했습니다.', [`${executedCount}개 완료`, '핸드오프 준비']);
            this.updateTraceStep(msg, 14, 'done', '최종 결과를 이어서 실행할 페이지로 연결했습니다.');
            return;
        }

        this.updatePipelineComponent(msg, 'tools', 'running', `${this.getToolLabel(name)} 결과를 반영해 추가 통합을 진행하고 있습니다.`, [`${executedCount}개 완료`, this.getToolLabel(name)]);
        this.updateTraceStep(msg, 11, 'done', `${this.getToolLabel(name)} 결과를 확보했습니다.`);
        this.updateTraceStep(msg, 12, 'running', '도구 결과를 읽기 쉬운 최종 답변으로 정리하고 있습니다.');
    }

    private finalizeTrace(msg: any) {
        this.finishRunningStep(msg, 5, '검색 전략과 응답 흐름 구성을 완료했습니다.');
        this.finishRunningStep(msg, 6, '컬렉션과 문서 범위 점검을 완료했습니다.');
        this.finishRunningStep(msg, 7, '검색 질의 확장을 완료했습니다.');
        this.finishRunningStep(msg, 8, '참고 문헌 검색을 완료했습니다.');
        this.finishRunningStep(msg, 9, '문헌 우선순위 정렬을 완료했습니다.');
        this.finishRunningStep(msg, 10, '핵심 근거 추출을 완료했습니다.');
        this.finishRunningStep(msg, 11, '필요한 추가 도구 실행을 완료했습니다.');
        this.updateTraceStep(msg, 12, 'done', msg.content?.trim() ? '최종 답변 초안 생성을 완료했습니다.' : '요약 응답 생성을 완료했습니다.');
        this.updateTraceStep(msg, 13, 'done', msg.references?.length > 0
            ? `참고 문헌 ${msg.references.length}건과 유사도 요약을 기준으로 답변을 점검했습니다.`
            : '도구 결과와 누락 파라미터를 점검했습니다.');

        const step14 = this.findTraceStep(msg, 14);
        if (step14 && step14.status === 'pending') {
            this.updateTraceStep(msg, 14, this.pendingNavigation ? 'done' : 'skipped', this.pendingNavigation
                ? '관련 페이지로 이어지는 핸드오프를 준비했습니다.'
                : '이번 턴은 페이지 이동 없이 답변만 제공합니다.');
        }

        for (const step of msg.traceSteps) {
            if (step.status === 'pending') {
                step.status = 'skipped';
            }
        }

        this.finalizePipeline(msg);
        this.syncCurrentTrace(msg);
    }

    private markTraceError(msg: any, detail: string) {
        const running = msg.traceSteps.find((step: any) => step.status === 'running');
        if (running) {
            running.status = 'error';
            running.detail = detail;
        } else {
            this.updateTraceStep(msg, 12, 'error', detail);
        }
        const runningPipeline = (msg.pipelineComponents || []).find((item: any) => item.status === 'running');
        if (runningPipeline) {
            runningPipeline.status = 'error';
            runningPipeline.detail = detail;
        }
    }

    private updateTraceStep(msg: any, stepId: number, status: string, detail?: string) {
        const step = this.findTraceStep(msg, stepId);
        if (!step) return;
        if (step.status === 'done' && status === 'running') return;
        if (step.status === 'error' && status !== 'error') return;
        step.status = status;
        if (detail) step.detail = detail;
        this.syncCurrentTrace(msg);
    }

    private finishRunningStep(msg: any, stepId: number, detail: string) {
        const step = this.findTraceStep(msg, stepId);
        if (!step) return;
        if (step.status === 'running' || step.status === 'pending') {
            step.status = 'done';
            step.detail = detail;
        }
    }

    private findTraceStep(msg: any, stepId: number): any {
        return (msg.traceSteps || []).find((step: any) => step.id === stepId) || null;
    }

    private applyPipelineEvent(msg: any, event: any) {
        this.updatePipelineComponent(msg, event.component, event.status || 'pending', event.detail || event.summary || '', event.metaBadges || this.buildPipelineBadges(event.component, event.meta || {}), event.plan || event.meta?.plan || []);

        if (event.component === 'memory' && event.meta?.memoryNote) {
            msg.currentLabel = '메모리 컨텍스트 반영';
            msg.currentDescription = event.meta.memoryNote;
        }

        if (event.component === 'orchestrator' && event.detail) {
            msg.currentLabel = '오케스트레이터 계획 수립';
            msg.currentDescription = event.detail;
        }
    }

    private updatePipelineComponent(msg: any, componentKey: string, status: string, detail?: string, metaBadges?: string[], plan?: string[]) {
        const component = this.findPipelineComponent(msg, componentKey);
        if (!component) return;
        component.status = status;
        if (detail) component.detail = detail;
        if (metaBadges && metaBadges.length > 0) component.metaBadges = metaBadges;
        if (plan) component.plan = plan;
    }

    private findPipelineComponent(msg: any, componentKey: string): any {
        return (msg.pipelineComponents || []).find((item: any) => item.key === componentKey) || null;
    }

    private buildPipelineBadges(component: string, meta: any): string[] {
        if (!meta) return [];

        switch (component) {
            case 'prompt':
                return [meta.language, meta.model, meta.collection].filter(Boolean);
            case 'orchestrator':
                return [meta.category, meta.page, meta.tab].filter(Boolean);
            case 'tools':
                return [meta.tool_name ? this.getToolLabel(meta.tool_name) : '', meta.tool_count ? `${meta.tool_count}개 실행` : ''].filter(Boolean);
            case 'memory':
                return [
                    Number.isFinite(meta.history_turns) ? `이력 ${meta.history_turns}턴` : '',
                    meta.collection ? `컬렉션 ${meta.collection}` : '',
                    meta.last_topic ? `최근 ${this.truncate(meta.last_topic, 24)}` : ''
                ].filter(Boolean);
            case 'streaming':
                return [meta.transport || 'SSE', meta.mode || '실시간 UI'].filter(Boolean);
            default:
                return [];
        }
    }

    private finalizePipeline(msg: any) {
        this.updatePipelineComponent(msg, 'prompt', 'done', '시스템 프롬프트와 사용자 질문이 최종 응답 생성에 반영되었습니다.');
        this.updatePipelineComponent(msg, 'memory', 'done', (msg.references?.length > 0)
            ? `대화 이력, 선택 컬렉션, 검색 근거 ${msg.references.length}건을 메모리 컨텍스트로 사용했습니다.`
            : '대화 이력과 선택 컬렉션을 메모리 컨텍스트로 사용했습니다.');
        this.updatePipelineComponent(msg, 'orchestrator', 'done', '오케스트레이터가 질문 분류, 도구 순서, 핸드오프를 조정했습니다.');

        const tools = this.findPipelineComponent(msg, 'tools');
        if (tools && tools.status === 'pending') {
            this.updatePipelineComponent(msg, 'tools', 'skipped', '이번 턴은 추가 도구 없이 답변을 생성했습니다.', ['도구 미사용']);
        } else if (tools && tools.status === 'running') {
            this.updatePipelineComponent(msg, 'tools', 'done', '도구 결과를 최종 답변과 핸드오프에 반영했습니다.', tools.metaBadges);
        }

        this.updatePipelineComponent(msg, 'streaming', 'done', '스트리밍 UI가 단계, 도구, 최종 답변을 모두 화면에 반영했습니다.', ['SSE 완료', '최종 답변 반영']);
    }

    private syncCurrentTrace(msg: any) {
        const current = this.getCurrentTraceStep(msg);
        msg.currentLabel = current?.title || '에이전트 실행';
        msg.currentDescription = current?.detail || current?.summary || '실행 상태를 갱신 중입니다.';
    }

    public getCurrentTraceStep(msg: any): any {
        const running = (msg.traceSteps || []).find((step: any) => step.status === 'running');
        if (running) return running;
        const error = (msg.traceSteps || []).find((step: any) => step.status === 'error');
        if (error) return error;
        const reversed = [...(msg.traceSteps || [])].reverse();
        return reversed.find((step: any) => step.status === 'done') || (msg.traceSteps || [])[0] || null;
    }

    public getPipelineComponents(msg: any): any[] {
        return msg.pipelineComponents || [];
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
        if (!msg.collapsed) {
            this.collapsePreviousAssistantTurns(this.chatMessages.indexOf(msg));
        }
    }

    public toggleTrace(msg: any) {
        msg.traceOpen = !msg.traceOpen;
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

    public getTraceStatusLabel(status: string): string {
        const map: any = {
            pending: '대기',
            running: '진행 중',
            done: '완료',
            skipped: '건너뜀',
            error: '오류'
        };
        return map[status] || status;
    }

    public getTraceStatusClasses(status: string): string {
        const map: any = {
            pending: 'bg-slate-100 text-slate-500 border-slate-200',
            running: 'bg-cyan-50 text-cyan-700 border-cyan-200',
            done: 'bg-emerald-50 text-emerald-700 border-emerald-200',
            skipped: 'bg-amber-50 text-amber-700 border-amber-200',
            error: 'bg-rose-50 text-rose-700 border-rose-200'
        };
        return map[status] || map.pending;
    }

    public getTraceStepClasses(step: any): string {
        const map: any = {
            pending: 'border-slate-200 bg-white',
            running: 'border-cyan-300 bg-cyan-50/80 shadow-sm shadow-cyan-100',
            done: 'border-emerald-200 bg-emerald-50/70',
            skipped: 'border-amber-200 bg-amber-50/70',
            error: 'border-rose-200 bg-rose-50/80'
        };
        return map[step.status] || map.pending;
    }

    public getTraceStepIcon(step: any): string {
        const map: any = {
            pending: '○',
            running: '◔',
            done: '✓',
            skipped: '↷',
            error: '⚠'
        };
        return map[step.status] || '○';
    }

    public getCompletedTraceCount(msg: any): number {
        return (msg.traceSteps || []).filter((step: any) => step.status === 'done').length;
    }

    public getCollapsedPreview(msg: any): string {
        const refs = msg.references?.length ? ` · 참고문헌 ${msg.references.length}건` : '';
        const text = msg.content?.trim() || msg.currentDescription || '결과 보기';
        return `${this.getCompletedTraceCount(msg)}/14 단계 완료${refs} · ${this.truncate(text, 54)}`;
    }

    public formatScore(score: number): string {
        return Number.isFinite(score) ? score.toFixed(4) : '-';
    }

    private parseSearchPapersResults(result: string): any[] {
        if (!result || typeof result !== 'string') return [];
        const refs: any[] = [];
        const regex = /--- Result (\d+) \(score: ([\d.]+)\) ---\nFile: (.+?) \| Chunk: (.+?)\nText: ([\s\S]*?)(?=\n--- Result|$)/g;
        let match;
        while ((match = regex.exec(result)) !== null) {
            refs.push({
                rank: Number(match[1]),
                score: Number(match[2]),
                filename: match[3],
                chunk: match[4],
                excerpt: (match[5] || '').trim()
            });
        }
        return refs.slice(0, 5);
    }

    private buildSimilaritySummary(refs: any[]): string {
        if (!refs || refs.length === 0) {
            return '유사도 요약 없음';
        }
        const scores = refs.map((item) => Number(item.score) || 0);
        const avg = scores.reduce((sum, value) => sum + value, 0) / scores.length;
        const max = Math.max(...scores);
        return `상위 ${refs.length}건 평균 유사도 ${avg.toFixed(4)} · 최고 ${max.toFixed(4)}`;
    }

    private detectLanguage(question: string): string {
        return /[가-힣]/.test(question) ? 'ko' : 'en';
    }

    private detectDifficulty(question: string): string {
        const score = [/[0-9]/.test(question), question.length > 30, /비교|예측|가설|분석|추론|recommend|predict/i.test(question)]
            .filter(Boolean).length;
        if (score >= 3) return '심층 분석';
        if (score === 2) return '표준 분석';
        return '빠른 응답';
    }

    private classifyQuestion(question: string): string {
        const q = question.toLowerCase();
        if (/그래프|차트|통계|피팅|scatter|plot/i.test(q)) return '데이터 분석';
        if (/실험|doe|레시피|노트|조건 기록/i.test(q)) return '실험 관리';
        if (/디바이|주파수|paschen|계산|자이로/i.test(q)) return '플라즈마 계산기';
        if (/수식|방정식|가정|boltzmann|theory|이론/i.test(q)) return '이론 연구';
        if (/oes|랭뮤어|이상|고장|진단|스펙트럼/i.test(q)) return '진단 분석';
        if (/예측|etch|식각|증착|rf|pressure|power|icp/i.test(q)) return '공정 예측';
        if (/프로젝트|협업|토론|activity|공유/i.test(q)) return '협업';
        return '주제 발굴';
    }

    private truncate(text: string, limit: number = 60): string {
        if (!text) return '';
        return text.length > limit ? `${text.slice(0, limit)}...` : text;
    }
}
