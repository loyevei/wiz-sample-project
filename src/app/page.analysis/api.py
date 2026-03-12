import math
import json

# ==============================================================================
# 데이터 분석 API
# ==============================================================================

def parse_data():
    """CSV 텍스트 데이터를 파싱하여 헤더와 행을 반환"""
    csv_text = wiz.request.query("csv_text", "")
    if not csv_text.strip():
        wiz.response.status(400, message="데이터가 비어 있습니다.")

    lines = [line.strip() for line in csv_text.strip().split('\n') if line.strip()]
    if len(lines) < 2:
        wiz.response.status(400, message="최소 헤더 1행 + 데이터 1행이 필요합니다.")

    # Detect delimiter
    header_line = lines[0]
    if '\t' in header_line:
        delimiter = '\t'
    else:
        delimiter = ','

    headers = [h.strip() for h in header_line.split(delimiter)]
    rows = []
    for line in lines[1:]:
        vals = [v.strip() for v in line.split(delimiter)]
        row = {}
        for i, h in enumerate(headers):
            if i < len(vals):
                try:
                    row[h] = float(vals[i])
                except ValueError:
                    row[h] = vals[i]
            else:
                row[h] = None
        rows.append(row)

    wiz.response.status(200, {"headers": headers, "rows": rows, "count": len(rows)})


def statistics():
    """기술 통계량 계산 (mean, std, median, min, max, variance, skewness, kurtosis)"""
    import numpy as np

    data_text = wiz.request.query("data_text", "")
    if not data_text.strip():
        wiz.response.status(400, message="데이터가 비어 있습니다.")

    results = []
    lines = [line.strip() for line in data_text.strip().split('\n') if line.strip()]

    for idx, line in enumerate(lines):
        try:
            values = [float(v.strip()) for v in line.split(',') if v.strip()]
        except ValueError:
            continue

        if len(values) < 2:
            continue

        arr = np.array(values)
        n = len(arr)
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        median_val = float(np.median(arr))
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))
        variance_val = float(np.var(arr, ddof=1)) if n > 1 else 0.0

        # Skewness (Fisher's definition)
        if n > 2 and std_val > 0:
            skewness_val = float(np.mean(((arr - mean_val) / (np.std(arr, ddof=0))) ** 3))
            skewness_val = skewness_val * (n * (n - 1)) ** 0.5 / (n - 2) if n > 2 else skewness_val
        else:
            skewness_val = 0.0

        # Kurtosis (excess kurtosis)
        if n > 3 and std_val > 0:
            kurtosis_val = float(np.mean(((arr - mean_val) / (np.std(arr, ddof=0))) ** 4)) - 3.0
        else:
            kurtosis_val = 0.0

        results.append({
            "dataset": idx + 1,
            "count": n,
            "mean": mean_val,
            "std": std_val,
            "median": median_val,
            "min": min_val,
            "max": max_val,
            "variance": variance_val,
            "skewness": round(skewness_val, 6),
            "kurtosis": round(kurtosis_val, 6),
            "sum": float(np.sum(arr)),
            "range": float(max_val - min_val)
        })

    if len(results) == 0:
        wiz.response.status(400, message="유효한 숫자 데이터가 없습니다.")

    wiz.response.status(200, {"results": results})


