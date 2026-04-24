import { OnInit, OnDestroy } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { Router } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { marked } from 'marked';

declare const wiz: any;

export class Component implements OnInit, OnDestroy {
    private readonly collectionStorageKey: string = 'plasma.selectedCollection';
    private readonly collectionChangeEventName: string = 'plasma-collection-changed';
    private readonly chatStateStorageKey: string = 'plasma.sidebarChatState';
    private collectionChangeListener: any = null;

    constructor(
        public service: Service,
        private router: Router,
        private sanitizer: DomSanitizer,
    ) {}

    // ═══════════════════════════════════════════════════════════════
    // State
    // ═══════════════════════════════════════════════════════════════
    public chatMessages: any[] = [];
    public chatInput: string = '';
    public chatLoading: boolean = false;
    public chatHistory: any[] = [];

    public collections: any[] = [];
    public selectedCollection: string = '';
    public collectionSelected: boolean = false;
    public collectionsLoading: boolean = false;

    public pendingNavigation: any = null;
    private autoNavigateAfterAnswer: boolean = false;

    private abortController: AbortController | null = null;
    private typewriterTimers: Map<any, any> = new Map();
    private scrollTimer: any = null;

    public suggestions = [
        { icon: '🔬', text: '플라즈마 에칭 관련 최신 연구 동향' },
        { icon: '📊', text: 'RF 파워와 에칭률의 관계 분석' },
        { icon: '🧪', text: 'SF6 가스 유량별 공정 예측' },
        { icon: '📖', text: '플라즈마 진단 방법 비교' },
    ];

    // ═══════════════════════════════════════════════════════════════
    // Lifecycle
    // ═══════════════════════════════════════════════════════════════
    public async ngOnInit() {
        await this.service.init();
        this.configureMarked();
        const restored = this.restoreChatState();
        if (!restored) {
            const saved = this.getStoredCollection();
            if (saved) {
                this.selectedCollection = saved;
                this.collectionSelected = true;
            }
        }
        await this.loadCollections();
        this.collectionChangeListener = async (event: any) => {
            const nextCollection = String(event?.detail?.collection || '').trim();
            const deletedCollection = String(event?.detail?.deletedCollection || '').trim();
            if (deletedCollection) {
                const previousCollection = this.selectedCollection;
                await this.loadCollections();
                this.collectionSelected = !!this.selectedCollection;
                if (previousCollection !== this.selectedCollection) {
                    this.chatMessages = [];
                    this.chatHistory = [];
                    this.clearStoredChatState();
                }
                await this.service.render();
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
            this.chatMessages = [];
            this.chatHistory = [];
            this.clearStoredChatState();
            await this.service.render();
        };
        window.addEventListener(this.collectionChangeEventName, this.collectionChangeListener as EventListener);
        await this.service.render();
    }

    public ngOnDestroy() {
        if (this.collectionChangeListener) {
            window.removeEventListener(this.collectionChangeEventName, this.collectionChangeListener as EventListener);
            this.collectionChangeListener = null;
        }
        this.persistChatState();
        this.typewriterTimers.forEach(t => clearInterval(t));
        this.typewriterTimers.clear();
        if (this.scrollTimer) clearTimeout(this.scrollTimer);
        if (this.abortController) this.abortController.abort();
    }

    private configureMarked() {
        marked.setOptions({ breaks: true, gfm: true });
    }

    // ═══════════════════════════════════════════════════════════════
    // Collection Management
    // ═══════════════════════════════════════════════════════════════
    public async loadCollections() {
        this.collectionsLoading = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call('collections');
            if (code === 200) {
                this.collections = (data.collections || data || [])
                    .filter((c: any) => c.total_docs > 0)
                    .sort((a: any, b: any) => (b.total_docs || 0) - (a.total_docs || 0));
            }
        } catch { }
        this.collectionsLoading = false;
        // Verify saved collection still exists
        if (this.collectionSelected && this.selectedCollection) {
            const exists = this.collections.some(c => c.name === this.selectedCollection);
            if (!exists && this.collections.length > 0) {
                this.collectionSelected = false;
                this.selectedCollection = '';
                this.persistCollection('');
            }
        }
        await this.service.render();
    }

