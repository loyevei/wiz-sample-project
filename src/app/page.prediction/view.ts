import { OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    private readonly collectionStorageKey: string = 'plasma.selectedCollection';

    // ==========================================================================
    // 탭 관리
    // ==========================================================================
    public activeTab: string = 'predict';
    public tabs = [
        { id: 'predict', label: '조건 예측', icon: 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z' },
        { id: 'paramdb', label: '파라미터 DB', icon: 'M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 0 1-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0 1 12 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M10.875 12c-.621 0-1.125.504-1.125 1.125M12 12c.621 0 1.125.504 1.125 1.125m0 0v1.5c0 .621-.504 1.125-1.125 1.125m-1.125-2.625c0 .621-.504 1.125-1.125 1.125' },
        { id: 'inverse', label: '역설계', icon: 'M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456ZM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423Z' },
        { id: 'uncertainty', label: '불확실성', icon: 'M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 5.25h.008v.008H12v-.008Z' },
        { id: 'analysis', label: '파라미터 분석', icon: 'M10.5 6a7.5 7.5 0 1 0 7.5 7.5h-7.5V6Z M13.5 10.5H21A7.5 7.5 0 0 0 13.5 3v7.5Z' },
    ];

    // ==========================================================================
    // 컬렉션
    // ==========================================================================
    public collections: any[] = [];
    public selectedCollection: string = '';
    public dbStats: any = {};

    // ==========================================================================
    // Tab 1: 조건 예측
    // ==========================================================================
    public params: any = {
        process_type: '', gas_type: '', pressure: '', power: '',
        temperature: '', substrate: '', target_property: ''
    };
    public predicting: boolean = false;
    public predictions: any[] = [];
    public predictionQuery: string = '';
    public totalSearched: number = 0;

    // Surrogate 예측
    public surrogateTarget: string = 'etch_rate';
    public surrogateConditions: any = {
        pressure: '', rf_power: '', gas_flow: '', temperature: '', frequency: '', bias_voltage: ''
    };
    public surrogateResult: any = null;
    public surrogatePredicting: boolean = false;
    public surrogateTargetOptions = [
        { value: 'etch_rate', label: '식각 속도 (Etch Rate)' },
        { value: 'deposition_rate', label: '증착 속도 (Deposition Rate)' },
        { value: 'uniformity', label: '균일도 (Uniformity)' },
        { value: 'selectivity', label: '선택비 (Selectivity)' },
    ];

    // ==========================================================================
    // Tab 2: 파라미터 DB
    // ==========================================================================
    public paramDbLoading: boolean = false;
    public paramDbSummary: any = {};
    public paramDbDocuments: any[] = [];
    public paramDbCached: boolean = false;
    public paramFilter: string = '';
    public paramSortBy: string = '';
    public expandedDoc: string = '';
    public paramDbExtracted: boolean = false;

    // ==========================================================================
    // Tab 3: 역설계
    // ==========================================================================
    public inverseTarget: string = '';
    public inverseLoading: boolean = false;
    public inverseConditions: any = {};
    public inverseEvidence: any[] = [];
    public inverseConfidence: number = 0;
    public inverseAnalyzed: boolean = false;
    public inverseSuggestions: string[] = [
        'Etch rate 200 nm/min with uniformity ±3%',
        'Deposition rate 50 nm/min at low temperature',
        'High selectivity over SiO2 with anisotropic profile',
        'Low damage etching for III-V semiconductors',
    ];

    // ==========================================================================
    // Tab 4: 불확실성
    // ==========================================================================
    public uncertaintyConditions: any = {
        pressure: '', rf_power: '', gas_flow: '', temperature: '', frequency: '', bias_voltage: ''
    };
    public uncertaintyLoading: boolean = false;
    public uncertainties: any = {};
    public uncertaintySimilarDocs: any[] = [];
    public uncertaintyAnalyzed: boolean = false;

    // ==========================================================================
    // Tab 5: 파라미터 분석
    // ==========================================================================
    public analysisParam: string = '';
    public analysisParamName: string = '';
    public analyzing: boolean = false;
    public paramAnalysis: any[] = [];

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
        await this.loadStats();
        await this.handleQueryParams();
        await this.service.render();
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
            case 'predict':
                if (params['process_type']) this.params.process_type = params['process_type'];
                if (params['gas_type']) this.params.gas_type = params['gas_type'];
                if (params['pressure']) this.params.pressure = params['pressure'];
                if (params['power']) this.params.power = params['power'];
                if (params['temperature']) this.params.temperature = params['temperature'];
                if (params['substrate']) this.params.substrate = params['substrate'];
                if (params['target_property']) this.params.target_property = params['target_property'];
                if (q && !this.params.target_property) this.params.target_property = q;
                const hasInput = Object.values(this.params).some((v: any) => v && v.toString().trim());
                if (hasInput) await this.predict();
                break;
            case 'inverse':
                this.inverseTarget = params['inverseTarget'] || q;
                if (this.inverseTarget) await this.runInverseSearch();
                break;
            case 'analysis':
                this.analysisParam = params['analysisParam'] || q;
                if (this.analysisParam) await this.analyzeParam();
                break;
            case 'paramdb':
                if (!this.paramDbExtracted) await this.extractParams();
                break;
        }
    }

    // ==========================================================================
    // 공통
    // ==========================================================================
    public switchTab(tabId: string) {
        this.activeTab = tabId;
        this.service.render();
    }

    public async loadCollections() {
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
    }

    public async loadStats() {
        try {
            const { code, data } = await wiz.call("stats", { collection: this.selectedCollection });
            if (code === 200) {
                this.dbStats = data || {};
                await this.service.render();
            }
        } catch (e) { }
    }

    public async onCollectionChange() {
        this.persistCollection(this.selectedCollection);
        this.paramDbExtracted = false;
        this.paramDbDocuments = [];
        this.paramDbSummary = {};
        await this.loadStats();
    }

    public getCollectionInfo() {
        return this.collections.find((c: any) => c.name === this.selectedCollection);
    }

    public objectKeys(obj: any): string[] {
        return obj ? Object.keys(obj) : [];
    }

    // ==========================================================================
    // Tab 1: 조건 예측
    // ==========================================================================
    public resetParams() {
        this.params = {
            process_type: '', gas_type: '', pressure: '', power: '',
            temperature: '', substrate: '', target_property: ''
        };
        this.predictions = [];
    }

    public async predict() {
        const hasInput = Object.values(this.params).some((v: any) => v.trim());
        if (!hasInput) return;
        this.predicting = true;
        this.predictions = [];
        await this.service.render();
        try {
            const { code, data } = await wiz.call("predict", {
                ...this.params, collection: this.selectedCollection
            });
            if (code === 200) {
                this.predictions = data.predictions || [];
                this.predictionQuery = data.query || '';
                this.totalSearched = data.total_searched || 0;
            }
        } catch (e) { }
        this.predicting = false;
        await this.service.render();
    }

    public async runSurrogatePredict() {
        const hasInput = Object.values(this.surrogateConditions).some((v: any) => v.toString().trim());
        if (!hasInput) return;
        this.surrogatePredicting = true;
        this.surrogateResult = null;
        await this.service.render();
        try {
            const params: any = { target_param: this.surrogateTarget, collection: this.selectedCollection };
            for (const [k, v] of Object.entries(this.surrogateConditions)) {
                if ((v as string).toString().trim()) params[k] = v;
            }
            const { code, data } = await wiz.call("surrogate_predict", params);
            if (code === 200) {
                this.surrogateResult = data;
            }
        } catch (e) { }
        this.surrogatePredicting = false;
        await this.service.render();
    }

    // ==========================================================================
    // Tab 2: 파라미터 DB
    // ==========================================================================
    public async extractParams(force: boolean = false) {
        this.paramDbLoading = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("extract_params", {
                collection: this.selectedCollection, force: force ? 'true' : 'false'
            });
            if (code === 200) {
                this.paramDbSummary = data.summary || {};
                this.paramDbCached = data.cached || false;
                this.paramDbExtracted = true;
                const docs = data.param_db?.documents || {};
                this.paramDbDocuments = Object.entries(docs).map(([id, info]: [string, any]) => ({
                    doc_id: id, ...info
                }));
            }
        } catch (e) { }
        this.paramDbLoading = false;
        await this.service.render();
    }

    public async loadParamDatabase() {
        try {
            const { code, data } = await wiz.call("param_database", {
                collection: this.selectedCollection,
                param_filter: this.paramFilter,
                sort_by: this.paramSortBy
            });
            if (code === 200) {
                this.paramDbDocuments = data.documents || [];
                this.paramDbSummary = data.summary || {};
                this.paramDbExtracted = true;
            }
        } catch (e) { }
        await this.service.render();
    }

    public toggleDoc(docId: string) {
        this.expandedDoc = this.expandedDoc === docId ? '' : docId;
        this.service.render();
    }

    public getParamKeys(): string[] {
        return Object.keys(this.paramDbSummary).filter(k => k !== 'gas_species');
    }

    public getConditionSummaryKeys(): string[] {
        return this.getParamKeys().filter(k => this.paramDbSummary[k]?.category === 'condition');
    }

    public getResultSummaryKeys(): string[] {
        return this.getParamKeys().filter(k => this.paramDbSummary[k]?.category === 'result');
    }

    // ==========================================================================
    // Tab 3: 역설계
    // ==========================================================================
    public async runInverseSearch() {
        if (!this.inverseTarget.trim()) return;
        this.inverseLoading = true;
        this.inverseAnalyzed = false;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("inverse_search", {
                target_text: this.inverseTarget, collection: this.selectedCollection
            });
            if (code === 200) {
                this.inverseConditions = data.suggested_conditions || {};
                this.inverseEvidence = data.evidence || [];
                this.inverseConfidence = data.confidence || 0;
                this.inverseAnalyzed = true;
            }
        } catch (e) { }
        this.inverseLoading = false;
        await this.service.render();
    }

    public useSuggestion(text: string) {
        this.inverseTarget = text;
        this.service.render();
    }

    public getInverseConditionKeys(): string[] {
        return Object.keys(this.inverseConditions).filter(k => k !== 'gas_species');
    }

    public confidenceColor(confidence: number): string {
        if (confidence >= 0.7) return 'text-emerald-600';
        if (confidence >= 0.4) return 'text-amber-600';
        return 'text-red-500';
    }

    public confidenceLabel(confidence: number): string {
        if (confidence >= 0.7) return '높음';
        if (confidence >= 0.4) return '보통';
        return '낮음';
    }

    // ==========================================================================
    // Tab 4: 불확실성
    // ==========================================================================
    public async runUncertainty() {
        const hasInput = Object.values(this.uncertaintyConditions).some((v: any) => v.toString().trim());
        if (!hasInput) return;
        this.uncertaintyLoading = true;
        this.uncertaintyAnalyzed = false;
        await this.service.render();
        try {
            const params: any = { collection: this.selectedCollection };
            for (const [k, v] of Object.entries(this.uncertaintyConditions)) {
                if ((v as string).toString().trim()) params[k] = v;
            }
            const { code, data } = await wiz.call("estimate_uncertainty", params);
            if (code === 200) {
                this.uncertainties = data.uncertainties || {};
                this.uncertaintySimilarDocs = data.similar_docs || [];
                this.uncertaintyAnalyzed = true;
            }
        } catch (e) { }
        this.uncertaintyLoading = false;
        await this.service.render();
    }

    public getUncertaintyKeys(): string[] {
        return Object.keys(this.uncertainties);
    }

    public reliabilityColor(r: number): string {
        if (r >= 0.7) return 'bg-emerald-500';
        if (r >= 0.4) return 'bg-amber-500';
        return 'bg-red-500';
    }

    // ==========================================================================
    // Tab 5: 파라미터 분석
    // ==========================================================================
    public async analyzeParam() {
        if (!this.analysisParam.trim()) return;
        this.analyzing = true;
        this.paramAnalysis = [];
        this.analysisParamName = this.analysisParam;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("analyze_params", {
                param_name: this.analysisParam, collection: this.selectedCollection
            });
            if (code === 200) {
                this.paramAnalysis = data.analysis || [];
            }
        } catch (e) { }
        this.analyzing = false;
        await this.service.render();
    }
}
