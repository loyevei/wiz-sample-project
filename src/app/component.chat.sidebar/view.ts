import { OnInit, OnDestroy, ViewChild, ElementRef, ChangeDetectorRef } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';
import { Router } from '@angular/router';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { marked } from 'marked';

declare const wiz: any;

export class Component implements OnInit, OnDestroy {
    private readonly COLLECTION_KEY = 'plasma.selectedCollection';
    private readonly COLLECTION_EVENT = 'plasma-collection-changed';
    private readonly STATE_KEY = 'plasma.sidebarChatState';
    private collectionListener: any = null;

    constructor(
        public service: Service,
        private router: Router,
        private sanitizer: DomSanitizer,
        private cdr: ChangeDetectorRef,
    ) {}

    // ── State ──
    public messages: any[] = [];
    public chatInput = '';
    public isLoading = false;
    public chatHistory: any[] = [];

    public collections: any[] = [];
    public selectedCollection = '';
    public collectionReady = false;
    public collectionsLoading = false;

    private abortController: AbortController | null = null;

    public suggestions = [
        { icon: '🔬', text: '플라즈마 에칭 관련 최신 연구 동향' },
        { icon: '📊', text: 'RF 파워와 에칭률의 관계 분석' },
        { icon: '🧪', text: 'SF6 가스 유량별 공정 예측' },
        { icon: '📖', text: '플라즈마 진단 방법 비교' },
    ];

    @ViewChild('chatBody') chatBodyRef!: ElementRef;
    @ViewChild('chatInputEl') chatInputRef!: ElementRef;

    // ── Lifecycle ──
    async ngOnInit() {
        await this.service.init();
        marked.setOptions({ breaks: true, gfm: true });

        const restored = this.restoreState();
        if (!restored) {
            const saved = this.getStoredCollection();
            if (saved) { this.selectedCollection = saved; this.collectionReady = true; }
        }
        await this.loadCollections();

        this.collectionListener = (e: any) => this.onCollectionChange(e);
        window.addEventListener(this.COLLECTION_EVENT, this.collectionListener);
        await this.service.render();
    }

    ngOnDestroy() {
        if (this.collectionListener) {
            window.removeEventListener(this.COLLECTION_EVENT, this.collectionListener);
        }
        this.persistState();
        this.cancel();
    }

    // ── Collection ──
    private getStoredCollection(): string {
        try { return localStorage.getItem(this.COLLECTION_KEY) || ''; } catch { return ''; }
    }

    private persistCollection(name: string) {
        try {
            if (name?.trim()) localStorage.setItem(this.COLLECTION_KEY, name);
            else localStorage.removeItem(this.COLLECTION_KEY);
        } catch {}
    }

    private broadcastCollection(col: string, deleted = '') {
        window.dispatchEvent(new CustomEvent(this.COLLECTION_EVENT, {
            detail: { collection: col.trim(), deletedCollection: deleted, source: 'chat-sidebar' }
        }));
    }

    private async onCollectionChange(e: any) {
        const next = String(e?.detail?.collection || '').trim();
        const deleted = String(e?.detail?.deletedCollection || '').trim();
        if (deleted) {
            await this.loadCollections();
            this.collectionReady = !!this.selectedCollection;
            this.cdr.detectChanges();
            return;
        }
        if (!next || next === this.selectedCollection) return;
        this.selectedCollection = next;
        this.collectionReady = true;
        this.persistCollection(next);
        this.clearChat();
        this.cdr.detectChanges();
    }