    public async selectCollection(name: string) {
        this.selectedCollection = name;
        this.collectionSelected = true;
        this.chatMessages = [];
        this.chatHistory = [];
        this.pendingNavigation = null;
        this.autoNavigateAfterAnswer = false;
        this.persistCollection(name);
        this.clearStoredChatState();
        this.broadcastCollectionChange(name);
        await this.service.render();
    }

    public async changeCollection() {
        this.collectionSelected = false;
        this.selectedCollection = '';
        this.chatMessages = [];
        this.chatHistory = [];
        this.pendingNavigation = null;
        this.autoNavigateAfterAnswer = false;
        this.persistCollection('');
        this.clearStoredChatState();
        this.broadcastCollectionChange('');
        await this.service.render();
    }

    private getStoredCollection(): string {
        try {
            return localStorage.getItem(this.collectionStorageKey) || '';
        } catch {
            return '';
        }
    }

    private persistCollection(name: string) {
        try {
            if (name && name.trim()) localStorage.setItem(this.collectionStorageKey, name);
            else localStorage.removeItem(this.collectionStorageKey);
        } catch { }
    }

    private persistChatState() {
        try {
            const snapshot: any = {
                chatMessages: this.chatMessages.map((message: any) => {
                    const clone = { ...message };
                    delete clone.typingActive;
                    clone.content = clone.content || clone.fullContent || '';
                    clone.fullContent = clone.content;
                    return clone;
                }),
                chatHistory: this.chatHistory,
                selectedCollection: this.selectedCollection,
                collectionSelected: this.collectionSelected,
                pendingNavigation: this.pendingNavigation,
            };
            if (!snapshot.chatMessages.length && !snapshot.pendingNavigation && !snapshot.selectedCollection) {
                sessionStorage.removeItem(this.chatStateStorageKey);
                return;
            }
            sessionStorage.setItem(this.chatStateStorageKey, JSON.stringify(snapshot));
        } catch { }
    }

    private restoreChatState(): boolean {
        try {
            const raw = sessionStorage.getItem(this.chatStateStorageKey);
            if (!raw) return false;
            sessionStorage.removeItem(this.chatStateStorageKey);
            const snapshot = JSON.parse(raw);
            this.chatHistory = Array.isArray(snapshot.chatHistory) ? snapshot.chatHistory : [];
            this.pendingNavigation = snapshot.pendingNavigation || null;
            this.selectedCollection = String(snapshot.selectedCollection || '').trim();
            this.collectionSelected = snapshot.collectionSelected ?? !!this.selectedCollection;

            if (Array.isArray(snapshot.chatMessages) && snapshot.chatMessages.length > 0) {
                this.chatMessages = snapshot.chatMessages.map((message: any) => {
                    const clone = { ...message };
                    if (clone.role === 'assistant') {
                        clone.typingActive = false;
                        clone.fullContent = clone.content || clone.fullContent || '';
                    }
                    return clone;
                });
            }

            return this.chatMessages.length > 0 || !!this.pendingNavigation || !!this.selectedCollection;
        } catch {
            return false;
        }
    }

    private clearStoredChatState() {
        try {
            sessionStorage.removeItem(this.chatStateStorageKey);
        } catch { }
    }

    private broadcastCollectionChange(collection: string, deletedCollection: string = '') {
        window.dispatchEvent(new CustomEvent(this.collectionChangeEventName, {
            detail: {
                collection: String(collection || '').trim(),
                deletedCollection: String(deletedCollection || '').trim(),
                source: 'component-chat-sidebar'
            }
        }));
    }

