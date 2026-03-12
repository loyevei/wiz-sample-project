import { OnInit } from '@angular/core';
import { Service } from '@wiz/libs/portal/season/service';

declare const wiz: any;

export class Component implements OnInit {
    public activeTab: string = 'plasma';
    public tabs = [
        { id: 'plasma', label: '플라즈마 계산' },
        { id: 'units', label: '단위 변환' },
        { id: 'constants', label: '물리 상수' },
        { id: 'equations', label: '주요 수식' },
        { id: 'paschen', label: 'Paschen 곡선' },
        { id: 'gasdb', label: '가스 DB' },
        { id: 'equipment', label: '장비 참조' }
    ];

    // ===== Plasma Calculator =====
    public plasmaInputs: any = {
        Te: 3, ne: 1e16, gas: 'Ar', pressure: 100, B: 0
    };
    public plasmaResults: any = null;
    public plasmaCalculating: boolean = false;

    // ===== Unit Converter =====
    public unitCategory: string = 'pressure';
    public unitCategories = [
        { id: 'pressure', label: '압력', units: ['Pa', 'mTorr', 'Torr', 'atm', 'bar', 'mbar', 'psi'] },
        { id: 'temperature', label: '온도/에너지', units: ['eV', 'K', '°C', 'J', 'erg'] },
        { id: 'length', label: '길이', units: ['m', 'cm', 'mm', 'μm', 'nm', 'Å'] },
        { id: 'density', label: '밀도', units: ['m⁻³', 'cm⁻³'] },
        { id: 'frequency', label: '주파수', units: ['Hz', 'kHz', 'MHz', 'GHz', 'rad/s'] }
    ];
    public unitFromVal: number = 1;
    public unitFromUnit: string = 'Pa';
    public unitToUnit: string = 'mTorr';
    public unitResult: number | null = null;

    // ===== Constants =====
    public constantsFilter: string = '';
    public physicalConstants: any[] = [
        { symbol: 'kB', name: 'Boltzmann 상수', value: 1.380649e-23, unit: 'J/K' },
        { symbol: 'e', name: '기본 전하', value: 1.602176634e-19, unit: 'C' },
        { symbol: 'me', name: '전자 질량', value: 9.1093837015e-31, unit: 'kg' },
        { symbol: 'mp', name: '양성자 질량', value: 1.67262192369e-27, unit: 'kg' },
        { symbol: 'ε₀', name: '진공 유전율', value: 8.8541878128e-12, unit: 'F/m' },
        { symbol: 'μ₀', name: '진공 투자율', value: 1.25663706212e-6, unit: 'H/m' },
        { symbol: 'c', name: '광속', value: 2.99792458e8, unit: 'm/s' },
        { symbol: 'h', name: '플랑크 상수', value: 6.62607015e-34, unit: 'J·s' },
        { symbol: 'ℏ', name: '환산 플랑크 상수', value: 1.054571817e-34, unit: 'J·s' },
        { symbol: 'NA', name: '아보가드로 수', value: 6.02214076e23, unit: 'mol⁻¹' },
        { symbol: 'R', name: '기체 상수', value: 8.314462618, unit: 'J/(mol·K)' },
        { symbol: 'σ', name: '슈테판-볼츠만 상수', value: 5.670374419e-8, unit: 'W/(m²·K⁴)' },
        { symbol: 'a₀', name: '보어 반경', value: 5.29177210903e-11, unit: 'm' },
        { symbol: 'Ry', name: '뤼드베리 에너지', value: 13.605693122994, unit: 'eV' },
        { symbol: 'mAr', name: 'Ar 원자 질량', value: 6.6335209e-26, unit: 'kg' }
    ];

    // ===== Paschen =====
    public paschenGas: string = 'Ar';
    public paschenPdMin: number = 0.1;
    public paschenPdMax: number = 1000;
    public paschenPoints: number = 100;
    public paschenGamma: number = 0.01;
    public paschenResult: any = null;
    public paschenCalculating: boolean = false;

