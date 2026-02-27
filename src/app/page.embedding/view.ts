import { OnInit } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit {
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

    // 컬렉션 관리
    public collections: any[] = [];
    public selectedCollection: string = '';
    public newCollectionName: string = '';
    public showCreateCollection: boolean = false;
    public creatingCollection: boolean = false;
    public deletingCollection: string = '';

    // 청킹 옵션
    public showAdvanced: boolean = false;
    public chunkSize: number = 500;
    public chunkOverlap: number = 100;
    public respectSentences: boolean = true;

    // 청킹 전략
    public chunkStrategies: any[] = [];
    public selectedStrategy: string = 'semantic_section';
    public similarityThreshold: number = 0.5;

    // 청크 타입 통계
    public chunkTypeStats: any = {};
    public chunkTypeEntries: any[] = [];
    public chunkTypeStatsLoading: boolean = false;

    // 미리보기
    public previewData: any = null;
    public previewLoading: boolean = false;

    // 통계
    public stats: any = {};
    public statsLoading: boolean = false;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.loadModels();
        await this.loadCollections();
        await this.loadChunkStrategies();
        await this.loadStats();
        await this.loadChunkTypeStats();
        await this.service.render();
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

    public async createCollection() {
        const name = this.newCollectionName.trim();
        if (!name) return;

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
                await this.loadCollections();
                this.selectedCollection = name;
                await this.loadStats();
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
        if (this.deletingCollection) return;

        const collectionInfo = this.collections.find(c => c.name === name);
        const docCount = collectionInfo?.total_docs || 0;
        const chunkCount = collectionInfo?.total_chunks || 0;

        let message = `'${name}' 컬렉션을 삭제하시겠습니까?`;
        if (docCount > 0 || chunkCount > 0) {
            message += `\n\n📊 ${docCount}개 문서, ${chunkCount}개 청크가 영구 삭제됩니다.`;
        }
        message += '\n\n⚠️ 이 작업은 되돌릴 수 없습니다.';

        const res = await this.service.alert.show({
            title: '컬렉션 삭제',
            message: message,
            action: '삭제',
            status: 'error'
        });
        if (!res) return;

        this.deletingCollection = name;
        await this.service.render();

        try {
            const { code, data } = await wiz.call("delete_collection", { collection_name: name });
            if (code === 200) {
                this.addLog(`🗑️ 컬렉션 '${name}' 삭제 완료`, 'success');
                if (this.selectedCollection === name) {
                    this.selectedCollection = '';
                }
                await this.loadCollections();
                if (this.collections.length > 0 && !this.selectedCollection) {
                    this.selectedCollection = this.collections[0].name;
                }
                await this.loadStats();
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
    // 청킹 전략
    // =========================================================================
    public async loadChunkStrategies() {
        try {
            const { code, data } = await wiz.call("chunk_strategies");
            if (code === 200) {
                this.chunkStrategies = data.strategies || [];
            }
        } catch (e) { }
    }

    public onStrategyChange() {
        const strategy = this.chunkStrategies.find(s => s.name === this.selectedStrategy);
        if (strategy) {
            const params = strategy.params || [];
            if (!params.includes('chunk_overlap')) this.chunkOverlap = 0;
            if (!params.includes('respect_sentences')) this.respectSentences = true;
            if (!params.includes('similarity_threshold')) this.similarityThreshold = 0.5;
        }
        this.previewData = null;
    }

    public getStrategyParams(): string[] {
        const strategy = this.chunkStrategies.find(s => s.name === this.selectedStrategy);
        return strategy?.params || ['chunk_size', 'chunk_overlap', 'respect_sentences'];
    }

    public getSelectedStrategyInfo(): any {
        return this.chunkStrategies.find(s => s.name === this.selectedStrategy) || {};
    }

    // =========================================================================
    // 청크 타입 통계
    // =========================================================================
    public async loadChunkTypeStats() {
        if (!this.selectedCollection) return;
        this.chunkTypeStatsLoading = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("chunk_type_stats", {
                collection: this.selectedCollection
            });
            if (code === 200) {
                this.chunkTypeStats = { stats: data.stats || {}, total: data.total || 0 };
                this.chunkTypeEntries = this.buildChunkTypeEntries(data.stats || {}, data.total || 0);
            }
        } catch (e) { }
        this.chunkTypeStatsLoading = false;
        await this.service.render();
    }

    private buildChunkTypeEntries(stats: any, total: number): any[] {
        const colors: any = {
            text: 'bg-blue-500', figure: 'bg-emerald-500', table: 'bg-amber-500',
            formula: 'bg-purple-500', header: 'bg-rose-500', mixed: 'bg-cyan-500'
        };
        const labels: any = {
            text: '텍스트', figure: '그림/OCR', table: '표',
            formula: '수식', header: '헤더', mixed: '혼합'
        };
        return Object.entries(stats).map(([key, count]: [string, any]) => ({
            type: key,
            count: count,
            label: labels[key] || key,
            percent: total > 0 ? Math.round((count / total) * 100) : 0,
            barColor: colors[key] || 'bg-gray-400'
        })).sort((a, b) => b.count - a.count);
    }

    // =========================================================================
    // 미리보기
    // =========================================================================
    public async previewExtract() {
        if (this.selectedFiles.length === 0) {
            this.addLog('⚠️ 미리보기할 PDF 파일을 선택하세요.', 'error');
            return;
        }
        this.previewLoading = true;
        this.previewData = null;
        await this.service.render();

        try {
            const file = this.selectedFiles[0];
            const fd = new FormData();
            fd.append('file', file);
            fd.append('strategy', this.selectedStrategy);
            fd.append('chunk_size', String(this.chunkSize));
            fd.append('chunk_overlap', String(this.chunkOverlap));
            fd.append('respect_sentences', String(this.respectSentences));
            fd.append('similarity_threshold', String(this.similarityThreshold));

            const { code, data } = await wiz.call("preview_extract", fd, {
                contentType: false,
                processData: false
            });

            if (code === 200) {
                this.previewData = data;
                this.addLog(`🔍 미리보기: ${data.total_pages}페이지, ${data.total_chunks}청크, 전략: ${data.strategy_used}`, 'success');
            } else {
                this.addLog(`❌ 미리보기 실패: ${data?.message || '알 수 없는 오류'}`, 'error');
            }
        } catch (e: any) {
            this.addLog(`❌ 미리보기 오류: ${e.message || '네트워크 오류'}`, 'error');
        }

        this.previewLoading = false;
        await this.service.render();
    }

    public getPreviewChunkTypeDist(): any[] {
        if (!this.previewData?.chunk_type_distribution) return [];
        return Object.entries(this.previewData.chunk_type_distribution).map(([key, count]) => ({
            type: key, count: count
        }));
    }

    public getChunkTypeColor(type: string): string {
        const colors: any = {
            text: 'bg-blue-100 text-blue-700', figure: 'bg-emerald-100 text-emerald-700',
            table: 'bg-amber-100 text-amber-700', formula: 'bg-purple-100 text-purple-700',
            header: 'bg-rose-100 text-rose-700', mixed: 'bg-cyan-100 text-cyan-700'
        };
        return colors[type] || 'bg-gray-100 text-gray-700';
    }

    public getChunkTypeLabel(type: string): string {
        const labels: any = {
            text: '텍스트', figure: '그림/OCR', table: '표',
            formula: '수식', header: '헤더', mixed: '혼합'
        };
        return labels[type] || type;
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

                const { code, data } = await wiz.call("upload", fd, {
                    contentType: false,
                    processData: false
                });

                if (code === 200) {
                    let detail = `${data.chunks_count}개 청크 → ${data.vectors_stored}개 벡터`;
                    if (data.figures_detected > 0) detail += `, 그림 ${data.figures_detected}개`;
                    if (data.formulas_detected > 0) detail += `, 수식 ${data.formulas_detected}개`;
                    if (data.tables_detected > 0) detail += `, 표 ${data.tables_detected}개`;
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
        this.previewData = null;

        let summary = `🏁 처리 완료: 성공 ${successCount}개`;
        if (failCount > 0) summary += `, 실패 ${failCount}개`;
        this.addLog(summary, failCount > 0 ? 'error' : 'success');

        await this.loadCollections();
        await this.loadStats();
        await this.loadChunkTypeStats();
        await this.service.render();
    }

    // =========================================================================
    // 통계
    // =========================================================================
    public async loadStats() {
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

    public async onCollectionChange() {
        await this.loadStats();
        const info = this.getSelectedCollectionInfo();
        if (info && info.model) {
            this.selectedModel = info.model;
        }
        await this.loadChunkTypeStats();
        await this.service.render();
    }
}
