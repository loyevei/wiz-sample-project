import math
import json

# ==============================================================================
# 물리 상수
# ==============================================================================
KB = 1.380649e-23       # Boltzmann constant (J/K)
E_CHARGE = 1.602176634e-19   # Elementary charge (C)
ME = 9.1093837015e-31   # Electron mass (kg)
MP = 1.67262192369e-27  # Proton mass (kg)
EPS0 = 8.8541878128e-12 # Vacuum permittivity (F/m)
PI = math.pi

GAS_MASSES = {
    'Ar': 39.948 * MP / 1.67262192369e-27 * 1.66054e-27,
    'N2': 28.014 * 1.66054e-27,
    'O2': 31.998 * 1.66054e-27,
    'He': 4.003 * 1.66054e-27,
    'H2': 2.016 * 1.66054e-27,
    'Air': 28.97 * 1.66054e-27,
}

GAS_CROSS_SECTIONS = {
    'Ar': 2.8e-20, 'N2': 2.5e-20, 'O2': 3.0e-20,
    'He': 1.5e-20, 'H2': 1.0e-20, 'Air': 2.5e-20,
}

PASCHEN_COEFFS = {
    'Ar':  {'A': 12, 'B': 180},
    'N2':  {'A': 12, 'B': 342},
    'O2':  {'A': 8.6, 'B': 275},
    'He':  {'A': 3, 'B': 34},
    'H2':  {'A': 5.1, 'B': 138.8},
    'Air': {'A': 15, 'B': 365},
}

# ==============================================================================
# Unit conversion factors (to SI base)
# ==============================================================================
PRESSURE_TO_PA = {
    'Pa': 1.0, 'mTorr': 0.133322, 'Torr': 133.322,
    'atm': 101325.0, 'bar': 1e5, 'mbar': 100.0, 'psi': 6894.76
}

TEMP_TO_K = {
    'K': lambda x: x,
    '°C': lambda x: x + 273.15,
    'eV': lambda x: x * E_CHARGE / KB,
    'J': lambda x: x / KB,
    'erg': lambda x: x * 1e-7 / KB,
}

K_TO_TEMP = {
    'K': lambda x: x,
    '°C': lambda x: x - 273.15,
    'eV': lambda x: x * KB / E_CHARGE,
    'J': lambda x: x * KB,
    'erg': lambda x: x * KB * 1e7,
}

LENGTH_TO_M = {
    'm': 1.0, 'cm': 1e-2, 'mm': 1e-3,
    'μm': 1e-6, 'nm': 1e-9, 'Å': 1e-10
}

DENSITY_TO_M3 = {
    'm⁻³': 1.0, 'cm⁻³': 1e6
}

FREQ_TO_HZ = {
    'Hz': 1.0, 'kHz': 1e3, 'MHz': 1e6,
    'GHz': 1e9, 'rad/s': 1.0 / (2 * PI)
}


def calculate_plasma():
    Te_eV = float(wiz.request.query("Te", 3))
    ne = float(wiz.request.query("ne", 1e16))
    gas = wiz.request.query("gas", "Ar")
    pressure_mTorr = float(wiz.request.query("pressure", 100))
    B = float(wiz.request.query("B", 0))

    Te_K = Te_eV * E_CHARGE / KB
    Te_J = Te_eV * E_CHARGE
    mi = GAS_MASSES.get(gas, GAS_MASSES['Ar'])
    sigma = GAS_CROSS_SECTIONS.get(gas, 2.8e-20)

    # Gas density from pressure (ideal gas law at room temp)
    pressure_Pa = pressure_mTorr * 0.133322
    ng = pressure_Pa / (KB * 300)  # room temperature

    results = {}

    # Debye length
    if ne > 0:
        lambda_D = math.sqrt(EPS0 * Te_J / (ne * E_CHARGE**2))
        results['debye_length'] = {'label': 'Debye 길이 (λ_D)', 'value': f'{lambda_D:.4e}', 'unit': 'm'}

    # Plasma frequency
    if ne > 0:
        omega_pe = math.sqrt(ne * E_CHARGE**2 / (ME * EPS0))
        f_pe = omega_pe / (2 * PI)
        results['plasma_freq'] = {'label': '플라즈마 주파수 (f_pe)', 'value': f'{f_pe:.4e}', 'unit': 'Hz'}

    # Electron thermal velocity
    v_th = math.sqrt(8 * Te_J / (PI * ME))
    results['thermal_vel'] = {'label': '전자 열속도 (v_th)', 'value': f'{v_th:.4e}', 'unit': 'm/s'}

    # Mean free path
    if ng > 0:
        lambda_mfp = 1.0 / (ng * sigma)
        results['mean_free_path'] = {'label': '평균 자유 경로 (λ_mfp)', 'value': f'{lambda_mfp:.4e}', 'unit': 'm'}

    # Bohm velocity
    v_B = math.sqrt(Te_J / mi)
    results['bohm_vel'] = {'label': 'Bohm 속도 (v_B)', 'value': f'{v_B:.4e}', 'unit': 'm/s'}

    # Ion acoustic speed
    results['ion_acoustic'] = {'label': '이온 음속 (c_s)', 'value': f'{v_B:.4e}', 'unit': 'm/s'}

    # Plasma parameter
    if ne > 0:
        ND = (4/3) * PI * ne * lambda_D**3
        results['plasma_param'] = {'label': '플라즈마 파라미터 (N_D)', 'value': f'{ND:.2e}', 'unit': ''}

    # Electron-neutral collision frequency
    if ng > 0:
        nu_en = ng * sigma * v_th
        results['collision_freq'] = {'label': '전자-중성자 충돌 주파수', 'value': f'{nu_en:.4e}', 'unit': 'Hz'}

    # Larmor radius (if B > 0)
    if B > 0:
        r_Le = ME * v_th / (E_CHARGE * B)
        r_Li = mi * v_B / (E_CHARGE * B)
        results['electron_larmor'] = {'label': '전자 라모어 반경', 'value': f'{r_Le:.4e}', 'unit': 'm'}
        results['ion_larmor'] = {'label': '이온 라모어 반경', 'value': f'{r_Li:.4e}', 'unit': 'm'}
        omega_ce = E_CHARGE * B / ME
        results['cyclotron_freq'] = {'label': '전자 사이클로트론 주파수', 'value': f'{omega_ce:.4e}', 'unit': 'rad/s'}

    wiz.response.status(200, results)


