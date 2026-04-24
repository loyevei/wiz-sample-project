import { OnInit, OnDestroy, ViewChild, ElementRef, ChangeDetectorRef } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { Router } from '@angular/router';

declare const wiz: any;

export class Component implements OnInit, OnDestroy {
    private readonly collectionStorageKey: string = 'plasma.selectedCollection';
    private readonly collectionChangeEventName: string = 'plasma-collection-changed';
    private readonly typingChunkSize: number = 2;
    private readonly typingIntervalMs: number = 18;
    private collectionChangeListener: any = null;

    public chatInput: string = '';
    public chatLoading: boolean = false;
    public chatMessages: any[] = [];
    public chatHistory: any[] = [];
    private chatAbortController: AbortController | null = null;
    private chatAssistantIdx: number = -1;
    private typingTimers: WeakMap<any, any> = new WeakMap();
    private journeyRevealTimers: WeakMap<any, any> = new WeakMap();
    private autoNavigateAfterAnswer: boolean = false;

    public collections: any[] = [];
    public selectedCollection: string = '';
    public collectionsLoading: boolean = false;
    public collectionSelected: boolean = false;

    public robotProfile: any = {
        name: 'KFE bot',
        subtitle: '플라즈마 연구 오케스트레이션 에이전트',
        tag: 'AGENT'
    };

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
        this.collectionChangeListener = async (event: any) => {
            const nextCollection = String(event?.detail?.collection || '').trim();
            const deletedCollection = String(event?.detail?.deletedCollection || '').trim();
            if (deletedCollection) {
                const previousCollection = this.selectedCollection;
                await this.loadCollections();
                this.collectionSelected = !!this.selectedCollection;
                if (previousCollection !== this.selectedCollection) {
                    this.resetConversationState();
                }
                this.cdr.detectChanges();
                return;
            }
            if (!nextCollection || nextCollection === this.selectedCollection) return;
            if (!this.collections.find((c: any) => c.name === nextCollection)) {
                await this.loadCollections();
                if (!this.collections.find((c: any) => c.name === nextCollection)) return;
            }
            this.selectedCollection = nextCollection;
            this.collectionSelected = !!nextCollection;
            this.persistCollection(nextCollection);
            this.resetConversationState();
            this.cdr.detectChanges();
        };
        window.addEventListener(this.collectionChangeEventName, this.collectionChangeListener as EventListener);
        await this.loadCollections();
        await this.service.render();
    }

    public ngOnDestroy() {
        if (this.collectionChangeListener) {
            window.removeEventListener(this.collectionChangeEventName, this.collectionChangeListener as EventListener);
            this.collectionChangeListener = null;
        }
        this.clearTypingAnimations();
        this.cancelChat();
    }

    // ===== Collection Management =====
    private getStoredCollection(): string {
        try { return localStorage.getItem(this.collectionStorageKey) || ''; } catch (e) { return ''; }
    }

    private persistCollection(name: string) {
        try {
            if (name && name.trim()) localStorage.setItem(this.collectionStorageKey, name);
            else localStorage.removeItem(this.collectionStorageKey);
        } catch (e) { }
    }

    public async loadCollections() {
        this.collectionsLoading = true;
        this.cdr.detectChanges();
        try {
            let code = 0; let data: any = {};
            try {
                const response = await fetch(`/wiz/api/page.embedding/collections`, { method: 'POST', credentials: 'same-origin' });
                const payload = await response.json();
                code = payload.code; data = payload.data || {};
                if (code !== 200) { const res = await wiz.call('collections'); code = res.code; data = res.data || {}; }
            } catch (e) { const res = await wiz.call('collections'); code = res.code; data = res.data || {}; }
            if (code === 200) {
                this.collections = (data.collections || []).sort((a: any, b: any) => (b.total_docs || 0) - (a.total_docs || 0));
                const stored = this.getStoredCollection();
                if (stored && this.collections.find((c: any) => c.name === stored)) this.selectedCollection = stored;
                if (this.selectedCollection && !this.collections.find((c: any) => c.name === this.selectedCollection)) this.selectedCollection = '';
                if (this.collections.length > 0 && !this.selectedCollection) this.selectedCollection = this.collections[0].name;
                if (this.selectedCollection) this.persistCollection(this.selectedCollection);
                else this.persistCollection('');
                this.collectionSelected = this.collections.length === 1 ? true : !!this.selectedCollection;
            }
        } catch (e) { }
        this.collectionsLoading = false;
        this.cdr.detectChanges();
    }

    public selectCollection(name: string) {
        this.syncSelectedCollection(name);
        this.collectionSelected = true;
        this.resetConversationState();
        this.cdr.detectChanges();
        setTimeout(() => { if (this.chatInputRef?.nativeElement) this.chatInputRef.nativeElement.focus(); }, 200);
    }

    public getSelectedCollectionInfo(): any {
        return this.collections.find((c: any) => c.name === this.selectedCollection) || null;
    }

    public changeCollection() {
        this.collectionSelected = false;
        this.pendingNavigation = null;
        this.cdr.detectChanges();
    }

    private syncSelectedCollection(name: string) {
        const n = String(name || '').trim();
        this.selectedCollection = n;
        this.persistCollection(n);
        window.dispatchEvent(new CustomEvent(this.collectionChangeEventName, { detail: { collection: n, source: 'agent-page' } }));
    }

    private getActiveCollection(preferred?: string): string {
        const n = String(preferred || '').trim();
        if (n) return n;
        return String(this.selectedCollection || this.getStoredCollection() || '').trim();
    }

    private resetConversationState() {
        this.cancelChat();
        this.clearTypingAnimations();
        this.chatMessages = [];
        this.chatHistory = [];
        this.chatAssistantIdx = -1;
        this.pendingNavigation = null;
        this.autoNavigateAfterAnswer = false;
    }

    // ===== Assistant Message Factory =====
    private createAssistantMessage(question: string, collection?: string): any {
        const activeCollection = this.getActiveCollection(collection);
        return {
            role: 'assistant', content: '', previewContent: '현재까지 핵심 포인트를 정리하고 있습니다.',
            toolCalls: [],
            executionPlan: this.buildPendingExecutionPlan(question, activeCollection),
            reasoningLogs: [
                { kind: 'question', status: 'done', title: '질문 접수', detail: question },
                { kind: 'orchestrator', status: 'running', title: '답변 경로 계산', detail: '질문을 어떤 페이지와 결과 흐름으로 풀지 정리하고 있습니다.' }
            ],
            collapsed: false, traceOpen: true,
            traceSteps: this.buildPendingTraceSteps(),
            answerQuality: this.buildAnswerQuality(question),
            references: [], similaritySummary: '',
            currentLabel: '답변 경로 계산',
            currentDescription: '백엔드가 질문을 어떤 페이지와 결과 흐름으로 풀지 정리하고 있습니다.',
            question, renderedContent: '', typingActive: false, typingTarget: '',
            journeyRevealCount: 1, traceCompleted: false,
            cardVisibility: { navigation: false, pageResult: false, quality: false, answer: false, evidence: false },
            cardRevealPending: {},
            pageResultReady: false, qualityReady: false, answerReady: false, evidenceReady: false,
            traceCategory: '분류 중', traceLanguage: this.detectLanguage(question), traceDifficulty: '판정 중',
            pageResultCard: this.buildPendingPageResultCard(question),
            navigationCard: this.buildPendingNavigationCard(),
            evidenceItems: [], evidenceOpen: false
        };
    }

    private buildPendingTraceSteps(): any[] {
        return [
            { id: 1, title: '질문 접수', summary: '질문을 등록했습니다.', detail: '백엔드 에이전트로 요청을 전달했습니다.', status: 'done' },
            { id: 2, title: '답변 경로 계산', summary: '실행 계획을 기다립니다.', detail: '백엔드가 실제 도메인 분류, 페이지 선정, 결과 추출 순서를 계산 중입니다.', status: 'running' }
        ];
    }

    private buildPendingExecutionPlan(question: string, collection?: string): any {
        const c = this.getActiveCollection(collection);
        return { question, category: '분류 중', page: '-', tab: '-',
            goal: '실제 페이지 결과를 근거로 최종답변과 handoff를 완성합니다.',
            goalStatus: 'running', goalSummary: '목표 달성 전까지 부족한 항목을 반복 점검합니다.', agentClusters: [],
            currentCluster: 'planner', allowedTools: [], evaluationStatus: 'pending',
            evaluationSummary: '각 cluster 실행 뒤 결과 품질을 평가합니다.',
            recoveryStrategy: '', recoveryHint: '', recoveryQuery: '', recoveryParams: {}, keywords: [], recommendedTools: [],
            params: {}, collection: c,
            planLines: ['질문을 분류하고, 맞는 페이지 결과를 먼저 읽은 뒤 한국어 최종답변으로 정리합니다.'],
            pageResultSummary: '', handoffSummary: '' };
    }

    private buildAnswerQuality(question: string): any {
        const d = this.estimateDifficulty(question);
        return { stage: 'pending', detail: '질문 유형과 근거 수집 범위를 점검하고 있습니다.',
            answerStyle: d === '심층 분석' ? '근거 통합 응답' : '구조화 응답', confidence: '분석 중',
            evidenceCount: 0, avgScore: null, synthesisPoints: [], verificationChecks: [], sources: [], llmUsed: false };
    }

    private buildPendingPageResultCard(question: string): any {
        return { loading: true, page: '결정 중', tab: '탭 분석 중', query: question || '', paramsText: '',
            summary: '질문에 맞는 페이지를 고른 뒤 실제 페이지 결과를 먼저 읽고 있습니다.',
            evidenceLines: ['질문 키워드와 인자값을 페이지 실행용으로 정리 중입니다.', '변경된 컬렉션 기준으로 검색 결과를 확보할 예정입니다.'] };
    }

    private buildPendingNavigationCard(): any {
        return { loading: true, skipped: false, title: '페이지 handoff 준비 중',
            summary: '질문에 맞는 페이지와 탭을 계산하고 있습니다.', actionLabel: '준비 중' };
    }

    private updatePreviewContent(msg: any, ...candidates: any[]): string {
        for (const c of candidates) { const t = String(c || '').trim(); if (t) { msg.previewContent = t; return t; } }
        return String(msg?.previewContent || '');
    }

    private patchPageResultCard(msg: any, patch: any = {}): any {
        msg.pageResultCard = { ...(msg.pageResultCard || this.buildPendingPageResultCard(msg?.question || '')), ...(patch || {}) };
        return msg.pageResultCard;
    }

    private patchNavigationCard(msg: any, patch: any = {}): any {
        msg.navigationCard = { ...(msg.navigationCard || this.buildPendingNavigationCard()), ...(patch || {}) };
        return msg.navigationCard;
    }

    private revealCard(msg: any, key: string, delay: number = 0) {
        if (!msg) return;
        msg.cardVisibility = msg.cardVisibility || {};
        msg.cardRevealPending = msg.cardRevealPending || {};
        if (msg.cardVisibility[key] || msg.cardRevealPending[key]) return;
        const apply = () => { msg.cardVisibility[key] = true; msg.cardRevealPending[key] = false; this.cdr.detectChanges(); this.syncCardSequence(msg); };
        if (delay <= 0) { apply(); return; }
        msg.cardRevealPending[key] = true;
        setTimeout(apply, delay);
    }

    private syncCardSequence(msg: any) {
        if (!msg) return;
        const vis = msg.cardVisibility || {};
        const readyCards = [
            { key: 'navigation', ready: Boolean(msg.navigationCard && !msg.navigationCard.loading) || Boolean(this.pendingNavigation && msg.navigationCard && !msg.navigationCard.loading), delay: 60 },
            { key: 'pageResult', ready: Boolean(msg.pageResultReady || (msg.pageResultCard && !msg.pageResultCard.loading)), delay: 120 },
            { key: 'quality', ready: Boolean(msg.qualityReady), delay: 100 },
            { key: 'answer', ready: Boolean(msg.answerReady), delay: 80 },
            { key: 'evidence', ready: Boolean(msg.evidenceReady), delay: 140 },
        ];
        let stagger = 0;
        for (const card of readyCards) {
            if (card.ready && !vis[card.key]) { this.revealCard(msg, card.key, card.delay + stagger); stagger += 80; }
        }
    }

    public shouldRenderNavigationCard(msg: any): boolean { return Boolean(msg?.cardVisibility?.navigation && (msg?.navigationCard || this.pendingNavigation)); }
    public shouldRenderPageResultCard(msg: any): boolean { return Boolean(msg?.cardVisibility?.pageResult && msg?.pageResultCard && (msg.pageResultCard.page || msg.pageResultCard.loading)); }
    public shouldRenderAnswerCard(msg: any): boolean { return Boolean(msg?.cardVisibility?.answer && (msg?.content || msg?.previewContent || msg?.typingActive)); }
    public shouldRenderQualityCard(msg: any): boolean { return Boolean(msg?.cardVisibility?.quality); }
    public shouldRenderEvidenceCard(msg: any): boolean { return Boolean(msg?.cardVisibility?.evidence && msg?.evidenceItems?.length > 0); }

    public getNextPendingCards(msg: any): Array<{ key: string, icon: string, label: string }> {
        if (!msg || msg.traceCompleted) return [];
        const vis = msg?.cardVisibility || {};
        return [
            { key: 'navigation', icon: '🧭', label: '페이지 이동' },
            { key: 'pageResult', icon: '🧾', label: '실행 결과' },
            { key: 'answer', icon: '🤖', label: '최종 답변' },
            { key: 'quality', icon: '🧪', label: '품질 분석' },
            { key: 'evidence', icon: '📚', label: '근거 문헌' },
        ].filter(c => !vis[c.key]).slice(0, 2);
    }

    public getCardStageChips(msg: any): Array<{ label: string, icon: string, status: string }> {
        const visible = msg?.cardVisibility || {};
        const pending = msg?.cardRevealPending || {};
        return [
            { key: 'navigation', label: '페이지 이동', icon: '🧭' },
            { key: 'pageResult', label: '실행 결과', icon: '🧾' },
            { key: 'answer', label: '최종 답변', icon: '🤖' },
            { key: 'quality', label: '품질 분석', icon: '🧪' },
            { key: 'evidence', label: '근거 문헌', icon: '📚' },
        ].map((s: any) => ({ ...s, status: visible[s.key] ? 'done' : pending[s.key] ? 'running' : 'pending' }));
    }

    public getCardStageChipClasses(status: string): string {
        const m: any = { pending: 'border-slate-200 bg-slate-50 text-slate-400', running: 'border-cyan-200 bg-cyan-50 text-cyan-700', done: 'border-emerald-200 bg-emerald-50 text-emerald-700' };
        return m[status] || m.pending;
    }

    public getResultCardAnimationDelay(kind: string): number { return 0; }

    public getAssistantPreviewLines(msg: any): string[] {
        const lines: string[] = [];
        const preview = String(msg?.previewContent || '').trim();
        const current = String(msg?.currentDescription || '').trim();
        const pageSummary = String(msg?.pageResultCard?.summary || '').trim();
        const qualityDetail = String(msg?.answerQuality?.detail || '').trim();
        if (preview) lines.push(preview);
        if (current && current !== preview) lines.push(current);
        if (msg?.executionPlan?.collection) lines.push(`현재 컬렉션: ${msg.executionPlan.collection}`);
        if (msg?.executionPlan?.page && msg?.executionPlan?.page !== '-') lines.push(`대상 페이지: ${msg.executionPlan.page}/${msg?.executionPlan?.tab || '-'}`);
        if (pageSummary && pageSummary !== preview && !msg?.pageResultCard?.loading) lines.push(pageSummary);
        if (qualityDetail && qualityDetail !== current) lines.push(qualityDetail);
        return Array.from(new Set(lines.filter((item) => item && item.length > 0))).slice(0, 3);
    }

    // ===== Send Message =====
    public async sendChat(text?: string) {
        const message = (text || this.chatInput || '').trim();
        if (!message || this.chatLoading) return;
        this.collapsePreviousAssistantTurns();
        this.clearTypingAnimations();
        this.pendingNavigation = null;
        this.chatMessages.push({ role: 'user', content: message });
        this.chatInput = '';
        this.chatLoading = true;
        this.autoNavigateAfterAnswer = false;

        const activeCollection = this.getActiveCollection();
        const assistantMsg: any = this.createAssistantMessage(message, activeCollection);
        this.chatMessages.push(assistantMsg);
        this.chatAssistantIdx = this.chatMessages.length - 1;
        this.scrollToBottom();
        this.cdr.detectChanges();

        this.chatAbortController = new AbortController();
        const params = new URLSearchParams();
        params.append('message', message);
        params.append('history', JSON.stringify(this.chatHistory));
        if (activeCollection) params.append('collection', activeCollection);

        let receivedDone = false;
        let receivedHistory = false;

        const markStreamComplete = () => {
            if (!this.chatLoading) return;
            this.chatLoading = false;
            this.cdr.detectChanges();
        };

        try {
            const response = await fetch('/wiz/api/page.agent/agent_chat', { method: 'POST', body: params, signal: this.chatAbortController.signal });

            if (!response.ok) {
                let errorMessage = `요청 실패 (${response.status})`;
                try {
                    const payload = await response.json();
                    errorMessage = payload?.data?.message || payload?.message || errorMessage;
                } catch (e) { }
                throw new Error(errorMessage);
            }

            if (!response.body) {
                throw new Error('응답 스트림을 열지 못했습니다.');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            const completionTimeoutToken = {};

            const flushBuffer = (force: boolean = false) => {
                const chunks = force ? [buffer] : buffer.split('\n\n');
                if (!force) {
                    buffer = chunks.pop() || '';
                } else {
                    buffer = '';
                }

                for (const chunk of chunks) {
                    const line = chunk.trim();
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const result = this.handleChatEvent(JSON.parse(line.slice(6)));
                        receivedDone = receivedDone || result.done;
                        receivedHistory = receivedHistory || result.history;
                        if (result.done) {
                            markStreamComplete();
                        }
                    } catch (e) { }
                }
            };

            const readNextChunk = async () => {
                const pendingRead = reader.read().catch(() => ({ done: true, value: undefined }));
                if (!receivedDone) {
                    return pendingRead;
                }

                let timeoutHandle: any = null;
                const timeoutPromise = new Promise<any>((resolve) => {
                    timeoutHandle = setTimeout(() => resolve(completionTimeoutToken), 400);
                });
                const result = await Promise.race([pendingRead, timeoutPromise]);
                if (timeoutHandle) {
                    clearTimeout(timeoutHandle);
                }

                if (result === completionTimeoutToken) {
                    await reader.cancel().catch(() => { });
                    return { done: true, value: undefined };
                }

                return result;
            };

            while (true) {
                const { done, value } = await readNextChunk();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                flushBuffer();
            }

            buffer += decoder.decode();
            if (buffer.trim()) {
                flushBuffer(true);
            }
        } catch (e: any) {
            if (e.name !== 'AbortError') {
                this.handleChatEvent({ type: 'error', message: e?.message || '연결이 끊어졌습니다.' });
            }
        }

        const currentMessage = this.chatMessages[this.chatAssistantIdx];
        if (currentMessage && !receivedDone) {
            this.finalizeAssistantState(currentMessage);
        }

        if (!receivedHistory && currentMessage) {
            const assistantContent = String(currentMessage?.content || currentMessage?.previewContent || '').trim();
            this.chatHistory = [
                ...this.chatHistory,
                { role: 'user', content: message },
                { role: 'assistant', content: assistantContent }
            ];
        }

        this.chatLoading = false;
        if (currentMessage) {
            this.finalizeAssistantState(currentMessage);
        }
        this.cdr.detectChanges();
    }

    // ===== SSE Event Handler =====
    private handleChatEvent(event: any): { done: boolean, history: boolean } {
        const msg = this.chatMessages[this.chatAssistantIdx];
        if (!msg) return { done: false, history: false };

        switch (event.type) {
            case 'pipeline': this.applyPipelineEvent(msg, event); break;
            case 'orchestration': this.applyOrchestrationEvent(msg, event); break;
            case 'quality':
                this.applyQualityEvent(msg, event);
                msg.qualityReady = true;
                this.revealCard(msg, 'quality', 80);
                break;
            case 'text_delta':
                msg.content = (msg.content || '') + (event.content || '');
                msg._streamedDeltas = true;
                msg.answerReady = true;
                this.revealCard(msg, 'answer', 0);
                this.updateTraceStep(msg, 14, 'running', '답변을 실시간 생성하고 있습니다.');
                break;
            case 'text_clear':
                msg.content = '';
                msg.renderedContent = '';
                msg._streamedDeltas = false;
                break;
            case 'text':
                if (msg._streamedDeltas && (event.content || '').trim()) {
                    // 스트리밍 델타로 이미 표시됨 → 최종 버전으로 교체
                    msg.content = event.content;
                    msg.renderedContent = event.content;
                    msg._streamedDeltas = false;
                    msg.answerReady = true;
                    this.revealCard(msg, 'answer', 0);
                } else if ((event.stage === 'verification' || msg.answerQuality?.stage === 'verification') && (event.content || '').trim()) {
                    msg.content = this.enrichFinalAnswerWithPageSummary(event.content || '', msg.pageResultCard);
                    this.queueTypewriterContent(msg, msg.content, true);
                    msg.answerReady = true;
                    this.revealCard(msg, 'answer', 60);
                } else if (event.stage === 'preview' && (event.content || '').trim()) {
                    this.updatePreviewContent(msg, event.content);
                    msg.content = event.content || '';
                    this.queueTypewriterContent(msg, msg.content, true);
                } else {
                    msg.content += event.content || '';
                    this.updatePreviewContent(msg, msg.currentDescription, msg.previewContent);
                    if ((msg.content || '').trim().length > 0 && event.stage !== 'preview') {
                        msg.answerReady = true;
                        this.revealCard(msg, 'answer', 60);
                    }
                }
                this.updateTraceStep(msg, 14, 'running', event.stage === 'preview'
                    ? '중간 결론을 먼저 표시하고, 최종 답변을 이어서 정리하고 있습니다.'
                    : '도구 결과와 참고 문헌을 바탕으로 최종 답변을 작성하고 있습니다.');
                break;
            case 'tool_use':
                msg.toolCalls.push({ type: 'use', id: event.id, name: event.name, input: event.input, collapsed: true });
                this.applyToolUseTrace(msg, event);
                break;
            case 'tool_result':
                this.handleToolResult(event);
                msg.toolCalls.push({ type: 'result', id: event.id, name: event.name, result: event.result, collapsed: true });
                this.applyToolResultTrace(msg, event);
                break;
            case 'history':
                this.chatHistory = event.messages || [];
                this.syncJourneyReveal(msg);
                this.scrollToBottom();
                this.cdr.detectChanges();
                return { done: false, history: true };
            case 'done':
                this.finalizeAssistantState(msg);
                this.syncJourneyReveal(msg);
                this.scrollToBottom();
                this.cdr.detectChanges();
                return { done: true, history: false };
            case 'evidence_items':
                msg.evidenceItems = event.items || [];
                msg.evidenceOpen = false;
                msg.evidenceReady = (msg.evidenceItems || []).length > 0;
                if (msg.evidenceReady) this.revealCard(msg, 'evidence', 100);
                break;
            case 'error':
                msg.content += `\n\n**Error:** ${event.message}`;
                this.queueTypewriterContent(msg, msg.content, false);
                msg.answerReady = true;
                this.revealCard(msg, 'answer', 0);
                this.markTraceError(msg, event.message || '에이전트 처리 중 오류가 발생했습니다.');
                break;
        }
        if (msg.traceSteps?.length > 0 && !msg.traceCompleted && event.type !== 'done') {
            msg.traceOpen = true;
        }
        this.syncJourneyReveal(msg);
        this.scrollToBottom();
        this.cdr.detectChanges();
        return { done: false, history: false };
    }

    // ===== Navigation =====
    public pendingNavigation: any = null;

    public buildAgentNavigationSummary(nav: any): string {
        if (!nav) return '';
        const c = this.getActiveCollection(nav.collection || nav.params?.collection);
        const lines = [`### 에이전트 실행 요약`, `- 분류 결과: **${nav.title || nav.page}**`, `- 선택 컬렉션: **${c || '-'}**`];
        if (nav.query) lines.push(`- 핵심 키워드: **${nav.query}**`);
        const entries = Object.entries(nav.params || {}).filter(([k, v]) => k !== 'collection' && v !== null && v !== undefined && String(v).trim().length > 0);
        if (entries.length > 0) lines.push(`- 전달 파라미터: ${entries.map(([k, v]) => `${k}=${v}`).join(', ')}`);
        lines.push(`- 다음 단계: 해당 페이지로 이동해 동일한 컬렉션으로 바로 실행합니다.`);
        return lines.join('\n');
    }

    private applyNavigationPayload(msg: any, data: any): any {
        const navCol = this.getActiveCollection(data.collection || data.params?.collection);
        if (navCol) this.syncSelectedCollection(navCol);
        this.pendingNavigation = {
            page: data.page, title: data.title_ko || data.page, url: data.url,
            tab: data.tab, query: data.query, params: data.params || {}, collection: navCol
        };
        if (msg) {
            this.patchNavigationCard(msg, {
                loading: false, skipped: false, title: data.title_ko || data.page,
                summary: this.buildAgentNavigationSummary(this.pendingNavigation),
                actionLabel: '바로 이동', tab: data.tab, query: data.query, collection: navCol
            });
        }
        return navCol;
    }

    private handleToolResult(event: any) {
        if (event.name !== 'navigate_to_page') return;
        const msg = this.chatMessages[this.chatAssistantIdx];
        try {
            const data = JSON.parse(event.result);
            if (data.action === 'navigate') {
                this.applyNavigationPayload(msg, data);
                this.cdr.detectChanges();
            }
        } catch (e) { }
    }

    private finalizeAssistantState(msg: any) {
        if (!msg) return;

        if (!msg.content?.trim() && msg.pageResultCard) {
            msg.content = this.buildPageResultFallbackAnswer(msg.pageResultCard);
        } else if (!msg.content?.trim() && this.pendingNavigation) {
            msg.content = this.buildAgentNavigationSummary(this.pendingNavigation);
        } else if (!msg.content?.trim()) {
            const fallback = [
                msg.pageResultCard?.summary,
                msg.navigationCard?.summary,
                msg.answerQuality?.detail,
                msg.previewContent,
            ].map((item: any) => String(item || '').trim()).find(Boolean);
            if (fallback) msg.content = fallback;
        }

        if (msg.content?.trim()) {
            this.queueTypewriterContent(msg, msg.content, true);
            msg.answerReady = true;
        }

        if (!msg.previewContent?.trim() && msg.content?.trim()) {
            msg.previewContent = String(msg.content).split(/\n+/)[0];
        }

        if (msg.navigationCard) {
            if (this.pendingNavigation) {
                this.patchNavigationCard(msg, {
                    loading: false,
                    summary: msg.navigationCard?.summary || this.buildAgentNavigationSummary(this.pendingNavigation),
                    actionLabel: '바로 이동'
                });
            } else if (msg.navigationCard.loading) {
                this.patchNavigationCard(msg, {
                    loading: false,
                    summary: '이번 답변은 별도의 페이지 이동 없이 여기서 바로 마무리했습니다.',
                    actionLabel: '이동 없음'
                });
            }
        }

        if (msg.pageResultCard?.loading) {
            this.patchPageResultCard(msg, {
                loading: false,
                summary: msg.pageResultCard.summary || '페이지 결과 없이 현재 대화 문맥으로 답변을 정리했습니다.'
            });
        }

        if (msg.answerReady) this.revealCard(msg, 'answer', 0);
        if (msg.navigationCard) this.revealCard(msg, 'navigation', 0);
        if (msg.pageResultReady || msg.pageResultCard) this.revealCard(msg, 'pageResult', 0);
        if (msg.qualityReady) this.revealCard(msg, 'quality', 60);
        if (msg.evidenceReady) this.revealCard(msg, 'evidence', 120);
        this.finalizeTrace(msg);
        this.collapsePreviousAssistantTurns(this.chatAssistantIdx);
    }

    public async navigateNow() {
        if (!this.pendingNavigation) return;
        const nav = this.pendingNavigation;
        const c = this.getActiveCollection(nav.collection || nav.params?.collection);
        if (c) { this.syncSelectedCollection(c); nav.collection = c; }
        const queryParams = this.buildNavigationQueryParams(nav);
        const targetPath = nav.url ? nav.url.split('?')[0] : '/' + nav.page;
        await this.forceNavigate(targetPath, queryParams);
        this.pendingNavigation = null;
        this.autoNavigateAfterAnswer = false;
        this.cdr.detectChanges();
    }

    private async forceNavigate(targetPath: string, queryParams: any) {
        const savedReuse = this.router.routeReuseStrategy.shouldReuseRoute;
        try {
            (this.router as any).onSameUrlNavigation = 'reload';
            this.router.routeReuseStrategy.shouldReuseRoute = () => false;
            await this.router.navigate([targetPath], { queryParams });
        } catch (e) {
            const qs = new URLSearchParams(
                Object.entries(queryParams || {}).reduce((acc: any, [k, v]) => { if (v !== null && v !== undefined) acc[k] = String(v); return acc; }, {})
            ).toString();
            window.location.href = qs ? `${targetPath}?${qs}` : targetPath;
        } finally {
            setTimeout(() => { (this.router as any).onSameUrlNavigation = 'ignore'; this.router.routeReuseStrategy.shouldReuseRoute = savedReuse; }, 50);
        }
    }

    private buildNavigationQueryParams(nav: any): any {
        const qp: any = {};
        const c = this.getActiveCollection(nav?.collection || nav?.params?.collection);
        if (nav?.tab) qp['tab'] = nav.tab;
        if (nav?.query) qp['q'] = nav.query;
        if (c) qp['collection'] = c;
        if (nav?.params) {
            for (const [k, v] of Object.entries(nav.params)) {
                if (k === 'collection') continue;
                if (v !== null && v !== undefined && String(v).trim()) qp[k] = String(v);
            }
        }
        return qp;
    }

    // ===== Cancel / Clear =====
    public cancelChat() {
        if (this.chatAbortController) { this.chatAbortController.abort(); this.chatAbortController = null; }
        this.clearTypingAnimations();
        this.clearJourneyRevealAnimations();
        this.chatLoading = false;
    }

    public clearChat() { this.resetConversationState(); }

    private clearTypingAnimations() { for (const msg of this.chatMessages) this.stopTypewriter(msg); }
    private clearJourneyRevealAnimations() { for (const msg of this.chatMessages) this.stopJourneyReveal(msg); }

    private stopTypewriter(msg: any) {
        const timer = this.typingTimers.get(msg);
        if (timer) { clearTimeout(timer); this.typingTimers.delete(msg); }
        if (msg) msg.typingActive = false;
    }

    private stopJourneyReveal(msg: any) {
        const timer = this.journeyRevealTimers.get(msg);
        if (timer) { clearTimeout(timer); this.journeyRevealTimers.delete(msg); }
    }

    // ===== Journey Reveal =====
    private syncJourneyReveal(msg: any) {
        if (!msg) return;
        const items = this.getAnswerJourney(msg);
        const total = items.length;
        if (total === 0) { msg.journeyRevealCount = 0; return; }
        const traceSteps = msg.traceSteps || [];
        const hasRunning = traceSteps.some((s: any) => s.status === 'running');
        const hasError = traceSteps.some((s: any) => s.status === 'error');
        const completed = this.getCompletedTraceCount(msg);
        const finished = !hasRunning && !hasError && traceSteps.length > 0 && completed >= traceSteps.length;
        const target = finished ? total : Math.min(total, Math.max(1, completed + 1));
        const current = Math.max(1, Number(msg.journeyRevealCount || 1));
        msg.journeyRevealCount = current;
        if (current >= target) { this.stopJourneyReveal(msg); return; }
        this.stopJourneyReveal(msg);
        const timer = setTimeout(() => {
            msg.journeyRevealCount = Math.min(target, Number(msg.journeyRevealCount || 1) + 1);
            this.journeyRevealTimers.delete(msg);
            this.cdr.detectChanges();
            this.syncJourneyReveal(msg);
        }, 260);
        this.journeyRevealTimers.set(msg, timer);
    }

    // ===== Typewriter =====
    private queueTypewriterContent(msg: any, nextContent: string, reset: boolean = false) {
        if (!msg) return;
        msg.typingTarget = String(nextContent || '');
        if (reset || !msg.renderedContent || msg.typingTarget.length < String(msg.renderedContent || '').length) msg.renderedContent = '';
        if (String(msg.renderedContent || '') === msg.typingTarget) { msg.typingActive = false; return; }
        if (this.typingTimers.get(msg)) { msg.typingActive = true; return; }
        msg.typingActive = true;
        const step = () => {
            const full = String(msg.typingTarget || '');
            const cur = String(msg.renderedContent || '');
            if (cur === full) { this.stopTypewriter(msg); this.cdr.detectChanges(); return; }
            const nl = Math.min(cur.length + this.typingChunkSize, full.length);
            msg.renderedContent = full.slice(0, nl);
            msg.typingActive = nl < full.length;
            this.scrollToBottom(); this.cdr.detectChanges();
            if (nl >= full.length) { this.stopTypewriter(msg); return; }
            const t = setTimeout(step, this.typingIntervalMs);
            this.typingTimers.set(msg, t);
        };
        const t = setTimeout(step, this.typingIntervalMs);
        this.typingTimers.set(msg, t);
    }

    public getDisplayedAssistantContent(msg: any): string {
        return String(msg?.renderedContent ?? msg?.content ?? '');
    }

    private collapsePreviousAssistantTurns(exceptIdx: number = -1) {
        for (let i = 0; i < this.chatMessages.length; i++) {
            const item = this.chatMessages[i];
            if (item.role !== 'assistant' || i === exceptIdx) continue;
            item.collapsed = true; item.traceOpen = false;
        }
    }

    // ===== Tool Trace =====
    private applyToolUseTrace(msg: any, event: any) {
        const input = event.input || {};
        const name = event.name;
        this.addReasoningLog(msg, 'tool-use', 'running', `${this.getToolLabel(name)} 실행`, this.formatToolReasoning(name, input, 'use'));
        if (name === 'get_collections') { this.updateTraceStep(msg, 9, 'running', '사용 가능한 컬렉션 목록과 문서 규모를 확인하고 있습니다.'); return; }
        if (name === 'search_papers') {
            this.updateTraceStep(msg, 8, 'done', '질문 목적에 맞는 검색 전략과 후속 흐름을 수립했습니다.');
            this.updateTraceStep(msg, 11, 'running', `벡터 데이터베이스에서 관련 참고 문헌을 검색하고 있습니다. ${input.query || msg.question}`);
            return;
        }
        if (name === 'read_page_results') {
            this.mergeExecutionPlan(msg, { page: input.page || '-', tab: input.tab || '-', params: input.params || {}, keywords: input.query ? [input.query] : msg.executionPlan?.keywords || [] });
            this.patchPageResultCard(msg, { loading: true, page: input.page || msg.pageResultCard?.page, tab: input.tab || msg.pageResultCard?.tab, query: input.query || msg.pageResultCard?.query, summary: '실제 페이지가 보여줄 결과를 읽어 현재까지 핵심 포인트를 정리하고 있습니다.' });
            this.revealCard(msg, 'pageResult', 100);
            this.updateTraceStep(msg, 6, 'done', '질문 키워드와 파라미터를 페이지 실행용으로 구조화했습니다.');
            this.updateTraceStep(msg, 7, 'done', `질문에 맞는 페이지와 탭을 선정했습니다. ${input.page || ''}/${input.tab || ''}`);
            this.updateTraceStep(msg, 8, 'done', '페이지 기반 실행 전략을 확정했습니다.');
            this.updateTraceStep(msg, 10, 'running', '실제 페이지가 보여줄 결과 JSON을 읽고 있습니다.');
            return;
        }
        if (name === 'navigate_to_page') {
            this.mergeExecutionPlan(msg, { page: input.page || msg.executionPlan?.page || '-', tab: input.tab || msg.executionPlan?.tab || '-', params: input.params || msg.executionPlan?.params || {}, keywords: input.query ? [input.query] : msg.executionPlan?.keywords || [] });
            this.patchNavigationCard(msg, { summary: '최종 답변 이후 이어질 페이지와 탭을 확정하고 있습니다.' });
            this.updateTraceStep(msg, 16, 'running', '최종 결과와 연동할 페이지/탭을 확정하고 있습니다.');
            return;
        }
        this.updateTraceStep(msg, 13, 'running', `${this.getToolLabel(name)} 도구를 실행하고 있습니다.`);
    }

    private applyToolResultTrace(msg: any, event: any) {
        const name = event.name;
        if (name === 'get_collections') { this.updateTraceStep(msg, 9, 'done', '검색 가능한 컬렉션 메타데이터를 확보했습니다.'); return; }
        if (name === 'search_papers') {
            const refs = this.parseSearchPapersResults(event.result);
            msg.references = refs; msg.similaritySummary = this.buildSimilaritySummary(refs);
            this.addReasoningLog(msg, 'tool-result', 'done', '문헌 검색 완료', refs.length > 0 ? `${refs.length}건의 참고 문헌 후보와 유사도를 확보했습니다.` : '검색 결과를 확보했습니다.');
            this.updateTraceStep(msg, 11, 'done', refs.length > 0 ? `${refs.length}건의 참고 문헌 후보를 검색하고 핵심 근거를 확정했습니다.` : '검색 결과를 확보했습니다.');
            this.updateTraceStep(msg, 12, 'done', refs.length > 0 ? '참고 문헌, 본문 요약, 유사도 정보를 메모리에 반영했습니다.' : '핵심 근거를 메모리에 반영했습니다.');
            this.updateTraceStep(msg, 13, 'running', '추가 분석 도구 실행 여부를 검토하고 있습니다.');
            return;
        }
        if (name === 'read_page_results') {
            const card = this.parsePageResultCard(event.result);
            if (card) { this.patchPageResultCard(msg, { ...card, loading: false }); this.updatePreviewContent(msg, card.summary, msg.previewContent); msg.pageResultReady = true; this.cdr.detectChanges(); }
            this.addReasoningLog(msg, 'tool-result', 'done', '페이지 결과 추출 완료', this.summarizePageResult(event.result));
            this.mergeExecutionPlan(msg, { pageResultSummary: this.summarizePageResult(event.result) });
            this.updateTraceStep(msg, 10, 'done', '실제 페이지 결과 JSON을 확보했습니다.');
            this.updateTraceStep(msg, 12, 'running', '페이지 결과를 메모리와 답변 컨텍스트에 반영하고 있습니다.');
            return;
        }
        if (name === 'navigate_to_page') {
            this.addReasoningLog(msg, 'navigation', 'done', '페이지 핸드오프 준비', this.parseToolResult(event.result));
            this.mergeExecutionPlan(msg, { handoffSummary: this.parseToolResult(event.result) });
            this.patchNavigationCard(msg, { loading: false, summary: this.parseToolResult(event.result), actionLabel: '바로 이동' });
            this.updateTraceStep(msg, 16, 'done', '최종 결과를 이어서 실행할 페이지로 연결했습니다.');
            this.cdr.detectChanges();
            return;
        }
        this.addReasoningLog(msg, 'tool-result', 'done', `${this.getToolLabel(name)} 결과 확보`, `${this.getToolLabel(name)} 결과를 통합 단계에 반영합니다.`);
        this.updateTraceStep(msg, 13, 'done', `${this.getToolLabel(name)} 결과를 확보했습니다.`);
        this.updateTraceStep(msg, 14, 'running', '도구 결과를 읽기 쉬운 최종 답변으로 정리하고 있습니다.');
    }

    private finalizeTrace(msg: any) {
        const q = msg.answerQuality || {};
        this.finishRunningStep(msg, 6, '파라미터 매핑을 완료했습니다.');
        this.finishRunningStep(msg, 7, '목표 페이지와 탭 선정을 완료했습니다.');
        this.finishRunningStep(msg, 8, '오케스트레이션 계획 구성을 완료했습니다.');
        this.finishRunningStep(msg, 9, '컬렉션과 문서 범위 점검을 완료했습니다.');
        this.finishRunningStep(msg, 10, '페이지 결과 추출을 완료했습니다.');
        this.finishRunningStep(msg, 11, '문헌·근거 수집을 완료했습니다.');
        this.finishRunningStep(msg, 12, '메모리 반영을 완료했습니다.');
        this.finishRunningStep(msg, 13, '필요한 추가 도구 실행을 완료했습니다.');
        this.updateTraceStep(msg, 14, 'done', q.synthesisPoints?.length > 0
            ? `근거 ${q.evidenceCount || msg.references?.length || 0}건을 조합해 최종 답변 구조를 정리했습니다.`
            : msg.content?.trim() ? '최종 답변 초안 생성을 완료했습니다.' : '요약 응답 생성을 완료했습니다.');
        this.updateTraceStep(msg, 15, 'done', q.verificationChecks?.length > 0
            ? `검증 체크 ${q.verificationChecks.length}개를 기준으로 답변을 점검했습니다.`
            : msg.references?.length > 0 ? `참고 문헌 ${msg.references.length}건과 유사도 요약을 기준으로 답변을 점검했습니다.` : '도구 결과와 누락 파라미터를 점검했습니다.');
        const step16 = this.findTraceStep(msg, 16);
        if (step16 && step16.status === 'pending') {
            this.updateTraceStep(msg, 16, this.pendingNavigation ? 'done' : 'skipped', this.pendingNavigation ? '관련 페이지로 이어지는 핸드오프를 준비했습니다.' : '이번 턴은 페이지 이동 없이 답변만 제공합니다.');
        }
        this.patchNavigationCard(msg, { loading: false, summary: msg.navigationCard?.summary || '이번 답변은 별도의 페이지 이동 없이 여기서 바로 마무리했습니다.', actionLabel: msg.navigationCard?.actionLabel || '이동 없음' });
        for (const step of msg.traceSteps) { if (step.status === 'pending') step.status = 'skipped'; }
        msg.traceCompleted = true; msg.traceOpen = false;
        this.syncCurrentTrace(msg);
    }

    private markTraceError(msg: any, detail: string) {
        const running = msg.traceSteps.find((s: any) => s.status === 'running');
        if (running) { running.status = 'error'; running.detail = detail; } else { this.updateTraceStep(msg, 12, 'error', detail); }
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
        if (step.status === 'running' || step.status === 'pending') { step.status = 'done'; step.detail = detail; }
    }

    private findTraceStep(msg: any, stepId: number): any {
        return (msg.traceSteps || []).find((s: any) => s.id === stepId) || null;
    }

    // ===== Quality =====
    private applyQualityEvent(msg: any, event: any) {
        const q = msg.answerQuality || this.buildAnswerQuality(msg.question || '');
        q.stage = event.stage || q.stage;
        q.detail = event.detail || q.detail;
        if (event.answerStyle) q.answerStyle = event.answerStyle;
        if (event.confidence) q.confidence = event.confidence;
        if (typeof event.llmUsed === 'boolean') q.llmUsed = event.llmUsed;
        if (Number.isFinite(event.evidenceCount)) q.evidenceCount = event.evidenceCount;
        if (event.avgScore !== null && event.avgScore !== undefined && Number.isFinite(Number(event.avgScore))) q.avgScore = Number(event.avgScore);
        if (Array.isArray(event.synthesisPoints)) q.synthesisPoints = event.synthesisPoints;
        if (Array.isArray(event.verificationChecks)) q.verificationChecks = event.verificationChecks;
        if (Array.isArray(event.sources)) q.sources = event.sources;
        msg.answerQuality = q;
        this.updatePreviewContent(msg, q.detail, q.synthesisPoints?.[0], msg.previewContent);
        if (q.stage === 'evidence' || q.stage === 'synthesis') {
            this.updateTraceStep(msg, 11, 'done', `근거 ${q.evidenceCount || msg.references?.length || 0}건을 답변 조합용으로 정리했습니다.`);
            this.updateTraceStep(msg, 14, 'running', q.detail || '검색 근거를 조합해 답변 구조를 정리하고 있습니다.');
            msg.currentLabel = '근거 조합 및 답변 구조화';
            msg.currentDescription = q.detail || '검색 근거를 묶어 읽기 쉬운 최종 답변으로 재구성하고 있습니다.';
            this.addReasoningLog(msg, 'quality', 'running', '답변 통합 중', msg.currentDescription);
        }
        if (q.stage === 'verification') {
            this.updateTraceStep(msg, 14, 'done', `근거 ${q.evidenceCount || msg.references?.length || 0}건을 기반으로 답변 구조 정리를 마쳤습니다.`);
            this.updateTraceStep(msg, 15, 'running', q.detail || '최종 답변의 근거 정합성과 표현 품질을 점검하고 있습니다.');
            msg.currentLabel = '답변 품질 검증';
            msg.currentDescription = q.detail || '최종 답변의 근거 정합성과 표현 품질을 점검하고 있습니다.';
            this.addReasoningLog(msg, 'quality', 'done', '품질 검증', msg.currentDescription);
        }
    }

    // ===== Pipeline / Orchestration =====
    private applyPipelineEvent(msg: any, event: any) {
        if (event.detail) {
            this.addReasoningLog(msg, 'pipeline', event.status || 'pending', `${event.component} 상태`, event.detail);
            this.updatePreviewContent(msg, event.detail);
        }
        if (event.component === 'goal_manager') {
            this.mergeExecutionPlan(msg, {
                goal: event.meta?.goal || msg.executionPlan?.goal || '',
                goalStatus: event.status || msg.executionPlan?.goalStatus || 'running',
                goalSummary: event.detail || msg.executionPlan?.goalSummary || '',
                currentCluster: event.meta?.current_cluster || msg.executionPlan?.currentCluster || 'planner',
                allowedTools: event.meta?.allowed_tools || msg.executionPlan?.allowedTools || [],
                recommendedTools: event.meta?.recommended_tools || msg.executionPlan?.recommendedTools || [],
                evaluationStatus: event.meta?.evaluation_status || msg.executionPlan?.evaluationStatus || 'pending',
                evaluationSummary: event.meta?.evaluation_summary || msg.executionPlan?.evaluationSummary || '',
                recoveryStrategy: event.meta?.recovery_strategy || msg.executionPlan?.recoveryStrategy || '',
                recoveryHint: event.meta?.recovery_hint || msg.executionPlan?.recoveryHint || '',
                recoveryQuery: event.meta?.recovery_query || msg.executionPlan?.recoveryQuery || '',
                recoveryParams: event.meta?.recovery_params || msg.executionPlan?.recoveryParams || {},
            });
            msg.currentLabel = '목표 반복 관리';
            msg.currentDescription = event.detail || '목표 달성 전까지 다음 행동을 재평가하고 있습니다.';
        }
        if (event.component === 'memory' && event.meta?.memoryNote) {
            msg.currentLabel = '메모리 컨텍스트 반영';
            msg.currentDescription = event.meta.memoryNote;
            this.updatePreviewContent(msg, event.meta.memoryNote);
        }
        if (event.component === 'orchestrator' && event.detail) {
            msg.currentLabel = '오케스트레이터 계획 수립';
            msg.currentDescription = event.detail;
            this.updatePreviewContent(msg, event.detail);
        }
    }

    private applyOrchestrationEvent(msg: any, event: any) {
        if (Array.isArray(event.trace_steps) && event.trace_steps.length > 0) msg.traceSteps = event.trace_steps;
        msg.traceCategory = event.category || msg.traceCategory;
        msg.traceLanguage = event.language || msg.traceLanguage;
        msg.traceDifficulty = event.difficulty || msg.traceDifficulty;
        msg.currentLabel = event.currentLabel || '오케스트레이션 계획 수립';
        msg.currentDescription = event.currentDescription || '질문 분류와 도구 순서를 확정했습니다.';
        msg.executionPlan = { ...(msg.executionPlan || {}), ...(event.execution_plan || {}), collection: event.collection || event.execution_plan?.collection || this.selectedCollection || '' };
        this.patchPageResultCard(msg, { page: event.page || msg.pageResultCard?.page, tab: event.tab || msg.pageResultCard?.tab, query: event.execution_plan?.params?.query || msg.pageResultCard?.query, summary: `선택된 경로 ${event.page || '-'}${event.tab ? ` · ${event.tab}` : ''} 기준으로 결과를 준비하고 있습니다.` });
        this.patchNavigationCard(msg, { loading: true, summary: `${event.page || '-'}${event.tab ? ` · ${event.tab}` : ''} 페이지로 이동을 준비하고 있습니다.` });
        this.revealCard(msg, 'navigation', 60);
        this.updatePreviewContent(msg, `관련 페이지 ${event.page || '-'}${event.tab ? `의 ${event.tab}` : ''} 결과를 바탕으로 답변 방향을 정하고 있습니다.`);
        this.addReasoningLog(msg, 'orchestrator', 'done', '질문 분류 완료', `${event.category} · ${event.page}/${event.tab}`);
        this.addReasoningLog(msg, 'keyword', 'done', '키워드 추출', (event.keywords || []).join(', ') || '키워드 없음');
        this.addReasoningLog(msg, 'page', 'done', '페이지 실행 계획', `${event.page}/${event.tab}로 이동해 결과를 추출한 뒤 최종 답변을 구성합니다.`);
        this.syncCurrentTrace(msg);
    }

    private mergeExecutionPlan(msg: any, patch: any) {
        msg.executionPlan = { ...(msg.executionPlan || {}), ...(patch || {}), params: { ...((msg.executionPlan || {}).params || {}), ...((patch || {}).params || {}) } };
    }

    private addReasoningLog(msg: any, kind: string, status: string, title: string, detail: string) {
        msg.reasoningLogs = msg.reasoningLogs || [];
        const n = `${kind}|${status}|${title}|${detail}`;
        const last = msg.reasoningLogs.length > 0 ? msg.reasoningLogs[msg.reasoningLogs.length - 1] : null;
        if (last && `${last.kind}|${last.status}|${last.title}|${last.detail}` === n) return;
        msg.reasoningLogs.push({ kind, status, title, detail });
    }

    // ===== Page Result helpers =====
    private formatToolReasoning(name: string, input: any, stage: 'use' | 'result'): string {
        if (name === 'read_page_results') return stage === 'use' ? `${input.page || '-'} / ${input.tab || '-'} 페이지에 ${input.query || ''} 키워드를 넣어 실제 결과를 읽습니다.` : '페이지 결과를 확보했습니다.';
        if (name === 'navigate_to_page') return `${input.page || '-'} / ${input.tab || '-'} 페이지로 이동할 준비를 합니다.`;
        if (name === 'search_papers') return `${input.query || ''} 키워드로 참고 문헌을 검색합니다.`;
        return `${this.getToolLabel(name)} 도구를 실행해 후속 답변 근거를 확보합니다.`;
    }

    private summarizePageResult(result: string): string {
        try {
            const p = JSON.parse(result);
            if (p.error) return `페이지 결과 추출 실패: ${p.error}`;
            if (p.page && p.tab) {
                const count = p.total ?? p.total_hits ?? p.total_searched;
                const query = p.query ? `'${p.query}'` : '질문 키워드';
                const pt = this.formatPageResultParams(p.params || {});
                if (count !== undefined) return `${p.page}/${p.tab} 페이지에 ${query}를 적용해 결과 ${count}건을 확보했습니다${pt ? ` (${pt})` : ''}.`;
                if (p.stats) return `${p.page}/${p.tab} 페이지 결과와 통계 정보를 확보했습니다${pt ? ` (${pt})` : ''}.`;
                return `${p.page}/${p.tab} 페이지 결과 JSON을 확보했습니다${pt ? ` (${pt})` : ''}.`;
            }
        } catch (e) { }
        return '페이지 결과 JSON을 확보했습니다.';
    }

    private formatPageResultParams(params: any): string {
        return Object.entries(params || {}).filter(([k, v]) => k !== 'collection' && v !== null && v !== undefined && String(v).trim().length > 0).map(([k, v]) => `${k}=${String(v)}`).join(', ');
    }

    private parsePageResultCard(result: string): any {
        try {
            const p = JSON.parse(result);
            if (!p || p.error || !p.page || !p.tab) return null;
            const count = p.total ?? p.total_hits ?? p.total_searched;
            const pt = this.formatPageResultParams(p.params || {});
            const el: string[] = [];
            if (p.query) el.push(`질문 키워드: ${p.query}`);
            if (pt) el.push(`적용 인자값: ${pt}`);
            if (count !== undefined) el.push(`확인된 결과 수: ${count}건`);
            else if (p.stats) el.push('통계 정보가 함께 반환된 결과입니다.');
            return { page: p.page, tab: p.tab, query: p.query || '', paramsText: pt, summary: this.summarizePageResult(result), evidenceLines: el.slice(0, 3) };
        } catch (e) { }
        return null;
    }

    private buildPageResultFallbackAnswer(card: any): string {
        if (!card) return '';
        const el = [...(card.evidenceLines || [])];
        if (el.length < 2) el.push(`실행된 페이지: ${card.page}/${card.tab}`);
        return ['핵심 결론', card.summary || '페이지 결과를 기준으로 질문 관련 정보를 확인했습니다.', '', `${card.page}/${card.tab} 페이지에서 질문과 관련된 결과를 분석했습니다. 세부 결과는 아래 근거 항목을 참고하세요.`, '', '근거', ...el.slice(0, 3).map((l: string) => `- ${l}`)].join('\n');
    }

    private enrichFinalAnswerWithPageSummary(content: string, card: any): string {
        const text = String(content || '').trim();
        if (!text || !card?.summary) return text;
        if (text.includes('페이지 결과 요약:')) return text;
        const lines = text.split('\n');
        const result: string[] = [];
        let inserted = false;
        for (const line of lines) {
            result.push(line);
            if (line.trim() === '근거') { result.push(`- 페이지 결과 요약: ${card.summary}`); inserted = true; }
        }
        if (!inserted) return [text, '', '근거', `- 페이지 결과 요약: ${card.summary}`].join('\n').trim();
        return result.join('\n').trim();
    }

    public toggleEvidence(msg: any) { msg.evidenceOpen = !msg.evidenceOpen; }
    public formatEvidenceScore(score: any): string {
        if (score === null || score === undefined) return '-';
        const n = Number(score); return Number.isFinite(n) ? n.toFixed(4) : '-';
    }

    // ===== Answer Journey =====
    public getReasoningLogs(msg: any): any[] { return msg.reasoningLogs || []; }

    public getAnswerJourney(msg: any): any[] {
        const items: any[] = [];
        const pushItem = (title: string, detail: string, status: string = 'done', icon: string = '•') => {
            if (!detail || !String(detail).trim()) return;
            const n = `${title}|${detail}|${status}`;
            const last = items.length > 0 ? items[items.length - 1] : null;
            if (last && `${last.title}|${last.detail}|${last.status}` === n) return;
            items.push({ title, detail, status, icon });
        };
        const findLog = (t: string) => this.getReasoningLogs(msg).find((l: any) => l.title === t) || null;
        if (msg.question) pushItem('질문 접수', msg.question, 'done', '❓');
        const plan = msg.executionPlan || {};
        const pp: string[] = [];
        if (plan.category) pp.push(`분류: ${plan.category}`);
        if (plan.page || plan.tab) pp.push(`목표 페이지: ${plan.page || '-'} / ${plan.tab || '-'}`);
        if ((plan.keywords || []).length > 0) pp.push(`키워드: ${(plan.keywords || []).join(', ')}`);
        if (plan.collection) pp.push(`컬렉션: ${plan.collection}`);
        if (pp.length > 0) pushItem('답변 경로 결정', pp.join('\n'), this.getCurrentTraceStep(msg)?.status || 'done', '🗺️');
        if (plan.goalSummary) pushItem('목표 상태', `${plan.goalSummary}${plan.goalStatus ? `\n상태: ${this.getTraceStatusLabel(plan.goalStatus)}` : ''}`, plan.goalStatus || 'running', '🎯');
        const sl: string[] = [];
        if (plan.currentCluster) sl.push(`현재 군집: ${String(plan.currentCluster)}`);
        if ((plan.allowedTools || []).length > 0) sl.push(`허용 도구: ${(plan.allowedTools || []).map((i: string) => this.getToolLabel(i)).join(' · ')}`);
        if (plan.recoveryStrategy) sl.push(`복구 전략: ${plan.recoveryStrategy}`);
        if (plan.recoveryHint) sl.push(String(plan.recoveryHint));
        if (sl.length > 0) pushItem('상태', sl.join('\n'), plan.goalStatus || 'running', '🧩');
        if (plan.evaluationSummary) pushItem('결과 평가', String(plan.evaluationSummary), plan.evaluationStatus || 'pending', '🧭');
        const planLines = this.getExecutionPlanLines(msg);
        const el: string[] = [];
        if (planLines.length > 0) el.push(...planLines.map((i: any) => `- ${i}`));
        const tl = this.getExecutionPlanToolLabels(msg);
        if (tl.length > 0) el.push(`- 도구 순서: ${tl.join(' → ')}`);
        const pr = this.getExecutionPlanParams(msg);
        if (pr.length > 0) el.push(`- 인자값: ${pr.map((i: any) => `${i.key}=${i.value}`).join(', ')}`);
        if (el.length > 0) pushItem('실행 계획', el.join('\n'), 'done', '📋');
        for (const t of ['답변 경로 계산', '논문 검색 실행', '문헌 검색 완료', '페이지 이동 실행', '페이지 핸드오프 준비']) {
            const log = findLog(t); if (log) pushItem(log.title, log.detail, log.status || 'done', this.getReasoningLogIcon(log));
        }
        if (msg.similaritySummary || (msg.references || []).length > 0) {
            const rl: string[] = [];
            if (msg.similaritySummary) rl.push(msg.similaritySummary);
            for (const ref of (msg.references || []).slice(0, 3)) rl.push(`${ref.filename} · sim ${this.formatScore(ref.score)}`);
            pushItem('근거 후보 정리', rl.join('\n'), 'done', '📚');
        }
        if (plan.handoffSummary) pushItem('페이지 이동 준비', plan.handoffSummary, 'done', '🚀');
        return items;
    }

    public getReasoningLogIcon(log: any): string {
        const m: any = { question: '❓', orchestrator: '🗺️', keyword: '🏷️', page: '🧭', pipeline: '⚙️', 'tool-use': '🧰', 'tool-result': '✅', navigation: '🚀', quality: '🧪' };
        return m[log.kind] || '•';
    }

    public getAnswerJourneyCount(msg: any): number { return this.getAnswerJourney(msg).length; }

    public getVisibleAnswerJourney(msg: any): any[] {
        const items = this.getAnswerJourney(msg);
        if (items.length <= 1) return items;
        return items.slice(0, Math.max(1, Math.min(items.length, Number(msg?.journeyRevealCount || 1))));
    }

    public getHiddenJourneyCount(msg: any): number { return Math.max(0, this.getAnswerJourney(msg).length - this.getVisibleAnswerJourney(msg).length); }
    public getUpcomingTraceStep(msg: any): any { return (msg.traceSteps || []).find((s: any) => s.status === 'pending') || null; }

    public getJourneyProgressPercent(msg: any): number {
        const total = (msg.traceSteps || []).length || 0;
        if (total === 0) return 0;
        const completed = this.getCompletedTraceCount(msg);
        const running = (msg.traceSteps || []).some((s: any) => s.status === 'running') ? 1 : 0;
        return Math.max(8, Math.min(100, Math.round(((completed + running * 0.5) / total) * 100)));
    }

    public getJourneyAnimationDelay(index: number, offset: number = 0): number { return offset + (Math.max(0, index) * 90); }

    private syncCurrentTrace(msg: any) {
        const c = this.getCurrentTraceStep(msg);
        msg.currentLabel = c?.title || '에이전트 실행';
        msg.currentDescription = c?.detail || c?.summary || '실행 상태를 갱신 중입니다.';
    }

    public getCurrentTraceStep(msg: any): any {
        const running = (msg.traceSteps || []).find((s: any) => s.status === 'running');
        if (running) return running;
        const error = (msg.traceSteps || []).find((s: any) => s.status === 'error');
        if (error) return error;
        const reversed = [...(msg.traceSteps || [])].reverse();
        return reversed.find((s: any) => s.status === 'done') || (msg.traceSteps || [])[0] || null;
    }

    public getExecutionPlanToolLabels(msg: any): string[] {
        return ((msg.executionPlan?.recommended_tools || msg.executionPlan?.recommendedTools || []) as string[]).map((i: string) => this.getToolLabel(i));
    }

    public getExecutionPlanParams(msg: any): Array<{ key: string, value: string }> {
        return Object.entries(msg.executionPlan?.params || {}).filter(([_, v]) => v !== null && v !== undefined && String(v).trim().length > 0).map(([k, v]) => ({ key: k, value: String(v) }));
    }

    public getExecutionPlanLines(msg: any): string[] { return msg.executionPlan?.plan_lines || msg.executionPlan?.planLines || []; }

    public getQualityBadges(msg: any): string[] {
        const q = msg.answerQuality || {};
        const b: string[] = [];
        if (q.llmUsed) b.push('LLM 해석');
        if (q.answerStyle) b.push(q.answerStyle);
        if (q.confidence) b.push(`신뢰도 ${q.confidence}`);
        if ((q.evidenceCount || 0) > 0) b.push(`근거 ${q.evidenceCount}건`);
        if (q.avgScore !== null && q.avgScore !== undefined && Number.isFinite(Number(q.avgScore))) b.push(`평균 ${Number(q.avgScore).toFixed(4)}`);
        return b;
    }

    // ===== UI Helpers =====
    public onKeydown(event: KeyboardEvent) {
        if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); this.sendChat(); }
    }

    private scrollToBottom() {
        setTimeout(() => { if (this.chatBodyRef?.nativeElement) this.chatBodyRef.nativeElement.scrollTop = this.chatBodyRef.nativeElement.scrollHeight; }, 50);
    }

    public toggleCollapse(msg: any) {
        msg.collapsed = !msg.collapsed;
        if (!msg.collapsed) this.collapsePreviousAssistantTurns(this.chatMessages.indexOf(msg));
    }

    public toggleTrace(msg: any) { msg.traceOpen = !msg.traceOpen; }

    public getToolIcon(name: string): string {
        const m: any = { search_papers: '📄', recommend_topics: '💡', detect_research_gaps: '🔍', generate_hypothesis: '🧪', analyze_keywords: '🏷️', predict_process: '⚙️', analyze_parameter_effect: '📈', inverse_search: '🔄', surrogate_predict: '🎯', compare_diagnostics: '⚖️', search_anomaly: '⚠️', failure_reasoning: '🔧', extract_equations: '📐', search_equations: '🔢', extract_assumptions: '📋', build_theory_graph: '🌐', read_page_results: '🧾', navigate_to_page: '🧭', get_collections: '📦' };
        return m[name] || '🔨';
    }

    public getToolLabel(name: string): string {
        const m: any = { search_papers: '논문 검색', recommend_topics: '주제 추천', detect_research_gaps: '연구 공백 탐지', generate_hypothesis: '가설 생성', analyze_keywords: '키워드 분석', predict_process: '공정 예측', analyze_parameter_effect: '파라미터 효과', inverse_search: '역탐색', surrogate_predict: '수치 예측', compare_diagnostics: '진단 비교', search_anomaly: '이상 검색', failure_reasoning: '고장 추론', extract_equations: '수식 추출', search_equations: '수식 검색', extract_assumptions: '가정 분석', build_theory_graph: '이론 그래프', read_page_results: '페이지 결과 읽기', navigate_to_page: '페이지 이동', get_collections: '컬렉션 목록' };
        return m[name] || name;
    }

    private estimateDifficulty(question: string): string {
        const s = [/[0-9]/.test(question), question.length > 30, /비교|예측|가설|분석|추론|recommend|predict/i.test(question)].filter(Boolean).length;
        if (s >= 3) return '심층 분석'; if (s === 2) return '표준 분석'; return '빠른 응답';
    }

    public formatToolInput(input: any): string {
        if (!input) return '';
        return Object.keys(input).map(k => `${k}: ${typeof input[k] === 'string' ? input[k] : JSON.stringify(input[k])}`).join(', ');
    }

    public parseToolResult(result: string): string {
        if (!result) return '';
        try {
            const p = JSON.parse(result);
            if (p.action === 'navigate') { const ps = Object.keys(p.params || {}).length > 0 ? ' | ' + Object.entries(p.params || {}).map(([k, v]) => `${k}=${v}`).join(', ') : ''; return `📍 ${p.title_ko || p.page} → ${p.tab || ''}${ps}`; }
            if (typeof p === 'object') { if (p.total !== undefined) return `${p.total}건의 결과를 찾았습니다.`; if (p.results) return `${p.results.length || 0}건의 결과`; if (p.error) return `❌ ${p.error}`; }
        } catch (e) { }
        return result.length > 200 ? result.slice(0, 200) + '...' : result;
    }

    public getTraceStatusLabel(status: string): string {
        const m: any = { pending: '대기', running: '진행 중', done: '완료', skipped: '건너뜀', error: '오류' };
        return m[status] || status;
    }

    public getTraceStatusClasses(status: string): string {
        const m: any = { pending: 'bg-slate-100 text-slate-500 border-slate-200', running: 'bg-cyan-50 text-cyan-700 border-cyan-200', done: 'bg-emerald-50 text-emerald-700 border-emerald-200', skipped: 'bg-amber-50 text-amber-700 border-amber-200', error: 'bg-rose-50 text-rose-700 border-rose-200' };
        return m[status] || m.pending;
    }

    public getTraceStepClasses(step: any): string {
        const m: any = { pending: 'border-slate-200 bg-white', running: 'border-cyan-300 bg-cyan-50/80 shadow-sm shadow-cyan-100', done: 'border-emerald-200 bg-emerald-50/70', skipped: 'border-amber-200 bg-amber-50/70', error: 'border-rose-200 bg-rose-50/80' };
        return m[step.status] || m.pending;
    }

    public getCompletedTraceCount(msg: any): number { return (msg.traceSteps || []).filter((s: any) => s.status === 'done').length; }

    public getCollapsedPreview(msg: any): string {
        const refs = msg.references?.length ? ` · 참고문헌 ${msg.references.length}건` : '';
        const text = msg.content?.trim() || msg.currentDescription || '결과 보기';
        return `${this.getCompletedTraceCount(msg)}/${(msg.traceSteps || []).length || 0} 단계 완료${refs} · ${this.truncate(text, 54)}`;
    }

    public formatScore(score: number): string { return Number.isFinite(score) ? score.toFixed(4) : '-'; }

    private parseSearchPapersResults(result: string): any[] {
        if (!result || typeof result !== 'string') return [];
        const refs: any[] = [];
        const regex = /--- Result (\d+) \(score: ([\d.]+)\) ---\nFile: (.+?) \| Chunk: (.+?)\nText: ([\s\S]*?)(?=\n--- Result|$)/g;
        let match;
        while ((match = regex.exec(result)) !== null) {
            refs.push({ rank: Number(match[1]), score: Number(match[2]), filename: match[3], chunk: match[4], excerpt: (match[5] || '').trim() });
        }
        return refs.slice(0, 5);
    }

    private buildSimilaritySummary(refs: any[]): string {
        if (!refs || refs.length === 0) return '유사도 요약 없음';
        const scores = refs.map((i: any) => Number(i.score) || 0);
        const avg = scores.reduce((s: number, v: number) => s + v, 0) / scores.length;
        return `상위 ${refs.length}건 평균 유사도 ${avg.toFixed(4)} · 최고 ${Math.max(...scores).toFixed(4)}`;
    }

    private detectLanguage(question: string): string { return /[가-힣]/.test(question) ? 'ko' : 'en'; }
    private truncate(text: string, limit: number = 60): string { return !text ? '' : text.length > limit ? `${text.slice(0, limit)}...` : text; }
}