def curve_fit():
    """커브 피팅: 다양한 모델로 X,Y 데이터 피팅"""
    import numpy as np

    data_text = wiz.request.query("data_text", "")
    model = wiz.request.query("model", "linear")

    if not data_text.strip():
        wiz.response.status(400, message="데이터가 비어 있습니다.")

    # Parse X, Y data
    x_vals = []
    y_vals = []
    lines = [line.strip() for line in data_text.strip().split('\n') if line.strip()]
    for line in lines:
        parts = [p.strip() for p in line.split(',')]
        if len(parts) >= 2:
            try:
                x_vals.append(float(parts[0]))
                y_vals.append(float(parts[1]))
            except ValueError:
                continue

    if len(x_vals) < 2:
        wiz.response.status(400, message="최소 2개 이상의 (x, y) 데이터 포인트가 필요합니다.")

    x = np.array(x_vals)
    y = np.array(y_vals)
    n = len(x)

    coefficients = {}
    y_fit = None
    equation = ""

    try:
        if model == "linear":
            # y = ax + b
            A = np.vstack([x, np.ones(n)]).T
            result = np.linalg.lstsq(A, y, rcond=None)
            a, b = result[0]
            coefficients = {"a (기울기)": float(a), "b (절편)": float(b)}
            y_fit = a * x + b
            equation = f"y = {a:.6g}x + {b:.6g}"

        elif model == "quadratic":
            # y = ax^2 + bx + c
            A = np.vstack([x**2, x, np.ones(n)]).T
            result = np.linalg.lstsq(A, y, rcond=None)
            a, b, c = result[0]
            coefficients = {"a (x² 계수)": float(a), "b (x 계수)": float(b), "c (상수)": float(c)}
            y_fit = a * x**2 + b * x + c
            equation = f"y = {a:.6g}x² + {b:.6g}x + {c:.6g}"

        elif model == "exponential":
            # y = a * exp(b * x)  →  ln(y) = ln(a) + b*x
            if np.all(y > 0):
                ln_y = np.log(y)
                A = np.vstack([x, np.ones(n)]).T
                result = np.linalg.lstsq(A, ln_y, rcond=None)
                b_coeff, ln_a = result[0]
                a_coeff = math.exp(ln_a)
                coefficients = {"a (진폭)": float(a_coeff), "b (지수)": float(b_coeff)}
                y_fit = a_coeff * np.exp(b_coeff * x)
                equation = f"y = {a_coeff:.6g} · exp({b_coeff:.6g}x)"
            else:
                wiz.response.status(400, message="지수 모델은 Y > 0인 데이터에만 적용 가능합니다.")

        elif model == "power":
            # y = a * x^b  →  ln(y) = ln(a) + b*ln(x)
            if np.all(x > 0) and np.all(y > 0):
                ln_x = np.log(x)
                ln_y = np.log(y)
                A = np.vstack([ln_x, np.ones(n)]).T
                result = np.linalg.lstsq(A, ln_y, rcond=None)
                b_coeff, ln_a = result[0]
                a_coeff = math.exp(ln_a)
                coefficients = {"a (계수)": float(a_coeff), "b (지수)": float(b_coeff)}
                y_fit = a_coeff * np.power(x, b_coeff)
                equation = f"y = {a_coeff:.6g} · x^{b_coeff:.6g}"
            else:
                wiz.response.status(400, message="거듭제곱 모델은 X > 0, Y > 0인 데이터에만 적용 가능합니다.")

        elif model == "gaussian":
            # y = a * exp(-(x - mu)^2 / (2 * sigma^2))
            # Estimate initial parameters from data
            mu_est = float(np.sum(x * y) / np.sum(y)) if np.sum(y) != 0 else float(np.mean(x))
            a_est = float(np.max(y))
            sigma_est = float(np.sqrt(np.abs(np.sum(y * (x - mu_est)**2) / np.sum(y)))) if np.sum(y) != 0 else 1.0
            if sigma_est == 0:
                sigma_est = 1.0

            # Simple iterative least squares for gaussian
            # Use linearized approach: ln(y) = ln(a) - (x-mu)^2/(2*sigma^2)
            if np.all(y > 0):
                from scipy.optimize import curve_fit as sp_curve_fit

                def gaussian_func(x, a, mu, sigma):
                    return a * np.exp(-(x - mu)**2 / (2 * sigma**2))

                try:
                    popt, pcov = sp_curve_fit(gaussian_func, x, y, p0=[a_est, mu_est, sigma_est], maxfev=10000)
                    a_fit, mu_fit, sigma_fit = popt
                    coefficients = {
                        "a (진폭)": float(a_fit),
                        "μ (평균)": float(mu_fit),
                        "σ (표준편차)": float(abs(sigma_fit))
                    }
                    y_fit = gaussian_func(x, *popt)
                    equation = f"y = {a_fit:.6g} · exp(-(x - {mu_fit:.6g})² / (2·{abs(sigma_fit):.6g}²))"
                except Exception:
                    # Fallback: simple estimation
                    coefficients = {
                        "a (진폭)": a_est,
                        "μ (평균)": mu_est,
                        "σ (표준편차)": sigma_est
                    }
                    y_fit = a_est * np.exp(-(x - mu_est)**2 / (2 * sigma_est**2))
                    equation = f"y ≈ {a_est:.6g} · exp(-(x - {mu_est:.6g})² / (2·{sigma_est:.6g}²))"
            else:
                wiz.response.status(400, message="가우시안 모델은 Y > 0인 데이터에만 적용 가능합니다.")

        else:
            wiz.response.status(400, message=f"지원하지 않는 모델: {model}")

    except Exception as e:
        wiz.response.status(400, message=f"피팅 오류: {str(e)}")

    # Calculate R²
    if y_fit is not None:
        ss_res = float(np.sum((y - y_fit) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # Build fitted values table
        fitted_values = []
        for i in range(n):
            fitted_values.append({
                "x": float(x[i]),
                "y": float(y[i]),
                "y_fit": float(y_fit[i]),
                "residual": float(y[i] - y_fit[i])
            })

        wiz.response.status(200, {
            "model": model,
            "equation": equation,
            "coefficients": coefficients,
            "r_squared": float(r_squared),
            "residual_sum": float(ss_res),
            "n_points": n,
            "fitted_values": fitted_values
        })

    wiz.response.status(400, message="피팅을 수행할 수 없습니다.")


def dashboard_stats():
    """대시보드 요약 통계"""
    stats = {
        "available_models": ["linear", "quadratic", "exponential", "power", "gaussian"],
        "statistics_metrics": ["mean", "std", "median", "min", "max", "variance", "skewness", "kurtosis"],
        "chart_types": ["line", "scatter", "bar"],
        "supported_formats": ["CSV (comma-separated)", "TSV (tab-separated)"]
    }
    wiz.response.status(200, stats)