def convert_units():
    value = float(wiz.request.query("value", 1))
    from_unit = wiz.request.query("from_unit", "Pa")
    to_unit = wiz.request.query("to_unit", "mTorr")

    result = None

    # Pressure
    if from_unit in PRESSURE_TO_PA and to_unit in PRESSURE_TO_PA:
        pa = value * PRESSURE_TO_PA[from_unit]
        result = pa / PRESSURE_TO_PA[to_unit]

    # Temperature/Energy
    elif from_unit in TEMP_TO_K and to_unit in K_TO_TEMP:
        k_val = TEMP_TO_K[from_unit](value)
        result = K_TO_TEMP[to_unit](k_val)

    # Length
    elif from_unit in LENGTH_TO_M and to_unit in LENGTH_TO_M:
        m_val = value * LENGTH_TO_M[from_unit]
        result = m_val / LENGTH_TO_M[to_unit]

    # Density
    elif from_unit in DENSITY_TO_M3 and to_unit in DENSITY_TO_M3:
        m3_val = value * DENSITY_TO_M3[from_unit]
        result = m3_val / DENSITY_TO_M3[to_unit]

    # Frequency
    elif from_unit in FREQ_TO_HZ and to_unit in FREQ_TO_HZ:
        hz_val = value * FREQ_TO_HZ[from_unit]
        result = hz_val / FREQ_TO_HZ[to_unit]

    if result is None:
        wiz.response.status(400, message="Unsupported unit conversion")

    wiz.response.status(200, {"result": result})


def paschen_curve():
    gas = wiz.request.query("gas", "Ar")
    pd_min = float(wiz.request.query("pd_min", 0.1))
    pd_max = float(wiz.request.query("pd_max", 1000))
    points = int(wiz.request.query("points", 50))
    gamma = float(wiz.request.query("gamma", 0.01))

    coeffs = PASCHEN_COEFFS.get(gas, PASCHEN_COEFFS['Ar'])
    A = coeffs['A']
    Bc = coeffs['B']

    curve = []
    min_voltage = float('inf')
    min_pd = 0

    for i in range(points):
        if points > 1:
            log_pd = math.log10(pd_min) + (math.log10(pd_max) - math.log10(pd_min)) * i / (points - 1)
            pd = 10 ** log_pd
        else:
            pd = pd_min

        denom = math.log(A * pd) - math.log(math.log(1 + 1.0 / gamma))
        if denom > 0:
            Vb = Bc * pd / denom
            if Vb > 0:
                curve.append({"pd": pd, "voltage": Vb})
                if Vb < min_voltage:
                    min_voltage = Vb
                    min_pd = pd

    # Limit to 30 points for display
    step = max(1, len(curve) // 30)
    display_curve = curve[::step]

    wiz.response.status(200, {
        "curve": display_curve,
        "min_voltage": min_voltage if min_voltage < float('inf') else None,
        "min_pd": min_pd,
        "A": A,
        "B": Bc,
        "gas": gas
    })
