import { OnInit, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';

declare const wiz: any;

export class Component implements OnInit, AfterViewChecked {
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
        { id: 'bar', label: '막대 (Bar)' },
        { id: 'scatter', label: '산점도 (Scatter)' },
        { id: 'pie', label: '파이 (Pie)' },
        { id: 'histogram', label: '히스토그램 (Histogram)' },
        { id: 'boxplot', label: '박스 플롯 (Box Plot)' },
        { id: 'heatmap', label: '열지도 (Heatmap)' }
    ];
    public plotterParsed: boolean = false;
    public plotterParsing: boolean = false;
    public chartRendered: boolean = false;
    private needsChartRender: boolean = false;

    @ViewChild('chartCanvas', { static: false }) chartCanvasRef!: ElementRef<HTMLCanvasElement>;

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

    // ===== Chart Colors =====
    private COLORS = [
        '#0891b2', '#7c3aed', '#dc2626', '#16a34a', '#ea580c',
        '#2563eb', '#d946ef', '#0d9488', '#ca8a04', '#6366f1'
    ];

    constructor(public service: Service, private route: ActivatedRoute) { }

    public async ngOnInit() {
        await this.service.init();
        await this.loadDashboard();
        await this.handleQueryParams();
        await this.service.render();
    }

    private async handleQueryParams() {
        const params = this.route.snapshot.queryParams;
        if (!params || Object.keys(params).length === 0) return;

        if (params['tab'] && this.tabs.find((t: any) => t.id === params['tab'])) {
            this.activeTab = params['tab'];
        }

        switch (this.activeTab) {
            case 'plotter':
                if (params['chart_type']) this.plotterChartType = params['chart_type'];
                if (params['csv_data']) {
                    this.plotterCsvInput = params['csv_data'];
                    await this.service.render();
                    await this.parsePlotData();
                }
                break;
            case 'statistics':
                if (params['q']) {
                    this.statsInput = params['q'];
                    await this.service.render();
                    await this.calculateStatistics();
                }
                break;
            case 'fitting':
                if (params['fitting_model']) this.fittingModel = params['fitting_model'];
                if (params['q']) {
                    this.fittingInput = params['q'];
                    await this.service.render();
                    await this.performFitting();
                }
                break;
        }
    }

    public ngAfterViewChecked() {
        if (this.needsChartRender && this.chartCanvasRef) {
            this.needsChartRender = false;
            setTimeout(() => this.renderChart(), 50);
        }
    }

    public async switchTab(tabId: string) {
        this.activeTab = tabId;
        if (tabId === 'dashboard') {
            await this.loadDashboard();
        }
        if (tabId === 'plotter' && this.chartRendered) {
            this.needsChartRender = true;
        }
        await this.service.render();
    }

    // ===== Plotter Methods =====
    public async parsePlotData() {
        this.plotterParsing = true;
        this.chartRendered = false;
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
                this.chartRendered = true;
                this.needsChartRender = true;
                this.addHistory('plotter', `${this.plotterChartType} 차트 렌더링 (${this.plotterRows.length}행, ${this.plotterHeaders.length}열)`);
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
        if (this.chartRendered) {
            this.needsChartRender = true;
        }
    }

    public isYColSelected(col: string): boolean {
        return this.plotterYCols.includes(col);
    }

    public getPlotterDisplayRows(): any[] {
        return this.plotterRows.slice(0, 50);
    }

    public selectXCol(col: string) {
        this.plotterXCol = col;
        if (this.chartRendered) {
            this.needsChartRender = true;
        }
    }

    public onChartTypeChange() {
        if (this.chartRendered) {
            this.needsChartRender = true;
        }
    }

    // ===== Chart Rendering Engine =====
    private renderChart() {
        if (!this.chartCanvasRef || !this.chartCanvasRef.nativeElement) return;
        const canvas = this.chartCanvasRef.nativeElement;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);
        const W = rect.width;
        const H = rect.height;

        // Clear
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, W, H);

        if (this.plotterRows.length === 0) return;

        switch (this.plotterChartType) {
            case 'line': this.drawLineChart(ctx, W, H); break;
            case 'bar': this.drawBarChart(ctx, W, H); break;
            case 'scatter': this.drawScatterChart(ctx, W, H); break;
            case 'pie': this.drawPieChart(ctx, W, H); break;
            case 'histogram': this.drawHistogram(ctx, W, H); break;
            case 'boxplot': this.drawBoxPlot(ctx, W, H); break;
            case 'heatmap': this.drawHeatmap(ctx, W, H); break;
            default: this.drawLineChart(ctx, W, H);
        }
    }

    private getAxisBounds(values: number[]): { min: number, max: number, step: number } {
        if (values.length === 0) return { min: 0, max: 1, step: 0.2 };
        let min = Math.min(...values);
        let max = Math.max(...values);
        if (min === max) { min -= 1; max += 1; }
        const range = max - min;
        const padding = range * 0.1;
        min -= padding; max += padding;
        const rawStep = range / 5;
        const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
        const step = Math.ceil(rawStep / mag) * mag;
        min = Math.floor(min / step) * step;
        max = Math.ceil(max / step) * step;
        return { min, max, step };
    }

    private drawAxes(ctx: CanvasRenderingContext2D, W: number, H: number, pad: any, xBounds: any, yBounds: any, xLabel: string, yLabel: string) {
        ctx.strokeStyle = '#e5e7eb';
        ctx.lineWidth = 1;
        ctx.font = '11px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        // Y-axis gridlines & labels
        const ySteps = Math.round((yBounds.max - yBounds.min) / yBounds.step);
        for (let i = 0; i <= ySteps; i++) {
            const val = yBounds.min + i * yBounds.step;
            const y = pad.top + (1 - (val - yBounds.min) / (yBounds.max - yBounds.min)) * (H - pad.top - pad.bottom);
            ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
            ctx.fillStyle = '#6b7280'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
            ctx.fillText(this.formatAxisLabel(val), pad.left - 8, y);
        }

        // X-axis labels
        const xSteps = Math.min(10, Math.round((xBounds.max - xBounds.min) / xBounds.step));
        for (let i = 0; i <= xSteps; i++) {
            const val = xBounds.min + i * xBounds.step;
            const x = pad.left + ((val - xBounds.min) / (xBounds.max - xBounds.min)) * (W - pad.left - pad.right);
            ctx.beginPath(); ctx.moveTo(x, H - pad.bottom); ctx.lineTo(x, H - pad.bottom + 5); ctx.strokeStyle = '#9ca3af'; ctx.stroke();
            ctx.fillStyle = '#6b7280'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
            ctx.fillText(this.formatAxisLabel(val), x, H - pad.bottom + 8);
        }

        // Axis lines
        ctx.strokeStyle = '#d1d5db'; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, H - pad.bottom); ctx.lineTo(W - pad.right, H - pad.bottom); ctx.stroke();

        // Labels
        ctx.fillStyle = '#374151'; ctx.font = '12px -apple-system, sans-serif';
        ctx.textAlign = 'center'; ctx.textBaseline = 'top';
        ctx.fillText(xLabel, (pad.left + W - pad.right) / 2, H - 12);
        ctx.save(); ctx.translate(14, (pad.top + H - pad.bottom) / 2); ctx.rotate(-Math.PI / 2);
        ctx.textBaseline = 'middle'; ctx.fillText(yLabel, 0, 0); ctx.restore();
    }

    private formatAxisLabel(val: number): string {
        if (Math.abs(val) >= 10000 || (Math.abs(val) < 0.01 && val !== 0)) return val.toExponential(1);
        if (Number.isInteger(val)) return val.toString();
        return val.toPrecision(3);
    }

    private drawLineChart(ctx: CanvasRenderingContext2D, W: number, H: number) {
        const pad = { top: 30, right: 30, bottom: 50, left: 65 };
        const xVals = this.plotterRows.map(r => parseFloat(r[this.plotterXCol]) || 0);
        const allYVals: number[] = [];
        const series: { col: string, vals: number[] }[] = [];
        for (const col of this.plotterYCols) {
            const vals = this.plotterRows.map(r => parseFloat(r[col]) || 0);
            series.push({ col, vals });
            allYVals.push(...vals);
        }
        if (series.length === 0 || xVals.length === 0) return;

        const xBounds = this.getAxisBounds(xVals);
        const yBounds = this.getAxisBounds(allYVals);
        this.drawAxes(ctx, W, H, pad, xBounds, yBounds, this.plotterXCol, this.plotterYCols.join(', '));
        this.drawLegend(ctx, W, pad, series.map(s => s.col));

        const plotW = W - pad.left - pad.right;
        const plotH = H - pad.top - pad.bottom;

        series.forEach((s, si) => {
            const color = this.COLORS[si % this.COLORS.length];
            ctx.strokeStyle = color; ctx.lineWidth = 2.5;
            ctx.beginPath();
            for (let i = 0; i < xVals.length; i++) {
                const x = pad.left + ((xVals[i] - xBounds.min) / (xBounds.max - xBounds.min)) * plotW;
                const y = pad.top + (1 - (s.vals[i] - yBounds.min) / (yBounds.max - yBounds.min)) * plotH;
                if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            ctx.stroke();

            // Data points
            for (let i = 0; i < xVals.length; i++) {
                const x = pad.left + ((xVals[i] - xBounds.min) / (xBounds.max - xBounds.min)) * plotW;
                const y = pad.top + (1 - (s.vals[i] - yBounds.min) / (yBounds.max - yBounds.min)) * plotH;
                ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2);
                ctx.fillStyle = '#fff'; ctx.fill();
                ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.stroke();
            }
        });
    }

    private drawBarChart(ctx: CanvasRenderingContext2D, W: number, H: number) {
        const pad = { top: 30, right: 30, bottom: 50, left: 65 };
        const labels = this.plotterRows.map(r => String(r[this.plotterXCol] || ''));
        const series: { col: string, vals: number[] }[] = [];
        const allYVals: number[] = [0];
        for (const col of this.plotterYCols) {
            const vals = this.plotterRows.map(r => parseFloat(r[col]) || 0);
            series.push({ col, vals });
            allYVals.push(...vals);
        }
        if (series.length === 0) return;

        const yBounds = this.getAxisBounds(allYVals);
        if (yBounds.min > 0) yBounds.min = 0;
        const plotW = W - pad.left - pad.right;
        const plotH = H - pad.top - pad.bottom;
        const n = labels.length;
        const groupW = plotW / n;
        const barW = (groupW * 0.7) / series.length;
        const offset = groupW * 0.15;

        // Y gridlines
        const ySteps = Math.round((yBounds.max - yBounds.min) / yBounds.step);
        ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 1;
        for (let i = 0; i <= ySteps; i++) {
            const val = yBounds.min + i * yBounds.step;
            const y = pad.top + (1 - (val - yBounds.min) / (yBounds.max - yBounds.min)) * plotH;
            ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
            ctx.fillStyle = '#6b7280'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.font = '11px -apple-system, sans-serif';
            ctx.fillText(this.formatAxisLabel(val), pad.left - 8, y);
        }
        ctx.strokeStyle = '#d1d5db'; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, H - pad.bottom); ctx.lineTo(W - pad.right, H - pad.bottom); ctx.stroke();

        // X labels
        ctx.font = '10px -apple-system, sans-serif'; ctx.fillStyle = '#6b7280'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
        labels.forEach((l, i) => {
            const x = pad.left + i * groupW + groupW / 2;
            ctx.fillText(String(l).slice(0, 8), x, H - pad.bottom + 8);
        });

        this.drawLegend(ctx, W, pad, series.map(s => s.col));

        // Bars
        const zeroY = pad.top + (1 - (0 - yBounds.min) / (yBounds.max - yBounds.min)) * plotH;
        series.forEach((s, si) => {
            const color = this.COLORS[si % this.COLORS.length];
            s.vals.forEach((v, i) => {
                const x = pad.left + i * groupW + offset + si * barW;
                const barH = (v / (yBounds.max - yBounds.min)) * plotH;
                const y = zeroY - barH;
                ctx.fillStyle = color;
                ctx.beginPath(); ctx.roundRect(x, Math.min(y, zeroY), barW - 1, Math.abs(barH), [3, 3, 0, 0]); ctx.fill();
            });
        });
    }

    private drawScatterChart(ctx: CanvasRenderingContext2D, W: number, H: number) {
        const pad = { top: 30, right: 30, bottom: 50, left: 65 };
        const xVals = this.plotterRows.map(r => parseFloat(r[this.plotterXCol]) || 0);
        const allYVals: number[] = [];
        const series: { col: string, vals: number[] }[] = [];
        for (const col of this.plotterYCols) {
            const vals = this.plotterRows.map(r => parseFloat(r[col]) || 0);
            series.push({ col, vals });
            allYVals.push(...vals);
        }
        if (series.length === 0) return;

        const xBounds = this.getAxisBounds(xVals);
        const yBounds = this.getAxisBounds(allYVals);
        this.drawAxes(ctx, W, H, pad, xBounds, yBounds, this.plotterXCol, this.plotterYCols.join(', '));
        this.drawLegend(ctx, W, pad, series.map(s => s.col));

        const plotW = W - pad.left - pad.right;
        const plotH = H - pad.top - pad.bottom;

        series.forEach((s, si) => {
            const color = this.COLORS[si % this.COLORS.length];
            for (let i = 0; i < xVals.length; i++) {
                const x = pad.left + ((xVals[i] - xBounds.min) / (xBounds.max - xBounds.min)) * plotW;
                const y = pad.top + (1 - (s.vals[i] - yBounds.min) / (yBounds.max - yBounds.min)) * plotH;
                ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2);
                ctx.fillStyle = this.hexToRgba(color, 0.6); ctx.fill();
                ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
            }
        });
    }

    private drawPieChart(ctx: CanvasRenderingContext2D, W: number, H: number) {
        const col = this.plotterYCols[0] || this.plotterHeaders[1] || this.plotterHeaders[0];
        if (!col) return;
        const vals = this.plotterRows.map(r => Math.abs(parseFloat(r[col]) || 0));
        const labels = this.plotterRows.map(r => String(r[this.plotterXCol] || ''));
        const total = vals.reduce((a, b) => a + b, 0);
        if (total === 0) return;

        const cx = W / 2; const cy = H / 2;
        const radius = Math.min(W, H) / 2 - 60;
        let startAngle = -Math.PI / 2;

        vals.forEach((v, i) => {
            const sliceAngle = (v / total) * Math.PI * 2;
            ctx.beginPath(); ctx.moveTo(cx, cy);
            ctx.arc(cx, cy, radius, startAngle, startAngle + sliceAngle);
            ctx.closePath();
            ctx.fillStyle = this.COLORS[i % this.COLORS.length];
            ctx.fill();
            ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();

            // Label
            const midAngle = startAngle + sliceAngle / 2;
            const lx = cx + (radius * 0.7) * Math.cos(midAngle);
            const ly = cy + (radius * 0.7) * Math.sin(midAngle);
            const pct = ((v / total) * 100).toFixed(1);
            ctx.fillStyle = '#fff'; ctx.font = 'bold 12px -apple-system, sans-serif';
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            if (sliceAngle > 0.3) ctx.fillText(`${pct}%`, lx, ly);

            // External label
            const elx = cx + (radius + 20) * Math.cos(midAngle);
            const ely = cy + (radius + 20) * Math.sin(midAngle);
            ctx.fillStyle = '#374151'; ctx.font = '11px -apple-system, sans-serif';
            ctx.textAlign = midAngle > Math.PI / 2 && midAngle < 3 * Math.PI / 2 ? 'right' : 'left';
            if (sliceAngle > 0.15) ctx.fillText(String(labels[i]).slice(0, 12), elx, ely);

            startAngle += sliceAngle;
        });
    }

    private drawHistogram(ctx: CanvasRenderingContext2D, W: number, H: number) {
        const pad = { top: 30, right: 30, bottom: 50, left: 65 };
        const col = this.plotterYCols[0] || this.plotterHeaders[1] || this.plotterHeaders[0];
        if (!col) return;
        const vals = this.plotterRows.map(r => parseFloat(r[col]) || 0);
        if (vals.length === 0) return;

        const min = Math.min(...vals); const max = Math.max(...vals);
        const binCount = Math.min(20, Math.max(5, Math.ceil(Math.sqrt(vals.length))));
        const binWidth = (max - min) / binCount || 1;
        const bins: number[] = new Array(binCount).fill(0);
        vals.forEach(v => {
            let idx = Math.floor((v - min) / binWidth);
            if (idx >= binCount) idx = binCount - 1;
            if (idx < 0) idx = 0;
            bins[idx]++;
        });
        const maxBin = Math.max(...bins);

        const xBounds = { min, max, step: binWidth };
        const yBounds = this.getAxisBounds([0, maxBin]);
        if (yBounds.min > 0) yBounds.min = 0;

        const plotW = W - pad.left - pad.right;
        const plotH = H - pad.top - pad.bottom;
        const barW = plotW / binCount;

        // Gridlines
        const ySteps = Math.round((yBounds.max - yBounds.min) / yBounds.step);
        ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 1;
        ctx.font = '11px -apple-system, sans-serif';
        for (let i = 0; i <= ySteps; i++) {
            const val = yBounds.min + i * yBounds.step;
            const y = pad.top + (1 - (val - yBounds.min) / (yBounds.max - yBounds.min)) * plotH;
            ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
            ctx.fillStyle = '#6b7280'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
            ctx.fillText(String(Math.round(val)), pad.left - 8, y);
        }
        ctx.strokeStyle = '#d1d5db'; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, H - pad.bottom); ctx.lineTo(W - pad.right, H - pad.bottom); ctx.stroke();

        // X labels
        for (let i = 0; i <= binCount; i += Math.max(1, Math.floor(binCount / 8))) {
            const val = min + i * binWidth;
            const x = pad.left + (i / binCount) * plotW;
            ctx.fillStyle = '#6b7280'; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
            ctx.fillText(this.formatAxisLabel(val), x, H - pad.bottom + 8);
        }

        // Title
        ctx.fillStyle = '#374151'; ctx.font = '12px -apple-system, sans-serif'; ctx.textAlign = 'center';
        ctx.fillText(`${col} 분포`, W / 2, H - 10);

        // Bars
        bins.forEach((count, i) => {
            const x = pad.left + i * barW;
            const barH = (count / (yBounds.max - yBounds.min)) * plotH;
            const y = pad.top + plotH - barH;
            ctx.fillStyle = this.hexToRgba(this.COLORS[0], 0.7);
            ctx.fillRect(x + 1, y, barW - 2, barH);
            ctx.strokeStyle = this.COLORS[0]; ctx.lineWidth = 1;
            ctx.strokeRect(x + 1, y, barW - 2, barH);
            if (count > 0 && barH > 15) {
                ctx.fillStyle = '#fff'; ctx.font = '10px -apple-system, sans-serif';
                ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                ctx.fillText(String(count), x + barW / 2, y + barH / 2);
            }
        });
    }

    private drawBoxPlot(ctx: CanvasRenderingContext2D, W: number, H: number) {
        const pad = { top: 30, right: 30, bottom: 50, left: 65 };
        const series: { col: string, vals: number[] }[] = [];
        const allVals: number[] = [];
        for (const col of this.plotterYCols.length > 0 ? this.plotterYCols : [this.plotterHeaders[1] || this.plotterHeaders[0]]) {
            if (!col) continue;
            const vals = this.plotterRows.map(r => parseFloat(r[col])).filter(v => !isNaN(v)).sort((a, b) => a - b);
            if (vals.length > 0) { series.push({ col, vals }); allVals.push(...vals); }
        }
        if (series.length === 0) return;

        const yBounds = this.getAxisBounds(allVals);
        const plotW = W - pad.left - pad.right;
        const plotH = H - pad.top - pad.bottom;

        // Y axis gridlines
        const ySteps = Math.round((yBounds.max - yBounds.min) / yBounds.step);
        ctx.strokeStyle = '#e5e7eb'; ctx.lineWidth = 1; ctx.font = '11px -apple-system, sans-serif';
        for (let i = 0; i <= ySteps; i++) {
            const val = yBounds.min + i * yBounds.step;
            const y = pad.top + (1 - (val - yBounds.min) / (yBounds.max - yBounds.min)) * plotH;
            ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
            ctx.fillStyle = '#6b7280'; ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
            ctx.fillText(this.formatAxisLabel(val), pad.left - 8, y);
        }
        ctx.strokeStyle = '#d1d5db'; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, H - pad.bottom); ctx.lineTo(W - pad.right, H - pad.bottom); ctx.stroke();

        const boxW = Math.min(80, plotW / series.length * 0.6);
        const gap = plotW / series.length;

        series.forEach((s, si) => {
            const color = this.COLORS[si % this.COLORS.length];
            const vals = s.vals;
            const n = vals.length;
            const q1 = vals[Math.floor(n * 0.25)];
            const median = vals[Math.floor(n * 0.5)];
            const q3 = vals[Math.floor(n * 0.75)];
            const iqr = q3 - q1;
            const whiskerLow = Math.max(vals[0], q1 - 1.5 * iqr);
            const whiskerHigh = Math.min(vals[n - 1], q3 + 1.5 * iqr);

            const cx = pad.left + si * gap + gap / 2;
            const mapY = (v: number) => pad.top + (1 - (v - yBounds.min) / (yBounds.max - yBounds.min)) * plotH;

            // Whiskers
            ctx.strokeStyle = color; ctx.lineWidth = 1.5;
            ctx.beginPath(); ctx.moveTo(cx, mapY(whiskerLow)); ctx.lineTo(cx, mapY(q1)); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(cx, mapY(q3)); ctx.lineTo(cx, mapY(whiskerHigh)); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(cx - boxW / 4, mapY(whiskerLow)); ctx.lineTo(cx + boxW / 4, mapY(whiskerLow)); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(cx - boxW / 4, mapY(whiskerHigh)); ctx.lineTo(cx + boxW / 4, mapY(whiskerHigh)); ctx.stroke();

            // Box
            const boxTop = mapY(q3); const boxBottom = mapY(q1);
            ctx.fillStyle = this.hexToRgba(color, 0.2);
            ctx.fillRect(cx - boxW / 2, boxTop, boxW, boxBottom - boxTop);
            ctx.strokeStyle = color; ctx.lineWidth = 2;
            ctx.strokeRect(cx - boxW / 2, boxTop, boxW, boxBottom - boxTop);

            // Median line
            const medY = mapY(median);
            ctx.strokeStyle = color; ctx.lineWidth = 2.5;
            ctx.beginPath(); ctx.moveTo(cx - boxW / 2, medY); ctx.lineTo(cx + boxW / 2, medY); ctx.stroke();

            // Outliers
            vals.forEach(v => {
                if (v < whiskerLow || v > whiskerHigh) {
                    ctx.beginPath(); ctx.arc(cx, mapY(v), 3, 0, Math.PI * 2);
                    ctx.fillStyle = color; ctx.fill();
                }
            });

            // Label
            ctx.fillStyle = '#374151'; ctx.font = '11px -apple-system, sans-serif';
            ctx.textAlign = 'center'; ctx.textBaseline = 'top';
            ctx.fillText(s.col.slice(0, 10), cx, H - pad.bottom + 8);
        });
    }

    private drawHeatmap(ctx: CanvasRenderingContext2D, W: number, H: number) {
        const pad = { top: 30, right: 60, bottom: 50, left: 65 };
        const numCols = this.plotterHeaders.filter(h => h !== this.plotterXCol);
        if (numCols.length === 0) return;

        const nRows = this.plotterRows.length;
        const nCols = numCols.length;
        const plotW = W - pad.left - pad.right;
        const plotH = H - pad.top - pad.bottom;
        const cellW = plotW / nCols;
        const cellH = plotH / nRows;

        // Find min/max
        let allMin = Infinity, allMax = -Infinity;
        for (const row of this.plotterRows) {
            for (const col of numCols) {
                const v = parseFloat(row[col]);
                if (!isNaN(v)) { allMin = Math.min(allMin, v); allMax = Math.max(allMax, v); }
            }
        }
        if (allMin === allMax) { allMin -= 1; allMax += 1; }

        // Draw cells
        this.plotterRows.forEach((row, ri) => {
            numCols.forEach((col, ci) => {
                const v = parseFloat(row[col]);
                const norm = isNaN(v) ? 0 : (v - allMin) / (allMax - allMin);
                const x = pad.left + ci * cellW;
                const y = pad.top + ri * cellH;
                ctx.fillStyle = this.heatmapColor(norm);
                ctx.fillRect(x, y, cellW - 1, cellH - 1);
                if (cellW > 30 && cellH > 15 && !isNaN(v)) {
                    ctx.fillStyle = norm > 0.5 ? '#fff' : '#000';
                    ctx.font = '10px -apple-system, sans-serif';
                    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                    ctx.fillText(v.toFixed(1), x + cellW / 2, y + cellH / 2);
                }
            });
        });

        // Column labels
        ctx.font = '10px -apple-system, sans-serif'; ctx.fillStyle = '#374151'; ctx.textAlign = 'center';
        numCols.forEach((col, ci) => {
            ctx.save(); const x = pad.left + ci * cellW + cellW / 2; const y = pad.top - 8;
            ctx.fillText(col.slice(0, 8), x, y);
            ctx.restore();
        });

        // Row labels
        ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
        this.plotterRows.forEach((row, ri) => {
            const y = pad.top + ri * cellH + cellH / 2;
            ctx.fillText(String(row[this.plotterXCol] || ri).toString().slice(0, 6), pad.left - 8, y);
        });

        // Color bar
        const barX = W - pad.right + 15; const barW = 15;
        for (let i = 0; i < plotH; i++) {
            const norm = 1 - i / plotH;
            ctx.fillStyle = this.heatmapColor(norm);
            ctx.fillRect(barX, pad.top + i, barW, 1);
        }
        ctx.strokeStyle = '#d1d5db'; ctx.lineWidth = 1;
        ctx.strokeRect(barX, pad.top, barW, plotH);
        ctx.fillStyle = '#6b7280'; ctx.font = '10px -apple-system, sans-serif'; ctx.textAlign = 'left';
        ctx.fillText(this.formatAxisLabel(allMax), barX + barW + 4, pad.top + 5);
        ctx.fillText(this.formatAxisLabel(allMin), barX + barW + 4, H - pad.bottom - 5);
    }

    private heatmapColor(norm: number): string {
        // Blue → Cyan → Green → Yellow → Red
        const r = norm < 0.5 ? Math.round(norm * 2 * 255) : 255;
        const g = norm < 0.5 ? Math.round(128 + norm * 254) : Math.round(255 * (1 - (norm - 0.5) * 2));
        const b = Math.round(255 * (1 - norm));
        return `rgb(${Math.min(255, r)},${Math.min(255, g)},${Math.min(255, b)})`;
    }

    private drawLegend(ctx: CanvasRenderingContext2D, W: number, pad: any, labels: string[]) {
        if (labels.length <= 1) return;
        ctx.font = '11px -apple-system, sans-serif';
        let x = pad.left + 10;
        const y = 12;
        labels.forEach((label, i) => {
            const color = this.COLORS[i % this.COLORS.length];
            ctx.fillStyle = color;
            ctx.fillRect(x, y - 4, 12, 8);
            ctx.fillStyle = '#374151';
            ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
            ctx.fillText(label, x + 16, y);
            x += ctx.measureText(label).width + 30;
        });
    }

    private hexToRgba(hex: string, alpha: number): string {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r},${g},${b},${alpha})`;
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
        const icons: any = { plotter: '📊', statistics: '📈', fitting: '📐', dashboard: '📋' };
        this.analysisHistory.unshift({
            type: type,
            description: description,
            timestamp: now.toLocaleString('ko-KR'),
            icon: icons[type] || '📉'
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
