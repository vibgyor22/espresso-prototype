"""
Statistical models for Espresso.

Models:
  - run_arima        : Proper ARIMA(p,d,q) via statsmodels with AIC-based order
                       selection; falls back to AR(1) OLS if statsmodels absent.
  - run_diff_in_diff : Two-Way Fixed Effects (unit + time FE) DiD with
                       unit-clustered standard errors.
  - run_panel_ols    : Same TWFE estimator as DiD but framed as association.
  - run_ols          : Simple cross-sectional OLS for non-panel data.
"""

import pandas as pd
import numpy as np
from scipy import optimize, stats

# Optional statsmodels for proper ARIMA
try:
    from statsmodels.tsa.arima.model import ARIMA as SM_ARIMA
    from statsmodels.tsa.holtwinters import SimpleExpSmoothing
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _two_way_demean(df, y_col, x_cols, unit_col, time_col, max_iter=30, tol=1e-9):
    """
    Remove unit and time fixed effects via iterative demeaning.

    Solves the Frisch-Waugh-Lovell system for TWFE without forming large dummy
    matrices.  Converges in ~10-20 iterations for typical panels.

    Returns:
        y_dm  : 1-D array, demeaned outcome
        X_dm  : 2-D array, demeaned regressors (one column per x_col)
    """
    df = df.copy()
    all_cols = [y_col] + list(x_cols)

    # Initialise demeaned columns
    for col in all_cols:
        df[f'_dm_{col}'] = df[col].astype(float)

    for _ in range(max_iter):
        max_change = 0.0
        for col in all_cols:
            dm = f'_dm_{col}'
            prev = df[dm].copy()
            # Subtract unit means then time means
            df[dm] -= df.groupby(unit_col)[dm].transform('mean')
            df[dm] -= df.groupby(time_col)[dm].transform('mean')
            max_change = max(max_change, (df[dm] - prev).abs().max())
        if max_change < tol:
            break

    y_dm = df[f'_dm_{y_col}'].values
    X_dm = df[[f'_dm_{col}' for col in x_cols]].values
    return y_dm, X_dm


def _clustered_se(X, residuals, cluster_ids):
    """
    Sandwich (cluster-robust) variance estimator.

    Clusters on the unique values of `cluster_ids`.
    Small-sample correction: G/(G-1) * (n-1)/(n-k).

    Returns:
        se    : 1-D array of clustered SEs
        vcov  : (k x k) variance-covariance matrix
    """
    clusters = np.asarray(cluster_ids)
    unique_clusters = np.unique(clusters)
    G = len(unique_clusters)
    n, k = X.shape

    bread = np.linalg.pinv(X.T @ X)
    meat = np.zeros((k, k))
    for c in unique_clusters:
        mask = clusters == c
        score = X[mask].T @ residuals[mask]
        meat += np.outer(score, score)

    correction = (G / (G - 1)) * ((n - 1) / (n - k)) if G > 1 and n > k else 1.0
    vcov = correction * bread @ meat @ bread
    se = np.sqrt(np.clip(np.diag(vcov), 0, None))
    return se, vcov


def _hc1_vcov(X, residuals):
    """HC1 heteroscedasticity-robust covariance matrix."""
    n, k = X.shape
    bread = np.linalg.pinv(X.T @ X)
    meat = np.zeros((k, k))
    for i in range(n):
        xi = X[i:i + 1].T
        meat += (residuals[i] ** 2) * (xi @ xi.T)
    correction = n / max(n - k, 1)
    return correction * bread @ meat @ bread


