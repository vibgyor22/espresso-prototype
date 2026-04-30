"""
Pre-analysis diagnostics for Espresso.

Tests:
  - ADF stationarity (statsmodels if available, otherwise manual approximation)
  - KPSS stationarity (statsmodels if available)
  - Parallel trends (regression-based, for DiD)
  - Breusch-Pagan heteroscedasticity
  - Durbin-Watson autocorrelation
  - Ljung-Box portmanteau test on ARIMA residuals
  - Shapiro-Wilk normality
  - VIF multicollinearity
"""

import pandas as pd
import numpy as np
from scipy import stats

try:
    from statsmodels.tsa.stattools import adfuller, kpss
    from statsmodels.stats.stattools import durbin_watson
    from statsmodels.stats.diagnostic import acorr_ljungbox
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Individual test functions
# ---------------------------------------------------------------------------

def check_stationarity(series, name='series'):
    """
    ADF test for unit root.

    Uses statsmodels adfuller (proper MacKinnon critical values) when
    available; falls back to a manual t-statistic approximation otherwise.
    """
    try:
        s = pd.Series(series).dropna()
        if len(s) < 4:
            return {
                'test': 'ADF (Augmented Dickey-Fuller)',
                'series_name': name,
                'is_stationary': None,
                'interpretation': 'Insufficient data for ADF test (need >= 4 obs)',
                'correction': 'Need at least 4 observations',
                'is_violated': False
            }

        if STATSMODELS_AVAILABLE:
            adf_stat, adf_pval, _, _, crit, _ = adfuller(s, autolag='AIC')
            is_stationary = adf_pval < 0.05
            return {
                'test': 'ADF (Augmented Dickey-Fuller)',
                'series_name': name,
                'test_statistic': float(adf_stat),
                'p_value': float(adf_pval),
                'critical_values': {k: float(v) for k, v in crit.items()},
                'is_stationary': is_stationary,
                'is_violated': not is_stationary,
                'interpretation': (
                    f"STATIONARY (ADF p={adf_pval:.4f})" if is_stationary
                    else f"NON-STATIONARY (ADF p={adf_pval:.4f}) — differencing may be needed"
                ),
                'correction': 'No correction needed' if is_stationary else 'Apply first differencing (d=1)'
            }

        # Manual fallback: regress Δy on y_{t-1}, compare t to -2.86 (5% critical)
        y = s.values
        dy = np.diff(y)
        y_lag = y[:-1]
        X = np.column_stack([np.ones(len(y_lag)), y_lag])
        try:
            coeffs = np.linalg.lstsq(X, dy, rcond=None)[0]
            residuals = dy - X @ coeffs
            n = len(dy)
            mse = np.sum(residuals ** 2) / max(n - 2, 1)
            var_beta = mse * np.linalg.inv(X.T @ X)[1, 1]
            t_stat = float(coeffs[1] / np.sqrt(var_beta)) if var_beta > 0 else 0.0
        except Exception:
            t_stat = 0.0

        is_stationary = t_stat < -2.86
        return {
            'test': 'ADF (Augmented Dickey-Fuller)',
            'series_name': name,
            'test_statistic': t_stat,
            'p_value': 0.05 if is_stationary else 0.95,
            'is_stationary': is_stationary,
            'is_violated': not is_stationary,
            'interpretation': (
                'STATIONARY (OK)' if is_stationary
                else 'NON-STATIONARY — differencing required'
            ),
            'correction': 'No correction needed' if is_stationary else 'Apply first differencing (d=1)'
        }

    except Exception as e:
        return {'test': 'ADF', 'series_name': name, 'error': str(e), 'is_violated': False}


def check_kpss(series, name='series'):
    """
    KPSS test for stationarity (null: series IS stationary).

    Complements ADF: ADF null is unit root; KPSS null is stationarity.
    Only runs when statsmodels is available.
    """
    if not STATSMODELS_AVAILABLE:
        return {
            'test': 'KPSS',
            'series_name': name,
            'is_violated': False,
            'interpretation': 'KPSS not available (install statsmodels)',
            'correction': 'No correction needed'
        }
    try:
        s = pd.Series(series).dropna()
        if len(s) < 5:
            return {
                'test': 'KPSS', 'series_name': name, 'is_violated': False,
                'interpretation': 'Insufficient data for KPSS'
            }
        stat, pval, _, _ = kpss(s, regression='c', nlags='auto')
        # pval < 0.05 → reject stationarity
        is_nonstationary = pval < 0.05
        return {
            'test': 'KPSS',
            'series_name': name,
            'test_statistic': float(stat),
            'p_value': float(pval),
            'is_violated': is_nonstationary,
            'interpretation': (
                f"KPSS: NON-STATIONARY (p={pval:.4f})" if is_nonstationary
                else f"KPSS: STATIONARY (p={pval:.4f})"
            ),
            'correction': 'Apply differencing' if is_nonstationary else 'No correction needed'
        }
    except Exception as e:
        return {'test': 'KPSS', 'series_name': name, 'error': str(e), 'is_violated': False}


