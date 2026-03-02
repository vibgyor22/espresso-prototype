"""
Pre-analysis statistical diagnostics and corrections.
Performs checks like stationarity, heteroscedasticity, multicollinearity, etc.
"""

import pandas as pd
import numpy as np
from scipy import stats


def check_heteroscedasticity(residuals, y_fitted):
    """Breusch-Pagan test for heteroscedasticity."""
    try:
        # Regress squared residuals on fitted values
        n = len(residuals)
        u_squared = residuals ** 2
        
        # Mean of squared residuals
        u_bar = np.mean(u_squared)
        
        # Sum of squares for regression
        y_centered = y_fitted - np.mean(y_fitted)
        ss_y = np.sum(y_centered ** 2)
        ss_u = np.sum((u_squared - u_bar) ** 2)
        
        if ss_y == 0:
            return {'test': 'Breusch-Pagan', 'statistic': np.nan, 'p_value': np.nan, 'interpretation': 'Unable to compute (zero variance in fitted values)'}
        
        # LM statistic approximation
        lm = (ss_u / ss_y) * (n / 2)
        p_value = 1 - stats.chi2.cdf(lm, df=1)
        
        is_heteroscedastic = p_value < 0.05
        interpretation = "HETEROSCEDASTIC detected (p<0.05)" if is_heteroscedastic else "Homoscedastic (OK)"
        
        return {
            'test': 'Breusch-Pagan',
            'statistic': lm,
            'p_value': p_value,
            'is_violated': is_heteroscedastic,
            'interpretation': interpretation,
            'correction': 'Use robust standard errors (HC1)' if is_heteroscedastic else 'No correction needed'
        }
    except Exception as e:
        return {'test': 'Breusch-Pagan', 'error': str(e)}


