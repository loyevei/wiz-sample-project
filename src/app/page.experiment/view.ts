import { OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';

declare const wiz: any;

export class Component implements OnInit {
    public activeTab: string = 'doe';
    public tabs = [
        { id: 'doe', label: 'DOE 실험 설계' },
        { id: 'notebook', label: '실험 노트' },
        { id: 'recipe', label: '레시피 관리' }
    ];

    // ===== DOE (Design of Experiments) =====
    public factors: any[] = [
        { name: '', min: 0, max: 100, levels: 3 }
    ];
    public doeMatrix: any[] = [];
    public doeResults: any[] = [];
    public doeGenerating: boolean = false;

    // ===== Notebook =====
    public notes: any[] = [];
    public noteSearch: string = '';
    public showNoteForm: boolean = false;
    public editingNote: any = null;
    public noteGenerating: boolean = false;
    public noteForm: any = {
        title: '',
        date: '',
        content: '',
        tags: '',
        source_type: 'manual',
        source_ref: '',
        auto_generated: false
    };

    // ===== Recipe =====
    public recipes: any[] = [];
    public recipeSearch: string = '';
    public showRecipeForm: boolean = false;
    public editingRecipe: any = null;
    public recipeForm: any = {
        name: '',
        gas: 'Ar',
        pressure: 100,
        power: 300,
        temperature: 25,
        time: 60,
        description: ''
    };

    constructor(public service: Service, private route: ActivatedRoute) { }

    public async ngOnInit() {
        await this.service.init();
        await this.loadNotes();
        await this.loadRecipes();
        this.noteForm.date = new Date().toISOString().split('T')[0];
        await this.handleQueryParams();
        await this.service.render();
    }

    private async handleQueryParams() {
        const params = this.route.snapshot.queryParams;
        if (!params || Object.keys(params).length === 0) return;

        if (params['tab'] && this.tabs.find((t: any) => t.id === params['tab'])) {
            this.activeTab = params['tab'];
        }

        const q = params['q'] || '';

        switch (this.activeTab) {
            case 'notebook':
                if (q) this.noteSearch = q;
                break;
            case 'recipe':
                if (q) this.recipeSearch = q;
                // Pre-fill recipe params from navigate_to_page
                if (params['gas']) this.recipeForm.gas = params['gas'];
                if (params['pressure']) this.recipeForm.pressure = parseFloat(params['pressure']);
                if (params['power']) this.recipeForm.power = parseFloat(params['power']);
                if (params['temperature']) this.recipeForm.temperature = parseFloat(params['temperature']);
                if (params['time']) this.recipeForm.time = parseFloat(params['time']);
                break;
        }
    }

    public async switchTab(tabId: string) {
        this.activeTab = tabId;
        await this.service.render();
    }

    // ===== DOE Methods =====
    public addFactor() {
        this.factors.push({ name: '', min: 0, max: 100, levels: 3 });
        this.service.render();
    }

    public removeFactor(index: number) {
        if (this.factors.length > 1) {
            this.factors.splice(index, 1);
            this.service.render();
        }
    }

    public async generateDOE() {
        const validFactors = this.factors.filter(f => f.name && f.name.trim() !== '');
        if (validFactors.length === 0) return;

        this.doeGenerating = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("generate_doe", {
                factors: JSON.stringify(validFactors)
            });
            if (code === 200) {
                this.doeMatrix = data.matrix || [];
                this.doeResults = data.matrix ? data.matrix.map(() => '') : [];
            }
        } catch (e) { }
        this.doeGenerating = false;
        await this.service.render();
    }

    public getFactorNames(): string[] {
        return this.factors.filter(f => f.name && f.name.trim() !== '').map(f => f.name);
    }

    // ===== Notebook Methods =====
    public async loadNotes() {
        try {
            const { code, data } = await wiz.call("list_notes");
            if (code === 200) this.notes = data || [];
        } catch (e) { }
    }

    public filteredNotes() {
        if (!this.noteSearch) return this.notes;
        const f = this.noteSearch.toLowerCase();
        return this.notes.filter(n =>
            n.title.toLowerCase().includes(f) ||
            (n.tags || '').toLowerCase().includes(f) ||
            (n.content || '').toLowerCase().includes(f)
        );
    }

    public openNoteForm(note?: any) {
        if (note) {
            this.editingNote = note;
            this.noteForm = {
                title: note.title,
                date: note.date,
                content: note.content,
                tags: note.tags || '',
                source_type: note.source_type || 'manual',
                source_ref: note.source_ref || '',
                auto_generated: !!note.auto_generated
            };
        } else {
            this.editingNote = null;
            this.noteForm = {
                title: '',
                date: new Date().toISOString().split('T')[0],
                content: '',
                tags: '',
                source_type: 'manual',
                source_ref: '',
                auto_generated: false
            };
        }
        this.showNoteForm = true;
        this.service.render();
    }

    public cancelNoteForm() {
        this.showNoteForm = false;
        this.editingNote = null;
        this.service.render();
    }

    public async saveNote() {
        if (!this.noteForm.title.trim()) return;
        try {
            const payload: any = { ...this.noteForm };
            if (this.editingNote) payload.id = this.editingNote.id;
            const { code } = await wiz.call("save_note", payload);
            if (code === 200) {
                this.showNoteForm = false;
                this.editingNote = null;
                await this.loadNotes();
            }
        } catch (e) { }
        await this.service.render();
    }

    public async deleteNote(noteId: string) {
        if (!confirm('이 노트를 삭제하시겠습니까?')) return;
        try {
            const { code } = await wiz.call("delete_note", { id: noteId });
            if (code === 200) await this.loadNotes();
        } catch (e) { }
        await this.service.render();
    }

    public async generateNoteDraft() {
        this.noteGenerating = true;
        await this.service.render();
        try {
            const selectedRecipe = this.editingRecipe || this.recipes[0] || {};
            const { code, data } = await wiz.call("generate_note_template", {
                title: this.noteForm.title,
                context: JSON.stringify({
                    factors: this.factors,
                    doeMatrix: this.doeMatrix,
                    recipes: this.recipes,
                    selectedRecipe: selectedRecipe,
                    collection: ''
                })
            });
            if (code === 200) {
                this.showNoteForm = true;
                this.noteForm = {
                    ...this.noteForm,
                    title: data.title || this.noteForm.title,
                    date: data.date || this.noteForm.date,
                    content: data.content || this.noteForm.content,
                    tags: data.tags || this.noteForm.tags,
                    source_type: 'auto-template',
                    source_ref: selectedRecipe?.id || '',
                    auto_generated: true
                };
            }
        } catch (e) { }
        this.noteGenerating = false;
        await this.service.render();
    }

    public openDatasetPage() {
        this.service.href('/experiment/dataset');
    }

    // ===== Recipe Methods =====
    public async loadRecipes() {
        try {
            const { code, data } = await wiz.call("list_recipes");
            if (code === 200) this.recipes = data || [];
        } catch (e) { }
    }

    public filteredRecipes() {
        if (!this.recipeSearch) return this.recipes;
        const f = this.recipeSearch.toLowerCase();
        return this.recipes.filter(r =>
            r.name.toLowerCase().includes(f) ||
            (r.gas || '').toLowerCase().includes(f) ||
            (r.description || '').toLowerCase().includes(f)
        );
    }

    public openRecipeForm(recipe?: any) {
        if (recipe) {
            this.editingRecipe = recipe;
            this.recipeForm = {
                name: recipe.name,
                gas: recipe.gas || 'Ar',
                pressure: recipe.pressure || 100,
                power: recipe.power || 300,
                temperature: recipe.temperature || 25,
                time: recipe.time || 60,
                description: recipe.description || ''
            };
        } else {
            this.editingRecipe = null;
            this.recipeForm = {
                name: '',
                gas: 'Ar',
                pressure: 100,
                power: 300,
                temperature: 25,
                time: 60,
                description: ''
            };
        }
        this.showRecipeForm = true;
        this.service.render();
    }

    public cancelRecipeForm() {
        this.showRecipeForm = false;
        this.editingRecipe = null;
        this.service.render();
    }

    public async saveRecipe() {
        if (!this.recipeForm.name.trim()) return;
        try {
            const payload: any = { ...this.recipeForm };
            if (this.editingRecipe) payload.id = this.editingRecipe.id;
            const { code } = await wiz.call("save_recipe", payload);
            if (code === 200) {
                this.showRecipeForm = false;
                this.editingRecipe = null;
                await this.loadRecipes();
            }
        } catch (e) { }
        await this.service.render();
    }

    public async deleteRecipe(recipeId: string) {
        if (!confirm('이 레시피를 삭제하시겠습니까?')) return;
        try {
            const { code } = await wiz.call("delete_recipe", { id: recipeId });
            if (code === 200) await this.loadRecipes();
        } catch (e) { }
        await this.service.render();
    }

    public formatDate(dateStr: string): string {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
    }
}