def check_ljung_box(residuals, lags=10):
    """
    Ljung-Box portmanteau test for residual autocorrelation.

    Preferred over Durbin-Watson for ARIMA residual checking.
    Falls back to Durbin-Watson if statsmodels unavailable.
    """
    r = np.asarray(residuals)[~np.isnan(residuals)]
    if len(r) < lags + 2:
        return {
            'test': 'Ljung-Box',
            'is_violated': False,
            'interpretation': f'Insufficient data for Ljung-Box (need > {lags + 1} obs)'
        }

    if STATSMODELS_AVAILABLE:
        try:
            lb = acorr_ljungbox(r, lags=[lags], return_df=True)
            stat = float(lb['lb_stat'].iloc[0])
            pval = float(lb['lb_pvalue'].iloc[0])
            is_violated = pval < 0.05
            return {
                'test': f'Ljung-Box (lag={lags})',
                'test_statistic': stat,
                'p_value': pval,
                'is_violated': is_violated,
                'interpretation': (
                    f"Residual autocorrelation detected (LB p={pval:.4f})" if is_violated
                    else f"No significant residual autocorrelation (LB p={pval:.4f})"
                ),
                'correction': 'Increase ARIMA order (more AR/MA terms)' if is_violated else 'No correction needed'
            }
        except Exception as e:
            pass  # fall through to DW

    return check_autocorrelation(r)


def check_autocorrelation(residuals):
    """Durbin-Watson test for first-order autocorrelation."""
    try:
        r = np.asarray(residuals)[~np.isnan(residuals)]
        if len(r) < 3:
            return {
                'test': 'Durbin-Watson', 'is_violated': False,
                'interpretation': 'Insufficient data'
            }
        dw = float(np.sum(np.diff(r) ** 2) / np.sum(r ** 2))
        has_autocorr = abs(dw - 2) > 0.5
        return {
            'test': 'Durbin-Watson',
            'dw_statistic': dw,
            'is_violated': has_autocorr,
            'interpretation': (
                f"Autocorrelation detected (DW={dw:.3f})" if has_autocorr
                else f"No significant autocorrelation (DW={dw:.3f})"
            ),
            'correction': 'Consider ARIMA or robust standard errors' if has_autocorr else 'No correction needed'
        }
    except Exception as e:
        return {'test': 'Durbin-Watson', 'error': str(e), 'is_violated': False}


def check_heteroscedasticity(residuals, y_fitted):
    """Breusch-Pagan test for heteroscedasticity."""
    try:
        r = np.asarray(residuals)
        yf = np.asarray(y_fitted)
        n = len(r)
        u2 = r ** 2
        u_bar = np.mean(u2)
        yf_c = yf - np.mean(yf)
        ss_y = np.sum(yf_c ** 2)
        ss_u = np.sum((u2 - u_bar) ** 2)

        if ss_y < 1e-15:
            return {
                'test': 'Breusch-Pagan', 'is_violated': False,
                'interpretation': 'Unable to compute (zero variance in fitted values)'
            }

        lm = (ss_u / ss_y) * (n / 2)
        pval = float(1 - stats.chi2.cdf(lm, df=1))
        is_hetero = pval < 0.05

        return {
            'test': 'Breusch-Pagan',
            'statistic': float(lm),
            'p_value': pval,
            'is_violated': is_hetero,
            'interpretation': (
                f"Heteroscedasticity detected (p={pval:.4f})" if is_hetero
                else f"Homoscedastic (p={pval:.4f})"
            ),
            'correction': 'Robust (HC1) standard errors applied' if is_hetero else 'No correction needed'
        }
    except Exception as e:
        return {'test': 'Breusch-Pagan', 'error': str(e), 'is_violated': False}