    // ===== Gas DB =====
    public gasFilter: string = '';
    public gasData: any[] = [
        { name: 'Argon (Ar)', formula: 'Ar', mass: 39.948, ionE: 15.76, crossSection: 2.8e-20, type: '불활성', color: 'purple', uses: '스퍼터링, 이온밀링, 플라즈마 세정' },
        { name: 'Nitrogen (N₂)', formula: 'N₂', mass: 28.014, ionE: 15.58, crossSection: 2.5e-20, type: '반응성', color: 'blue', uses: '질화, 표면처리, 캐리어 가스' },
        { name: 'Oxygen (O₂)', formula: 'O₂', mass: 31.998, ionE: 12.07, crossSection: 3.0e-20, type: '반응성', color: 'red', uses: '산화, 애싱, RIE 에칭' },
        { name: 'CF₄', formula: 'CF₄', mass: 88.004, ionE: 15.9, crossSection: 4.5e-20, type: '반응성', color: 'green', uses: 'Si/SiO₂ 에칭' },
        { name: 'SF₆', formula: 'SF₆', mass: 146.06, ionE: 15.3, crossSection: 5.2e-20, type: '반응성', color: 'teal', uses: 'Si 등방 에칭, DRIE' },
        { name: 'Cl₂', formula: 'Cl₂', mass: 70.906, ionE: 11.48, crossSection: 3.5e-20, type: '반응성', color: 'yellow', uses: 'III-V 반도체 에칭, 금속 에칭' },
        { name: 'H₂', formula: 'H₂', mass: 2.016, ionE: 15.43, crossSection: 1.0e-20, type: '환원성', color: 'pink', uses: '환원, 다이아몬드 CVD' },
        { name: 'He', formula: 'He', mass: 4.003, ionE: 24.59, crossSection: 1.5e-20, type: '불활성', color: 'gray', uses: '냉각, 누설 검지' },
        { name: 'CHF₃', formula: 'CHF₃', mass: 70.014, ionE: 13.86, crossSection: 4.0e-20, type: '반응성', color: 'indigo', uses: 'SiO₂ 선택적 에칭' },
        { name: 'C₄F₈', formula: 'C₄F₈', mass: 200.03, ionE: 13.38, crossSection: 6.0e-20, type: '반응성', color: 'emerald', uses: 'DRIE 패시베이션' },
        { name: 'NF₃', formula: 'NF₃', mass: 71.002, ionE: 13.0, crossSection: 3.8e-20, type: '반응성', color: 'orange', uses: '챔버 세정, CVD 세정' },
        { name: 'SiH₄', formula: 'SiH₄', mass: 32.117, ionE: 11.0, crossSection: 3.2e-20, type: '전구체', color: 'amber', uses: 'Si, SiNx, SiO₂ CVD' }
    ];

    // ===== Equipment =====
    public equipFilter: string = '';
    public equipmentData: any[] = [
        { name: 'CCP (용량결합 플라즈마)', type: 'Source', freqRange: '13.56 MHz', pressureRange: '10 mTorr ~ 10 Torr', densityRange: '10⁹~10¹¹ cm⁻³', apps: 'RIE, PECVD, 스퍼터링' },
        { name: 'ICP (유도결합 플라즈마)', type: 'Source', freqRange: '13.56 MHz', pressureRange: '1~100 mTorr', densityRange: '10¹¹~10¹² cm⁻³', apps: '고밀도 에칭, 이온 소스' },
        { name: 'Helicon', type: 'Source', freqRange: '1~30 MHz', pressureRange: '0.1~10 mTorr', densityRange: '10¹²~10¹³ cm⁻³', apps: '이온빔, 추진기' },
        { name: 'ECR (전자 사이클로트론 공명)', type: 'Source', freqRange: '2.45 GHz', pressureRange: '0.1~10 mTorr', densityRange: '10¹¹~10¹² cm⁻³', apps: 'CVD, 에칭, 이온 소스' },
        { name: 'MW (마이크로파)', type: 'Source', freqRange: '2.45 GHz', pressureRange: '10~760 Torr', densityRange: '10¹¹~10¹³ cm⁻³', apps: '대기압 플라즈마, 다이아몬드 CVD' },
        { name: 'DC Magnetron', type: 'Sputter', freqRange: 'DC', pressureRange: '1~30 mTorr', densityRange: '10¹⁰~10¹¹ cm⁻³', apps: '금속 박막 증착' },
        { name: 'RF Magnetron', type: 'Sputter', freqRange: '13.56 MHz', pressureRange: '1~30 mTorr', densityRange: '10¹⁰~10¹¹ cm⁻³', apps: '절연체 박막 증착' },
        { name: 'HiPIMS', type: 'Sputter', freqRange: 'Pulsed DC', pressureRange: '1~30 mTorr', densityRange: '10¹²~10¹³ cm⁻³', apps: '고밀도 박막, 초경합금' }
    ];