    async loadCollections() {
        this.collectionsLoading = true;
        this.cdr.detectChanges();
        try {
            let list: any[] = [];
            try {
                const r = await fetch('/wiz/api/page.embedding/collections', { method: 'POST', credentials: 'same-origin' });
                const p = await r.json();
                if (p.code === 200) list = p.data?.collections || [];
            } catch {}
            if (!list.length) {
                const r = await wiz.call('collections');
                if (r.code === 200) list = r.data?.collections || [];
            }
            this.collections = list.sort((a: any, b: any) => (b.total_docs || 0) - (a.total_docs || 0));
            const stored = this.getStoredCollection();
            if (stored && this.collections.find((c: any) => c.name === stored)) {
                this.selectedCollection = stored;
            } else if (this.collections.length > 0 && !this.selectedCollection) {
                this.selectedCollection = this.collections[0].name;
            }
            if (this.selectedCollection) this.persistCollection(this.selectedCollection);
            this.collectionReady = this.collections.length === 1 || !!this.selectedCollection;
        } catch {}
        this.collectionsLoading = false;
        this.cdr.detectChanges();
    }

    selectCollection(name: string) {
        this.selectedCollection = name;
        this.collectionReady = true;
        this.persistCollection(name);
        this.broadcastCollection(name);
        this.clearChat();
        this.cdr.detectChanges();
        setTimeout(() => this.chatInputRef?.nativeElement?.focus(), 200);
    }

    changeCollection() {
        this.collectionReady = false;
        this.cdr.detectChanges();
    }

