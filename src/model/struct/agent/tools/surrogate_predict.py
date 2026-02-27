# =============================================================================
# surrogate_predict Tool — 파라미터 DB 기반 Ridge 회귀 예측
# =============================================================================
import os
import sys
import json
import numpy as np

from base_tool import BaseTool

PARAM_PATTERNS = {
    "pressure": {"label": "압력 (Pressure)", "category": "condition", "base_unit": "mTorr"},
    "rf_power": {"label": "RF 전력 (Power)", "category": "condition", "base_unit": "W"},
    "gas_flow": {"label": "가스 유량 (Gas Flow)", "category": "condition", "base_unit": "sccm"},
    "temperature": {"label": "온도 (Temperature)", "category": "condition", "base_unit": "°C"},
    "frequency": {"label": "주파수 (Frequency)", "category": "condition", "base_unit": "MHz"},
    "bias_voltage": {"label": "바이어스 전압 (Bias)", "category": "condition", "base_unit": "V"},
    "etch_rate": {"label": "식각 속도 (Etch Rate)", "category": "result", "base_unit": "nm/min"},
    "deposition_rate": {"label": "증착 속도 (Deposition Rate)", "category": "result", "base_unit": "nm/min"},
    "uniformity": {"label": "균일도 (Uniformity)", "category": "result", "base_unit": "%"},
    "selectivity": {"label": "선택비 (Selectivity)", "category": "result", "base_unit": ":1"},
}


def _build_feature_matrix(param_db, target_param):
    cond_keys = [k for k, v in PARAM_PATTERNS.items()
                 if v.get("category") == "condition"]
    X_rows, y_vals, doc_ids = [], [], []

    for doc_id, doc_info in param_db.get("documents", {}).items():
        params = doc_info.get("params", {})
        if target_param not in params:
            continue
        tvs = [v["value"] for v in params[target_param].get("values", [])
               if isinstance(v.get("value"), (int, float))]
        if not tvs:
            continue
        feat = []
        has_cond = False
        for ck in cond_keys:
            if ck in params:
                cvs = [v["value"] for v in params[ck].get("values", [])
                       if isinstance(v.get("value"), (int, float))]
                if cvs:
                    feat.append(float(np.mean(cvs)))
                    has_cond = True
                    continue
            feat.append(np.nan)
        if has_cond:
            for tv in tvs:
                X_rows.append(feat.copy())
                y_vals.append(tv)
                doc_ids.append(doc_id)

    if not X_rows:
        return np.array([]), np.array([]), cond_keys, []

    X = np.array(X_rows)
    y = np.array(y_vals)
    col_means = np.nanmean(X, axis=0)
    for i in range(X.shape[1]):
        mask = np.isnan(X[:, i])
        X[mask, i] = col_means[i] if not np.isnan(col_means[i]) else 0.0
    return X, y, cond_keys, doc_ids


