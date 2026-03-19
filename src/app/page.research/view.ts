import { OnInit, ViewChild, ElementRef, AfterViewInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    private readonly collectionStorageKey: string = 'plasma.selectedCollection';

    // ============================
    // 탭 관리
    // ============================
    public activeTab: string = 'discover';
    public tabs = [
        { id: 'discover', label: '주제 탐색', icon: 'M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607Z' },
        { id: 'topicmap', label: '토픽 맵', icon: 'M9 6.75V15m6-6v8.25m.503 3.498 4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0Z' },
        { id: 'gap', label: 'Research Gap', icon: 'M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0Zm-9 3.75h.008v.008H12v-.008Z' },
        { id: 'hypothesis', label: '가설 생성', icon: 'M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18' },
        { id: 'keywords', label: '키워드 분석', icon: 'M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3Z' },
        { id: 'recommend', label: '논문 추천', icon: 'M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z' },
        { id: 'proposal', label: '제안서 생성', icon: 'M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z' },
        { id: 'patent', label: '특허 검색', icon: 'M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6m-1.5 12V10.332A48.36 48.36 0 0012 9.75c-2.551 0-5.056.2-7.5.582V21M3 21h18M12 6.75h.008v.008H12V6.75z' }
    ];

    // ============================
    // 주제 탐색 (discover)
    // ============================
    public searchKeyword: string = '';
    public searching: boolean = false;
    public searchResults: any[] = [];
    public lastKeyword: string = '';
    public totalHits: number = 0;

    public relatedDocs: any[] = [];
    public relatedSource: string = '';

    public recommending: boolean = false;
    public recommendations: any[] = [];
    public recommendKeyword: string = '';
    public recommendStats: any = {};
    public expandedRec: number = -1;

    // ============================
    // 컬렉션 선택
    // ============================
    public collections: any[] = [];
    public selectedCollection: string = '';
    public collectionsLoading: boolean = false;

    // ============================
    // 토픽 맵 (topicmap)
    // ============================
    public topicClusters: any[] = [];
    public topicPoints: any[] = [];
    public topicLoading: boolean = false;
    public topicTotalDocs: number = 0;
    public topicNClusters: number = 0;
    public selectedCluster: number = -2;
    public topicMethod: string = '';
    public topicMapLoaded: boolean = false;
    public hoveredPoint: any = null;
    public topicInterpretation: any = null;

    // ============================
    // Research Gap Detector (gap)
    // ============================
    public gapKeywords: string = '';
    public gapLoading: boolean = false;
    public gapResults: any[] = [];
    public gapKeywordDensities: any[] = [];
    public gapTotalKeywords: number = 0;
    public gapAnalyzed: boolean = false;
    public expandedGap: number = -1;

    // ============================
    // Hypothesis Generator (hypothesis)
    // ============================
    public hypothesisCondition: string = '';
    public hypothesisLoading: boolean = false;
    public hypotheses: any[] = [];
    public hypothesisEvidence: any[] = [];
    public hypothesisNovelTerms: any[] = [];
    public hypothesisGenerated: boolean = false;
    public expandedHypothesis: number = -1;

    // ============================
    // 키워드 분석 (keywords)
    // ============================
    public keywordsData: any[] = [];
    public keywordsLoading: boolean = false;
    public maxFrequency: number = 1;

    // ============================
    // 논문 추천 (recommend)
    // ============================
    public recInterests: string = '';
    public recLoading: boolean = false;
    public recResults: any[] = [];

    // ============================
    // 제안서 생성 (proposal)
    // ============================
    public proposalTitle: string = '';
    public proposalObjective: string = '';
    public proposalKeywords: string = '';
    public proposalLoading: boolean = false;
    public proposalResult: any = null;

    // ============================
    // 특허 검색 (patent)
    // ============================
    public patentQuery: string = '';
    public patentSearching: boolean = false;
    public patentResults: any[] = [];

    public suggestedTags: string[] = [
        '플라즈마 에칭', 'RF 방전', '박막 증착', '균일도 개선',
        '반응성 이온', '공정 최적화', '플라즈마 진단', '핵융합'
    ];

    public gapSuggestedTags: string[] = [
        '플라즈마, 에칭, 균일도',
        '박막 증착, 온도, 압력',
        'RF 방전, ICP, 전력',
        '나노, 표면, 패시베이션'
    ];

    public hypothesisSuggestions: string[] = [
        '대기압 플라즈마에서 폴리머 표면 처리 시 접착력 향상 조건',
        'RF 플라즈마 에칭에서 균일도를 결정하는 핵심 파라미터',
        'PECVD 박막 증착에서 온도와 압력이 막질에 미치는 영향',
        'ICP 플라즈마의 전자 밀도 분포와 식각 속도의 관계'
    ];

    @ViewChild('topicCanvas', { static: false }) topicCanvasRef!: ElementRef<HTMLCanvasElement>;

    constructor(public service: Service, private route: ActivatedRoute) { }

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
            }
        } catch (e) { }
    }

    public async ngOnInit() {
        await this.service.init();
        await this.loadCollections();
        await this.handleQueryParams();
    }

    private async handleQueryParams() {
        const params = this.route.snapshot.queryParams;
        if (!params || Object.keys(params).length === 0) return;

        if (params['tab'] && this.tabs.find((t: any) => t.id === params['tab'])) {
            this.activeTab = params['tab'];
        }
        if (params['collection'] && this.collections.find((c: any) => c.name === params['collection'])) {
            this.selectedCollection = params['collection'];
            this.persistCollection(this.selectedCollection);
        }

        const q = params['q'] || '';
        await this.service.render();

        switch (this.activeTab) {
            case 'discover':
                if (q) { this.searchKeyword = q; await this.searchAndRecommend(); }
                break;
            case 'gap':
                this.gapKeywords = params['gapKeywords'] || q;
                if (this.gapKeywords) await this.analyzeGaps();
                break;
            case 'hypothesis':
                this.hypothesisCondition = params['hypothesisCondition'] || q;
                if (this.hypothesisCondition) await this.generateHypothesis();
                break;
            case 'keywords':
                await this.loadKeywords();
                break;
            case 'topicmap':
                await this.loadTopicMap();
                break;
            case 'recommend':
                this.recInterests = params['interests'] || q;
                if (this.recInterests) {
                    await this.getRecommendations();
                }
                break;
            case 'proposal':
                this.proposalTitle = params['title'] || q;
                this.proposalObjective = params['objective'] || '';
                this.proposalKeywords = params['keywords'] || '';
                if (this.proposalTitle) {
                    await this.generateProposal();
                }
                break;
            case 'patent':
                this.patentQuery = params['patentQuery'] || q;
                if (this.patentQuery) {
                    await this.searchPatents();
                }
                break;
        }
    }

    // ============================
    // 탭 전환
    // ============================
    public async switchTab(tabId: string) {
        this.activeTab = tabId;
        await this.service.render();

        // 토픽 맵 탭 활성화 시 Canvas 다시 렌더링
        if (tabId === 'topicmap' && this.topicMapLoaded) {
            setTimeout(() => this.renderTopicCanvas(), 100);
        }
    }

    // ============================
    // 컬렉션 관리
    // ============================
    public async loadCollections() {
        this.collectionsLoading = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("collections");
            if (code === 200) {
                this.collections = data.collections || [];
                const storedCollection = this.getStoredCollection();
                if (storedCollection && this.collections.find((c: any) => c.name === storedCollection)) {
                    this.selectedCollection = storedCollection;
                }
                if (this.collections.length > 0 && !this.selectedCollection) {
                    this.selectedCollection = this.collections[0].name;
                }
                if (this.selectedCollection && !this.collections.find((c: any) => c.name === this.selectedCollection)) {
                    this.selectedCollection = this.collections.length > 0 ? this.collections[0].name : '';
                }
                if (this.selectedCollection) {
                    this.persistCollection(this.selectedCollection);
                }
            }
        } catch (e) { }
        this.collectionsLoading = false;
        await this.service.render();
    }

    public async onCollectionChange() {
        this.persistCollection(this.selectedCollection);
        // 모든 탭 데이터 초기화
        this.searchResults = [];
        this.recommendations = [];
        this.relatedDocs = [];
        this.expandedRec = -1;
        this.recommendKeyword = '';
        this.lastKeyword = '';
        this.totalHits = 0;

        this.topicClusters = [];
        this.topicPoints = [];
        this.topicMapLoaded = false;
        this.topicInterpretation = null;
        this.topicNClusters = 0;
        this.topicTotalDocs = 0;
        this.selectedCluster = -2;

        this.gapResults = [];
        this.gapKeywordDensities = [];
        this.gapAnalyzed = false;
        this.expandedGap = -1;

        this.hypotheses = [];
        this.hypothesisEvidence = [];
        this.hypothesisNovelTerms = [];
        this.hypothesisGenerated = false;
        this.expandedHypothesis = -1;

        this.keywordsData = [];
        await this.service.render();

        if (this.selectedCollection && this.activeTab === 'keywords') {
            await this.loadKeywords();
        }
    }

    public getCollectionInfo() {
        return this.collections.find((c: any) => c.name === this.selectedCollection);
    }

    // ============================
    // 주제 탐색 메서드
    // ============================
    public async search() {
        if (!this.searchKeyword.trim() && this.searchKeyword !== '') return;

        this.searching = true;
        this.searchResults = [];
        this.relatedDocs = [];
        this.recommendations = [];
        this.expandedRec = -1;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("discover", {
                keyword: this.searchKeyword,
                top_k: 20,
                collection: this.selectedCollection
            });
            if (code === 200) {
                if (data.mode === 'search') {
                    this.searchResults = data.clusters || [];
                    this.lastKeyword = data.keyword;
                    this.totalHits = data.total_hits;
                }
            }
        } catch (e) { }

        this.searching = false;
        await this.service.render();
    }

    public async recommend() {
        const kw = this.searchKeyword.trim();
        if (!kw) return;

        this.recommending = true;
        this.recommendations = [];
        this.recommendKeyword = kw;
        this.expandedRec = -1;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("recommend", {
                keyword: kw,
                collection: this.selectedCollection
            });
            if (code === 200) {
                this.recommendations = data.recommendations || [];
                this.recommendStats = data.stats || {};
            }
        } catch (e) { }

        this.recommending = false;
        await this.service.render();
    }

    public async searchAndRecommend() {
        await this.search();
        if (this.searchKeyword.trim()) {
            await this.recommend();
        }
    }

    public toggleRec(index: number) {
        this.expandedRec = this.expandedRec === index ? -1 : index;
    }

    public getTypeLabel(type: string): string {
        switch (type) {
            case 'cross_topic': return '교차 주제';
            case 'research_gap': return '연구 공백';
            case 'expansion': return '확장 탐색';
            default: return type;
        }
    }

    public getTypeColor(type: string): string {
        switch (type) {
            case 'cross_topic': return 'bg-violet-100 text-violet-700';
            case 'research_gap': return 'bg-rose-100 text-rose-700';
            case 'expansion': return 'bg-sky-100 text-sky-700';
            default: return 'bg-gray-100 text-gray-700';
        }
    }

    public getTypeIcon(type: string): string {
        switch (type) {
            case 'cross_topic': return 'M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5';
            case 'research_gap': return 'M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z';
            case 'expansion': return 'M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15';
            default: return '';
        }
    }

    public async findRelated(docId: string) {
        try {
            const { code, data } = await wiz.call("related", {
                doc_id: docId,
                collection: this.selectedCollection
            });
            if (code === 200) {
                this.relatedDocs = data.related || [];
                this.relatedSource = data.source_filename || docId;
                await this.service.render();
            }
        } catch (e) { }
    }

    // ============================
    // 키워드 분석 메서드
    // ============================
    public async loadKeywords() {
        this.keywordsLoading = true;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("keywords", {
                collection: this.selectedCollection
            });
            if (code === 200) {
                this.keywordsData = data.keywords || [];
                if (this.keywordsData.length > 0) {
                    this.maxFrequency = this.keywordsData[0].frequency || 1;
                }
            }
        } catch (e) { }

        this.keywordsLoading = false;
        await this.service.render();
    }

    // ============================
    // 토픽 맵 메서드
    // ============================
    public async loadTopicMap() {
        this.topicLoading = true;
        this.topicClusters = [];
        this.topicPoints = [];
        this.selectedCluster = -2;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("topic_map", {
                collection: this.selectedCollection,
                max_chunks: 500
            });
            if (code === 200) {
                this.topicClusters = data.clusters || [];
                this.topicPoints = data.points || [];
                this.topicTotalDocs = data.total_docs || 0;
                this.topicNClusters = data.n_clusters || 0;
                this.topicMethod = data.method || '';
                this.topicInterpretation = data.interpretation || null;
                this.topicMapLoaded = true;
            }
        } catch (e) { }

        this.topicLoading = false;
        await this.service.render();
        setTimeout(() => this.renderTopicCanvas(), 100);
    }

    public selectCluster(clusterId: number) {
        this.selectedCluster = this.selectedCluster === clusterId ? -2 : clusterId;
        this.renderTopicCanvas();
    }

    public getFilteredPoints(): any[] {
        if (this.selectedCluster === -2) return this.topicPoints;
        return this.topicPoints.filter((p: any) => p.cluster_id === this.selectedCluster);
    }

    public renderTopicCanvas() {
        if (!this.topicCanvasRef || !this.topicCanvasRef.nativeElement) return;

        const canvas = this.topicCanvasRef.nativeElement;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const W = rect.width;
        const H = rect.height;
        const padding = 40;

        ctx.fillStyle = '#fafafa';
        ctx.fillRect(0, 0, W, H);

        ctx.strokeStyle = '#f0f0f0';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 10; i++) {
            const x = padding + (W - 2 * padding) * i / 10;
            const y = padding + (H - 2 * padding) * i / 10;
            ctx.beginPath(); ctx.moveTo(x, padding); ctx.lineTo(x, H - padding); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(padding, y); ctx.lineTo(W - padding, y); ctx.stroke();
        }

        const points = this.topicPoints;
        if (!points || points.length === 0) return;

        const selectedCluster = this.selectedCluster;
        for (const p of points) {
            const px = padding + (p.x / 100) * (W - 2 * padding);
            const py = padding + (1 - p.y / 100) * (H - 2 * padding);
            const isSelected = selectedCluster === -2 || p.cluster_id === selectedCluster;
            const alpha = isSelected ? 0.85 : 0.15;
            const radius = isSelected ? 5 : 3;
            ctx.beginPath();
            ctx.arc(px, py, radius, 0, Math.PI * 2);
            ctx.fillStyle = this.hexToRgba(p.color, alpha);
            ctx.fill();
            if (isSelected) {
                ctx.strokeStyle = this.hexToRgba(p.color, 1);
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }
        }

        // Draw relationship lines between clusters
        if (this.topicInterpretation && this.topicInterpretation.relationships) {
            for (const rel of this.topicInterpretation.relationships) {
                if (rel.cosine_similarity < 0.35) continue;
                if (selectedCluster !== -2 && selectedCluster !== rel.cluster_a && selectedCluster !== rel.cluster_b) continue;
                const ax = padding + (rel.center_a.x / 100) * (W - 2 * padding);
                const ay = padding + (1 - rel.center_a.y / 100) * (H - 2 * padding);
                const bx = padding + (rel.center_b.x / 100) * (W - 2 * padding);
                const by = padding + (1 - rel.center_b.y / 100) * (H - 2 * padding);
                ctx.beginPath();
                ctx.setLineDash(rel.relation === 'similar' ? [6, 3] : [4, 4]);
                const lineAlpha = rel.relation === 'similar' ? 0.6 : (rel.relation === 'related' ? 0.3 : 0.15);
                ctx.strokeStyle = rel.relation === 'similar' ? `rgba(16,185,129,${lineAlpha})` : `rgba(156,163,175,${lineAlpha})`;
                ctx.lineWidth = rel.relation === 'similar' ? 2 : 1;
                ctx.moveTo(ax, ay);
                ctx.lineTo(bx, by);
                ctx.stroke();
                ctx.setLineDash([]);
                // Draw similarity label at midpoint for similar/related pairs
                if (rel.cosine_similarity >= 0.4) {
                    const mx = (ax + bx) / 2;
                    const my = (ay + by) / 2;
                    const simText = `${(rel.cosine_similarity * 100).toFixed(0)}%`;
                    ctx.font = '9px -apple-system, sans-serif';
                    ctx.fillStyle = rel.relation === 'similar' ? 'rgba(16,185,129,0.8)' : 'rgba(156,163,175,0.6)';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(simText, mx, my - 6);
                }
            }
        }

        for (const cluster of this.topicClusters) {
            if (cluster.id === -1) continue;
            if (selectedCluster !== -2 && selectedCluster !== cluster.id) continue;
            const cx = padding + (cluster.center.x / 100) * (W - 2 * padding);
            const cy = padding + (1 - cluster.center.y / 100) * (H - 2 * padding);
            const topKws = cluster.keywords.slice(0, 2).map((k: any) => k.term).join(', ');
            const label = topKws || cluster.label;
            ctx.font = '11px -apple-system, sans-serif';
            const metrics = ctx.measureText(label);
            const tw = metrics.width + 12;
            const th = 20;
            ctx.fillStyle = 'rgba(255,255,255,0.9)';
            ctx.beginPath();
            ctx.roundRect(cx - tw / 2, cy - th - 8, tw, th, 4);
            ctx.fill();
            ctx.strokeStyle = cluster.color;
            ctx.lineWidth = 1;
            ctx.stroke();
            ctx.fillStyle = '#374151';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(label, cx, cy - th / 2 - 8 + th / 2);
        }
    }

    private hexToRgba(hex: string, alpha: number): string {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r},${g},${b},${alpha})`;
    }

    public onCanvasMouseMove(event: MouseEvent) {
        if (!this.topicCanvasRef || !this.topicCanvasRef.nativeElement) return;
        const canvas = this.topicCanvasRef.nativeElement;
        const rect = canvas.getBoundingClientRect();
        const mx = event.clientX - rect.left;
        const my = event.clientY - rect.top;
        const W = rect.width;
        const H = rect.height;
        const padding = 40;

        let closest: any = null;
        let minDist = 15;
        for (const p of this.topicPoints) {
            const px = padding + (p.x / 100) * (W - 2 * padding);
            const py = padding + (1 - p.y / 100) * (H - 2 * padding);
            const dist = Math.sqrt((mx - px) ** 2 + (my - py) ** 2);
            if (dist < minDist) { minDist = dist; closest = p; }
        }
        this.hoveredPoint = closest;
    }

    public onCanvasMouseLeave() { this.hoveredPoint = null; }

    public onCanvasClick(event: MouseEvent) {
        if (this.hoveredPoint) {
            this.selectCluster(this.hoveredPoint.cluster_id);
        }
    }

    // ============================
    // Research Gap Detector 메서드
    // ============================
    public async analyzeGaps() {
        if (!this.gapKeywords.trim()) return;

        this.gapLoading = true;
        this.gapResults = [];
        this.gapKeywordDensities = [];
        this.expandedGap = -1;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("gap_detector", {
                keywords: this.gapKeywords,
                collection: this.selectedCollection
            });
            if (code === 200) {
                this.gapResults = data.gaps || [];
                this.gapKeywordDensities = data.keyword_densities || [];
                this.gapTotalKeywords = data.total_keywords || 0;
                this.gapAnalyzed = true;
            }
        } catch (e) { }

        this.gapLoading = false;
        await this.service.render();
    }

    public toggleGap(index: number) {
        this.expandedGap = this.expandedGap === index ? -1 : index;
    }

    public getPotentialColor(potential: string): string {
        switch (potential) {
            case '높음': return 'bg-rose-100 text-rose-700';
            case '보통': return 'bg-amber-100 text-amber-700';
            case '낮음': return 'bg-green-100 text-green-700';
            default: return 'bg-gray-100 text-gray-700';
        }
    }

    public getDensityBarWidth(density: number): number {
        return Math.min(100, density * 100);
    }

    public getDensityColor(density: number): string {
        if (density >= 0.5) return 'bg-green-500';
        if (density >= 0.3) return 'bg-amber-500';
        return 'bg-rose-500';
    }

    // ============================
    // Hypothesis Generator 메서드
    // ============================
    public async generateHypothesis() {
        if (!this.hypothesisCondition.trim()) return;

        this.hypothesisLoading = true;
        this.hypotheses = [];
        this.hypothesisEvidence = [];
        this.hypothesisNovelTerms = [];
        this.expandedHypothesis = -1;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("generate_hypothesis", {
                condition: this.hypothesisCondition,
                collection: this.selectedCollection
            });
            if (code === 200) {
                this.hypotheses = data.hypotheses || [];
                this.hypothesisEvidence = data.evidence_docs || [];
                this.hypothesisNovelTerms = data.novel_terms || [];
                this.hypothesisGenerated = true;
            }
        } catch (e) { }

        this.hypothesisLoading = false;
        await this.service.render();
    }

    public toggleHypothesis(index: number) {
        this.expandedHypothesis = this.expandedHypothesis === index ? -1 : index;
    }

    public getHypothesisTypeColor(type: string): string {
        switch (type) {
            case 'parameter_optimization': return 'bg-blue-100 text-blue-700';
            case 'mechanism_study': return 'bg-purple-100 text-purple-700';
            case 'cross_domain': return 'bg-rose-100 text-rose-700';
            case 'novel_application': return 'bg-emerald-100 text-emerald-700';
            case 'prediction_model': return 'bg-amber-100 text-amber-700';
            default: return 'bg-gray-100 text-gray-700';
        }
    }

    public getHypothesisIcon(type: string): string {
        switch (type) {
            case 'parameter_optimization': return 'M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75';
            case 'mechanism_study': return 'M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5';
            case 'cross_domain': return 'M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5';
            case 'novel_application': return 'M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z';
            case 'prediction_model': return 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z';
            default: return '';
        }
    }

    // ============================
    // 논문 추천 (recommend)
    // ============================
    public async getRecommendations() {
        if (!this.recInterests.trim()) return;
        this.recLoading = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("recommend_papers", {
                interests: this.recInterests,
                collection: this.selectedCollection
            });
            if (code === 200) this.recResults = data || [];
        } catch (e) { }
        this.recLoading = false;
        await this.service.render();
    }

    // ============================
    // 제안서 생성 (proposal)
    // ============================
    public async generateProposal() {
        if (!this.proposalTitle.trim()) return;
        this.proposalLoading = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("generate_proposal", {
                title: this.proposalTitle,
                objective: this.proposalObjective,
                keywords: this.proposalKeywords,
                collection: this.selectedCollection
            });
            if (code === 200) this.proposalResult = data;
        } catch (e) { }
        this.proposalLoading = false;
        await this.service.render();
    }

    // ============================
    // 특허 검색 (patent)
    // ============================
    public async searchPatents() {
        if (!this.patentQuery.trim()) return;
        this.patentSearching = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("search_patents", {
                query: this.patentQuery,
                collection: this.selectedCollection
            });
            if (code === 200) this.patentResults = data || [];
        } catch (e) { }
        this.patentSearching = false;
        await this.service.render();
    }
}
