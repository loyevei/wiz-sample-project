import { OnInit, OnDestroy } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit, OnDestroy {
    private readonly collectionChangeEventName: string = 'plasma-collection-changed';
    private collectionChangeListener: any = null;

    // 파일 관련
    public selectedFiles: File[] = [];
    public dragOver: boolean = false;
    public processing: boolean = false;
    public statusMessage: string = '';
    public logs: any[] = [];
    public showGuide: boolean = true;
    public currentFileIndex: number = 0;
    public totalFiles: number = 0;
    public progressPercent: number = 0;

    // 모델 선택
    public models: any[] = [];
    public selectedModel: string = '';
    public modelGroups: { label: string, lang: string, models: any[] }[] = [];

    // 커스텀 모델 추가
    public showAddModel: boolean = false;
    public newModelName: string = '';
    public addingModel: boolean = false;
    public addModelStatus: string = '';
    public removingModel: string = '';

    // 컬렉션 관리
    public collections: any[] = [];
    public selectedCollection: string = '';
    public newCollectionName: string = '';
    public showCreateCollection: boolean = false;
    public creatingCollection: boolean = false;
    public deletingCollection: string = '';

    // 청킹 옵션
    public chunkSize: number = 500;
    public chunkOverlap: number = 100;
    public respectSentences: boolean = true;
    public similarityThreshold: number = 0.5;

    // Vision LLM 옵션
    public useVision: boolean = false;
    public visionAvailable: boolean = false;

    // Nougat / Extraction Mode 옵션
    public extractionMode: string = 'surya';
    public nougatAvailable: boolean = false;
    public gemmaRescue: boolean = false;

    // 청킹 전략
    public chunkStrategies: any[] = [];
    public selectedStrategy: string = 'semantic_section';

    // 미리보기
    public previewData: any = null;
    public previewLoading: boolean = false;

    // 청크 타입 통계
    public chunkTypeStats: any = {};
    public chunkTypeEntries: any[] = [];
    public chunkTypeStatsLoading: boolean = false;

    // 통계
    public stats: any = {};
    public statsLoading: boolean = false;

    // 문서 목록
    public docList: any[] = [];
    public docListLoading: boolean = false;
    public expandedDocId: string = '';
    public deletingDocId: string = '';

    // 청크 브라우저
    public docChunks: any[] = [];
    public docChunksLoading: boolean = false;
    public docChunksPage: number = 1;
    public docChunksDump: number = 20;
    public docChunksTotal: number = 0;
    public docChunksTotalPages: number = 1;
    public docChunksTypeFilter: string = '';
    public expandedChunkId: string = '';

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.loadModels();
        await this.loadChunkStrategies();
        await this.loadCollections();
        await this.loadStats();
        await this.loadChunkTypeStats();
        await this.loadDocuments();
        await this.checkVisionStatus();
        await this.checkNougatStatus();
        await this.service.render();
        this.collectionChangeListener = async (event: any) => {
            const nextCollection = String(event?.detail?.collection || '').trim();
            const deletedCollection = String(event?.detail?.deletedCollection || '').trim();
            if (deletedCollection) {
                const previousCollection = this.selectedCollection;
                await this.loadCollections();
                if (previousCollection !== this.selectedCollection) {
                    await this.onCollectionChange(false);
                }
                return;
            }
            if (!nextCollection || nextCollection === this.selectedCollection) return;
            if (!this.collections.find((c: any) => c.name === nextCollection)) {
                await this.loadCollections();
                if (!this.collections.find((c: any) => c.name === nextCollection)) return;
            }
            this.selectedCollection = nextCollection;
            await this.onCollectionChange(false);
        };
        window.addEventListener(this.collectionChangeEventName, this.collectionChangeListener as EventListener);
    }

    public ngOnDestroy() {
        if (this.collectionChangeListener) {
            window.removeEventListener(this.collectionChangeEventName, this.collectionChangeListener as EventListener);
            this.collectionChangeListener = null;
        }
    }

    // =========================================================================
    // 모델 관련
    // =========================================================================
    public async loadModels() {
        try {
            const { code, data } = await wiz.call("models");
            if (code === 200) {
                this.models = data.models || [];
                if (!this.selectedModel && data.default) {
                    this.selectedModel = data.default;
                }
                this.modelGroups = this.groupModelsByLang(this.models);
            }
        } catch (e) { }
    }

    private groupModelsByLang(models: any[]): any[] {
        const langOrder = ['ko', 'en', 'multi'];
        const langLabels: any = { ko: '🇰🇷 한국어', en: '🇺🇸 영어', multi: '🌐 다국어' };
        const groups: any = {};
        for (const m of models) {
            const lang = m.lang || 'multi';
            if (!groups[lang]) groups[lang] = [];
            groups[lang].push(m);
        }
        return langOrder
            .filter(l => groups[l])
            .map(l => ({ label: langLabels[l] || l, lang: l, models: groups[l] }));
    }

    public getSelectedModelInfo() {
        return this.models.find(m => m.name === this.selectedModel) || {};
    }

    public async addCustomModel() {
        const name = this.newModelName.trim();
        if (!name) return;

        if (this.models.find(m => m.name === name)) {
            this.addModelStatus = `⚠️ '${name}' 모델이 이미 등록되어 있습니다.`;
            await this.service.render();
            return;
        }

        this.addingModel = true;
        this.addModelStatus = `🔄 '${name}' 모델을 다운로드하고 있습니다... (최초 다운로드 시 수 분 소요)`;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("add_custom_model", { model_name: name });
            if (code === 200) {
                this.addModelStatus = `✅ ${data.message}`;
                this.newModelName = '';
                this.addLog(`✅ 모델 추가: ${data.model?.short_name} (${data.model?.dim}D)`, 'success');
                await this.loadModels();
            } else {
                this.addModelStatus = `❌ ${data?.message || '모델 추가 실패'}`;
                this.addLog(`❌ 모델 추가 실패: ${data?.message || '알 수 없는 오류'}`, 'error');
            }
        } catch (e: any) {
            this.addModelStatus = `❌ 네트워크 오류: ${e.message || '연결 실패'}`;
            this.addLog(`❌ 모델 추가 오류: ${e.message || '네트워크 오류'}`, 'error');
        }

        this.addingModel = false;
        await this.service.render();
    }

    public async removeCustomModel(modelName: string) {
        if (this.removingModel) return;

        const res = await this.service.modal.show({
            title: '커스텀 모델 삭제',
            message: `'${modelName}' 모델을 레지스트리에서 삭제하시겠습니까?\n\n⚠️ 이 모델을 사용하는 컬렉션은 영향받지 않지만, 새 임베딩 생성 시 이 모델을 선택할 수 없게 됩니다.`,
            action: '삭제',
            actionBtn: 'error',
            status: 'error'
        });
        if (!res) return;

        this.removingModel = modelName;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("remove_custom_model", { model_name: modelName });
            if (code === 200) {
                this.addLog(`🗑️ 모델 삭제: ${modelName}`, 'success');
                if (this.selectedModel === modelName) {
                    this.selectedModel = '';
                }
                await this.loadModels();
            } else {
                this.addLog(`❌ 모델 삭제 실패: ${data?.message || '알 수 없는 오류'}`, 'error');
            }
        } catch (e: any) {
            this.addLog(`❌ 모델 삭제 오류: ${e.message || '네트워크 오류'}`, 'error');
        }

        this.removingModel = '';
        await this.service.render();
    }

    public getLangLabel(lang: string): string {
        const labels: any = { ko: '한국어', en: '영어', multi: '다국어' };
        return labels[lang] || lang;
    }

    public getLangClass(lang: string): string {
        if (lang === 'ko') return 'bg-green-100 text-green-700';
        if (lang === 'en') return 'bg-amber-100 text-amber-700';
        return 'bg-blue-100 text-blue-700';
    }

    // =========================================================================
    // 컬렉션 관련
    // =========================================================================
    public async loadCollections() {
        try {
            const { code, data } = await wiz.call("collections");
            if (code === 200) {
                this.collections = data.collections || [];
                if (!this.selectedCollection && this.collections.length > 0) {
                    this.selectedCollection = this.collections[0].name;
                }
                // 선택된 컬렉션이 삭제된 경우 초기화
                if (this.selectedCollection && !this.collections.find(c => c.name === this.selectedCollection)) {
                    this.selectedCollection = this.collections.length > 0 ? this.collections[0].name : '';
                }
            }
        } catch (e) { }
        await this.service.render();
    }

    public getSelectedCollectionInfo() {
        return this.collections.find(c => c.name === this.selectedCollection) || {};
    }

    private applySelectedCollectionSummary() {
        const info: any = this.getSelectedCollectionInfo() || {};
        this.stats = {
            ...this.stats,
            total_docs: info.total_docs || 0,
            total_chunks: info.total_chunks || 0,
            model_name: info.model || this.selectedModel,
            model_short_name: info.short_name || this.getSelectedModelInfo().short_name || this.selectedModel,
            model_dim: info.dim || this.getSelectedModelInfo().dim || 0,
            collection: this.selectedCollection,
            created_at: info.created_at || ''
        };
        if (info && info.model) {
            this.selectedModel = info.model;
        }
    }

    private async refreshSelectedCollectionDataInBackground() {
        await Promise.all([
            this.loadStats(),
            this.loadChunkTypeStats()
        ]);
    }

    private async withTimeout<T>(promise: Promise<T>, timeoutMs: number, message: string): Promise<T> {
        let timeoutHandle: any = null;
        const timeoutPromise = new Promise<T>((_, reject) => {
            timeoutHandle = setTimeout(() => reject(new Error(message)), timeoutMs);
        });

        try {
            return await Promise.race([promise, timeoutPromise]);
        } finally {
            if (timeoutHandle) {
                clearTimeout(timeoutHandle);
            }
        }
    }

    private async verifyCreatedCollectionInBackground(collectionName: string) {
        await this.loadCollections();
        const exists = this.collections.find(c => c.name === collectionName);
        if (exists) {
            return;
        }

        this.collections = this.collections.filter(c => c.name !== collectionName);
        if (this.selectedCollection === collectionName) {
            this.selectedCollection = this.collections.length > 0 ? this.collections[0].name : '';
            this.applySelectedCollectionSummary();
        }
        this.addLog(`❌ 컬렉션 '${collectionName}' 생성 확인에 실패했습니다. 다시 시도해주세요.`, 'error');
        await this.service.render();
    }

    public async createCollection() {
        const name = this.newCollectionName.trim();
        if (!name) return;

        // 프론트엔드 사전 유효성 검사
        if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name)) {
            this.addLog('⚠️ 컬렉션 이름은 영문 또는 밑줄로 시작하고, 영문/숫자/밑줄만 사용할 수 있습니다.', 'error');
            return;
        }

        if (this.collections.find(c => c.name === name)) {
            this.addLog(`⚠️ '${name}' 컬렉션이 이미 존재합니다. 다른 이름을 사용하세요.`, 'error');
            return;
        }

        this.creatingCollection = true;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("create_collection", {
                collection_name: name,
                model_name: this.selectedModel
            });

            if (code === 200) {
                this.addLog(`✅ 컬렉션 '${name}' 생성 완료 (${this.getSelectedModelInfo().short_name || ''}, ${data.dim}D)`, 'success');
                this.newCollectionName = '';
                this.showCreateCollection = false;
                const selectedModelInfo = this.getSelectedModelInfo();
                if (!this.collections.find(c => c.name === name)) {
                    this.collections = [
                        ...this.collections,
                        {
                            name,
                            model: this.selectedModel,
                            short_name: selectedModelInfo.short_name || this.selectedModel,
                            dim: data.dim,
                            created_at: data?.created_at || new Date().toISOString(),
                            total_docs: 0,
                            total_chunks: 0
                        }
                    ];
                }
                this.selectedCollection = name;
                this.statsLoading = false;
                this.chunkTypeStatsLoading = false;
                this.chunkTypeStats = {};
                this.chunkTypeEntries = [];
                this.applySelectedCollectionSummary();
                this.broadcastCollectionChange(this.selectedCollection);
                this.creatingCollection = false;
                await this.service.render();
                void this.verifyCreatedCollectionInBackground(name);
                return;
            } else {
                this.addLog(`❌ 컬렉션 생성 실패: ${data?.message || '알 수 없는 오류'}`, 'error');
            }
        } catch (e: any) {
            this.addLog(`❌ 컬렉션 생성 오류: ${e.message || '네트워크 오류'}`, 'error');
        }

        this.creatingCollection = false;
        await this.service.render();
    }

    public async deleteCollection(name: string) {
        if (this.deletingCollection) return; // 이미 삭제 중이면 무시

        const collectionInfo = this.collections.find(c => c.name === name);
        const docCount = collectionInfo?.total_docs || 0;
        const chunkCount = collectionInfo?.total_chunks || 0;

        let message = `'${name}' 컬렉션을 삭제하시겠습니까?`;
        if (docCount > 0 || chunkCount > 0) {
            message += `\n\n📊 ${docCount}개 문서, ${chunkCount}개 청크가 영구 삭제됩니다.`;
        }
        message += '\n\n⚠️ 이 작업은 되돌릴 수 없습니다.';

        const res = await this.service.modal.show({
            title: '컬렉션 삭제',
            message,
            action: '삭제',
            actionBtn: 'error',
            status: 'error'
        });
        if (!res) return;

        this.deletingCollection = name;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("delete_collection", { collection_name: name });
            if (code === 200) {
                this.addLog(`🗑️ 컬렉션 '${name}' 삭제 완료`, 'success');
                const previousCollection = this.selectedCollection;
                this.collections = this.collections.filter(c => c.name !== name);
                if (previousCollection === name) {
                    this.selectedCollection = this.collections.length > 0 ? this.collections[0].name : '';
                }
                this.broadcastCollectionChange(this.selectedCollection, name);
                if (!this.selectedCollection) {
                    this.stats = {};
                    this.chunkTypeStats = {};
                    this.chunkTypeEntries = [];
                } else {
                    this.chunkTypeStats = {};
                    this.chunkTypeEntries = [];
                    this.statsLoading = false;
                    this.chunkTypeStatsLoading = false;
                    this.applySelectedCollectionSummary();
                    if (previousCollection !== this.selectedCollection) {
                        void this.refreshSelectedCollectionDataInBackground();
                    }
                }
            } else {
                this.addLog(`❌ 삭제 실패: ${data?.message || '알 수 없는 오류'}`, 'error');
            }
        } catch (e: any) {
            this.addLog(`❌ 삭제 오류: ${e.message || '네트워크 오류'}`, 'error');
        }

        this.deletingCollection = '';
        await this.service.render();
    }

    // =========================================================================
    // 파일 관련
    // =========================================================================
    public openFileDialog() {
        const el = document.getElementById('pdfFileInput') as HTMLInputElement;
        if (el) el.click();
    }

    public onDragOver(event: DragEvent) {
        event.preventDefault();
        event.stopPropagation();
        this.dragOver = true;
    }

    public onDragLeave(event: DragEvent) {
        event.preventDefault();
        event.stopPropagation();
        this.dragOver = false;
    }

    public onDrop(event: DragEvent) {
        event.preventDefault();
        event.stopPropagation();
        this.dragOver = false;
        const files = event.dataTransfer?.files;
        if (files) this.addFiles(files);
    }

    public onFileSelect(event: any) {
        const files = event.target.files;
        if (files) this.addFiles(files);
        event.target.value = '';
    }

    private addFiles(fileList: FileList) {
        let added = 0;
        for (let i = 0; i < fileList.length; i++) {
            const file = fileList[i];
            if (file.type === 'application/pdf') {
                const exists = this.selectedFiles.some(f => f.name === file.name && f.size === file.size);
                if (!exists) {
                    this.selectedFiles.push(file);
                    added++;
                }
            }
        }
        if (added > 0) {
            this.addLog(`📎 ${added}개 파일 추가됨 (총 ${this.selectedFiles.length}개)`);
        }
    }

    public removeFile(index: number) {
        const name = this.selectedFiles[index].name;
        this.selectedFiles.splice(index, 1);
        this.addLog(`🗑️ ${name} 제거됨`);
    }

    public formatSize(bytes: number): string {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    private addLog(message: string, type: string = 'info') {
        const now = new Date();
        const time = now.toLocaleTimeString('ko-KR', { hour12: false });
        this.logs.unshift({ time, message, type });
    }

    // =========================================================================
    // 업로드
    // =========================================================================
    public async upload() {
        if (this.selectedFiles.length === 0) return;
        if (!this.selectedCollection) {
            this.addLog('⚠️ 컬렉션을 선택하거나 생성하세요.', 'error');
            return;
        }

        this.processing = true;
        this.totalFiles = this.selectedFiles.length;
        this.currentFileIndex = 0;
        this.progressPercent = 0;
        this.showGuide = false;
        this.statusMessage = '업로드 준비 중...';
        await this.service.render();

        const files = [...this.selectedFiles];
        let successCount = 0;
        let failCount = 0;

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            this.currentFileIndex = i;
            this.progressPercent = Math.round((i / files.length) * 100);
            this.statusMessage = `${file.name} 처리 중...`;
            this.addLog(`📄 ${file.name} (${this.formatSize(file.size)}) 업로드 시작`);
            await this.service.render();

            try {
                const fd = new FormData();
                fd.append('file', file);
                fd.append('collection', this.selectedCollection);
                fd.append('model', this.selectedModel);
                fd.append('chunk_size', String(this.chunkSize));
                fd.append('chunk_overlap', String(this.chunkOverlap));
                fd.append('respect_sentences', String(this.respectSentences));
                fd.append('chunk_strategy', this.selectedStrategy);
                fd.append('similarity_threshold', String(this.similarityThreshold));
                if (this.useVision) fd.append('use_vision', 'true');
                fd.append('extraction_mode', this.extractionMode);
                if (this.extractionMode === 'nougat_hybrid') fd.append('use_nougat', 'true');
                if (this.gemmaRescue) fd.append('gemma_rescue', 'true');

                const response = await fetch('/wiz/api/page.embedding.v2/upload', {
                    method: 'POST',
                    body: fd
                });
                const payload = await response.json();
                const code = payload?.code;
                const data = payload?.data || {};

                if (code === 200) {
                    let detail = `${data.chunks_count}개 청크 → ${data.vectors_stored}개 벡터`;
                    if (data.figures_detected > 0) detail += `, 그림 ${data.figures_detected}개`;
                    if (data.formulas_detected > 0) detail += `, 수식 ${data.formulas_detected}개`;
                    if (data.tables_detected > 0) detail += `, 표 ${data.tables_detected}개`;
                    if (data.nougat_pages_used > 0) detail += `, Nougat ${data.nougat_pages_used}p`;
                    if (data.gemma_rescues > 0) detail += `, Gemma rescue ${data.gemma_rescues}건`;
                    this.addLog(`✅ ${file.name}: ${detail} [${data.model_used}]`, 'success');
                    successCount++;
                } else {
                    this.addLog(`❌ ${file.name}: ${data?.message || '처리 실패'}`, 'error');
                    failCount++;
                }
            } catch (e: any) {
                this.addLog(`❌ ${file.name}: ${e.message || '네트워크 오류'}`, 'error');
                failCount++;
            }
            await this.service.render();
        }

        this.progressPercent = 100;
        this.selectedFiles = [];
        this.processing = false;
        this.statusMessage = '';

        let summary = `🏁 처리 완료: 성공 ${successCount}개`;
        if (failCount > 0) summary += `, 실패 ${failCount}개`;
        this.addLog(summary, failCount > 0 ? 'error' : 'success');

        await this.loadCollections();
        await this.loadStats();
        await this.loadChunkTypeStats();
        await this.loadDocuments();
        await this.service.render();
    }

    // =========================================================================
    // 통계
    // =========================================================================
    public async loadStats() {
        if (!this.selectedCollection) {
            this.stats = {};
            this.statsLoading = false;
            await this.service.render();
            return;
        }

        this.statsLoading = true;
        await this.service.render();

        try {
            const params: any = {};
            if (this.selectedCollection) params.collection = this.selectedCollection;
            const { code, data } = await wiz.call("stats", params);
            if (code === 200) {
                this.stats = data || {};
            }
        } catch (e) { }

        this.statsLoading = false;
        await this.service.render();
    }

    public async onCollectionChange(emitEvent: boolean = true) {
        this.applySelectedCollectionSummary();
        this.expandedDocId = '';
        this.docChunks = [];
        await this.service.render();
        void this.refreshSelectedCollectionDataInBackground();
        // 컬렉션 변경 시 해당 컬렉션의 모델로 자동 전환
        const info = this.getSelectedCollectionInfo();
        if (info && info.model) {
            this.selectedModel = info.model;
        }
        if (emitEvent) {
            this.broadcastCollectionChange(this.selectedCollection);
        }
        await this.loadDocuments();
        await this.service.render();
    }

    private broadcastCollectionChange(collection: string, deletedCollection: string = '') {
        window.dispatchEvent(new CustomEvent(this.collectionChangeEventName, {
            detail: {
                collection: String(collection || '').trim(),
                deletedCollection: String(deletedCollection || '').trim(),
                source: 'page-embedding'
            }
        }));
    }

    // =========================================================================
    // 청킹 전략 관련
    // =========================================================================
    public async loadChunkStrategies() {
        try {
            const { code, data } = await wiz.call("chunk_strategies");
            if (code === 200) {
                this.chunkStrategies = data.strategies || [];
                if (!this.selectedStrategy) {
                    const def = this.chunkStrategies.find((s: any) => s.default);
                    this.selectedStrategy = def ? def.name : 'semantic_section';
                }
            }
        } catch (e) { }
    }

    public onStrategyChange() {
        this.service.render();
    }

    public getStrategyParams(): string[] {
        const s = this.chunkStrategies.find((x: any) => x.name === this.selectedStrategy);
        return s ? s.params : ['chunk_size', 'chunk_overlap', 'respect_sentences'];
    }

    public getSelectedStrategyInfo(): any {
        return this.chunkStrategies.find((s: any) => s.name === this.selectedStrategy) || {};
    }

    public getStrategyIcon(name: string): string {
        const icons: any = {
            'semantic_section': '🧠',
            'fixed': '📐',
            'sentence': '📝',
            'paragraph': '📄',
            'recursive': '🔄',
            'semantic_embedding': '🎯'
        };
        return icons[name] || '📋';
    }

    // =========================================================================
    // 미리보기
    // =========================================================================
    public async previewExtract() {
        if (this.selectedFiles.length === 0) return;
        this.previewLoading = true;
        this.previewData = null;
        await this.service.render();

        try {
            const fd = new FormData();
            fd.append('file', this.selectedFiles[0]);
            fd.append('strategy', this.selectedStrategy);
            fd.append('chunk_size', String(this.chunkSize));
            fd.append('chunk_overlap', String(this.chunkOverlap));
            fd.append('respect_sentences', String(this.respectSentences));
            fd.append('similarity_threshold', String(this.similarityThreshold));
            if (this.useVision) fd.append('use_vision', 'true');

            const { code, data } = await wiz.call("preview_extract", fd, {
                contentType: false,
                processData: false
            });

            if (code === 200) {
                this.previewData = data;
                this.addLog(`🔍 미리보기: ${data.total_chunks}개 청크, ${data.total_pages}페이지 (${data.strategy_used})`, 'success');
            } else {
                this.addLog(`❌ 미리보기 실패: ${data?.message || '오류'}`, 'error');
            }
        } catch (e: any) {
            this.addLog(`❌ 미리보기 오류: ${e.message || '네트워크 오류'}`, 'error');
        }

        this.previewLoading = false;
        await this.service.render();
    }

    public getPreviewChunkTypeDist(): any[] {
        if (!this.previewData?.chunk_type_distribution) return [];
        const dist = this.previewData.chunk_type_distribution;
        return Object.entries(dist).map(([type, count]) => ({ type, count }));
    }

    // =========================================================================
    // 청크 타입 통계
    // =========================================================================
    public async loadChunkTypeStats() {
        if (!this.selectedCollection) {
            this.chunkTypeStats = {};
            this.chunkTypeEntries = [];
            this.chunkTypeStatsLoading = false;
            await this.service.render();
            return;
        }
        this.chunkTypeStatsLoading = true;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("chunk_type_stats", {
                collection: this.selectedCollection
            });
            if (code === 200) {
                this.chunkTypeStats = data;
                this.chunkTypeEntries = this.buildChunkTypeEntries(data.stats || {}, data.total || 0);
            }
        } catch (e) { }

        this.chunkTypeStatsLoading = false;
        await this.service.render();
    }

    public async checkVisionStatus() {
        try {
            const { code, data } = await wiz.call("vision_status");
            if (code === 200) {
                this.visionAvailable = data.available;
            }
        } catch (e) { }
    }

    public async checkNougatStatus() {
        try {
            const { code, data } = await wiz.call("nougat_status");
            if (code === 200) {
                this.nougatAvailable = data.available;
            }
        } catch (e) { }
    }

    private buildChunkTypeEntries(stats: any, total: number): any[] {
        if (!stats || total === 0) return [];
        const colorMap: any = {
            text: { barColor: 'bg-blue-500', bgColor: 'bg-blue-50', textColor: 'text-blue-700' },
            formula: { barColor: 'bg-amber-500', bgColor: 'bg-amber-50', textColor: 'text-amber-700' },
            figure: { barColor: 'bg-emerald-500', bgColor: 'bg-emerald-50', textColor: 'text-emerald-700' },
            table: { barColor: 'bg-rose-500', bgColor: 'bg-rose-50', textColor: 'text-rose-700' },
            mixed: { barColor: 'bg-purple-500', bgColor: 'bg-purple-50', textColor: 'text-purple-700' }
        };
        const defaultColor = { barColor: 'bg-gray-500', bgColor: 'bg-gray-50', textColor: 'text-gray-700' };
        return Object.entries(stats)
            .sort(([, a]: any, [, b]: any) => b - a)
            .map(([type, count]: any) => {
                const colors = colorMap[type] || defaultColor;
                return {
                    type, count,
                    label: this.getChunkTypeLabel(type),
                    percent: Math.round((count / total) * 100),
                    ...colors
                };
            });
    }

    public getChunkTypeColor(type: string): string {
        const colors: any = {
            text: 'bg-blue-100 text-blue-700',
            formula: 'bg-amber-100 text-amber-700',
            figure: 'bg-emerald-100 text-emerald-700',
            table: 'bg-rose-100 text-rose-700',
            mixed: 'bg-purple-100 text-purple-700'
        };
        return colors[type] || 'bg-gray-100 text-gray-700';
    }

    public getChunkTypeLabel(type: string): string {
        const labels: any = {
            text: '텍스트',
            formula: '수식',
            figure: '그림',
            table: '표',
            mixed: '복합'
        };
        return labels[type] || type;
    }

    // =========================================================================
    // 문서 목록
    // =========================================================================
    public async loadDocuments() {
        if (!this.selectedCollection) {
            this.docList = [];
            return;
        }
        this.docListLoading = true;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("documents", {
                collection: this.selectedCollection
            });
            if (code === 200) {
                this.docList = data.documents || [];
            }
        } catch (e) { }

        this.docListLoading = false;
        await this.service.render();
    }

    public getDocTypeEntries(doc: any): any[] {
        const tc = doc.type_counts || {};
        const total = Object.values(tc).reduce((a: number, b: any) => a + b, 0) as number;
        if (total === 0) return [];
        return Object.entries(tc)
            .sort(([, a]: any, [, b]: any) => b - a)
            .map(([type, count]: any) => ({
                type, count,
                label: this.getChunkTypeLabel(type),
                percent: Math.round((count / total) * 100)
            }));
    }

    public async toggleDocChunks(docId: string) {
        if (this.expandedDocId === docId) {
            this.expandedDocId = '';
            this.docChunks = [];
            await this.service.render();
            return;
        }
        this.expandedDocId = docId;
        this.docChunksPage = 1;
        this.docChunksTypeFilter = '';
        this.expandedChunkId = '';
        await this.loadDocChunks();
    }

    public async loadDocChunks() {
        if (!this.expandedDocId || !this.selectedCollection) return;
        this.docChunksLoading = true;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("document_chunks", {
                collection: this.selectedCollection,
                doc_id: this.expandedDocId,
                page: this.docChunksPage,
                dump: this.docChunksDump,
                chunk_type: this.docChunksTypeFilter
            });
            if (code === 200) {
                this.docChunks = data.chunks || [];
                this.docChunksTotal = data.total || 0;
                this.docChunksTotalPages = data.total_pages || 1;
            }
        } catch (e) { }

        this.docChunksLoading = false;
        await this.service.render();
    }

    public async onChunkTypeFilterChange(type: string) {
        this.docChunksTypeFilter = this.docChunksTypeFilter === type ? '' : type;
        this.docChunksPage = 1;
        await this.loadDocChunks();
    }

    public async onChunkPageChange(page: number) {
        if (page < 1 || page > this.docChunksTotalPages) return;
        this.docChunksPage = page;
        await this.loadDocChunks();
    }

    public toggleChunkDetail(chunkId: string) {
        this.expandedChunkId = this.expandedChunkId === chunkId ? '' : chunkId;
        this.service.render();
    }

    public truncateText(text: string, maxLen: number = 200): string {
        if (!text) return '';
        return text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
    }

    public async deleteDocument(doc: any) {
        if (this.deletingDocId) return;

        const res = await this.service.modal.show({
            title: '문서 삭제',
            message: `'${doc.filename}' 문서를 삭제하시겠습니까?\n\n📊 ${doc.chunk_count}개 청크가 영구 삭제됩니다.\n\n⚠️ 이 작업은 되돌릴 수 없습니다.`,
            action: '삭제',
            actionBtn: 'error',
            status: 'error'
        });
        if (!res) return;

        this.deletingDocId = doc.doc_id;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("delete_document", {
                collection: this.selectedCollection,
                doc_id: doc.doc_id
            });
            if (code === 200) {
                this.addLog(`🗑️ 문서 삭제: ${doc.filename} (${data.deleted_chunks}개 청크)`, 'success');
                if (this.expandedDocId === doc.doc_id) {
                    this.expandedDocId = '';
                    this.docChunks = [];
                }
                await this.loadDocuments();
                await this.loadCollections();
                await this.loadStats();
                await this.loadChunkTypeStats();
            } else {
                this.addLog(`❌ 문서 삭제 실패: ${data?.message || '알 수 없는 오류'}`, 'error');
            }
        } catch (e: any) {
            this.addLog(`❌ 문서 삭제 오류: ${e.message || '네트워크 오류'}`, 'error');
        }

        this.deletingDocId = '';
        await this.service.render();
    }
}