class SurrogatePredictTool(BaseTool):
    name = "surrogate_predict"
    description = "Use Ridge regression on the extracted parameter database to numerically predict a target process result (etch rate, deposition rate, uniformity, selectivity) given input conditions. Returns prediction, 95% confidence interval, R² score, and feature importance."
    input_schema = {
        "type": "object",
        "properties": {
            "target_param": {
                "type": "string",
                "description": "Target parameter to predict: etch_rate, deposition_rate, uniformity, or selectivity",
                "enum": ["etch_rate", "deposition_rate", "uniformity", "selectivity"]
            },
            "pressure": {"type": "number", "description": "Pressure in mTorr"},
            "rf_power": {"type": "number", "description": "RF power in W"},
            "gas_flow": {"type": "number", "description": "Gas flow in sccm"},
            "temperature": {"type": "number", "description": "Temperature in °C"},
            "frequency": {"type": "number", "description": "Frequency in MHz"},
            "bias_voltage": {"type": "number", "description": "Bias voltage in V"},
            "collection": {"type": "string", "description": "Collection name. Default: plasma_papers"}
        },
        "required": ["target_param"]
    }

    def execute(self, target_param="etch_rate", pressure=None, rf_power=None,
                gas_flow=None, temperature=None, frequency=None,
                bias_voltage=None, collection="", **kwargs):
        PARAM_DB_DIR = "/opt/app/data"

        if not collection:
            collection = "plasma_papers"

        if target_param not in PARAM_PATTERNS or PARAM_PATTERNS[target_param]["category"] != "result":
            available = [k for k, v in PARAM_PATTERNS.items() if v["category"] == "result"]
            return f"Error: Invalid target_param '{target_param}'. Available: {', '.join(available)}"

        input_conditions = {}
        for key, val in [("pressure", pressure), ("rf_power", rf_power),
                          ("gas_flow", gas_flow), ("temperature", temperature),
                          ("frequency", frequency), ("bias_voltage", bias_voltage)]:
            if val is not None:
                try:
                    input_conditions[key] = float(val)
                except (ValueError, TypeError):
                    pass

        if not input_conditions:
            return "Error: At least one condition parameter (pressure, rf_power, gas_flow, temperature, frequency, bias_voltage) is required."

        # Load param DB
        db_path = os.path.join(PARAM_DB_DIR, f"param_db_{collection}.json")
        if not os.path.exists(db_path):
            return f"Error: Parameter database not found for '{collection}'. Run parameter extraction first on the Prediction page."

        with open(db_path, "r", encoding="utf-8") as f:
            param_db = json.load(f)

        X, y, feature_names, doc_ids = _build_feature_matrix(param_db, target_param)

        if len(X) < 3:
            available = [k for k, v in PARAM_PATTERNS.items() if v["category"] == "result"]
            return f"Insufficient training data ({len(X)} samples, minimum 3 required). Available targets: {', '.join(available)}"

        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import cross_val_predict, LeaveOneOut

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        ridge = Ridge(alpha=1.0)
        ridge.fit(X_scaled, y)

        # Build input vector
        input_vec = np.zeros(len(feature_names))
        for i, fn in enumerate(feature_names):
            if fn in input_conditions:
                input_vec[i] = input_conditions[fn]
            else:
                input_vec[i] = float(np.mean(X[:, i]))

        input_scaled = scaler.transform([input_vec])
        prediction = float(ridge.predict(input_scaled)[0])

        # Cross-validation
        cv = LeaveOneOut() if len(X) <= 20 else 5
        try:
            cv_preds = cross_val_predict(Ridge(alpha=1.0), X_scaled, y, cv=cv)
            residuals = y - cv_preds
            rmse = float(np.sqrt(np.mean(residuals**2)))
            ss_res = float(np.sum(residuals**2))
            ss_tot = float(np.sum((y - y.mean())**2))
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        except Exception:
            rmse = float(np.std(y))
            r2 = 0

        pinfo = PARAM_PATTERNS[target_param]
        ci_low = round(prediction - 1.96 * rmse, 4)
        ci_high = round(prediction + 1.96 * rmse, 4)

        lines = [f"서로게이트 예측 결과:\n"]
        lines.append(f"  대상: {pinfo['label']}")
        lines.append(f"  예측값: {round(prediction, 4)} {pinfo['base_unit']}")
        lines.append(f"  95% 신뢰구간: [{ci_low}, {ci_high}] {pinfo['base_unit']}")
        lines.append(f"  모델 성능: R² = {round(r2, 4)}, RMSE = {round(rmse, 4)}")
        lines.append(f"  훈련 데이터: {len(X)}건 (범위: {round(float(y.min()),2)} ~ {round(float(y.max()),2)})")
        lines.append(f"\n입력 조건:")
        for k, v in input_conditions.items():
            label = PARAM_PATTERNS.get(k, {}).get("label", k)
            unit = PARAM_PATTERNS.get(k, {}).get("base_unit", "")
            lines.append(f"  {label}: {v} {unit}")

        lines.append(f"\n특성 중요도 (Ridge 계수):")
        importance = sorted(
            [(fn, float(ridge.coef_[i])) for i, fn in enumerate(feature_names)],
            key=lambda x: abs(x[1]), reverse=True
        )
        for fn, coef in importance:
            if abs(coef) > 0.001:
                label = PARAM_PATTERNS.get(fn, {}).get("label", fn)
                direction = "↑" if coef > 0 else "↓"
                lines.append(f"  {label}: {round(coef, 4)} {direction}")

        return "\n".join(lines)

Tool = SurrogatePredictTool
