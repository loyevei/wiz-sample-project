import { OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
    private readonly collectionStorageKey: string = 'plasma.selectedCollection';

    public activeTab: string = 'search';
    public tabs: any[] = [
        { id: 'search', label: '문헌 검색' },
        { id: 'spectrum', label: '스펙트럼 분석' },
        { id: 'multimodal', label: '멀티모달 검색' },
        { id: 'detection', label: '이상 탐지' },
        { id: 'failure', label: '고장 진단' },
        { id: 'compare', label: '진단 비교' },
        { id: 'boltzmann', label: 'Boltzmann Plot' },
        { id: 'langmuir', label: 'Langmuir Probe' },
        { id: 'actinometry', label: 'Actinometry' }
    ];

    // Collections
    public collections: any[] = [];
    public selectedCollection: string = '';

    // Overview stats
    public overviewStats: any = {};
    public overviewLoading: boolean = false;
    public diagnosticOverview: any[] = [];

    // ===== Search Tab =====
    public searchQuery: string = '';
    public selectedDiagType: string = '';
    public searching: boolean = false;
    public searchResults: any[] = [];
    public lastSearchQuery: string = '';
    public diagnosticTypes: string[] = [
        'OES', 'Langmuir Probe', 'Mass Spectrometry',
        'Ellipsometry', 'SEM', 'XPS', 'AFM', 'Interferometry'
    ];

    // ===== Spectrum Tab =====
    public spectrumInput: string = '';
    public spectrumLabel: string = '';
    public spectrumConditions: string = '';
    public uploading: boolean = false;
    public spectrumResult: any = null;
    public storedSpectra: any[] = [];
    public searchingSpectrum: boolean = false;
    public similarSpectra: any[] = [];
    public relatedPapers: any[] = [];
    public spectrumQueryInfo: any = null;

    // ===== Multimodal Tab =====
    public mmTextQuery: string = '';
    public mmSpectrumData: string = '';
    public mmTextWeight: number = 0.6;
    public mmSpectrumWeight: number = 0.4;
    public mmSearching: boolean = false;
    public mmResults: any[] = [];
    public mmSpectrumInfo: any = null;

    // ===== Detection Tab =====
    public baselineInput: string = '';
    public baselineLabel: string = 'default';
    public baselineThreshold: number = 0.15;
    public settingBaseline: boolean = false;
    public baselineInfo: any = null;
    public detectionInput: string = '';
    public checking: boolean = false;
    public detectionResult: any = null;
    public anomalyHistory: any[] = [];
    public historyStats: any = null;

    // ===== Failure Tab =====
    public failureSymptom: string = '';
    public failureSpectrumData: string = '';
    public failureSearching: boolean = false;
    public failureResult: any = null;
    public failurePatterns: any[] = [];
    public newPatternName: string = '';
    public newPatternSymptoms: string = '';
    public newPatternCauses: string = '';
    public newPatternSolutions: string = '';
    public newPatternPeaks: string = '';
    public showPatternForm: boolean = false;
    public commonSymptoms: string[] = [
        '아킹 발생', '균일도 저하', '파티클 증가',
        '식각 속도 변동', '플라즈마 불안정', '챔버 오염',
        '전력 반사 증가', '가스 누출'
    ];

    // ===== Boltzmann Plot Tab =====
    public boltzmannData: string = '';
    public boltzmannLoading: boolean = false;
    public boltzmannResult: any = null;

    // ===== Langmuir Probe Tab =====
    public langmuirData: string = '';
    public langmuirLoading: boolean = false;
    public langmuirResult: any = null;

    // ===== Actinometry Tab =====
    public actinometryData: string = '';
    public actinometryRefGas: string = 'Ar';
    public actinometryLoading: boolean = false;
    public actinometryResult: any = null;

    // ===== Compare Tab =====
    public compareMethodA: string = '';
    public compareMethodB: string = '';
    public comparing: boolean = false;
    public comparisonResult: any = null;

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
        await this.loadOverview();
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
            case 'search':
                if (q) this.searchQuery = q;
                if (params['diagType']) this.selectedDiagType = params['diagType'];
                if (this.searchQuery || this.selectedDiagType) await this.searchDiagnostic();
                break;
            case 'failure':
                this.failureSymptom = params['symptom'] || q;
                await this.loadFailurePatterns();
                if (this.failureSymptom) await this.failureReasoning();
                break;
            case 'compare':
                if (params['methodA']) this.compareMethodA = params['methodA'];
                if (params['methodB']) this.compareMethodB = params['methodB'];
                if (q && !this.compareMethodA) this.compareMethodA = q;
                if (this.compareMethodA && this.compareMethodB) await this.compareDiagnostics();
                break;
            case 'spectrum':
                await this.loadStoredSpectra();
                break;
            case 'detection':
                await this.loadBaseline();
                await this.loadAnomalyHistory();
                break;
        }
    }

    // ===== Common =====
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

    public getCollectionInfo() {
        return this.collections.find((c: any) => c.name === this.selectedCollection);
    }

    public async onCollectionChange() {
        this.persistCollection(this.selectedCollection);
        // 탭별 기존 결과 초기화
        this.searchResults = [];
        this.similarSpectra = [];
        this.relatedPapers = [];
        this.mmResults = [];
        this.comparisonResult = null;
        this.failureResult = null;
        this.diagnosticOverview = [];
        // 개요 재로드
        await this.loadOverview();
        // 현재 탭에 따라 추가 데이터 로드
        if (this.activeTab === 'spectrum') await this.loadStoredSpectra();
        if (this.activeTab === 'failure') await this.loadFailurePatterns();
        await this.service.render();
    }

    public async loadOverview() {
        this.overviewLoading = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("overview", { collection: this.selectedCollection });
            if (code === 200) {
                const diag = data.diagnostics || {};
                this.diagnosticOverview = Object.entries(diag).map(([method, info]: [string, any]) => ({
                    method, count: info.count, doc_count: info.doc_count, max_score: info.max_score
                })).sort((a: any, b: any) => b.max_score - a.max_score);
                this.overviewStats = {
                    total_chunks: data.total_chunks || 0,
                    spectrum_count: data.spectrum_count || 0,
                    has_baseline: data.has_baseline || false,
                    anomaly_count: data.anomaly_count || 0
                };
            }
        } catch (e) { }
        this.overviewLoading = false;
        await this.service.render();
    }

    public async switchTab(tabId: string) {
        this.activeTab = tabId;
        if (tabId === 'spectrum') await this.loadStoredSpectra();
        if (tabId === 'detection') { await this.loadBaseline(); await this.loadAnomalyHistory(); }
        if (tabId === 'failure') await this.loadFailurePatterns();
        await this.service.render();
    }

    // ===== Search Tab =====
    public async searchDiagnostic() {
        if (!this.searchQuery.trim() && !this.selectedDiagType) return;
        this.searching = true;
        this.searchResults = [];
        await this.service.render();
        try {
            const { code, data } = await wiz.call("search_diagnostic", {
                query: this.searchQuery, diagnostic_type: this.selectedDiagType,
                top_k: 20, collection: this.selectedCollection
            });
            if (code === 200) {
                this.searchResults = data.results || [];
                this.lastSearchQuery = data.query || '';
            }
        } catch (e) { }
        this.searching = false;
        await this.service.render();
    }

    // ===== Spectrum Tab =====
    public async handleSpectrumFile(event: any) {
        const file = event?.target?.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (e: any) => {
            this.spectrumInput = e.target.result;
            this.spectrumLabel = file.name.replace(/\.[^.]+$/, '');
            await this.service.render();
        };
        reader.readAsText(file);
    }

    public async uploadSpectrum() {
        if (!this.spectrumInput.trim()) return;
        this.uploading = true;
        this.spectrumResult = null;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("upload_spectrum", {
                spectrum_data: this.spectrumInput, label: this.spectrumLabel,
                conditions: this.spectrumConditions
            });
            if (code === 200) {
                this.spectrumResult = data.spectrum;
                await this.loadStoredSpectra();
            }
        } catch (e) { }
        this.uploading = false;
        await this.service.render();
    }

    public async loadStoredSpectra() {
        try {
            const { code, data } = await wiz.call("spectrum_list");
            if (code === 200) this.storedSpectra = data.spectra || [];
        } catch (e) { }
        await this.service.render();
    }

    public async searchSimilarSpectrum() {
        if (!this.spectrumInput.trim()) return;
        this.searchingSpectrum = true;
        this.similarSpectra = [];
        this.relatedPapers = [];
        await this.service.render();
        try {
            const { code, data } = await wiz.call("search_similar_spectrum", {
                spectrum_data: this.spectrumInput, top_k: 10, collection: this.selectedCollection
            });
            if (code === 200) {
                this.similarSpectra = data.similar_spectra || [];
                this.relatedPapers = data.related_papers || [];
                this.spectrumQueryInfo = data.query_info || null;
            }
        } catch (e) { }
        this.searchingSpectrum = false;
        await this.service.render();
    }

    public async deleteSpectrum(id: string) {
        try {
            const { code } = await wiz.call("delete_spectrum", { id });
            if (code === 200) await this.loadStoredSpectra();
        } catch (e) { }
    }

    // ===== Multimodal Tab =====
    public async handleMmSpectrumFile(event: any) {
        const file = event?.target?.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (e: any) => {
            this.mmSpectrumData = e.target.result;
            await this.service.render();
        };
        reader.readAsText(file);
    }

    public async multimodalSearch() {
        if (!this.mmTextQuery.trim() && !this.mmSpectrumData.trim()) return;
        this.mmSearching = true;
        this.mmResults = [];
        this.mmSpectrumInfo = null;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("multimodal_search", {
                text_query: this.mmTextQuery, spectrum_data: this.mmSpectrumData,
                text_weight: this.mmTextWeight, spectrum_weight: this.mmSpectrumWeight,
                top_k: 15, collection: this.selectedCollection
            });
            if (code === 200) {
                this.mmResults = data.results || [];
                this.mmSpectrumInfo = data.spectrum_info || null;
            }
        } catch (e) { }
        this.mmSearching = false;
        await this.service.render();
    }

    // ===== Detection Tab =====
    public async handleBaselineFile(event: any) {
        const file = event?.target?.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (e: any) => {
            this.baselineInput = e.target.result;
            await this.service.render();
        };
        reader.readAsText(file);
    }

    public async setBaseline() {
        if (!this.baselineInput.trim()) return;
        this.settingBaseline = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("set_baseline", {
                spectra_data: this.baselineInput, label: this.baselineLabel,
                threshold: this.baselineThreshold
            });
            if (code === 200) {
                this.baselineInfo = data.baseline;
                await this.loadOverview();
            }
        } catch (e) { }
        this.settingBaseline = false;
        await this.service.render();
    }

    public async loadBaseline() {
        try {
            const { code, data } = await wiz.call("get_baseline");
            if (code === 200 && data.has_baseline) this.baselineInfo = data;
        } catch (e) { }
        await this.service.render();
    }

    public async handleDetectionFile(event: any) {
        const file = event?.target?.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (e: any) => {
            this.detectionInput = e.target.result;
            await this.service.render();
        };
        reader.readAsText(file);
    }

    public async checkAnomaly() {
        if (!this.detectionInput.trim()) return;
        this.checking = true;
        this.detectionResult = null;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("check_anomaly", { spectrum_data: this.detectionInput });
            if (code === 200) {
                this.detectionResult = data;
                await this.loadAnomalyHistory();
            }
        } catch (e) { }
        this.checking = false;
        await this.service.render();
    }

    public async loadAnomalyHistory() {
        try {
            const { code, data } = await wiz.call("anomaly_history_list", { limit: 50 });
            if (code === 200) {
                this.anomalyHistory = data.history || [];
                this.historyStats = { total: data.total, anomaly_count: data.anomaly_count, avg_distance: data.avg_distance };
            }
        } catch (e) { }
        await this.service.render();
    }

    public async updateThreshold() {
        try {
            await wiz.call("update_threshold", { threshold: this.baselineThreshold });
            await this.loadBaseline();
        } catch (e) { }
    }

    public async clearHistory() {
        try {
            await wiz.call("clear_history");
            this.anomalyHistory = [];
            this.historyStats = null;
            await this.service.render();
        } catch (e) { }
    }

    // ===== Failure Tab =====
    public async handleFailureSpectrumFile(event: any) {
        const file = event?.target?.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = async (e: any) => {
            this.failureSpectrumData = e.target.result;
            await this.service.render();
        };
        reader.readAsText(file);
    }

    public async failureReasoning() {
        if (!this.failureSymptom.trim()) return;
        this.failureSearching = true;
        this.failureResult = null;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("failure_reasoning", {
                symptom: this.failureSymptom, spectrum_data: this.failureSpectrumData,
                collection: this.selectedCollection
            });
            if (code === 200) this.failureResult = data;
        } catch (e) { }
        this.failureSearching = false;
        await this.service.render();
    }

    public async loadFailurePatterns() {
        try {
            const { code, data } = await wiz.call("list_failure_patterns");
            if (code === 200) this.failurePatterns = data.patterns || [];
        } catch (e) { }
        await this.service.render();
    }

    public async registerPattern() {
        if (!this.newPatternName.trim()) return;
        try {
            const { code } = await wiz.call("register_failure_pattern", {
                name: this.newPatternName, symptoms: this.newPatternSymptoms,
                causes: this.newPatternCauses, solutions: this.newPatternSolutions,
                related_peaks: this.newPatternPeaks
            });
            if (code === 200) {
                this.newPatternName = ''; this.newPatternSymptoms = '';
                this.newPatternCauses = ''; this.newPatternSolutions = '';
                this.newPatternPeaks = ''; this.showPatternForm = false;
                await this.loadFailurePatterns();
            }
        } catch (e) { }
    }

    public async deletePattern(id: string) {
        try {
            const { code } = await wiz.call("delete_failure_pattern", { id });
            if (code === 200) await this.loadFailurePatterns();
        } catch (e) { }
    }

    // ===== Compare Tab =====
    public async compareDiagnostics() {
        if (!this.compareMethodA.trim() || !this.compareMethodB.trim()) return;
        this.comparing = true;
        this.comparisonResult = null;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("compare_diagnostics", {
                method_a: this.compareMethodA, method_b: this.compareMethodB,
                collection: this.selectedCollection
            });
            if (code === 200) this.comparisonResult = data;
        } catch (e) { }
        this.comparing = false;
        await this.service.render();
    }

    // ===== Helpers =====
    public severityColor(severity: number): string {
        if (severity < 0.3) return 'text-green-600';
        if (severity < 0.6) return 'text-amber-600';
        return 'text-red-600';
    }

    public severityBg(severity: number): string {
        if (severity < 0.3) return 'bg-green-500';
        if (severity < 0.6) return 'bg-amber-500';
        return 'bg-red-500';
    }

    public severityLabel(severity: number): string {
        if (severity < 0.3) return '정상';
        if (severity < 0.6) return '주의';
        return '위험';
    }

    public objectKeys(obj: any): string[] {
        return obj ? Object.keys(obj) : [];
    }

    // ===== Boltzmann Plot =====
    public async analyzeBoltzmann() {
        if (!this.boltzmannData.trim()) return;
        this.boltzmannLoading = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("boltzmann_plot", {
                spectrum_data: this.boltzmannData
            });
            if (code === 200) this.boltzmannResult = data;
        } catch (e) { }
        this.boltzmannLoading = false;
        await this.service.render();
    }

    // ===== Langmuir Probe =====
    public async analyzeLangmuir() {
        if (!this.langmuirData.trim()) return;
        this.langmuirLoading = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("langmuir_analysis", {
                iv_data: this.langmuirData
            });
            if (code === 200) this.langmuirResult = data;
        } catch (e) { }
        this.langmuirLoading = false;
        await this.service.render();
    }

    // ===== Actinometry =====
    public async analyzeActinometry() {
        if (!this.actinometryData.trim()) return;
        this.actinometryLoading = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("actinometry_analysis", {
                spectrum_data: this.actinometryData,
                ref_gas: this.actinometryRefGas
            });
            if (code === 200) this.actinometryResult = data;
        } catch (e) { }
        this.actinometryLoading = false;
        await this.service.render();
    }
}