    constructor(public service: Service) { }

    public async ngOnInit() {
        await this.service.init();
        await this.service.render();
    }

    public async switchTab(tabId: string) {
        this.activeTab = tabId;
        await this.service.render();
    }

    // ===== Plasma Calculator =====
    public async calculatePlasma() {
        this.plasmaCalculating = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("calculate_plasma", this.plasmaInputs);
            if (code === 200) this.plasmaResults = data;
        } catch (e) { }
        this.plasmaCalculating = false;
        await this.service.render();
    }

    // ===== Unit Converter =====
    public async convertUnit() {
        try {
            const { code, data } = await wiz.call("convert_units", {
                value: this.unitFromVal, from_unit: this.unitFromUnit, to_unit: this.unitToUnit
            });
            if (code === 200) this.unitResult = data.result;
        } catch (e) { }
        await this.service.render();
    }

    public getUnitsForCategory(): string[] {
        const cat = this.unitCategories.find(c => c.id === this.unitCategory);
        return cat ? cat.units : [];
    }

    public onCategoryChange() {
        const units = this.getUnitsForCategory();
        this.unitFromUnit = units[0] || '';
        this.unitToUnit = units[1] || units[0] || '';
        this.unitResult = null;
    }

    // ===== Paschen =====
    public async calculatePaschen() {
        this.paschenCalculating = true;
        await this.service.render();
        try {
            const { code, data } = await wiz.call("paschen_curve", {
                gas: this.paschenGas, pd_min: this.paschenPdMin, pd_max: this.paschenPdMax,
                points: this.paschenPoints, gamma: this.paschenGamma
            });
            if (code === 200) this.paschenResult = data;
        } catch (e) { }
        this.paschenCalculating = false;
        await this.service.render();
    }

    // ===== Filters =====
    public filteredConstants() {
        if (!this.constantsFilter) return this.physicalConstants;
        const f = this.constantsFilter.toLowerCase();
        return this.physicalConstants.filter(c =>
            c.name.toLowerCase().includes(f) || c.symbol.toLowerCase().includes(f)
        );
    }

    public filteredGases() {
        if (!this.gasFilter) return this.gasData;
        const f = this.gasFilter.toLowerCase();
        return this.gasData.filter(g =>
            g.name.toLowerCase().includes(f) || g.formula.toLowerCase().includes(f) || g.uses.toLowerCase().includes(f)
        );
    }

    public filteredEquipment() {
        if (!this.equipFilter) return this.equipmentData;
        const f = this.equipFilter.toLowerCase();
        return this.equipmentData.filter(eq =>
            eq.name.toLowerCase().includes(f) || eq.type.toLowerCase().includes(f) || eq.apps.toLowerCase().includes(f)
        );
    }

    public formatSci(val: number): string {
        if (val === 0) return '0';
        if (Math.abs(val) >= 0.01 && Math.abs(val) < 10000) return val.toPrecision(4);
        return val.toExponential(3);
    }
}