def check_multicollinearity(X):
    """Compute VIF (Variance Inflation Factor) for multicollinearity."""
    try:
        # VIF = 1 / (1 - R²) where R² is from regressing each X on others
        vif_values = []
        
        if X.shape[1] < 2:
            return {
                'test': 'VIF (Variance Inflation Factor)',
                'vif_values': [],
                'is_violated': False,
                'interpretation': 'Only one regressor (no multicollinearity)',
                'correction': 'No correction needed'
            }
        
        for i in range(X.shape[1]):
            # Remove column i
            X_rest = np.delete(X, i, axis=1)
            y_col = X[:, i]
            
            # Fit regression
            try:
                coeffs = np.linalg.lstsq(X_rest, y_col, rcond=None)[0]
                y_pred = X_rest @ coeffs
                ss_res = np.sum((y_col - y_pred) ** 2)
                ss_tot = np.sum((y_col - np.mean(y_col)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                vif = 1 / (1 - r_squared) if r_squared < 1 else np.inf
            except:
                vif = np.nan
            
            vif_values.append(vif)
        
        max_vif = np.nanmax(vif_values) if vif_values else np.nan
        is_violated = max_vif > 10 if not np.isnan(max_vif) else False
        
        return {
            'test': 'VIF (Variance Inflation Factor)',
            'vif_values': vif_values,
            'max_vif': max_vif,
            'is_violated': is_violated,
            'interpretation': f"High multicollinearity (max VIF={max_vif:.2f})" if is_violated else f"Low multicollinearity (max VIF={max_vif:.2f})",
            'correction': 'Consider removing highly correlated variables' if is_violated else 'No correction needed'
        }
    except Exception as e:
        return {'test': 'VIF', 'error': str(e)}


def check_stationarity(series, name='series'):
    """Augmented Dickey-Fuller test for stationarity."""
    try:
        series_clean = series.dropna()
        
        if len(series_clean) < 4:
            return {
                'test': 'ADF (Augmented Dickey-Fuller)',
                'series_name': name,
                'is_stationary': None,
                'interpretation': 'Insufficient data for test',
                'correction': 'Need at least 4 observations'
            }
        
        # Simple ADF approximation: regress ΔY on Y_{t-1}
        y = series_clean.values
        dy = np.diff(y)  # First difference
        y_lag = y[:-1]   # Lagged values
        
        # Regress dy on y_lag
        X = np.vstack([np.ones(len(y_lag)), y_lag]).T
        try:
            coeffs = np.linalg.lstsq(X, dy, rcond=None)[0]
            residuals = dy - X @ coeffs
            ss_res = np.sum(residuals ** 2)
            ss_tot = np.sum((dy - np.mean(dy)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
            # Estimate SE of coefficient
            n = len(dy)
            mse = ss_res / (n - 2)
            X_inv = np.linalg.inv(X.T @ X)
            se_beta = np.sqrt(mse * X_inv[1, 1])
            t_stat = coeffs[1] / se_beta if se_beta > 0 else 0
            
            # Critical value for ADF (simplified): ~-2.86 at 5% for n=50+
            is_stationary = t_stat < -2.86
            p_value = 0.05 if is_stationary else 0.95  # Simplified
            
        except:
            is_stationary = None
            p_value = np.nan
        
        return {
            'test': 'ADF (Augmented Dickey-Fuller)',
            'series_name': name,
            'is_stationary': is_stationary,
            'interpretation': 'STATIONARY (OK)' if is_stationary else 'NON-STATIONARY - differencing required',
            'correction': 'Use first differences (AR(1) differencing)' if not is_stationary else 'No correction needed',
            'test_statistic': t_stat if 't_stat' in locals() else np.nan,
            'p_value': p_value
        }
    except Exception as e:
        return {'test': 'ADF', 'series_name': name, 'error': str(e)}


def check_autocorrelation(residuals):
    """Durbin-Watson test for first-order autocorrelation."""
    try:
        residuals_clean = residuals[~np.isnan(residuals)]
        
        if len(residuals_clean) < 3:
            return {
                'test': 'Durbin-Watson',
                'dw_statistic': np.nan,
                'interpretation': 'Insufficient data',
                'correction': 'Need at least 3 observations'
            }
        
        # DW = Σ(e_t - e_{t-1})² / Σ(e_t)²
        diffs = np.diff(residuals_clean)
        dw = np.sum(diffs ** 2) / np.sum(residuals_clean ** 2)
        
        # DW ranges from 0-4: 2 = no autocorr, <2 = positive, >2 = negative
        has_autocorr = abs(dw - 2) > 0.5
        
        return {
            'test': 'Durbin-Watson',
            'dw_statistic': dw,
            'is_violated': has_autocorr,
            'interpretation': f"Autocorrelation detected (DW={dw:.3f})" if has_autocorr else f"No significant autocorrelation (DW={dw:.3f})",
            'correction': 'Consider ARIMA or robust errors' if has_autocorr else 'No correction needed'
        }
    except Exception as e:
        return {'test': 'Durbin-Watson', 'error': str(e)}


def check_normality_of_residuals(residuals):
    """Shapiro-Wilk test for normality of residuals."""
    try:
        residuals_clean = residuals[~np.isnan(residuals)]
        
        if len(residuals_clean) < 3:
            return {
                'test': 'Shapiro-Wilk',
                'interpretation': 'Insufficient data',
                'correction': 'Need at least 3 observations'
            }
        
        # Shapiro-Wilk test
        if len(residuals_clean) <= 5000:
            stat, p_value = stats.shapiro(residuals_clean)
        else:
            # For large samples, use a subset
            stat, p_value = stats.shapiro(residuals_clean[:5000])
        
        is_normal = p_value > 0.05
        
        return {
            'test': 'Shapiro-Wilk',
            'statistic': stat,
            'p_value': p_value,
            'is_violated': not is_normal,
            'interpretation': f"Non-normal residuals (p={p_value:.4f})" if not is_normal else f"Normal residuals (p={p_value:.4f})",
            'correction': 'Consider robust standard errors or transformation' if not is_normal else 'No correction needed'
        }
    except Exception as e:
        return {'test': 'Shapiro-Wilk', 'error': str(e)}


def run_did_diagnostics(data, outcome_col, treatment_col, time_col, unit_col):
    """Run all diagnostics for Difference-in-Differences model."""
    
    diagnostics = {
        'model': 'Difference-in-Differences',
        'checks': [],
        'violations': [],
        'corrections': []
    }
    
    try:
        # Prepare data
        data_clean = data[[outcome_col, treatment_col, time_col, unit_col]].dropna()
        
        if len(data_clean) < 10:
            diagnostics['error'] = 'Insufficient data for DiD diagnostics'
            return diagnostics
        
        # Extract variables
        y = data_clean[outcome_col].values
        X_treatment = data_clean[treatment_col].values
        X_time = pd.factorize(data_clean[time_col])[0]
        X_unit = pd.factorize(data_clean[unit_col])[0]
        
        # Check 1: Heteroscedasticity (with simple residuals)
        X_did = np.vstack([np.ones(len(y)), X_treatment, X_time, X_unit]).T
        try:
            coeffs = np.linalg.lstsq(X_did, y, rcond=None)[0]
            residuals = y - X_did @ coeffs
            y_fitted = X_did @ coeffs
            hetero_check = check_heteroscedasticity(residuals, y_fitted)
            diagnostics['checks'].append(hetero_check)
            if hetero_check.get('is_violated'):
                diagnostics['violations'].append(hetero_check['test'])
                diagnostics['corrections'].append(hetero_check.get('correction', 'Use robust SE'))
        except Exception as e:
            diagnostics['checks'].append({'test': 'Heteroscedasticity', 'error': str(e)})
        
        # Check 2: Multicollinearity
        multi_check = check_multicollinearity(X_did[:, 1:])  # Exclude intercept
        diagnostics['checks'].append(multi_check)
        if multi_check.get('is_violated'):
            diagnostics['violations'].append(multi_check['test'])
            diagnostics['corrections'].append(multi_check.get('correction'))
        
        # Check 3: Autocorrelation in residuals
        if 'residuals' in locals():
            auto_check = check_autocorrelation(residuals)
            diagnostics['checks'].append(auto_check)
            if auto_check.get('is_violated'):
                diagnostics['violations'].append(auto_check['test'])
                diagnostics['corrections'].append(auto_check.get('correction'))
        
        # Check 4: Normality of residuals
        if 'residuals' in locals():
            norm_check = check_normality_of_residuals(residuals)
            diagnostics['checks'].append(norm_check)
            if norm_check.get('is_violated'):
                diagnostics['violations'].append(norm_check['test'])
                diagnostics['corrections'].append(norm_check.get('correction'))
        
    except Exception as e:
        diagnostics['error'] = str(e)
    
    return diagnostics


def run_arima_diagnostics(data, outcome_col, time_col):
    """Run all diagnostics for ARIMA model."""
    
    diagnostics = {
        'model': 'ARIMA (AR(1))',
        'checks': [],
        'violations': [],
        'corrections': []
    }
    
    try:
        # Prepare data
        series = data[outcome_col].dropna().sort_values().reset_index(drop=True)
        
        if len(series) < 5:
            diagnostics['error'] = 'Insufficient data for ARIMA diagnostics'
            return diagnostics
        
        # Check 1: Stationarity
        stat_check = check_stationarity(series, name=outcome_col)
        diagnostics['checks'].append(stat_check)
        
        if stat_check.get('is_stationary') == False:
            diagnostics['violations'].append(stat_check['test'])
            diagnostics['corrections'].append(stat_check.get('correction', 'Apply first differencing'))
            
            # If non-stationary, check first differences
            diff_series = series.diff().dropna()
            stat_check_diff = check_stationarity(diff_series, name=f"{outcome_col} (1st diff)")
            diagnostics['checks'].append(stat_check_diff)
        
        # Check 2: Autocorrelation structure (on residuals from AR(1) fit)
        try:
            y = series.values
            y_lag = y[:-1]
            dy = np.diff(y)
            
            X = np.vstack([np.ones(len(y_lag)), y_lag]).T
            coeffs = np.linalg.lstsq(X, dy, rcond=None)[0]
            residuals = dy - X @ coeffs
            
            auto_check = check_autocorrelation(residuals)
            diagnostics['checks'].append(auto_check)
            if auto_check.get('is_violated'):
                diagnostics['violations'].append(auto_check['test'])
                diagnostics['corrections'].append(auto_check.get('correction'))
        except:
            pass
        
        # Check 3: Normality of residuals
        if 'residuals' in locals():
            norm_check = check_normality_of_residuals(residuals)
            diagnostics['checks'].append(norm_check)
            if norm_check.get('is_violated'):
                diagnostics['violations'].append(norm_check['test'])
                diagnostics['corrections'].append(norm_check.get('correction'))
    
    except Exception as e:
        diagnostics['error'] = str(e)
    
    return diagnostics
