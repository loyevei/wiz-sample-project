import { OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';

declare const wiz: any;

export class Component implements OnInit {
    public records: any[] = [];
    public projects: any[] = [];
    public collections: any[] = [];
    public searchText: string = '';
    public selectedProjectFilter: string = '';
    public selectedCollectionFilter: string = '';
    public showForm: boolean = false;
    public editingRecord: any = null;
    public form: any = {
        title: '',
        project_id: '',
        collection: '',
        source_type: 'manual',
        notes: '',
        tags: '',
        conditionsText: '',
        outcomesText: '',
        evidenceText: ''
    };

    constructor(public service: Service, private route: ActivatedRoute) { }

    public async ngOnInit() {
        await this.service.init();
        await this.loadProjects();
        await this.loadCollections();
        await this.loadRecords();
        await this.handleQueryParams();
        await this.service.render();
    }

    private async handleQueryParams() {
        const params = this.route.snapshot.queryParams;
        if (!params || Object.keys(params).length === 0) return;
        if (params['project']) this.selectedProjectFilter = params['project'];
        if (params['collection']) {
            this.selectedCollectionFilter = params['collection'];
            this.form.collection = params['collection'];
        }
        if (params['title']) this.form.title = params['title'];
    }

    public async loadRecords() {
        try {
            const { code, data } = await wiz.call('list_records');
            if (code === 200) this.records = data || [];
        } catch (e) { }
    }

    public async loadProjects() {
        try {
            const { code, data } = await wiz.call('list_projects');
            if (code === 200) this.projects = data || [];
        } catch (e) { }
    }

    public async loadCollections() {
        try {
            const { code, data } = await wiz.call('list_collections');
            if (code === 200) this.collections = data || [];
        } catch (e) { }
    }

    public filteredRecords() {
        const keyword = this.searchText.toLowerCase();
        return this.records.filter((record: any) => {
            if (this.selectedProjectFilter && record.project_id !== this.selectedProjectFilter) return false;
            if (this.selectedCollectionFilter && record.collection !== this.selectedCollectionFilter) return false;
            if (!keyword) return true;
            return [record.title, record.notes, record.tags, record.collection]
                .filter(Boolean)
                .some((value: string) => String(value).toLowerCase().includes(keyword));
        });
    }

    public openForm(record?: any) {
        if (record) {
            this.editingRecord = record;
            this.form = {
                title: record.title || '',
                project_id: record.project_id || '',
                collection: record.collection || '',
                source_type: record.source_type || 'manual',
                notes: record.notes || '',
                tags: record.tags || '',
                conditionsText: this.stringifyPairs(record.conditions || []),
                outcomesText: this.stringifyPairs(record.outcomes || []),
                evidenceText: JSON.stringify(record.evidence_refs || [], null, 2)
            };
        } else {
            this.editingRecord = null;
            this.form = {
                title: '',
                project_id: this.selectedProjectFilter || '',
                collection: this.selectedCollectionFilter || '',
                source_type: 'manual',
                notes: '',
                tags: '',
                conditionsText: '[\n  {"name": "pressure", "value": "100 mTorr"}\n]',
                outcomesText: '[\n  {"name": "etch_rate", "value": "120 nm/min"}\n]',
                evidenceText: '[]'
            };
        }
        this.showForm = true;
        this.service.render();
    }

    public cancelForm() {
        this.showForm = false;
        this.editingRecord = null;
        this.service.render();
    }

    public async saveRecord() {
        if (!this.form.title.trim()) return;
        try {
            const payload: any = {
                title: this.form.title,
                project_id: this.form.project_id,
                collection: this.form.collection,
                source_type: this.form.source_type,
                notes: this.form.notes,
                tags: this.form.tags,
                conditions: this.form.conditionsText,
                outcomes: this.form.outcomesText,
                evidence_refs: this.form.evidenceText
            };
            if (this.editingRecord) payload.id = this.editingRecord.id;
            const { code } = await wiz.call('save_record', payload);
            if (code === 200) {
                this.showForm = false;
                this.editingRecord = null;
                await this.loadRecords();
            }
        } catch (e) { }
        await this.service.render();
    }

    public async deleteRecord(recordId: string) {
        if (!confirm('이 데이터셋 레코드를 삭제하시겠습니까?')) return;
        try {
            const { code } = await wiz.call('delete_record', { id: recordId });
            if (code === 200) await this.loadRecords();
        } catch (e) { }
        await this.service.render();
    }

    public getProjectName(projectId: string): string {
        const project = this.projects.find((item: any) => item.id === projectId);
        return project?.name || '-';
    }

    public formatDate(dateStr: string): string {
        if (!dateStr) return '';
        return new Date(dateStr).toLocaleString('ko-KR', {
            year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
        });
    }

    private stringifyPairs(items: any[]): string {
        return JSON.stringify(items || [], null, 2);
    }
}