def check_normality_of_residuals(residuals):
    """Shapiro-Wilk test for normality of residuals."""
    try:
        r = np.asarray(residuals)[~np.isnan(residuals)]
        if len(r) < 3:
            return {
                'test': 'Shapiro-Wilk', 'is_violated': False,
                'interpretation': 'Insufficient data'
            }
        sample = r[:5000]
        stat, pval = stats.shapiro(sample)
        is_nonnormal = pval < 0.05
        return {
            'test': 'Shapiro-Wilk',
            'statistic': float(stat),
            'p_value': float(pval),
            'is_violated': is_nonnormal,
            'interpretation': (
                f"Non-normal residuals (p={pval:.4f})" if is_nonnormal
                else f"Residuals consistent with normality (p={pval:.4f})"
            ),
            'correction': 'Consider robust SEs or bootstrap CIs' if is_nonnormal else 'No correction needed'
        }
    except Exception as e:
        return {'test': 'Shapiro-Wilk', 'error': str(e), 'is_violated': False}


def check_multicollinearity(X):
    """VIF (Variance Inflation Factor) for multicollinearity."""
    try:
        if X.shape[1] < 2:
            return {
                'test': 'VIF', 'vif_values': [], 'is_violated': False,
                'interpretation': 'Single regressor — no multicollinearity possible',
                'correction': 'No correction needed'
            }
        vif_values = []
        for i in range(X.shape[1]):
            X_rest = np.delete(X, i, axis=1)
            y_col = X[:, i]
            coeffs = np.linalg.lstsq(X_rest, y_col, rcond=None)[0]
            y_pred = X_rest @ coeffs
            ss_res = np.sum((y_col - y_pred) ** 2)
            ss_tot = np.sum((y_col - np.mean(y_col)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
            vif_values.append(1 / (1 - r2) if r2 < 1 else np.inf)

        max_vif = float(np.nanmax(vif_values))
        is_violated = max_vif > 10
        return {
            'test': 'VIF',
            'vif_values': [float(v) for v in vif_values],
            'max_vif': max_vif,
            'is_violated': is_violated,
            'interpretation': (
                f"High multicollinearity (max VIF={max_vif:.1f})" if is_violated
                else f"Acceptable multicollinearity (max VIF={max_vif:.1f})"
            ),
            'correction': 'Consider dropping collinear variables' if is_violated else 'No correction needed'
        }
    except Exception as e:
        return {'test': 'VIF', 'error': str(e), 'is_violated': False}


def check_parallel_trends(data, outcome_col, treatment_col, time_col, unit_col):
    """
    Regression-based parallel pre-trends test for DiD.

    Method:
      1. Identify "treated" units: units that ever had treatment > 0.
      2. Identify the first period where any treated unit has treatment > 0.
      3. Restrict to pre-treatment observations.
      4. Regress outcome on: time_trend, treated_group, time×treated_group.
      5. Test H0: the interaction coefficient = 0 (parallel slopes).

    A significant interaction (p < 0.10) suggests differing pre-trends,
    which undermines the DiD identifying assumption.
    """
    try:
        df = data[[unit_col, time_col, outcome_col, treatment_col]].copy().dropna()
        for col in [outcome_col, treatment_col, time_col]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()

        # Identify treated units
        unit_max_tx = df.groupby(unit_col)[treatment_col].max()
        treated_units = set(unit_max_tx[unit_max_tx > 0].index)

        if not treated_units:
            return {
                'test': 'Parallel Trends',
                'is_violated': False,
                'interpretation': 'No treated units identified for parallel trends test',
                'correction': 'No correction needed'
            }

        df['_treated_group'] = df[unit_col].isin(treated_units).astype(float)

        # Find first treatment period
        treated_df = df[df['_treated_group'] == 1]
        first_tx_period = treated_df[treated_df[treatment_col] > 0][time_col].min()

        if pd.isna(first_tx_period):
            return {
                'test': 'Parallel Trends', 'is_violated': False,
                'interpretation': 'Could not determine first treatment period',
                'correction': 'No correction needed'
            }

        pre_df = df[df[time_col] < first_tx_period].copy()
        n_pre_periods = pre_df[time_col].nunique()

        if len(pre_df) < 10 or n_pre_periods < 2:
            return {
                'test': 'Parallel Trends', 'is_violated': False,
                'interpretation': (
                    f'Too few pre-treatment observations ({len(pre_df)}) '
                    f'to test parallel trends (need >= 10 with >= 2 periods)'
                ),
                'correction': 'No correction needed',
                'n_pre_periods': n_pre_periods
            }

        pre_df['_t'] = pre_df[time_col] - pre_df[time_col].min()
        pre_df['_interact'] = pre_df['_treated_group'] * pre_df['_t']

        y = pre_df[outcome_col].values
        X = np.column_stack([
            np.ones(len(pre_df)),
            pre_df['_t'].values,
            pre_df['_treated_group'].values,
            pre_df['_interact'].values
        ])
        n, k = X.shape

        try:
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            residuals = y - X @ beta
            mse = np.sum(residuals ** 2) / max(n - k, 1)
            vcov = mse * np.linalg.pinv(X.T @ X)
            se = np.sqrt(np.clip(np.diag(vcov), 0, None))

            interact_coef = float(beta[3])
            interact_se = float(se[3])
            t_stat = interact_coef / interact_se if interact_se > 0 else 0.0
            pval = float(2 * (1 - stats.t.cdf(abs(t_stat), df=n - k)))

            is_violated = pval < 0.10  # 10% threshold (standard in lit)
            return {
                'test': 'Parallel Trends (pre-trend regression)',
                'interaction_coef': interact_coef,
                'interaction_se': interact_se,
                'p_value': pval,
                'is_violated': is_violated,
                'first_treatment_period': float(first_tx_period),
                'n_pre_periods': n_pre_periods,
                'interpretation': (
                    f"Pre-trends VIOLATED (interact p={pval:.3f}<0.10): "
                    f"treated and control groups had different trends before treatment"
                    if is_violated else
                    f"Parallel trends plausible (interact p={pval:.3f}>=0.10)"
                ),
                'correction': (
                    'Interpret DiD with caution; consider synthetic control or matching'
                    if is_violated else 'No correction needed'
                )
            }
        except np.linalg.LinAlgError:
            return {
                'test': 'Parallel Trends', 'is_violated': False,
                'interpretation': 'Could not compute parallel trends test (singular matrix)',
                'correction': 'No correction needed'
            }

    except Exception as e:
        return {'test': 'Parallel Trends', 'error': str(e), 'is_violated': False}


# ---------------------------------------------------------------------------
# Composite diagnostic runners
# ---------------------------------------------------------------------------

def run_arima_diagnostics(data, outcome_col, time_col):
    """Full diagnostics for ARIMA: stationarity (ADF + KPSS), Ljung-Box, normality."""
    diagnostics = {
        'model': 'ARIMA',
        'checks': [],
        'violations': [],
        'corrections': []
    }

    try:
        series = data[outcome_col].dropna()
        if len(series) < 5:
            diagnostics['error'] = 'Insufficient data for ARIMA diagnostics (need >= 5 obs)'
            return diagnostics

        # 1. ADF stationarity
        adf = check_stationarity(series, name=outcome_col)
        diagnostics['checks'].append(adf)
        if adf.get('is_violated'):
            diagnostics['violations'].append(adf['test'])
            diagnostics['corrections'].append(adf.get('correction', 'Apply differencing'))

            # Also test first differences
            diff_series = series.diff().dropna()
            adf_diff = check_stationarity(diff_series, name=f'{outcome_col} (1st diff)')
            diagnostics['checks'].append(adf_diff)

        # 2. KPSS
        kpss_result = check_kpss(series, name=outcome_col)
        diagnostics['checks'].append(kpss_result)
        if kpss_result.get('is_violated'):
            diagnostics['violations'].append(kpss_result['test'])
            diagnostics['corrections'].append(kpss_result.get('correction', 'Apply differencing'))

        # 3. Ljung-Box on AR(1) residuals (proxy for ARIMA residuals pre-fit)
        y = series.values
        if len(y) >= 4:
            X = np.column_stack([np.ones(len(y) - 1), y[:-1]])
            beta = np.linalg.lstsq(X, y[1:], rcond=None)[0]
            residuals = y[1:] - X @ beta
            lb = check_ljung_box(residuals)
            diagnostics['checks'].append(lb)
            if lb.get('is_violated'):
                diagnostics['violations'].append(lb['test'])
                diagnostics['corrections'].append(lb.get('correction', 'Increase ARIMA order'))

            # 4. Normality of residuals
            norm = check_normality_of_residuals(residuals)
            diagnostics['checks'].append(norm)
            if norm.get('is_violated'):
                diagnostics['violations'].append(norm['test'])
                diagnostics['corrections'].append(norm.get('correction', 'Use robust CIs'))

    except Exception as e:
        diagnostics['error'] = str(e)

    return diagnostics


def run_did_diagnostics(data, outcome_col, treatment_col, time_col, unit_col):
    """Full diagnostics for DiD: parallel trends, heteroscedasticity, autocorrelation, normality."""
    diagnostics = {
        'model': 'Difference-in-Differences (TWFE)',
        'checks': [],
        'violations': [],
        'corrections': []
    }

    try:
        df = data[[outcome_col, treatment_col, time_col, unit_col]].dropna()
        if len(df) < 10:
            diagnostics['error'] = 'Insufficient data for DiD diagnostics'
            return diagnostics

        for col in [outcome_col, treatment_col, time_col]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()

        # 1. Parallel trends (most important DiD assumption)
        pt = check_parallel_trends(df, outcome_col, treatment_col, time_col, unit_col)
        diagnostics['checks'].append(pt)
        if pt.get('is_violated'):
            diagnostics['violations'].append(pt['test'])
            diagnostics['corrections'].append(pt.get('correction', 'Interpret with caution'))

        # Simple OLS residuals for other checks (fast approximation)
        y = df[outcome_col].values
        X_t = pd.factorize(df[time_col])[0]
        X_u = pd.factorize(df[unit_col])[0]
        X_tx = df[treatment_col].values
        X_mat = np.column_stack([np.ones(len(y)), X_tx, X_t, X_u])
        try:
            coeffs = np.linalg.lstsq(X_mat, y, rcond=None)[0]
            residuals = y - X_mat @ coeffs
            y_fitted = X_mat @ coeffs

            # 2. Heteroscedasticity
            hetero = check_heteroscedasticity(residuals, y_fitted)
            diagnostics['checks'].append(hetero)
            if hetero.get('is_violated'):
                diagnostics['violations'].append(hetero['test'])
                diagnostics['corrections'].append(hetero.get('correction', 'Clustered SEs applied'))

            # 3. Autocorrelation (DW)
            auto = check_autocorrelation(residuals)
            diagnostics['checks'].append(auto)
            if auto.get('is_violated'):
                diagnostics['violations'].append(auto['test'])
                diagnostics['corrections'].append(auto.get('correction', 'Use clustered SEs'))

            # 4. Normality
            norm = check_normality_of_residuals(residuals)
            diagnostics['checks'].append(norm)
            if norm.get('is_violated'):
                diagnostics['violations'].append(norm['test'])
                diagnostics['corrections'].append(norm.get('correction', 'Use robust SEs'))

        except Exception:
            pass

    except Exception as e:
        diagnostics['error'] = str(e)

    return diagnostics


def run_ols_diagnostics(data, outcome_col, treatment_col):
    """Diagnostics for cross-sectional OLS: heteroscedasticity, normality."""
    diagnostics = {
        'model': 'OLS',
        'checks': [],
        'violations': [],
        'corrections': []
    }
    try:
        df = data[[outcome_col, treatment_col]].dropna()
        for col in [outcome_col, treatment_col]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()

        if len(df) < 5:
            diagnostics['error'] = 'Insufficient data for OLS diagnostics'
            return diagnostics

        y = df[outcome_col].values
        X = np.column_stack([np.ones(len(df)), df[treatment_col].values])
        coeffs = np.linalg.lstsq(X, y, rcond=None)[0]
        residuals = y - X @ coeffs
        y_fitted = X @ coeffs

        hetero = check_heteroscedasticity(residuals, y_fitted)
        diagnostics['checks'].append(hetero)
        if hetero.get('is_violated'):
            diagnostics['violations'].append(hetero['test'])
            diagnostics['corrections'].append('HC1 robust standard errors applied')

        norm = check_normality_of_residuals(residuals)
        diagnostics['checks'].append(norm)
        if norm.get('is_violated'):
            diagnostics['violations'].append(norm['test'])
            diagnostics['corrections'].append(norm.get('correction', 'Use robust CIs'))

    except Exception as e:
        diagnostics['error'] = str(e)

    return diagnostics