    // ── Chat Core ──
    async sendChat(text?: string) {
        const message = (text || this.chatInput || '').trim();
        if (!message || this.isLoading) return;

        this.chatInput = '';
        this.isLoading = true;

        // Collapse previous assistant messages
        for (const m of this.messages) {
            if (m.role === 'assistant') m.collapsed = true;
        }

        this.messages.push({ role: 'user', content: message });
        const assistant: any = {
            role: 'assistant', content: '', steps: [],
            isStreaming: true, collapsed: false,
            navigation: null, pageResult: null,
            evidence: null, evidenceOpen: false,
        };
        this.messages.push(assistant);
        this.scrollToBottom();
        this.cdr.detectChanges();

        let receivedDone = false;
        let receivedHistory = false;

        try {
            this.abortController = new AbortController();
            const form = new FormData();
            form.append('message', message);
            form.append('history', JSON.stringify(this.chatHistory));
            form.append('collection', this.selectedCollection);

            const response = await fetch('/wiz/api/page.agent.v2/agent_chat', {
                method: 'POST', body: form, signal: this.abortController.signal,
            });
            const reader = response.body!.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            const DONE_TOKEN = {};

            const readNext = async () => {
                const pending = reader.read().catch(() => ({ done: true, value: undefined }));
                if (!receivedDone) return pending;
                const timeout = new Promise<any>(r => setTimeout(() => r(DONE_TOKEN), 400));
                const result = await Promise.race([pending, timeout]);
                if (result === DONE_TOKEN) {
                    await reader.cancel().catch(() => {});
                    return { done: true, value: undefined };
                }
                return result;
            };

            while (true) {
                const { done, value } = await readNext();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const chunks = buffer.split('\n\n');
                buffer = chunks.pop() || '';
                for (const chunk of chunks) {
                    const line = chunk.trim();
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const event = JSON.parse(line.slice(6));
                        if (event.type === 'done') receivedDone = true;
                        if (event.type === 'history') receivedHistory = true;
                        this.handleEvent(assistant, event);
                    } catch {}
                }
                this.cdr.detectChanges();
            }
            buffer += decoder.decode();
            if (buffer.trim()) {
                for (const chunk of buffer.split('\n\n')) {
                    const line = chunk.trim();
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const event = JSON.parse(line.slice(6));
                        if (event.type === 'done') receivedDone = true;
                        if (event.type === 'history') receivedHistory = true;
                        this.handleEvent(assistant, event);
                    } catch {}
                }
            }
        } catch (e: any) {
            if (e.name !== 'AbortError') {
                assistant.content += '\n\n⚠️ 연결 오류가 발생했습니다.';
            }
        }

        // Finalize
        assistant.isStreaming = false;
        if (!assistant.content?.trim()) {
            assistant.content = this.buildFallback(assistant);
        }
        if (!receivedHistory) {
            this.chatHistory = [
                ...this.chatHistory,
                { role: 'user', content: message },
                { role: 'assistant', content: assistant.content || '' },
            ];
        }
        // Mark all steps as done
        for (const step of assistant.steps) {
            if (step.status === 'running') step.status = 'done';
        }

        // Auto-navigate after completion
        if (assistant.navigation && !assistant.navigation.autoNavigated) {
            setTimeout(() => this.autoNavigate(assistant), 300);
        }

        this.isLoading = false;
        this.abortController = null;
        this.persistState();
        this.cdr.detectChanges();
    }

    // ── SSE Event Handler ──
    private handleEvent(msg: any, event: any) {
        switch (event.type) {
            case 'orchestration':
                msg.steps.push({
                    type: 'thinking', status: 'done', name: 'Orchestration',
                    detail: `${event.page || ''}${event.tab ? ' · ' + event.tab : ''} 경로로 분석합니다`,
                    collapsed: true,
                });
                break;

            case 'pipeline':
                // Lightweight status — just update last thinking step
                break;

            case 'tool_use':
                msg.steps.push({
                    type: 'tool', status: 'running', id: event.id,
                    name: event.name || '', detail: '',
                    input: event.input, output: null, collapsed: true,
                });
                break;

            case 'tool_result': {
                const step = msg.steps.find((s: any) => s.id === event.id);
                if (step) {
                    step.status = 'done';
                    step.output = event.result;
                    step.detail = this.summarizeTool(event.name, event.result);
                }
                // Navigation
                if (event.name === 'navigate_to_page') {
                    try {
                        const d = typeof event.result === 'string' ? JSON.parse(event.result) : event.result;
                        if (d?.page || d?.url) {
                            msg.navigation = {
                                page: d.page, tab: d.tab, url: d.url,
                                query: d.query, params: d.params || {},
                                collection: d.collection || this.selectedCollection,
                                title: d.title_ko || d.page, autoNavigated: false,
                            };
                            const col = String(d.collection || d.params?.collection || '').trim();
                            if (col) {
                                this.selectedCollection = col;
                                this.persistCollection(col);
                                this.broadcastCollection(col);
                            }
                        }
                    } catch {}
                }
                // Page results
                if (event.name === 'read_page_results') {
                    try {
                        const d = typeof event.result === 'string' ? JSON.parse(event.result) : event.result;
                        msg.pageResult = {
                            page: d.page || '', tab: d.tab || '',
                            query: d.query || '', totalHits: d.total_hits || d.total_searched || 0,
                            results: (d.results || d.data || []).slice(0, 5).map((item: any) => ({
                                title: item.title || item.name || item.doc_id || '',
                                score: item.score || item.relevance_score || null,
                            })).filter((item: any) => item.title),
                        };
                    } catch {}
                }
                break;
            }

            case 'text_delta':
                msg.content = (msg.content || '') + (event.content || '');
                msg.isStreaming = true;
                msg._streamedDeltas = true;
                break;

            case 'text_clear':
                msg.content = '';
                msg._streamedDeltas = false;
                break;

            case 'text':
                if ((event.content || '').trim()) {
                    if (msg._streamedDeltas) {
                        msg.content = event.content;
                        msg._streamedDeltas = false;
                    } else {
                        msg.content = msg.content
                            ? msg.content + '\n\n' + event.content
                            : event.content;
                    }
                }
                break;

            case 'quality':
                msg.quality = event;
                break;

            case 'evidence_items':
                msg.evidence = event.items || [];
                break;

            case 'history':
                this.chatHistory = event.messages || [];
                break;

            case 'done':
                msg.isStreaming = false;
                this.isLoading = false;
                break;

            case 'error':
                msg.content += `\n\n⚠️ ${event.message || '오류가 발생했습니다.'}`;
                msg.isStreaming = false;
                break;
        }
        this.scrollToBottom();
    }

    // ── Tool Helpers ──
    getToolIcon(name: string): string {
        const m: Record<string, string> = {
            search_papers: '🔍', navigate_to_page: '🧭', read_page_results: '📄',
            recommend_topics: '💡', detect_research_gaps: '🔎', generate_hypothesis: '🧬',
            predict_process: '📊', surrogate_predict: '🤖', inverse_search: '🔄',
            analyze_parameter_effect: '📈', search_anomaly: '⚡', compare_diagnostics: '🔬',
            analyze_keywords: '🏷️', get_collections: '📦', extract_equations: '∑',
        };
        return m[name] || '🔧';
    }

    getToolLabel(name: string): string {
        const m: Record<string, string> = {
            search_papers: '논문 검색', navigate_to_page: '페이지 이동',
            read_page_results: '페이지 결과 수집', recommend_topics: '주제 추천',
            detect_research_gaps: '연구 갭 분석', generate_hypothesis: '가설 생성',
            predict_process: '공정 예측', surrogate_predict: '대리 예측',
            inverse_search: '역설계 탐색', analyze_parameter_effect: '파라미터 분석',
            search_anomaly: '이상 탐지', compare_diagnostics: '진단 비교',
            analyze_keywords: '키워드 분석', get_collections: '컬렉션 조회',
            extract_equations: '수식 추출',
        };
        return m[name] || name;
    }

    private summarizeTool(name: string, result: any): string {
        try {
            const d = typeof result === 'string' ? JSON.parse(result) : result;
            if (name === 'read_page_results') return `${d.page || ''}/${d.tab || ''} — ${d.total_hits || 0}건`;
            if (name === 'navigate_to_page') return `${d.title_ko || d.page || ''} 페이지`;
            if (name === 'search_papers') return `논문 ${d.total || d.results?.length || 0}건`;
            return '';
        } catch { return ''; }
    }

    formatToolData(data: any): string {
        if (!data) return '';
        try {
            const parsed = typeof data === 'string' ? JSON.parse(data) : data;
            return JSON.stringify(parsed, null, 2);
        } catch { return String(data).substring(0, 500); }
    }

    toggleStep(step: any) { step.collapsed = !step.collapsed; }

    // ── Navigation ──
    async navigateNow(nav: any) {
        if (!nav) return;
        nav.autoNavigated = true;
        this.persistState();

        const target = nav.url ? nav.url.split('?')[0] : '/' + nav.page;
        const qp: any = {};
        if (nav.tab) qp.tab = nav.tab;
        if (nav.query) qp.q = nav.query;
        if (nav.collection) qp.collection = nav.collection;
        if (nav.params) {
            for (const [k, v] of Object.entries(nav.params)) {
                if (k !== 'collection' && v != null && String(v).trim()) qp[k] = String(v);
            }
        }
        const saved = this.router.routeReuseStrategy.shouldReuseRoute;
        try {
            (this.router as any).onSameUrlNavigation = 'reload';
            this.router.routeReuseStrategy.shouldReuseRoute = () => false;
            await this.router.navigate([target], { queryParams: qp });
        } catch {
            const qs = new URLSearchParams(
                Object.entries(qp).reduce((a: any, [k, v]) => { if (v) a[k] = String(v); return a; }, {})
            ).toString();
            window.location.href = qs ? `${target}?${qs}` : target;
        } finally {
            setTimeout(() => {
                (this.router as any).onSameUrlNavigation = 'ignore';
                this.router.routeReuseStrategy.shouldReuseRoute = saved;
            }, 50);
        }
        this.cdr.detectChanges();
    }

    private autoNavigate(msg: any) {
        if (!msg.navigation || msg.navigation.autoNavigated) return;
        this.navigateNow(msg.navigation);
    }

    // ── Markdown ──
    renderMd(text: string): SafeHtml {
        if (!text) return this.sanitizer.bypassSecurityTrustHtml('');
        try {
            let html = marked.parse(text, { breaks: true, gfm: true }) as string;
            html = html.replace(
                /<pre><code(?:\s+class="language-(\w+)")?>([\s\S]*?)<\/code><\/pre>/g,
                (_, lang, code) => {
                    const l = lang || 'text';
                    return `<div class="cb"><div class="cb-h"><span>${l}</span><button onclick="navigator.clipboard.writeText(this.closest('.cb').querySelector('code').textContent).then(()=>{this.textContent='복사됨';setTimeout(()=>this.textContent='복사',1500)})">복사</button></div><pre><code>${code}</code></pre></div>`;
                }
            );
            return this.sanitizer.bypassSecurityTrustHtml(html);
        } catch { return this.sanitizer.bypassSecurityTrustHtml(text); }
    }

    // ── Controls ──
    cancel() {
        this.abortController?.abort();
        this.abortController = null;
        this.isLoading = false;
        const last = this.messages[this.messages.length - 1];
        if (last?.role === 'assistant') {
            last.isStreaming = false;
            if (!last.content) last.content = '⏹ 중단되었습니다.';
        }
    }

    clearChat() {
        this.cancel();
        this.messages = [];
        this.chatHistory = [];
        try { sessionStorage.removeItem(this.STATE_KEY); } catch {}
        this.cdr.detectChanges();
    }

    closeChat() {
        this.persistState();
        this.service.status.toggle('chat');
    }

    onKeydown(e: KeyboardEvent) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendChat(); }
    }

    copyAnswer(msg: any) {
        if (msg.content) navigator.clipboard.writeText(msg.content);
    }

    toggleCollapse(msg: any) { msg.collapsed = !msg.collapsed; }

    scrollToBottom() {
        setTimeout(() => {
            const el = this.chatBodyRef?.nativeElement;
            if (el) el.scrollTop = el.scrollHeight;
        }, 50);
    }

    // ── Fallback ──
    private buildFallback(msg: any): string {
        const parts: string[] = [];
        if (msg.pageResult) {
            parts.push(`📊 **${msg.pageResult.page}/${msg.pageResult.tab}** 페이지에서 '${msg.pageResult.query}' 관련 결과 **${msg.pageResult.totalHits}건**을 확인했습니다.\n`);
            if (msg.pageResult.results?.length) {
                parts.push('**주요 결과:**');
                msg.pageResult.results.forEach((item: any, i: number) => {
                    const scoreText = item.score ? ` (유사도: ${(item.score * 100).toFixed(0)}%)` : '';
                    parts.push(`${i + 1}. **${item.title}**${scoreText}`);
                });
            }
        }
        if (msg.navigation) {
            parts.push(`\n🧭 해당 조건으로 **${msg.navigation.title || msg.navigation.page}** 페이지로 이동하여 더 자세한 결과를 확인할 수 있습니다.`);
        }
        if (parts.length) return parts.join('\n');
        return '응답을 생성하지 못했습니다.';
    }

    // ── Quality ──
    getQualityBadges(msg: any): string[] {
        const q = msg?.quality;
        if (!q) return [];
        const b: string[] = [];
        if (q.confidence) b.push(`신뢰도: ${q.confidence}`);
        if (q.evidenceCount) b.push(`근거 ${q.evidenceCount}건`);
        if (q.answerStyle) b.push(q.answerStyle);
        if (q.llmUsed) b.push('LLM 정제');
        return b;
    }

    formatScore(score: number): string {
        return score != null ? `${(score * 100).toFixed(0)}%` : '';
    }

    // ── State ──
    private persistState() {
        try {
            sessionStorage.setItem(this.STATE_KEY, JSON.stringify({
                messages: this.messages.map(m => ({
                    ...m, isStreaming: false,
                    steps: (m.steps || []).map((s: any) => ({
                        ...s, status: s.status === 'running' ? 'done' : s.status
                    })),
                })),
                chatHistory: this.chatHistory,
                selectedCollection: this.selectedCollection,
                collectionReady: this.collectionReady,
            }));
        } catch {}
    }

    private restoreState(): boolean {
        try {
            const raw = sessionStorage.getItem(this.STATE_KEY);
            if (!raw) return false;
            const s = JSON.parse(raw);
            if (s.messages?.length) {
                this.messages = s.messages;
                this.chatHistory = s.chatHistory || [];
                this.selectedCollection = s.selectedCollection || '';
                this.collectionReady = s.collectionReady ?? !!this.selectedCollection;
                return true;
            }
        } catch {}
        return false;
    }
}