def _linear_regression_result(model, y, X, main_index=1, se_type='HC1 robust',
                              extra=None, aliases=True):
    """Return a standard Espresso regression result from y and X."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    n, k = X.shape

    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    fitted = X @ beta
    residuals = y - fitted

    rss = float(np.sum(residuals ** 2))
    tss = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 1.0 - rss / tss if tss > 0 else 0.0

    vcov = _hc1_vcov(X, residuals)
    se = np.sqrt(np.clip(np.diag(vcov), 0, None))
    dof = max(n - k, 1)
    t_stats = np.divide(beta, se, out=np.zeros_like(beta), where=se > 0)
    pvalues = 2 * (1 - stats.t.cdf(np.abs(t_stats), df=dof))

    effect = float(beta[main_index])
    effect_se = float(se[main_index])
    pvalue = float(pvalues[main_index])
    t_crit = float(stats.t.ppf(0.975, df=dof))
    ci_lower = effect - t_crit * effect_se
    ci_upper = effect + t_crit * effect_se

    result = {
        'model': model,
        'coefficients': [float(b) for b in beta],
        'standard_errors': [float(s) for s in se],
        'effect': effect,
        'se': effect_se,
        'pvalue': pvalue,
        't_stat': float(t_stats[main_index]),
        'significant': pvalue < 0.05,
        'n_obs': int(n),
        'r_squared': r_squared,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'se_type': se_type,
        'residuals': residuals.tolist(),
        'fitted_values': fitted.tolist(),
    }
    if aliases:
        result['slope'] = effect
        result['treatment_effect'] = effect
    if extra:
        result.update(extra)
    return result


def _prepare_time_series(data, outcome_col, time_col, unit_col=None):
    """Clean, aggregate if needed, and sort data into a single time series."""
    cols = [time_col, outcome_col]
    if unit_col and unit_col in data.columns:
        cols.append(unit_col)
    df = data[cols].copy().dropna()
    df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
    df[time_col] = pd.to_numeric(df[time_col], errors='coerce')
    df = df.dropna()
    if unit_col and unit_col in df.columns:
        df = df.groupby(time_col, as_index=False)[outcome_col].mean()
    df = df.sort_values(time_col)
    return df[outcome_col].values, df[time_col].values


# ---------------------------------------------------------------------------
# ARIMA
# ---------------------------------------------------------------------------

def run_arima(data, outcome_col, time_col, unit_col=None, forecast_periods=10):
    """
    Fit ARIMA(p,d,q) to a time series and produce multi-step forecasts.

    Order selection: AIC grid search over p in [0..3], d in [0..1], q in [0..3]
    using statsmodels.  Falls back to AR(1) OLS if statsmodels is unavailable
    or the series is too short (<10 observations).

    If `unit_col` is provided the series is aggregated (mean) across units
    before fitting — useful for panel datasets when a single overall forecast
    is requested.
    """
    try:
        cols = [time_col, outcome_col]
        if unit_col and unit_col in data.columns:
            cols.append(unit_col)
        df = data[cols].copy().dropna()

        df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
        df[time_col] = pd.to_numeric(df[time_col], errors='coerce')
        df = df.dropna()

        if unit_col and unit_col in df.columns:
            df = df.groupby(time_col)[outcome_col].mean().reset_index()

        df = df.sort_values(time_col)
        y = df[outcome_col].values
        time_values = df[time_col].values
        n = len(y)

        if n < 3:
            return {'model': 'arima', 'error': 'Insufficient data for ARIMA (need >= 3 obs)'}

        if STATSMODELS_AVAILABLE and n >= 10:
            return _run_arima_statsmodels(y, time_values, forecast_periods)
        else:
            return _run_ar1_fallback(y, time_values, forecast_periods)

    except Exception as e:
        return {'model': 'arima', 'error': str(e)}


def _run_arima_statsmodels(y, time_values, forecast_periods):
    """Auto-order ARIMA via statsmodels AIC grid search."""
    n = len(y)
    max_p = min(3, n // 5)
    max_q = min(3, n // 5)

    best_aic = np.inf
    best_order = (1, 0, 0)
    best_fit = None

    for d in range(2):
        for p in range(max_p + 1):
            for q in range(max_q + 1):
                if p == 0 and q == 0:
                    continue
                try:
                    fit = SM_ARIMA(y, order=(p, d, q)).fit(
                        method_kwargs={'warn_convergence': False}
                    )
                    if fit.aic < best_aic:
                        best_aic = fit.aic
                        best_order = (p, d, q)
                        best_fit = fit
                except Exception:
                    pass

    if best_fit is None:
        return _run_ar1_fallback(y, time_values, forecast_periods)

    fc = best_fit.get_forecast(steps=forecast_periods)
    forecasts = fc.predicted_mean.tolist()
    ci = fc.conf_int(alpha=0.05)
    if hasattr(ci, 'iloc'):
        ci_lower = ci.iloc[:, 0].tolist()
        ci_upper = ci.iloc[:, 1].tolist()
    else:
        ci = np.asarray(ci)
        ci_lower = ci[:, 0].tolist()
        ci_upper = ci[:, 1].tolist()

    forecast_times = [time_values[-1] + i for i in range(1, forecast_periods + 1)]
    fitted = best_fit.fittedvalues
    residuals = y - fitted
    rmse = float(np.sqrt(np.mean(residuals ** 2)))

    # Grab AR(1) coef if available for backwards compat with html_report
    params = best_fit.params
    if hasattr(params, 'get'):
        ar1_coef = float(params.get('ar.L1', 0.0))
    else:
        ar1_coef = 0.0
        names = getattr(best_fit, 'param_names', [])
        if 'ar.L1' in names:
            ar1_coef = float(params[names.index('ar.L1')])

    return {
        'model': 'arima',
        'arima_order': best_order,
        'aic': float(best_aic),
        'ar1_coef': ar1_coef,
        'forecast_next_period': forecasts[0],
        'forecasts': forecasts,
        'forecast_times': forecast_times,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'historical_values': y.tolist(),
        'historical_times': time_values.tolist(),
        'n_obs': n,
        'rmse': rmse,
        'last_value': float(y[-1]),
        'engine': 'statsmodels',
        'interpretation': (
            f"ARIMA{best_order} fitted (AIC={best_aic:.1f}). "
            f"Last observed: {y[-1]:.4f}. "
            f"Next-period forecast: {forecasts[0]:.4f} "
            f"(95% CI: [{ci_lower[0]:.4f}, {ci_upper[0]:.4f}])."
        )
    }


def _run_ar1_fallback(y, time_values, forecast_periods):
    """AR(1) via OLS — used when statsmodels is unavailable or n < 10."""
    n = len(y)
    X = np.column_stack([np.ones(n - 1), y[:-1]])
    y_target = y[1:]

    beta = np.linalg.lstsq(X, y_target, rcond=None)[0]
    fitted = X @ beta
    residuals = y_target - fitted
    rmse = float(np.sqrt(np.mean(residuals ** 2)))

    rss = float(np.sum(residuals ** 2))
    aic = 2 * 2 + (n - 1) * np.log(rss / (n - 1)) if rss > 0 else np.nan

    forecasts, last_y = [], float(y[-1])
    for h in range(forecast_periods):
        prev = last_y if h == 0 else forecasts[-1]
        forecasts.append(float(beta[0] + beta[1] * prev))

    forecast_times = [float(time_values[-1]) + i for i in range(1, forecast_periods + 1)]
    # Naïve growing PI: ±1.96 * RMSE * sqrt(h)
    ci_lower = [f - 1.96 * rmse * np.sqrt(h + 1) for h, f in enumerate(forecasts)]
    ci_upper = [f + 1.96 * rmse * np.sqrt(h + 1) for h, f in enumerate(forecasts)]

    return {
        'model': 'arima',
        'arima_order': (1, 0, 0),
        'aic': aic,
        'ar1_coef': float(beta[1]),
        'forecast_next_period': forecasts[0],
        'forecasts': forecasts,
        'forecast_times': forecast_times,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'historical_values': y.tolist(),
        'historical_times': [float(t) for t in time_values],
        'n_obs': n,
        'rmse': rmse,
        'last_value': float(y[-1]),
        'engine': 'ar1_fallback',
        'interpretation': (
            f"AR(1) model (statsmodels unavailable or n<10). "
            f"Last observed: {y[-1]:.4f}. "
            f"Next-period forecast: {forecasts[0]:.4f}."
        )
    }


def run_linear_trend(data, outcome_col, time_col, unit_col=None, forecast_periods=10):
    """Forecast with a linear time trend estimated by OLS."""
    try:
        y, time_values = _prepare_time_series(data, outcome_col, time_col, unit_col)
        n = len(y)
        if n < 3:
            return {'model': 'linear_trend', 'error': 'Need at least 3 observations'}

        t = np.asarray(time_values, dtype=float)
        t0 = t.min()
        X = np.column_stack([np.ones(n), t - t0])
        result = _linear_regression_result('linear_trend', y, X, main_index=1)
        beta = result['coefficients']

        step = np.median(np.diff(np.sort(t))) if n > 1 else 1.0
        if not np.isfinite(step) or step == 0:
            step = 1.0
        forecast_times = [float(t[-1] + step * i) for i in range(1, forecast_periods + 1)]
        Xf = np.column_stack([np.ones(forecast_periods), np.asarray(forecast_times) - t0])
        forecasts = Xf @ np.asarray(beta)

        residuals = np.asarray(result['residuals'])
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        ci_lower = []
        ci_upper = []
        for h, f in enumerate(forecasts, 1):
            band = 1.96 * rmse * np.sqrt(1 + h / max(n, 1))
            ci_lower.append(float(f - band))
            ci_upper.append(float(f + band))

        result.update({
            'forecasts': [float(v) for v in forecasts],
            'forecast_next_period': float(forecasts[0]),
            'forecast_times': forecast_times,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'historical_values': [float(v) for v in y],
            'historical_times': [float(v) for v in time_values],
            'last_value': float(y[-1]),
            'rmse': rmse,
            'engine': 'ols_trend',
            'interpretation': (
                f"Linear trend forecast: next-period value {forecasts[0]:.4f}; "
                f"trend slope {beta[1]:.4f} per period."
            )
        })
        return result
    except Exception as e:
        return {'model': 'linear_trend', 'error': str(e)}


def run_exp_smoothing(data, outcome_col, time_col, unit_col=None, forecast_periods=10):
    """Forecast with simple exponential smoothing."""
    try:
        y, time_values = _prepare_time_series(data, outcome_col, time_col, unit_col)
        n = len(y)
        if n < 4:
            return {'model': 'exp_smoothing', 'error': 'Need at least 4 observations'}

        if STATSMODELS_AVAILABLE:
            fit = SimpleExpSmoothing(y, initialization_method='estimated').fit(optimized=True)
            forecasts = fit.forecast(forecast_periods)
            fitted = fit.fittedvalues
            alpha = float(fit.params.get('smoothing_level', np.nan))
            engine = 'statsmodels'
        else:
            best_alpha, best_sse, best_fitted = 0.3, np.inf, None
            for alpha in np.linspace(0.05, 0.95, 19):
                fitted = np.zeros(n)
                fitted[0] = y[0]
                for i in range(1, n):
                    fitted[i] = alpha * y[i - 1] + (1 - alpha) * fitted[i - 1]
                sse = np.sum((y[1:] - fitted[1:]) ** 2)
                if sse < best_sse:
                    best_alpha, best_sse, best_fitted = float(alpha), sse, fitted
            alpha = best_alpha
            fitted = best_fitted
            level = alpha * y[-1] + (1 - alpha) * fitted[-1]
            forecasts = np.repeat(level, forecast_periods)
            engine = 'grid_search_fallback'

        residuals = y - np.asarray(fitted)
        rmse = float(np.sqrt(np.mean(residuals[1:] ** 2))) if n > 1 else 0.0
        step = np.median(np.diff(np.sort(time_values))) if n > 1 else 1.0
        if not np.isfinite(step) or step == 0:
            step = 1.0
        forecast_times = [float(time_values[-1] + step * i) for i in range(1, forecast_periods + 1)]
        forecasts = [float(v) for v in forecasts]
        ci_lower = [float(f - 1.96 * rmse * np.sqrt(h)) for h, f in enumerate(forecasts, 1)]
        ci_upper = [float(f + 1.96 * rmse * np.sqrt(h)) for h, f in enumerate(forecasts, 1)]

        return {
            'model': 'exp_smoothing',
            'alpha': alpha,
            'forecast_next_period': forecasts[0],
            'forecasts': forecasts,
            'forecast_times': forecast_times,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'historical_values': [float(v) for v in y],
            'historical_times': [float(v) for v in time_values],
            'n_obs': n,
            'rmse': rmse,
            'last_value': float(y[-1]),
            'engine': engine,
            'interpretation': (
                f"Simple exponential smoothing forecast: next-period value "
                f"{forecasts[0]:.4f} with alpha={alpha:.3f}."
            )
        }
    except Exception as e:
        return {'model': 'exp_smoothing', 'error': str(e)}


def run_random_walk(data, outcome_col, time_col, unit_col=None, forecast_periods=10):
    """Naive random-walk forecast that carries the last observation forward."""
    try:
        y, time_values = _prepare_time_series(data, outcome_col, time_col, unit_col)
        n = len(y)
        if n < 3:
            return {'model': 'random_walk', 'error': 'Need at least 3 observations'}
        diffs = np.diff(y)
        rmse = float(np.sqrt(np.mean(diffs ** 2))) if len(diffs) else 0.0
        forecasts = [float(y[-1])] * forecast_periods
        step = np.median(np.diff(np.sort(time_values))) if n > 1 else 1.0
        if not np.isfinite(step) or step == 0:
            step = 1.0
        forecast_times = [float(time_values[-1] + step * i) for i in range(1, forecast_periods + 1)]
        ci_lower = [float(f - 1.96 * rmse * np.sqrt(h)) for h, f in enumerate(forecasts, 1)]
        ci_upper = [float(f + 1.96 * rmse * np.sqrt(h)) for h, f in enumerate(forecasts, 1)]
        return {
            'model': 'random_walk',
            'forecast_next_period': forecasts[0],
            'forecasts': forecasts,
            'forecast_times': forecast_times,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'historical_values': [float(v) for v in y],
            'historical_times': [float(v) for v in time_values],
            'n_obs': n,
            'rmse': rmse,
            'last_value': float(y[-1]),
            'engine': 'naive',
            'interpretation': (
                f"Random-walk baseline: all forecasts equal the last observed "
                f"value ({y[-1]:.4f})."
            )
        }
    except Exception as e:
        return {'model': 'random_walk', 'error': str(e)}


# ---------------------------------------------------------------------------
# Two-Way Fixed Effects (DiD / Panel OLS)
# ---------------------------------------------------------------------------

def _twfe_core(data, outcome_col, treatment_col, time_col, unit_col, model_label):
    """
    Shared TWFE estimator for DiD and Panel OLS.

    Specification: Y_it = α_i + γ_t + β·X_it + ε_it

    Identification strategy:
      - Unit FE (α_i) and time FE (γ_t) via iterative two-way demeaning.
      - β estimated by OLS on demeaned variables.
      - Standard errors clustered at the unit level.

    Returns a results dict.
    """
    df = data[[unit_col, time_col, outcome_col, treatment_col]].copy()
    df = df.dropna()

    for col in [outcome_col, treatment_col, time_col]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna()

    n = len(df)
    n_units = df[unit_col].nunique()
    n_periods = df[time_col].nunique()

    if n < 10:
        return {model_label: model_label, 'error': f'Too few observations ({n})'}
    if n_units < 2:
        return {model_label: model_label, 'error': 'Need >= 2 units for TWFE'}
    if n_periods < 2:
        return {model_label: model_label, 'error': 'Need >= 2 time periods for TWFE'}

    # Two-way demean
    y_dm, X_dm = _two_way_demean(df, outcome_col, [treatment_col], unit_col, time_col)
    X_dm2 = X_dm.reshape(-1, 1)

    if np.std(X_dm2) < 1e-10:
        return {model_label: model_label, 'error': 'No within-variation in treatment after absorbing FEs'}

    # OLS on demeaned data (FEs absorbed, no intercept)
    beta = np.linalg.lstsq(X_dm2, y_dm, rcond=None)[0]
    residuals = y_dm - X_dm2 @ beta

    rss = float(np.sum(residuals ** 2))
    tss = float(np.sum((y_dm - np.mean(y_dm)) ** 2))
    r_squared = 1.0 - rss / tss if tss > 0 else 0.0

    # Clustered SEs (unit level)
    cluster_ids = df[unit_col].values
    se_clust, vcov = _clustered_se(X_dm2, residuals, cluster_ids)

    treatment_effect = float(beta[0])
    treatment_se = float(se_clust[0])

    # t-distribution with G-1 df (Cameron & Miller 2015)
    dof = n_units - 1
    t_stat = treatment_effect / treatment_se if treatment_se > 0 else 0.0
    pvalue = float(2 * (1 - stats.t.cdf(abs(t_stat), df=dof)))

    t_crit = float(stats.t.ppf(0.975, df=dof))
    ci_lower = treatment_effect - t_crit * treatment_se
    ci_upper = treatment_effect + t_crit * treatment_se

    return {
        'model': model_label,
        'treatment_effect': treatment_effect,
        'se': treatment_se,
        'pvalue': pvalue,
        't_stat': t_stat,
        'significant': pvalue < 0.05,
        'n_obs': n,
        'n_units': n_units,
        'n_periods': n_periods,
        'r_squared': r_squared,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'se_type': 'clustered (unit level)',
        'fe_type': 'Two-way fixed effects (unit + time)',
        'interpretation': (
            f"TWFE estimate: β = {treatment_effect:.4f} "
            f"(clustered SE: {treatment_se:.4f}, p = {pvalue:.4f}, "
            f"95% CI [{ci_lower:.4f}, {ci_upper:.4f}]). "
            f"{'Significant at 5%.' if pvalue < 0.05 else 'Not significant at 5%.'} "
            f"Unit and time fixed effects absorbed."
        )
    }


def run_diff_in_diff(data, outcome_col, treatment_col, time_col, unit_col):
    """
    Two-Way Fixed Effects DiD: Y_it = α_i + γ_t + β·Treatment_it + ε_it.

    β is the average treatment effect estimate.
    Standard errors clustered at the unit level.
    """
    try:
        return _twfe_core(data, outcome_col, treatment_col, time_col, unit_col, 'diff_in_diff')
    except Exception as e:
        return {'model': 'diff_in_diff', 'error': str(e)}


def run_panel_ols(data, outcome_col, treatment_col, time_col, unit_col):
    """
    Panel OLS with two-way fixed effects — for association questions.

    Same TWFE estimator as DiD but reported as a regression coefficient
    rather than a causal treatment effect.
    """
    try:
        return _twfe_core(data, outcome_col, treatment_col, time_col, unit_col, 'panel_ols')
    except Exception as e:
        return {'model': 'panel_ols', 'error': str(e)}


# ---------------------------------------------------------------------------
# Cross-sectional OLS
# ---------------------------------------------------------------------------

def run_ols(data, outcome_col, treatment_col):
    """
    Simple cross-sectional OLS: Y = α + β·X + ε.

    Used for association questions without a panel structure.
    Returns HC1-robust standard errors.
    """
    try:
        df = data[[outcome_col, treatment_col]].copy().dropna()
        df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
        df[treatment_col] = pd.to_numeric(df[treatment_col], errors='coerce')
        df = df.dropna()

        n = len(df)
        if n < 5:
            return {'model': 'ols', 'error': f'Too few observations ({n})'}

        y = df[outcome_col].values
        X = np.column_stack([np.ones(n), df[treatment_col].values])
        k = X.shape[1]

        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        fitted = X @ beta
        residuals = y - fitted

        rss = float(np.sum(residuals ** 2))
        tss = float(np.sum((y - np.mean(y)) ** 2))
        r_squared = 1.0 - rss / tss if tss > 0 else 0.0

        # HC1 robust variance (White 1980 with small-sample correction)
        meat = np.zeros((k, k))
        for i in range(n):
            xi = X[i:i+1].T
            meat += (residuals[i] ** 2) * (xi @ xi.T)
        correction = n / (n - k)
        bread = np.linalg.inv(X.T @ X)
        vcov_hc1 = correction * bread @ meat @ bread
        se = np.sqrt(np.clip(np.diag(vcov_hc1), 0, None))

        t_stats = beta / se
        pvalues = 2 * (1 - stats.t.cdf(np.abs(t_stats), df=n - k))

        slope = float(beta[1])
        slope_se = float(se[1])
        slope_pval = float(pvalues[1])
        ci_lower = slope - 1.96 * slope_se
        ci_upper = slope + 1.96 * slope_se

        return {
            'model': 'ols',
            'slope': slope,
            'intercept': float(beta[0]),
            'treatment_effect': slope,   # alias for unified reporting
            'se': slope_se,
            'pvalue': slope_pval,
            't_stat': float(t_stats[1]),
            'significant': slope_pval < 0.05,
            'n_obs': n,
            'r_squared': r_squared,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'se_type': 'HC1 robust',
            'interpretation': (
                f"OLS: slope = {slope:.4f} (HC1 SE: {slope_se:.4f}, "
                f"p = {slope_pval:.4f}, 95% CI [{ci_lower:.4f}, {ci_upper:.4f}]). "
                f"R² = {r_squared:.4f}. "
                f"{'Significant at 5%.' if slope_pval < 0.05 else 'Not significant.'}"
            )
        }
    except Exception as e:
        return {'model': 'ols', 'error': str(e)}


def run_pooled_ols(data, outcome_col, treatment_col):
    """Pooled OLS with HC1 robust standard errors."""
    result = run_ols(data, outcome_col, treatment_col)
    if 'error' in result:
        result['model'] = 'pooled_ols'
        return result
    result['model'] = 'pooled_ols'
    result['interpretation'] = result['interpretation'].replace('OLS:', 'Pooled OLS:')
    return result


def run_log_linear(data, outcome_col, treatment_col):
    """Semi-elasticity model: log(y) = alpha + beta*x + error."""
    try:
        df = data[[outcome_col, treatment_col]].copy().dropna()
        df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
        df[treatment_col] = pd.to_numeric(df[treatment_col], errors='coerce')
        df = df.dropna()
        df = df[df[outcome_col] > 0]
        n = len(df)
        if n < 5:
            return {'model': 'log_linear', 'error': f'Too few positive observations ({n})'}

        y = np.log(df[outcome_col].values)
        x = df[treatment_col].values
        X = np.column_stack([np.ones(n), x])
        result = _linear_regression_result('log_linear', y, X)
        semi_elasticity = 100 * (np.exp(result['effect']) - 1)
        result.update({
            'semi_elasticity_percent': float(semi_elasticity),
            'interpretation': (
                f"Log-linear model: a one-unit increase in {treatment_col} is "
                f"associated with an estimated {semi_elasticity:.2f}% change in "
                f"{outcome_col}."
            )
        })
        return result
    except Exception as e:
        return {'model': 'log_linear', 'error': str(e)}


def run_log_log(data, outcome_col, treatment_col):
    """Elasticity model: log(y) = alpha + beta*log(x) + error."""
    try:
        df = data[[outcome_col, treatment_col]].copy().dropna()
        df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
        df[treatment_col] = pd.to_numeric(df[treatment_col], errors='coerce')
        df = df.dropna()
        df = df[(df[outcome_col] > 0) & (df[treatment_col] > 0)]
        n = len(df)
        if n < 5:
            return {'model': 'log_log', 'error': f'Too few positive observations ({n})'}

        y = np.log(df[outcome_col].values)
        x = np.log(df[treatment_col].values)
        X = np.column_stack([np.ones(n), x])
        result = _linear_regression_result('log_log', y, X)
        result.update({
            'elasticity': result['effect'],
            'interpretation': (
                f"Log-log model: a 1% increase in {treatment_col} is associated "
                f"with an estimated {result['effect']:.3f}% change in {outcome_col}."
            )
        })
        return result
    except Exception as e:
        return {'model': 'log_log', 'error': str(e)}


def run_polynomial_ols(data, outcome_col, treatment_col, degree=2):
    """Quadratic OLS with marginal effect at the mean of x."""
    try:
        if degree != 2:
            return {'model': 'polynomial_ols', 'error': 'Only degree=2 is currently supported'}
        df = data[[outcome_col, treatment_col]].copy().dropna()
        df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
        df[treatment_col] = pd.to_numeric(df[treatment_col], errors='coerce')
        df = df.dropna()
        n = len(df)
        if n < 8:
            return {'model': 'polynomial_ols', 'error': f'Too few observations ({n})'}

        y = df[outcome_col].values
        x = df[treatment_col].values
        X = np.column_stack([np.ones(n), x, x ** 2])
        base = _linear_regression_result('polynomial_ols', y, X, main_index=1)

        beta = np.asarray(base['coefficients'])
        residuals = np.asarray(base['residuals'])
        vcov = _hc1_vcov(X, residuals)
        x_bar = float(np.mean(x))
        gradient = np.array([0.0, 1.0, 2.0 * x_bar])
        marginal = float(beta[1] + 2 * beta[2] * x_bar)
        marginal_se = float(np.sqrt(max(gradient @ vcov @ gradient, 0.0)))
        dof = max(n - X.shape[1], 1)
        t_stat = marginal / marginal_se if marginal_se > 0 else 0.0
        pvalue = float(2 * (1 - stats.t.cdf(abs(t_stat), df=dof)))
        t_crit = float(stats.t.ppf(0.975, df=dof))

        base.update({
            'effect': marginal,
            'slope': marginal,
            'treatment_effect': marginal,
            'se': marginal_se,
            'pvalue': pvalue,
            't_stat': t_stat,
            'ci_lower': marginal - t_crit * marginal_se,
            'ci_upper': marginal + t_crit * marginal_se,
            'x_mean': x_bar,
            'linear_term': float(beta[1]),
            'quadratic_term': float(beta[2]),
            'interpretation': (
                f"Quadratic OLS: marginal effect at mean {treatment_col} "
                f"({x_bar:.4f}) is {marginal:.4f}."
            )
        })
        return base
    except Exception as e:
        return {'model': 'polynomial_ols', 'error': str(e)}


def run_median_quantile(data, outcome_col, treatment_col):
    """Median (0.5 quantile) regression using least absolute deviations."""
    try:
        df = data[[outcome_col, treatment_col]].copy().dropna()
        df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
        df[treatment_col] = pd.to_numeric(df[treatment_col], errors='coerce')
        df = df.dropna()
        n = len(df)
        if n < 8:
            return {'model': 'median_quantile', 'error': f'Too few observations ({n})'}

        y = df[outcome_col].values
        x = df[treatment_col].values
        X = np.column_stack([np.ones(n), x])

        ols_start = np.linalg.lstsq(X, y, rcond=None)[0]

        def objective(beta):
            return np.sum(np.abs(y - X @ beta))

        opt = optimize.minimize(objective, ols_start, method='Nelder-Mead')
        beta = opt.x if opt.success else ols_start
        fitted = X @ beta
        residuals = y - fitted
        mad = float(np.median(np.abs(residuals - np.median(residuals))))
        robust_sigma = 1.4826 * mad if mad > 0 else float(np.std(residuals))
        bread = np.linalg.pinv(X.T @ X)
        se = np.sqrt(np.clip(np.diag(robust_sigma ** 2 * bread), 0, None))
        slope = float(beta[1])
        slope_se = float(se[1]) if len(se) > 1 else 0.0
        dof = max(n - X.shape[1], 1)
        t_stat = slope / slope_se if slope_se > 0 else 0.0
        pvalue = float(2 * (1 - stats.t.cdf(abs(t_stat), df=dof)))
        t_crit = float(stats.t.ppf(0.975, df=dof))
        pseudo_r1 = 1 - (np.sum(np.abs(residuals)) / np.sum(np.abs(y - np.median(y))))

        return {
            'model': 'median_quantile',
            'coefficients': [float(v) for v in beta],
            'intercept': float(beta[0]),
            'slope': slope,
            'treatment_effect': slope,
            'effect': slope,
            'se': slope_se,
            'pvalue': pvalue,
            't_stat': t_stat,
            'significant': pvalue < 0.05,
            'n_obs': n,
            'r_squared': float(pseudo_r1),
            'ci_lower': slope - t_crit * slope_se,
            'ci_upper': slope + t_crit * slope_se,
            'se_type': 'MAD approximation',
            'quantile': 0.5,
            'interpretation': (
                f"Median quantile regression: the median {outcome_col} changes by "
                f"{slope:.4f} for a one-unit increase in {treatment_col}."
            )
        }
    except Exception as e:
        return {'model': 'median_quantile', 'error': str(e)}


def run_entity_fixed_effects(data, outcome_col, treatment_col, unit_col):
    """Within-unit fixed effects regression with unit-clustered SEs."""
    try:
        df = data[[unit_col, outcome_col, treatment_col]].copy().dropna()
        df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
        df[treatment_col] = pd.to_numeric(df[treatment_col], errors='coerce')
        df = df.dropna()
        n = len(df)
        n_units = df[unit_col].nunique()
        if n < 8 or n_units < 2:
            return {'model': 'entity_fe', 'error': 'Need at least 8 observations and 2 units'}

        y_dm = df[outcome_col] - df.groupby(unit_col)[outcome_col].transform('mean')
        x_dm = df[treatment_col] - df.groupby(unit_col)[treatment_col].transform('mean')
        X = x_dm.values.reshape(-1, 1)
        y = y_dm.values
        if np.std(X) < 1e-10:
            return {'model': 'entity_fe', 'error': 'No within-unit variation in predictor'}

        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        residuals = y - X @ beta
        se, _ = _clustered_se(X, residuals, df[unit_col].values)
        effect = float(beta[0])
        effect_se = float(se[0])
        dof = n_units - 1
        t_stat = effect / effect_se if effect_se > 0 else 0.0
        pvalue = float(2 * (1 - stats.t.cdf(abs(t_stat), df=dof)))
        t_crit = float(stats.t.ppf(0.975, df=dof))
        tss = float(np.sum((y - np.mean(y)) ** 2))
        rss = float(np.sum(residuals ** 2))

        return {
            'model': 'entity_fe',
            'treatment_effect': effect,
            'effect': effect,
            'slope': effect,
            'se': effect_se,
            'pvalue': pvalue,
            't_stat': t_stat,
            'significant': pvalue < 0.05,
            'n_obs': n,
            'n_units': n_units,
            'r_squared': 1.0 - rss / tss if tss > 0 else 0.0,
            'ci_lower': effect - t_crit * effect_se,
            'ci_upper': effect + t_crit * effect_se,
            'se_type': 'clustered (unit level)',
            'fe_type': 'Entity fixed effects',
            'interpretation': (
                f"Entity fixed effects estimate: beta={effect:.4f}, "
                f"clustered SE={effect_se:.4f}, p={pvalue:.4f}."
            )
        }
    except Exception as e:
        return {'model': 'entity_fe', 'error': str(e)}


def run_time_fixed_effects(data, outcome_col, treatment_col, time_col):
    """Regression after absorbing common time effects."""
    try:
        df = data[[time_col, outcome_col, treatment_col]].copy().dropna()
        df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
        df[treatment_col] = pd.to_numeric(df[treatment_col], errors='coerce')
        df = df.dropna()
        n = len(df)
        if n < 8 or df[time_col].nunique() < 2:
            return {'model': 'time_fe', 'error': 'Need at least 8 observations and 2 time periods'}
        y_dm = df[outcome_col] - df.groupby(time_col)[outcome_col].transform('mean')
        x_dm = df[treatment_col] - df.groupby(time_col)[treatment_col].transform('mean')
        if float(np.std(x_dm)) < 1e-10:
            return {'model': 'time_fe', 'error': 'No variation after absorbing time effects'}
        result = _linear_regression_result(
            'time_fe',
            y_dm.values,
            x_dm.values.reshape(-1, 1),
            main_index=0,
            extra={'fe_type': 'Time fixed effects'},
        )
        result['interpretation'] = (
            f"Time fixed effects estimate: beta={result['effect']:.4f}, "
            f"p={result['pvalue']:.4f}."
        )
        return result
    except Exception as e:
        return {'model': 'time_fe', 'error': str(e)}


def run_first_difference(data, outcome_col, treatment_col, time_col, unit_col):
    """First-difference panel regression: Delta y on Delta x."""
    try:
        df = data[[unit_col, time_col, outcome_col, treatment_col]].copy().dropna()
        df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
        df[treatment_col] = pd.to_numeric(df[treatment_col], errors='coerce')
        df[time_col] = pd.to_numeric(df[time_col], errors='coerce')
        df = df.dropna().sort_values([unit_col, time_col])
        df['_dy'] = df.groupby(unit_col)[outcome_col].diff()
        df['_dx'] = df.groupby(unit_col)[treatment_col].diff()
        dfd = df.dropna(subset=['_dy', '_dx'])
        n = len(dfd)
        if n < 5:
            return {'model': 'first_difference', 'error': f'Too few differenced observations ({n})'}
        X = np.column_stack([np.ones(n), dfd['_dx'].values])
        result = _linear_regression_result(
            'first_difference',
            dfd['_dy'].values,
            X,
            main_index=1,
            extra={'fe_type': 'First differences'},
        )
        result['n_units'] = int(dfd[unit_col].nunique())
        result['interpretation'] = (
            f"First-difference estimate: beta={result['effect']:.4f}, "
            f"p={result['pvalue']:.4f}."
        )
        return result
    except Exception as e:
        return {'model': 'first_difference', 'error': str(e)}
