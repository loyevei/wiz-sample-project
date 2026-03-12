import { OnInit } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

declare const wiz: any;

export class Component implements OnInit {
    public activeTab: string = 'plotter';
    public tabs = [
        { id: 'plotter', label: '데이터 플로터' },
        { id: 'statistics', label: '통계 분석' },
        { id: 'fitting', label: '커브 피팅' },
        { id: 'dashboard', label: '대시보드' }
    ];

    // ===== Plotter =====
    public plotterCsvInput: string = 'x,y1,y2\n0,0,0\n1,2,1\n2,4,4\n3,6,9\n4,8,16\n5,10,25';
    public plotterHeaders: string[] = [];
    public plotterRows: any[] = [];
    public plotterXCol: string = '';
    public plotterYCols: string[] = [];
    public plotterChartType: string = 'line';
    public plotterChartTypes = [
        { id: 'line', label: '꺾은선 (Line)' },
        { id: 'scatter', label: '산점도 (Scatter)' },
        { id: 'bar', label: '막대 (Bar)' }
    ];
    public plotterParsed: boolean = false;
    public plotterParsing: boolean = false;

    // ===== Statistics =====
    public statsInput: string = '12.5, 14.3, 11.8, 15.1, 13.7, 12.9, 16.2, 14.8, 13.1, 15.5\n10.2, 11.5, 9.8, 12.3, 10.7, 11.1, 13.0, 12.1, 10.5, 11.8';
    public statsResults: any[] = [];
    public statsCalculating: boolean = false;

    // ===== Curve Fitting =====
    public fittingInput: string = '0, 0.1\n1, 2.1\n2, 3.9\n3, 6.2\n4, 7.8\n5, 10.1\n6, 12.3\n7, 13.9\n8, 16.1\n9, 18.0\n10, 20.2';
    public fittingModel: string = 'linear';
    public fittingModels = [
        { id: 'linear', label: '선형 (Linear)', eq: 'y = ax + b' },
        { id: 'quadratic', label: '2차 (Quadratic)', eq: 'y = ax² + bx + c' },
        { id: 'exponential', label: '지수 (Exponential)', eq: 'y = a·exp(bx)' },
        { id: 'power', label: '거듭제곱 (Power)', eq: 'y = a·x^b' },
        { id: 'gaussian', label: '가우시안 (Gaussian)', eq: 'y = a·exp(-(x-μ)²/2σ²)' }
    ];
    public fittingResult: any = null;
    public fittingCalculating: boolean = false;

    // ===== Dashboard =====
    public dashboardStats: any = null;
    public analysisHistory: any[] = [];
    public dashboardLoading: boolean = false;

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.loadDashboard();
        await this.service.render();
    }

    public async switchTab(tabId: string) {
        this.activeTab = tabId;
        if (tabId === 'dashboard') {
            await this.loadDashboard();
        }
        await this.service.render();
    }

    // ===== Plotter Methods =====
    public async parsePlotData() {
        this.plotterParsing = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("parse_data", { csv_text: this.plotterCsvInput });
            if (code === 200) {
                this.plotterHeaders = data.headers || [];
                this.plotterRows = data.rows || [];
                this.plotterParsed = true;
                if (this.plotterHeaders.length > 0) {
                    this.plotterXCol = this.plotterHeaders[0];
                }
                if (this.plotterHeaders.length > 1) {
                    this.plotterYCols = [this.plotterHeaders[1]];
                }
            }
        } catch (e) { }
        this.plotterParsing = false;
        await this.service.render();
    }

    public toggleYCol(col: string) {
        const idx = this.plotterYCols.indexOf(col);
        if (idx >= 0) {
            this.plotterYCols.splice(idx, 1);
        } else {
            this.plotterYCols.push(col);
        }
    }

    public isYColSelected(col: string): boolean {
        return this.plotterYCols.includes(col);
    }

    public getPlotterDisplayRows(): any[] {
        return this.plotterRows.slice(0, 50);
    }

    // ===== Statistics Methods =====
    public async calculateStatistics() {
        this.statsCalculating = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("statistics", { data_text: this.statsInput });
            if (code === 200) {
                this.statsResults = data.results || [];
                this.addHistory('statistics', `${this.statsResults.length}개 데이터셋 통계 분석 완료`);
            }
        } catch (e) { }
        this.statsCalculating = false;
        await this.service.render();
    }

    // ===== Curve Fitting Methods =====
    public selectFittingModel(modelId: string) {
        this.fittingModel = modelId;
        this.fittingResult = null;
    }

    public getSelectedModelInfo(): any {
        return this.fittingModels.find(m => m.id === this.fittingModel);
    }

    public async performFitting() {
        this.fittingCalculating = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("curve_fit", {
                data_text: this.fittingInput,
                model: this.fittingModel
            });
            if (code === 200) {
                this.fittingResult = data;
                this.addHistory('fitting', `${this.fittingModel} 모델 커브 피팅 완료 (R²=${data.r_squared?.toFixed(4)})`);
            }
        } catch (e) { }
        this.fittingCalculating = false;
        await this.service.render();
    }

    // ===== Dashboard Methods =====
    public async loadDashboard() {
        this.dashboardLoading = true;
        try {
            const { code, data } = await wiz.call("dashboard_stats");
            if (code === 200) {
                this.dashboardStats = data;
            }
        } catch (e) { }
        this.dashboardLoading = false;
    }

    private addHistory(type: string, description: string) {
        const now = new Date();
        this.analysisHistory.unshift({
            type: type,
            description: description,
            timestamp: now.toLocaleString('ko-KR'),
            icon: type === 'statistics' ? '📊' : type === 'fitting' ? '📈' : '📉'
        });
        if (this.analysisHistory.length > 20) {
            this.analysisHistory = this.analysisHistory.slice(0, 20);
        }
    }

    // ===== Utility =====
    public formatSci(val: number): string {
        if (val === null || val === undefined) return '-';
        if (val === 0) return '0';
        if (Math.abs(val) >= 0.01 && Math.abs(val) < 10000) return val.toPrecision(6);
        return val.toExponential(4);
    }

    public objectKeys(obj: any): string[] {
        return obj ? Object.keys(obj) : [];
    }
}
