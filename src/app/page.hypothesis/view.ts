import { OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { marked } from 'marked';

declare const wiz: any;
const APP_ID = "page.hypothesis";

export class Component implements OnInit, OnDestroy {
    private queryParamSub: any = null;
    private readonly collectionStorageKey: string = 'plasma.selectedCollection';
    private readonly collectionChangeEventName: string = 'plasma-collection-changed';
    private collectionChangeListener: any = null;
    private abortController: AbortController | null = null;

    constructor(
        public service: Service,
        private route: ActivatedRoute,
        private sanitizer: DomSanitizer
    ) { }

    // ========================================================================
    // 상태 관리
    // ========================================================================
    public tab: string = 'input';
    public collections: any[] = [];
    public selectedCollection: string = '';

    // --- Input ---
    public hypothesisTitle: string = '';
    public hypothesisContent: string = '';
    public history: any[] = [];

    // --- Papers ---
    public papers: any[] = [];
    public papersLoading: boolean = false;
    public papersOnlyEquations: boolean = false;

    // --- Equations ---
    public equations: any[] = [];
    public equationsLoading: boolean = false;
    public selectedEquationIds: Set<string> = new Set();

    // --- Result ---
    public verifying: boolean = false;
    public verifyStep: string = '';
    public verifyStepMessage: string = '';
    public resultText: string = '';
    public resultHtml: SafeHtml = '';
    public conclusion: string = '';
    public conclusionLabel: string = '';
    public resultPapersCount: number = 0;
    public resultEquationsCount: number = 0;

    // ========================================================================
    // 예시 가설
    // ========================================================================
    public templates = [
        { title: 'RF 파워와 에칭률의 관계', content: 'RF 파워를 증가시키면 플라즈마 밀도가 높아져 에칭률이 선형적으로 증가한다.' },
        { title: '전자 온도와 디바이 길이', content: '전자 온도가 증가하면 디바이 차폐 길이(Debye length)가 증가하여 플라즈마 시스(sheath) 두께가 변화한다.' },
        { title: '가스 압력과 플라즈마 밀도', content: '작동 가스 압력을 낮추면 평균 자유 경로가 증가하여 전자 에너지 분포 함수(EEDF)가 비맥스웰 분포를 따르게 된다.' },
        { title: '자기장과 플라즈마 가둠', content: '토로이달 자기장 강도를 증가시키면 플라즈마 가둠 시간이 개선되어 핵융합 반응률이 향상된다.' }
    ];

    // ========================================================================
    // Lifecycle
    // ========================================================================
    public async ngOnInit() {
        await this.service.init();
        await this.loadCollections();
        await this.loadHistory();

        const params = this.route.snapshot.queryParams;
        if (params['tab'] && ['input', 'papers', 'equations', 'result'].includes(params['tab'])) {
            this.tab = params['tab'];
        }
        if (params['collection'] && this.collections.find((c: any) => c.name === params['collection'])) {
            this.selectedCollection = params['collection'];
        }

        this.queryParamSub = this.route.queryParams.subscribe(async (p: any) => {
            if (p['tab'] && ['input', 'papers', 'equations', 'result'].includes(p['tab'])) {
                this.tab = p['tab'];
                await this.service.render();
            }
        });

        this.collectionChangeListener = async (event: any) => {
            const next = String(event?.detail?.collection || '').trim();
            if (!next || next === this.selectedCollection) return;
            await this.loadCollections();
            if (this.collections.find((c: any) => c.name === next)) {
                this.selectedCollection = next;
                await this.service.render();
            }
        };
        window.addEventListener(this.collectionChangeEventName, this.collectionChangeListener as EventListener);

        await this.service.render();
    }

    ngOnDestroy() {
        if (this.queryParamSub) this.queryParamSub.unsubscribe();
        if (this.collectionChangeListener) {
            window.removeEventListener(this.collectionChangeEventName, this.collectionChangeListener as EventListener);
        }
        if (this.abortController) this.abortController.abort();
    }

    // ========================================================================
    // 탭 전환
    // ========================================================================
    public async selectTab(tab: string) {
        this.tab = tab;
        await this.service.render();
    }

    // ========================================================================
    // 컬렉션
    // ========================================================================
    private getStoredCollection(): string {
        try { return localStorage.getItem(this.collectionStorageKey) || ''; } catch { return ''; }
    }

    private persistCollection(name: string) {
        try { if (name) localStorage.setItem(this.collectionStorageKey, name); } catch { }
    }

    public async loadCollections() {
        const { code, data } = await wiz.call("collections");
        if (code === 200 && data.collections) {
            this.collections = data.collections;
            const stored = this.getStoredCollection();
            if (stored && this.collections.find((c: any) => c.name === stored)) {
                this.selectedCollection = stored;
            } else if (this.collections.length > 0) {
                this.selectedCollection = this.collections[0].name;
            }
            this.persistCollection(this.selectedCollection);
        }
    }

    public async onCollectionChange() {
        this.persistCollection(this.selectedCollection);
        this.papers = [];
        this.equations = [];
        this.resultText = '';
        this.conclusion = '';
        window.dispatchEvent(new CustomEvent(this.collectionChangeEventName, {
            detail: { collection: this.selectedCollection, source: 'page-hypothesis' }
        }));
        await this.service.render();
    }

    // ========================================================================
    // 이력
    // ========================================================================
    public async loadHistory() {
        const { code, data } = await wiz.call("load_history");
        if (code === 200) {
            this.history = data.history || [];
        }
    }

    public async loadFromHistory(item: any) {
        this.hypothesisTitle = item.title || '';
        this.hypothesisContent = item.content || '';
        if (item.collection && this.collections.find((c: any) => c.name === item.collection)) {
            this.selectedCollection = item.collection;
        }
        await this.service.render();
    }

    public applyTemplate(t: any) {
        this.hypothesisTitle = t.title;
        this.hypothesisContent = t.content;
        this.service.render();
    }

    // ========================================================================
    // 유사 논문 검색
    // ========================================================================
    public async searchPapers() {
        if (!this.hypothesisTitle && !this.hypothesisContent) return;
        if (!this.selectedCollection) return;
        this.papersLoading = true;
        this.tab = 'papers';
        await this.service.render();

        const { code, data } = await wiz.call("search_papers", {
            title: this.hypothesisTitle,
            content: this.hypothesisContent,
            collection: this.selectedCollection,
            limit: 20
        });
        if (code === 200) {
            this.papers = data.papers || [];
        }
        this.papersLoading = false;
        await this.service.render();
    }

    public filteredPapers() {
        if (!this.papersOnlyEquations) return this.papers;
        return this.papers.filter((p: any) => p.has_equation);
    }

    // ========================================================================
    // 수식 추출
    // ========================================================================
    public async extractEquations() {
        const docIds = this.papers.filter((p: any) => p.has_equation).map((p: any) => p.doc_id);
        if (docIds.length === 0) {
            const top = this.papers.slice(0, 5).map((p: any) => p.doc_id);
            if (top.length === 0) return;
            docIds.push(...top);
        }

        this.equationsLoading = true;
        this.tab = 'equations';
        await this.service.render();

        const { code, data } = await wiz.call("extract_equations", {
            collection: this.selectedCollection,
            doc_ids: docIds.join(",")
        });
        if (code === 200) {
            this.equations = data.equations || [];
            this.selectedEquationIds = new Set(this.equations.map((eq: any) => eq.id));
        }
        this.equationsLoading = false;
        await this.service.render();
    }

    public toggleEquation(id: string) {
        if (this.selectedEquationIds.has(id)) {
            this.selectedEquationIds.delete(id);
        } else {
            this.selectedEquationIds.add(id);
        }
        this.service.render();
    }

    public isEquationSelected(id: string): boolean {
        return this.selectedEquationIds.has(id);
    }

    public selectAllEquations() {
        this.selectedEquationIds = new Set(this.equations.map((eq: any) => eq.id));
        this.service.render();
    }

    public deselectAllEquations() {
        this.selectedEquationIds.clear();
        this.service.render();
    }

    // ========================================================================
    // SSE 가설 검증
    // ========================================================================
    public async startVerification() {
        if (!this.hypothesisTitle && !this.hypothesisContent) return;
        if (!this.selectedCollection) return;

        this.verifying = true;
        this.verifyStep = 'searching';
        this.verifyStepMessage = '시작 중...';
        this.resultText = '';
        this.resultHtml = '';
        this.conclusion = '';
        this.conclusionLabel = '';
        this.tab = 'result';
        await this.service.render();

        const formData = new FormData();
        formData.append('title', this.hypothesisTitle);
        formData.append('content', this.hypothesisContent);
        formData.append('collection', this.selectedCollection);
        formData.append('paper_limit', '20');
        if (this.selectedEquationIds.size > 0 && this.selectedEquationIds.size < this.equations.length) {
            formData.append('selected_equations', Array.from(this.selectedEquationIds).join(','));
        }

        this.abortController = new AbortController();

        try {
            const response = await fetch(`/wiz/api/${APP_ID}/verify`, {
                method: 'POST',
                body: formData,
                signal: this.abortController.signal
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
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const event = JSON.parse(line.slice(6));
                        await this.handleVerifyEvent(event);
                    } catch { }
                }
            }
        } catch (e: any) {
            if (e.name !== 'AbortError') {
                this.verifyStepMessage = `오류: ${e.message}`;
            }
        } finally {
            this.verifying = false;
            this.abortController = null;
            await this.service.render();
        }
    }

    private async handleVerifyEvent(event: any) {
        switch (event.type) {
            case 'step':
                this.verifyStep = event.step;
                this.verifyStepMessage = event.message;
                break;
            case 'papers':
                if (!this.papers.length) {
                    this.papers = event.papers || [];
                }
                this.resultPapersCount = event.total || 0;
                break;
            case 'equations':
                if (!this.equations.length) {
                    this.equations = event.equations || [];
                }
                this.resultEquationsCount = event.total || 0;
                break;
            case 'text':
                this.resultText += event.content;
                this.resultHtml = this.renderMarkdown(this.resultText);
                break;
            case 'result':
                this.conclusion = event.conclusion;
                this.conclusionLabel = event.conclusion_label;
                this.resultPapersCount = event.papers_count || this.resultPapersCount;
                this.resultEquationsCount = event.equations_count || this.resultEquationsCount;
                // Save to history
                await wiz.call("save_history", {
                    data: JSON.stringify({
                        title: this.hypothesisTitle,
                        content: this.hypothesisContent,
                        collection: this.selectedCollection,
                        conclusion: this.conclusion,
                        conclusion_label: this.conclusionLabel,
                        papers_count: this.resultPapersCount,
                        equations_count: this.resultEquationsCount
                    })
                });
                await this.loadHistory();
                break;
            case 'error':
                this.verifyStepMessage = `오류: ${event.message}`;
                break;
            case 'done':
                this.verifying = false;
                break;
        }
        await this.service.render();
    }

    public cancelVerification() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
        this.verifying = false;
        this.service.render();
    }

    // ========================================================================
    // 전체 파이프라인 (입력 → 검색 → 추출 → 검증)
    // ========================================================================
    public async runFullPipeline() {
        if (!this.hypothesisTitle && !this.hypothesisContent) {
            await this.service.alert.show({ title: '알림', message: '가설을 입력하세요.', action: '확인' });
            return;
        }
        if (!this.selectedCollection) {
            await this.service.alert.show({ title: '알림', message: '컬렉션을 선택하세요.', action: '확인' });
            return;
        }
        await this.startVerification();
    }

    // ========================================================================
    // 마크다운 렌더링
    // ========================================================================
    public renderMarkdown(text: string): SafeHtml {
        if (!text) return '';
        try {
            const html = marked.parse(text) as string;
            return this.sanitizer.bypassSecurityTrustHtml(html);
        } catch {
            return text;
        }
    }

    // ========================================================================
    // 유틸
    // ========================================================================
    public getConclusionColor(c: string): string {
        if (c === 'supported') return 'emerald';
        if (c === 'contradicted') return 'red';
        return 'amber';
    }

    public getConclusionIcon(c: string): string {
        if (c === 'supported') return 'fa-check-circle';
        if (c === 'contradicted') return 'fa-times-circle';
        return 'fa-question-circle';
    }

    public getStepIndex(step: string): number {
        const steps = ['searching', 'extracting', 'verifying'];
        return steps.indexOf(step);
    }

    public copyResult() {
        if (this.resultText) {
            navigator.clipboard.writeText(this.resultText);
        }
    }

    public formatDate(iso: string): string {
        try {
            const d = new Date(iso);
            return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
        } catch { return iso; }
    }
}
