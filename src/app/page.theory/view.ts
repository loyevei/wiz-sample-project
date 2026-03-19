import { OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit, OnDestroy {
    constructor(public service: Service, private route: ActivatedRoute) { }

    private readonly collectionStorageKey: string = 'plasma.selectedCollection';

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

    // ==============================================================================
    // 상태 관리
    // ==============================================================================
    public tab: string = 'equation';
    public collections: any[] = [];
    public selectedCollection: string = '';

    // --- Equation Tab ---
    public equationLoading: boolean = false;
    public equationStats: any = null;
    public equations: any[] = [];
    public equationQuery: string = '';
    public equationSearchResults: any[] = [];
    public equationSearchClassification: any = null;
    public equationSearching: boolean = false;
    public equationCategoryFilter: string = '';

    // --- Assumption Tab ---
    public assumptionLoading: boolean = false;
    public assumptionStats: any = null;
    public assumptionDocuments: any[] = [];
    public selectedDocIds: Set<string> = new Set();
    public consistencyResult: any = null;
    public consistencyChecking: boolean = false;

    // --- Graph Tab ---
    public graphLoading: boolean = false;
    public graphNodes: any[] = [];
    public graphEdges: any[] = [];
    public graphStats: any = null;
    public graphCached: boolean = false;
    public graphCanvas: any = null;
    public graphCtx: any = null;
    public selectedNode: any = null;
    public graphSearchQuery: string = '';
    public graphSearchResults: any[] = [];
    public impactResults: any[] = [];
    public graphNodeTypeFilter: string = '';
    public graphDragNode: any = null;
    public graphOffset: { x: number, y: number } = { x: 0, y: 0 };
    public graphScale: number = 1;

    // ==============================================================================
    // Lifecycle
    // ==============================================================================
    public async ngOnInit() {
        await this.service.init();
        await this.loadCollections();
        await this.handleQueryParams();
        await this.service.render();
    }

    private async handleQueryParams() {
        const params = this.route.snapshot.queryParams;
        if (!params || Object.keys(params).length === 0) return;

        if (params['tab'] && ['equation', 'assumption', 'graph'].includes(params['tab'])) {
            this.tab = params['tab'];
        }
        if (params['collection'] && this.collections.find((c: any) => c.name === params['collection'])) {
            this.selectedCollection = params['collection'];
            this.persistCollection(this.selectedCollection);
        }

        const q = params['q'] || '';
        await this.service.render();

        switch (this.tab) {
            case 'equation':
                this.equationQuery = params['equationQuery'] || q;
                if (!this.equationStats) await this.loadEquationStats();
                if (this.equationQuery) await this.searchEquations();
                break;
            case 'assumption':
                if (!this.assumptionStats) await this.loadAssumptionStats();
                break;
            case 'graph':
                this.graphSearchQuery = params['graphSearchQuery'] || q;
                if (this.graphNodes.length === 0) await this.loadTheoryGraph();
                if (this.graphSearchQuery) await this.searchGraph();
                break;
        }
    }

    ngOnDestroy() { }

    // ==============================================================================
    // 탭 전환
    // ==============================================================================
    public async selectTab(tab: string) {
        this.tab = tab;
        await this.service.render();

        if (tab === 'equation' && !this.equationStats && this.selectedCollection) {
            await this.loadEquationStats();
        } else if (tab === 'assumption' && !this.assumptionStats && this.selectedCollection) {
            await this.loadAssumptionStats();
        } else if (tab === 'graph' && this.graphNodes.length === 0 && this.selectedCollection) {
            await this.loadTheoryGraph();
        }
    }

    // ==============================================================================
    // 컬렉션 관리
    // ==============================================================================
    public async loadCollections() {
        const { code, data } = await wiz.call("collections");
        if (code === 200 && data.collections) {
            this.collections = data.collections;
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
        await this.service.render();
    }

    public async onCollectionChange() {
        this.persistCollection(this.selectedCollection);
        this.equationStats = null;
        this.equations = [];
        this.equationSearchResults = [];
        this.assumptionStats = null;
        this.assumptionDocuments = [];
        this.selectedDocIds = new Set();
        this.consistencyResult = null;
        this.graphNodes = [];
        this.graphEdges = [];
        this.graphStats = null;
        this.selectedNode = null;
        this.graphSearchResults = [];
        this.impactResults = [];
        await this.service.render();

        if (this.tab === 'equation') {
            await this.loadEquationStats();
        } else if (this.tab === 'assumption') {
            await this.loadAssumptionStats();
        } else if (this.tab === 'graph') {
            await this.loadTheoryGraph();
        }
    }

    // ==============================================================================
    // Equation Tab
    // ==============================================================================
    public async loadEquationStats() {
        if (!this.selectedCollection) return;
        this.equationLoading = true;
        await this.service.render();

        const { code, data } = await wiz.call("equation_stats", { collection: this.selectedCollection });
        if (code === 200) {
            this.equationStats = data.stats;
        }
        this.equationLoading = false;
        await this.service.render();
    }

    public async extractEquations() {
        if (!this.selectedCollection) return;
        this.equationLoading = true;
        await this.service.render();

        const { code, data } = await wiz.call("extract_equations", { collection: this.selectedCollection });
        if (code === 200) {
            this.equations = data.equations || [];
            if (data.stats) this.equationStats = data.stats;
        }
        this.equationLoading = false;
        await this.service.render();
    }

    public async searchEquations() {
        if (!this.equationQuery.trim()) return;
        this.equationSearching = true;
        await this.service.render();

        const { code, data } = await wiz.call("search_equations", {
            collection: this.selectedCollection,
            equation: this.equationQuery
        });
        if (code === 200) {
            this.equationSearchResults = data.results || [];
            this.equationSearchClassification = data.query_classification || null;
        }
        this.equationSearching = false;
        await this.service.render();
    }

    public filteredEquations() {
        if (!this.equationCategoryFilter) return this.equations;
        return this.equations.filter((eq: any) =>
            eq.classification?.category === this.equationCategoryFilter
        );
    }

    public getCategoryColor(cat: string): string {
        const colors: any = {
            governing: 'indigo', constitutive: 'violet',
            empirical: 'amber', boundary: 'emerald', other: 'gray'
        };
        return colors[cat] || 'gray';
    }

    // ==============================================================================
    // Assumption Tab
    // ==============================================================================
    public async loadAssumptionStats() {
        if (!this.selectedCollection) return;
        this.assumptionLoading = true;
        await this.service.render();

        const { code, data } = await wiz.call("assumption_stats", { collection: this.selectedCollection });
        if (code === 200) {
            this.assumptionStats = data.stats;
        }
        this.assumptionLoading = false;
        await this.service.render();
    }

    public async extractAssumptions() {
        if (!this.selectedCollection) return;
        this.assumptionLoading = true;
        await this.service.render();

        const docIds = this.selectedDocIds.size > 0
            ? Array.from(this.selectedDocIds).join(',')
            : '';

        const { code, data } = await wiz.call("extract_assumptions", {
            collection: this.selectedCollection,
            doc_ids: docIds
        });
        if (code === 200) {
            this.assumptionDocuments = data.documents || [];
            if (data.stats) this.assumptionStats = data.stats;
        }
        this.assumptionLoading = false;
        await this.service.render();
    }

    public toggleDocSelection(docId: string) {
        if (this.selectedDocIds.has(docId)) {
            this.selectedDocIds.delete(docId);
        } else {
            this.selectedDocIds.add(docId);
        }
        this.service.render();
    }

    public isDocSelected(docId: string): boolean {
        return this.selectedDocIds.has(docId);
    }

    public async checkConsistency() {
        if (this.selectedDocIds.size < 2) {
            await this.service.alert.show({
                title: '알림',
                message: '상충 검사를 하려면 2개 이상의 문서를 선택하세요.',
                action: '확인'
            });
            return;
        }
        this.consistencyChecking = true;
        await this.service.render();

        const { code, data } = await wiz.call("check_consistency", {
            collection: this.selectedCollection,
            doc_ids: Array.from(this.selectedDocIds).join(',')
        });
        if (code === 200) {
            this.consistencyResult = data;
        }
        this.consistencyChecking = false;
        await this.service.render();
    }

    // ==============================================================================
    // Graph Tab
    // ==============================================================================
    public async loadTheoryGraph() {
        if (!this.selectedCollection) return;
        this.graphLoading = true;
        await this.service.render();

        const { code, data } = await wiz.call("get_theory_graph", { collection: this.selectedCollection });
        if (code === 200 && data.nodes && data.nodes.length > 0) {
            this.graphNodes = data.nodes;
            this.graphEdges = data.edges || [];
            this.graphStats = data.stats;
            this.graphCached = data.cached || false;
            this.assignNodePositions();
            this.graphLoading = false;
            await this.service.render();
            setTimeout(() => this.renderGraphCanvas(), 100);
        } else {
            this.graphCached = false;
            this.graphLoading = false;
            await this.service.render();
        }
    }

    public async buildTheoryGraph() {
        if (!this.selectedCollection) return;
        this.graphLoading = true;
        this.graphNodes = [];
        this.graphEdges = [];
        await this.service.render();

        const { code, data } = await wiz.call("build_theory_graph", { collection: this.selectedCollection });
        if (code === 200) {
            this.graphNodes = data.nodes || [];
            this.graphEdges = data.edges || [];
            this.graphStats = data.stats;
            this.graphCached = true;
            this.assignNodePositions();
            this.graphLoading = false;
            await this.service.render();
            setTimeout(() => this.renderGraphCanvas(), 100);
        } else {
            this.graphLoading = false;
            await this.service.render();
        }
    }

    public async traceImpact(nodeId: string) {
        if (!nodeId) return;
        const { code, data } = await wiz.call("trace_impact", {
            collection: this.selectedCollection,
            node_id: nodeId
        });
        if (code === 200) {
            this.impactResults = data.impacted || [];
        }
        await this.service.render();
    }

    public async searchGraph() {
        if (!this.graphSearchQuery.trim()) return;
        const { code, data } = await wiz.call("search_graph", {
            collection: this.selectedCollection,
            query: this.graphSearchQuery
        });
        if (code === 200) {
            this.graphSearchResults = data.results || [];
        }
        await this.service.render();
    }

    public highlightNode(nodeId: string) {
        this.selectedNode = this.graphNodes.find((n: any) => n.id === nodeId) || null;
        this.renderGraphCanvas();
        this.service.render();
    }

    // ==============================================================================
    // Graph 렌더링
    // ==============================================================================
    private assignNodePositions() {
        const nodesByType: any = {};
        this.graphNodes.forEach((n: any) => {
            if (!nodesByType[n.type]) nodesByType[n.type] = [];
            nodesByType[n.type].push(n);
        });

        const typeOrder = ['concept', 'equation', 'condition'];
        let yBase = 80;

        typeOrder.forEach((type) => {
            const group = nodesByType[type] || [];
            const cols = Math.ceil(Math.sqrt(group.length * 2));
            group.forEach((n: any, i: number) => {
                const col = i % cols;
                const row = Math.floor(i / cols);
                n._x = 100 + col * 160 + (Math.random() - 0.5) * 40;
                n._y = yBase + row * 120 + (Math.random() - 0.5) * 30;
            });
            yBase += (Math.ceil(group.length / cols) + 1) * 120;
        });

        // 기타 타입
        Object.keys(nodesByType).filter(t => !typeOrder.includes(t)).forEach((type) => {
            const group = nodesByType[type];
            const cols = Math.ceil(Math.sqrt(group.length * 2));
            group.forEach((n: any, i: number) => {
                n._x = 100 + (i % cols) * 160 + (Math.random() - 0.5) * 40;
                n._y = yBase + Math.floor(i / cols) * 120 + (Math.random() - 0.5) * 30;
            });
            yBase += (Math.ceil(group.length / cols) + 1) * 120;
        });
    }

    public renderGraphCanvas() {
        const canvas = document.getElementById('theoryGraphCanvas') as HTMLCanvasElement;
        if (!canvas) return;
        this.graphCanvas = canvas;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        this.graphCtx = ctx;

        const parent = canvas.parentElement;
        if (parent) {
            canvas.width = parent.clientWidth;
            canvas.height = Math.max(parent.clientHeight, 600);
        }

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.save();
        ctx.translate(this.graphOffset.x, this.graphOffset.y);
        ctx.scale(this.graphScale, this.graphScale);

        const nodeMap: any = {};
        this.graphNodes.forEach((n: any) => { nodeMap[n.id] = n; });

        // 엣지 그리기
        const relationColors: any = {
            causes: '#ef4444', affects: '#f97316', depends_on: '#3b82f6',
            uses: '#8b5cf6', proportional: '#10b981', contradicts: '#dc2626'
        };

        this.graphEdges.forEach((e: any) => {
            const src = nodeMap[e.source];
            const tgt = nodeMap[e.target];
            if (!src || !tgt || src._x == null || tgt._x == null) return;

            // 필터
            if (this.graphNodeTypeFilter) {
                if (src.type !== this.graphNodeTypeFilter && tgt.type !== this.graphNodeTypeFilter) return;
            }

            ctx.beginPath();
            ctx.moveTo(src._x, src._y);
            ctx.lineTo(tgt._x, tgt._y);
            ctx.strokeStyle = relationColors[e.relation] || '#94a3b8';
            ctx.lineWidth = e.relation === 'contradicts' ? 2 : 1;
            if (e.relation === 'contradicts') {
                ctx.setLineDash([4, 4]);
            } else {
                ctx.setLineDash([]);
            }
            ctx.globalAlpha = this.selectedNode
                ? (e.source === this.selectedNode.id || e.target === this.selectedNode.id ? 0.9 : 0.1)
                : 0.4;
            ctx.stroke();
            ctx.setLineDash([]);

            // 화살표
            const angle = Math.atan2(tgt._y - src._y, tgt._x - src._x);
            const headLen = 8;
            const endX = tgt._x - Math.cos(angle) * 20;
            const endY = tgt._y - Math.sin(angle) * 20;
            ctx.beginPath();
            ctx.moveTo(endX, endY);
            ctx.lineTo(endX - headLen * Math.cos(angle - Math.PI / 6), endY - headLen * Math.sin(angle - Math.PI / 6));
            ctx.moveTo(endX, endY);
            ctx.lineTo(endX - headLen * Math.cos(angle + Math.PI / 6), endY - headLen * Math.sin(angle + Math.PI / 6));
            ctx.stroke();
        });

        ctx.globalAlpha = 1;

        // 노드 그리기
        const typeColors: any = {
            concept: '#6366f1', equation: '#8b5cf6', condition: '#f59e0b'
        };
        const typeShapes: any = { concept: 'circle', equation: 'diamond', condition: 'square' };

        this.graphNodes.forEach((n: any) => {
            if (n._x == null) return;
            if (this.graphNodeTypeFilter && n.type !== this.graphNodeTypeFilter) return;

            const color = typeColors[n.type] || '#64748b';
            const isSelected = this.selectedNode && this.selectedNode.id === n.id;
            const isConnected = this.selectedNode && this.graphEdges.some((e: any) =>
                (e.source === this.selectedNode.id && e.target === n.id) ||
                (e.target === this.selectedNode.id && e.source === n.id)
            );

            ctx.globalAlpha = this.selectedNode ? (isSelected || isConnected ? 1 : 0.2) : 1;

            const r = (n.degree || 1) * 3 + 8;
            const shape = typeShapes[n.type] || 'circle';

            ctx.fillStyle = isSelected ? '#1e40af' : color;
            ctx.strokeStyle = isSelected ? '#1e3a8a' : '#fff';
            ctx.lineWidth = isSelected ? 3 : 1.5;

            if (shape === 'circle') {
                ctx.beginPath();
                ctx.arc(n._x, n._y, r, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();
            } else if (shape === 'diamond') {
                ctx.beginPath();
                ctx.moveTo(n._x, n._y - r);
                ctx.lineTo(n._x + r, n._y);
                ctx.lineTo(n._x, n._y + r);
                ctx.lineTo(n._x - r, n._y);
                ctx.closePath();
                ctx.fill();
                ctx.stroke();
            } else {
                ctx.fillRect(n._x - r, n._y - r, r * 2, r * 2);
                ctx.strokeRect(n._x - r, n._y - r, r * 2, r * 2);
            }

            // 라벨
            ctx.fillStyle = '#1e293b';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            const label = n.label.length > 18 ? n.label.substring(0, 16) + '…' : n.label;
            ctx.fillText(label, n._x, n._y + r + 14);
        });

        ctx.globalAlpha = 1;
        ctx.restore();
    }

    public onGraphCanvasClick(event: MouseEvent) {
        const canvas = this.graphCanvas;
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        const mx = (event.clientX - rect.left - this.graphOffset.x) / this.graphScale;
        const my = (event.clientY - rect.top - this.graphOffset.y) / this.graphScale;

        let found: any = null;
        for (const n of this.graphNodes) {
            if (n._x == null) continue;
            const dist = Math.sqrt((n._x - mx) ** 2 + (n._y - my) ** 2);
            const r = (n.degree || 1) * 3 + 8;
            if (dist < r + 5) {
                found = n;
                break;
            }
        }

        if (found) {
            this.selectedNode = found;
            this.traceImpact(found.id);
        } else {
            this.selectedNode = null;
            this.impactResults = [];
        }
        this.renderGraphCanvas();
        this.service.render();
    }

    public onGraphWheel(event: WheelEvent) {
        event.preventDefault();
        const delta = event.deltaY > 0 ? 0.9 : 1.1;
        this.graphScale = Math.max(0.3, Math.min(3, this.graphScale * delta));
        this.renderGraphCanvas();
    }

    public getNodeTypeLabel(type: string): string {
        const labels: any = { concept: '개념', equation: '수식', condition: '조건/가정' };
        return labels[type] || type;
    }

    public getRelationLabel(rel: string): string {
        const labels: any = {
            causes: '원인→결과', affects: '영향', depends_on: '의존',
            uses: '사용', proportional: '비례', contradicts: '상충'
        };
        return labels[rel] || rel;
    }
}