    // ═══════════════════════════════════════════════════════════════
    // Chat Core
    // ═══════════════════════════════════════════════════════════════
    public async sendChat(text?: string) {
        const message = (text || this.chatInput || '').trim();
        if (!message || this.chatLoading) return;

        this.chatInput = '';
        this.chatLoading = true;
        this.pendingNavigation = null;
        this.autoNavigateAfterAnswer = false;

        // User message
        this.chatMessages.push({ role: 'user', content: message });

        // Collapse previous assistant messages
        for (let i = 0; i < this.chatMessages.length - 1; i++) {
            if (this.chatMessages[i].role === 'assistant') {
                this.chatMessages[i].collapsed = true;
            }
        }

        // Assistant message placeholder
        const msg = this.createAssistantMessage();
        this.chatMessages.push(msg);

        this.scrollToBottom();
        await this.service.render();

        // SSE request
        try {
            this.abortController = new AbortController();
            const formData = new FormData();
            formData.append('message', message);
            formData.append('history', JSON.stringify(this.chatHistory));
            formData.append('collection', this.selectedCollection);

            const response = await fetch('/wiz/api/page.agent.v2/agent_chat', {
                method: 'POST',
                body: formData,
                signal: this.abortController.signal,
            });

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
                            this.handleChatEvent(msg, event);
                        } catch { }
                    }
                }
            }
        } catch (e: any) {
            if (e.name !== 'AbortError') {
                msg.content = msg.content || '⚠️ 연결 오류가 발생했습니다.';
                msg.error = true;
            }
        } finally {
            this.chatLoading = false;
            this.abortController = null;
            await this.service.render();
        }
    }

    public cancelChat() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
        this.chatLoading = false;
        // Finalize current message
        const last = this.chatMessages[this.chatMessages.length - 1];
        if (last?.role === 'assistant') {
            this.finalizeMessage(last);
            if (!last.content) last.content = '⏹ 사용자가 중단했습니다.';
        }
    }

    public async clearChat() {
        this.chatMessages = [];
        this.chatHistory = [];
        this.pendingNavigation = null;
        this.autoNavigateAfterAnswer = false;
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
        this.chatLoading = false;
        this.clearStoredChatState();
        await this.service.render();
    }

    // ═══════════════════════════════════════════════════════════════
    // SSE Event Handler
    // ═══════════════════════════════════════════════════════════════
    private handleChatEvent(msg: any, event: any) {
        switch (event.type) {
            case 'orchestration':
                msg.traceSteps = (event.trace_steps || []).map((s: any) => ({
                    id: s.id,
                    title: s.title || '',
                    status: s.status || 'pending',
                    detail: s.detail || '',
                }));
                msg.traceOpen = false;
                if (event.execution_plan) {
                    msg.executionPlan = event.execution_plan;
                }
                msg.pageResultCard = {
                    loading: true,
                    page: event.page || event.execution_plan?.page || '',
                    tab: event.tab || event.execution_plan?.tab || '',
                    query: event.execution_plan?.params?.query || event.execution_plan?.query || '',
                    paramsText: this.formatPageResultParams(event.execution_plan?.params || {}),
                    summary: `선택된 경로 ${event.page || '-'}${event.tab ? ` · ${event.tab}` : ''} 기준으로 결과를 준비하고 있습니다.`,
                    evidenceLines: []
                };
                msg.navigationCard = {
                    loading: true,
                    summary: `${event.page || '-'}${event.tab ? ` · ${event.tab}` : ''} 페이지로 이동을 준비하고 있습니다.`,
                    page: event.page || '',
                    tab: event.tab || '',
                    query: event.execution_plan?.params?.query || event.execution_plan?.query || '',
                    params: event.execution_plan?.params || {},
                };
                msg.currentDescription = `관련 페이지 ${event.page || '-'}${event.tab ? `의 ${event.tab}` : ''} 결과를 바탕으로 답변 방향을 정하고 있습니다.`;
                break;

            case 'pipeline':
                this.updatePipelineTrace(msg, event);
                if (event.detail) {
                    msg.currentDescription = event.detail;
                }
                break;

            case 'tool_use': {
                if (!msg.toolCalls) msg.toolCalls = [];
                msg.toolCalls.push({
                    type: 'use',
                    name: event.name || '',
                    input: event.input || {},
                });

                if (event.name === 'read_page_results') {
                    msg.pageResultCard = {
                        loading: true,
                        page: event.input?.page || msg.pageResultCard?.page || '',
                        tab: event.input?.tab || msg.pageResultCard?.tab || '',
                        query: event.input?.query || msg.pageResultCard?.query || '',
                        paramsText: this.formatPageResultParams(event.input?.params || {}),
                        summary: '실제 페이지가 보여줄 결과를 읽어 현재까지 핵심 포인트를 정리하고 있습니다.',
                        evidenceLines: []
                    };
                }

                if (event.name === 'navigate_to_page') {
                    msg.navigationCard = {
                        loading: true,
                        summary: '최종 답변 이후 이어질 페이지와 탭을 확정하고 있습니다.',
                        page: event.input?.page || msg.navigationCard?.page || '',
                        tab: event.input?.tab || msg.navigationCard?.tab || '',
                        query: event.input?.query || msg.navigationCard?.query || '',
                        params: event.input?.params || msg.navigationCard?.params || {},
                    };
                }
                break;
            }

            case 'tool_result': {
                if (!msg.toolCalls) msg.toolCalls = [];
                msg.toolCalls.push({
                    type: 'result',
                    name: event.name || '',
                    output: event.result,
                });

                // Navigation
                if (event.name === 'navigate_to_page') {
                    try {
                        const output = typeof event.result === 'string'
                            ? JSON.parse(event.result) : event.result;
                        if (output?.navigated || output?.page || output?.url) {
                            this.applyNavigationPayload(msg, output);
                        }
                    } catch { }
                }

                // Page results
                if (event.name === 'read_page_results') {
                    try {
                        const pageResultCard = this.parsePageResultCard(event.result);
                        if (pageResultCard) {
                            msg.pageResultCard = {
                                ...pageResultCard,
                                loading: false,
                            };
                            msg.currentDescription = pageResultCard.summary;
                        }
                    } catch { }
                }
                break;
            }

            case 'quality':
                msg.answerQuality = event;
                break;

            case 'text':
                if (event.content) {
                    this.startTypewriter(msg, event.content);
                }
                break;

            case 'evidence_items':
                msg.evidenceItems = event.items || [];
                break;

            case 'history':
                this.chatHistory = event.messages || [];
                break;

            case 'done':
                this.finalizeMessage(msg);
                this.persistChatState();
                if (this.autoNavigateAfterAnswer && this.pendingNavigation) {
                    setTimeout(() => {
                        this.navigateNow();
                    }, 250);
                }
                break;

            case 'error':
                msg.content = msg.content || `⚠️ ${event.message || '오류가 발생했습니다.'}`;
                msg.error = true;
                this.chatLoading = false;
                this.persistChatState();
                break;
        }

        this.scrollToBottom();
        this.service.render();
    }

    // ═══════════════════════════════════════════════════════════════
    // Trace / Pipeline Helpers
    // ═══════════════════════════════════════════════════════════════
    private updatePipelineTrace(msg: any, event: any) {
        if (!msg.traceSteps?.length) return;

        const component = event.component;
        const status = event.status;

        const stepMap: Record<string, number[]> = {
            'prompt': [1, 8],
            'memory': [9],
            'orchestrator': [2, 3, 4, 5, 6, 7, 14],
            'tools': [10, 11, 12, 13],
            'streaming': [15, 16],
        };

        const ids = stepMap[component];
        if (!ids) return;

        for (const step of msg.traceSteps) {
            if (!ids.includes(step.id)) continue;
            if (status === 'done') {
                step.status = 'done';
            } else if (status === 'skipped') {
                step.status = 'skipped';
            } else if (status === 'running' && step.status === 'pending') {
                step.status = 'running';
            }
        }

        // Update detail
        if (event.detail) {
            const active = msg.traceSteps.find(
                (s: any) => ids.includes(s.id) && s.status === 'running'
            );
            if (active) active.detail = event.detail;
        }

        // Check completion
        msg.traceCompleted = msg.traceSteps.every(
            (s: any) => s.status === 'done' || s.status === 'skipped'
        );
    }

    public toggleTrace(msg: any) {
        msg.traceOpen = !msg.traceOpen;
    }

    public getCurrentTraceStep(msg: any): any {
        if (!msg?.traceSteps?.length) return null;
        return msg.traceSteps.find((s: any) => s.status === 'running') ||
            msg.traceSteps.filter((s: any) => s.status === 'done').pop() ||
            msg.traceSteps[0];
    }

    public getCompletedTraceCount(msg: any): number {
        if (!msg?.traceSteps?.length) return 0;
        return msg.traceSteps.filter((s: any) => s.status === 'done').length;
    }

    // ═══════════════════════════════════════════════════════════════
    // Navigation
    // ═══════════════════════════════════════════════════════════════
    private applyNavigationPayload(msg: any, data: any) {
        const navigationCollection = String(data?.collection || data?.params?.collection || '').trim();
        if (navigationCollection) {
            this.selectedCollection = navigationCollection;
            this.collectionSelected = true;
            this.persistCollection(navigationCollection);
            this.broadcastCollectionChange(navigationCollection);
        }

        this.pendingNavigation = {
            page: data.page,
            title: data.title_ko || data.title || data.page,
            url: data.url,
            tab: data.tab,
            query: data.query,
            params: data.params || {},
            collection: navigationCollection,
        };

        msg.navigationCard = {
            loading: false,
            summary: this.parseToolResult(this.pendingNavigation),
            page: this.pendingNavigation.page,
            tab: this.pendingNavigation.tab,
            query: this.pendingNavigation.query,
            params: this.pendingNavigation.params,
        };

        this.autoNavigateAfterAnswer = true;
    }

    public async navigateNow() {
        if (!this.pendingNavigation) return;
        const nav = this.pendingNavigation;
        this.autoNavigateAfterAnswer = false;
        this.persistChatState();
        this.pendingNavigation = null;
        await this.forceNavigate(nav);
    }

    private async forceNavigate(nav: any) {
        const targetPath = this.getNavigationTargetPath(nav);
        const queryParams = this.buildNavigationQueryParams(nav);
        const savedReuse = this.router.routeReuseStrategy.shouldReuseRoute;

        try {
            (this.router as any).onSameUrlNavigation = 'reload';
            this.router.routeReuseStrategy.shouldReuseRoute = () => false;
            await this.router.navigate([targetPath], { queryParams });
        } catch {
            const queryString = new URLSearchParams(
                Object.entries(queryParams || {}).reduce((acc: any, [key, value]) => {
                    if (value !== null && value !== undefined && String(value).trim().length > 0) {
                        acc[key] = String(value);
                    }
                    return acc;
                }, {})
            ).toString();
            window.location.href = queryString ? `${targetPath}?${queryString}` : targetPath;
        } finally {
            setTimeout(() => {
                (this.router as any).onSameUrlNavigation = 'ignore';
                this.router.routeReuseStrategy.shouldReuseRoute = savedReuse;
            }, 50);
        }
    }

    private getNavigationTargetPath(nav: any): string {
        const rawPath = String(nav?.url || nav?.page || '').trim();
        if (!rawPath) return '/';
        const path = rawPath.split('?')[0];
        return path.startsWith('/') ? path : `/${path}`;
    }

    private buildNavigationQueryParams(nav: any): any {
        const queryParams: any = {};

        if (nav?.tab) queryParams.tab = nav.tab;
        if (nav?.query) queryParams.q = nav.query;

        for (const [key, value] of Object.entries(nav?.params || {})) {
            if (key === 'collection') continue;
            if (value === null || value === undefined) continue;
            const normalized = String(value).trim();
            if (!normalized.length) continue;
            queryParams[key] = normalized;
        }

        if (nav?.collection) {
            queryParams.collection = nav.collection;
        }

        return queryParams;
    }

    public buildNavigationSummary(nav: any): string {
        if (!nav) return '';
        const parts = [`${nav.page}/${nav.tab}`];
        if (nav.query) parts.push(`"${nav.query}"`);
        if (nav.params) {
            const p = Object.entries(nav.params)
                .filter(([, v]) => v !== undefined && v !== null && String(v).trim())
                .map(([k, v]) => `${k}=${v}`)
                .join(', ');
            if (p) parts.push(`(${p})`);
        }
        return parts.join(' · ');
    }

    // ═══════════════════════════════════════════════════════════════
    // Typewriter Effect
    // ═══════════════════════════════════════════════════════════════
    private startTypewriter(msg: any, fullText: string) {
        msg.fullContent = fullText;
        msg.typingActive = true;

        if (this.typewriterTimers.has(msg)) {
            clearInterval(this.typewriterTimers.get(msg));
        }

        let idx = msg.content?.length || 0;
        const timer = setInterval(() => {
            if (idx >= fullText.length) {
                clearInterval(timer);
                this.typewriterTimers.delete(msg);
                msg.content = fullText;
                msg.typingActive = false;
                this.service.render();
                return;
            }
            msg.content = fullText.slice(0, idx + 2);
            idx += 2;
            this.service.render();
            this.scrollToBottom();
        }, 18);

        this.typewriterTimers.set(msg, timer);
    }

    // ═══════════════════════════════════════════════════════════════
    // Message Creation / Finalization
    // ═══════════════════════════════════════════════════════════════
    private createAssistantMessage(): any {
        return {
            role: 'assistant',
            content: '',
            collapsed: false,
            traceSteps: [],
            traceOpen: false,
            traceCompleted: false,
            executionPlan: null,
            toolCalls: [],
            navigationCard: null,
            pageResultCard: null,
            answerQuality: null,
            evidenceItems: [],
            evidenceOpen: false,
            error: false,
            typingActive: false,
            fullContent: '',
            currentDescription: '',
        };
    }

    private finalizeMessage(msg: any) {
        // Complete trace steps
        if (msg.traceSteps) {
            for (const step of msg.traceSteps) {
                if (step.status === 'running') step.status = 'done';
                if (step.status === 'pending') step.status = 'skipped';
            }
            msg.traceCompleted = true;
        }

        // Stop typewriter
        if (this.typewriterTimers.has(msg)) {
            clearInterval(this.typewriterTimers.get(msg));
            this.typewriterTimers.delete(msg);
            if (msg.fullContent) msg.content = msg.fullContent;
            msg.typingActive = false;
        }

        this.chatLoading = false;
    }

    // ═══════════════════════════════════════════════════════════════
    // Tool Helpers
    // ═══════════════════════════════════════════════════════════════
    public getUsedToolNames(msg: any): string[] {
        if (!msg?.toolCalls?.length) return [];
        const seen = new Set<string>();
        return msg.toolCalls
            .filter((tc: any) => tc.type === 'result' && tc.name)
            .map((tc: any) => tc.name)
            .filter((name: string) => {
                if (seen.has(name)) return false;
                seen.add(name);
                return true;
            });
    }

    public getToolIcon(name: string): string {
        const icons: Record<string, string> = {
            search_papers: '🔍', navigate_to_page: '🧭', read_page_results: '📄',
            recommend_topics: '💡', detect_research_gaps: '🔎', generate_hypothesis: '🧬',
            predict_process: '📊', surrogate_predict: '🤖', inverse_search: '🔄',
            analyze_parameter_effect: '📈', search_anomaly: '⚡', compare_diagnostics: '🔬',
            failure_reasoning: '🛠️', search_equations: '📐', extract_assumptions: '📝',
            build_theory_graph: '🕸️', analyze_keywords: '🏷️', get_collections: '📦',
            extract_equations: '∑',
        };
        return icons[name] || '🔧';
    }

    public getToolLabel(name: string): string {
        const labels: Record<string, string> = {
            search_papers: '논문 검색', navigate_to_page: '페이지 이동',
            read_page_results: '결과 수집', recommend_topics: '주제 추천',
            detect_research_gaps: '갭 분석', generate_hypothesis: '가설 생성',
            predict_process: '공정 예측', surrogate_predict: '대리 예측',
            inverse_search: '역설계', analyze_parameter_effect: '파라미터 분석',
            search_anomaly: '이상 탐지', compare_diagnostics: '진단 비교',
            failure_reasoning: '고장 추론', search_equations: '수식 검색',
            extract_assumptions: '가정 추출', build_theory_graph: '이론 그래프',
            analyze_keywords: '키워드 분석', get_collections: '컬렉션 조회',
            extract_equations: '수식 추출',
        };
        return labels[name] || name;
    }

    // ═══════════════════════════════════════════════════════════════
    // Render Helpers
    // ═══════════════════════════════════════════════════════════════
    public shouldRenderNavigationCard(msg: any): boolean {
        return !!msg.navigationCard;
    }

    public shouldRenderPageResultCard(msg: any): boolean {
        return !!msg.pageResultCard;
    }

    public shouldRenderAnswerCard(msg: any): boolean {
        return !!(msg.content || msg.typingActive);
    }

    public shouldRenderQualityCard(msg: any): boolean {
        return !!msg.answerQuality && this.getQualityBadges(msg).length > 0;
    }

    public shouldRenderEvidenceCard(msg: any): boolean {
        return msg.evidenceItems && msg.evidenceItems.length > 0;
    }

    public getQualityBadges(msg: any): string[] {
        if (!msg?.answerQuality) return [];
        const q = msg.answerQuality;
        const badges: string[] = [];
        if (q.confidence) badges.push(`신뢰도: ${q.confidence}`);
        if (q.evidenceCount) badges.push(`근거 ${q.evidenceCount}건`);
        if (q.answerStyle) badges.push(q.answerStyle);
        if (q.llmUsed) badges.push('LLM 정제');
        return badges;
    }

    public getAssistantPreviewLines(msg: any): string[] {
        const desc = msg.currentDescription || '';
        if (!desc) return ['답변을 생성하고 있습니다...'];
        return desc.split('\n').filter((l: string) => l.trim()).slice(0, 3);
    }

    // ═══════════════════════════════════════════════════════════════
    // Evidence
    // ═══════════════════════════════════════════════════════════════
    public toggleEvidence(msg: any) {
        msg.evidenceOpen = !msg.evidenceOpen;
    }

    public formatEvidenceScore(score: any): string {
        if (score === null || score === undefined) return '';
        const n = Number(score);
        return isNaN(n) ? String(score) : `${(n * 100).toFixed(1)}%`;
    }

    private formatPageResultParams(params: any): string {
        const entries = Object.entries(params || {}).filter(([key, value]) => {
            return key !== 'collection' && value !== null && value !== undefined && String(value).trim().length > 0;
        });
        return entries.map(([key, value]) => `${key}=${String(value)}`).join(', ');
    }

    private summarizePageResult(result: any): string {
        try {
            const parsed = typeof result === 'string' ? JSON.parse(result) : result;
            if (parsed?.error) return `페이지 결과 추출 실패: ${parsed.error}`;
            if (parsed?.page && parsed?.tab) {
                const count = parsed.total ?? parsed.total_hits ?? parsed.total_searched;
                const query = parsed.query ? `'${parsed.query}'` : '질문 키워드';
                const paramsText = this.formatPageResultParams(parsed.params || {});
                if (count !== undefined) {
                    return `${parsed.page}/${parsed.tab} 페이지에 ${query}를 적용해 결과 ${count}건을 확보했습니다${paramsText ? ` (${paramsText})` : ''}.`;
                }
                if (parsed.stats) return `${parsed.page}/${parsed.tab} 페이지 결과와 통계 정보를 확보했습니다${paramsText ? ` (${paramsText})` : ''}.`;
                return `${parsed.page}/${parsed.tab} 페이지 결과 JSON을 확보했습니다${paramsText ? ` (${paramsText})` : ''}.`;
            }
        } catch { }
        return '페이지 결과 JSON을 확보했습니다.';
    }

    private parsePageResultCard(result: any): any {
        try {
            const parsed = typeof result === 'string' ? JSON.parse(result) : result;
            if (!parsed || parsed.error || !parsed.page || !parsed.tab) return null;

            const count = parsed.total ?? parsed.total_hits ?? parsed.total_searched;
            const paramsText = this.formatPageResultParams(parsed.params || {});
            const evidenceLines: string[] = [];

            if (parsed.query) evidenceLines.push(`질문 키워드: ${parsed.query}`);
            if (paramsText) evidenceLines.push(`적용 인자값: ${paramsText}`);
            if (count !== undefined) evidenceLines.push(`확인된 결과 수: ${count}건`);
            else if (parsed.stats) evidenceLines.push('통계 정보가 함께 반환된 결과입니다.');

            return {
                page: parsed.page,
                tab: parsed.tab,
                query: parsed.query || '',
                paramsText,
                summary: this.summarizePageResult(parsed),
                evidenceLines: evidenceLines.slice(0, 3)
            };
        } catch { }
        return null;
    }

    public parseToolResult(result: any): string {
        try {
            const parsed = typeof result === 'string' ? JSON.parse(result) : result;
            if (!parsed) return '페이지 이동 정보를 정리했습니다.';
            const page = parsed.page || '-';
            const tab = parsed.tab ? ` / ${parsed.tab}` : '';
            const query = parsed.query ? ` · "${parsed.query}"` : '';
            const paramsText = this.formatPageResultParams(parsed.params || {});
            return `${page}${tab} 페이지로 이어서 볼 수 있습니다${query}${paramsText ? ` (${paramsText})` : ''}.`;
        } catch { }
        return typeof result === 'string' ? result : '페이지 이동 정보를 정리했습니다.';
    }

    private extractEvidenceLines(output: any): string[] {
        if (!output) return [];
        const lines: string[] = [];
        try {
            if (output.results && Array.isArray(output.results)) {
                for (const r of output.results.slice(0, 5)) {
                    const title = r.title || r.name || r.doc_id || '';
                    if (title) lines.push(title);
                }
            }
        } catch { }
        return lines;
    }

    // ═══════════════════════════════════════════════════════════════
    // Markdown Rendering
    // ═══════════════════════════════════════════════════════════════
    public getDisplayedAssistantContent(msg: any): SafeHtml {
        if (!msg.content) return this.sanitizer.bypassSecurityTrustHtml('');
        const html = this.renderMarkdown(msg.content);
        return this.sanitizer.bypassSecurityTrustHtml(html);
    }

    private renderMarkdown(text: string): string {
        try {
            let html = marked.parse(text, { breaks: true, gfm: true }) as string;
            // Wrap code blocks with header
            html = html.replace(
                /<pre><code(?:\s+class="language-(\w+)")?>([\s\S]*?)<\/code><\/pre>/g,
                (_, lang, code) => {
                    const language = lang || 'text';
                    return `<div class="code-block-wrapper">
                        <div class="code-block-header">
                            <span class="code-lang">${language}</span>
                            <button class="code-copy-btn" onclick="(() => { const c = this.closest('.code-block-wrapper').querySelector('code').textContent; navigator.clipboard.writeText(c); this.textContent = '복사됨!'; setTimeout(() => this.textContent = '복사', 1500); })()">복사</button>
                        </div>
                        <pre><code class="language-${language}">${code}</code></pre>
                    </div>`;
                }
            );
            return html;
        } catch {
            return text;
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // Utility
    // ═══════════════════════════════════════════════════════════════
    public onKeydown(event: KeyboardEvent) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendChat();
        }
    }

    private scrollToBottom() {
        if (this.scrollTimer) clearTimeout(this.scrollTimer);
        this.scrollTimer = setTimeout(() => {
            const el = document.querySelector('.chat-sidebar-body');
            if (el) el.scrollTop = el.scrollHeight;
        }, 50);
    }

    public toggleCollapse(msg: any) {
        msg.collapsed = !msg.collapsed;
    }

    public getCollapsedPreview(msg: any): string {
        const text = msg.content || msg.currentDescription || '답변';
        return text.length > 60 ? text.slice(0, 60) + '...' : text;
    }

    public async copyAnswer(msg: any) {
        if (!msg?.content) return;
        try {
            await navigator.clipboard.writeText(msg.content);
        } catch { }
    }

    public closeChat() {
        this.service.status.toggle('chat', false);
        localStorage.setItem('chat_sidebar_open', 'false');
    }
}
