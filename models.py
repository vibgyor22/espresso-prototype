import pandas as pd
import numpy as np
from scipy import stats

def run_diff_in_diff(data, outcome_col, treatment_col, time_col, unit_col):
    """
    Run a difference-in-differences regression.
    
    Returns:
    - results: dict with coefficient, se, pvalue, interpretation
    """
    try:
        # Prepare data: ensure numeric columns
        df = data[[unit_col, time_col, outcome_col, treatment_col]].copy()
        df = df.dropna()
        
        # Convert to numeric
        df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
        df[treatment_col] = pd.to_numeric(df[treatment_col], errors='coerce')
        df[time_col] = pd.to_numeric(df[time_col], errors='coerce')
        df = df.dropna()
        
        # Create binary indicators for treatment
        # Check if treatment_col is already binary (0/1)
        unique_treatments = df[treatment_col].unique()
        if len(unique_treatments) == 2 and set(unique_treatments) == {0, 1}:
            # Already binary
            df['is_treated'] = df[treatment_col].astype(int)
        else:
            # Continuous: threshold at median
            treatment_median = df[treatment_col].median()
            df['is_treated'] = (df[treatment_col] > treatment_median).astype(int)
        
        # Find min and max time to define before/after
        min_time = df[time_col].min()
        max_time = df[time_col].max()
        mid_time = (min_time + max_time) / 2
        df['post'] = (df[time_col] > mid_time).astype(int)
        
        # Interaction term: treated × post
        df['treated_x_post'] = df['is_treated'] * df['post']
        
        # Simple OLS: outcome ~ 1 + is_treated + post + treated_x_post
        # The coefficient on treated_x_post is the treatment effect
        X = df[['is_treated', 'post', 'treated_x_post']].values
        X = np.column_stack([np.ones(len(X)), X])  # Add intercept
        y = df[outcome_col].values
        
        # Check for collinearity (rank deficiency)
        rank = np.linalg.matrix_rank(X)
        if rank < X.shape[1]:
            return {
                'model': 'diff_in_diff',
                'error': 'Perfect collinearity in design matrix (possibly constant treatment or time)'
            }
        
        # Solve OLS: β = (X'X)^-1 X'y
        try:
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
        except np.linalg.LinAlgError:
            return {
                'model': 'diff_in_diff',
                'error': 'Singular matrix - cannot invert X\'X'
            }
        
        # Residuals and standard errors
        residuals = y - X @ beta
        rss = np.sum(residuals ** 2)
        n = len(y)
        k = X.shape[1]
        
        if n <= k:
            return {
                'model': 'diff_in_diff',
                'error': f'Not enough observations ({n}) for {k} parameters'
            }
        
        mse = rss / (n - k)
        try:
            var_covar = mse * np.linalg.inv(X.T @ X)
            se = np.sqrt(np.diag(var_covar))
        except np.linalg.LinAlgError:
            return {
                'model': 'diff_in_diff',
                'error': 'Cannot invert variance-covariance matrix'
            }
        
        # t-stats and p-values (two-tailed)
        t_stat = beta / se
        pvalue = 2 * (1 - stats.t.cdf(np.abs(t_stat), n - k))
        
        # Treatment effect is coefficient on treated_x_post (index 3)
        treatment_effect = beta[3]
        treatment_se = se[3]
        treatment_pval = pvalue[3]
        
        return {
            'model': 'diff_in_diff',
            'treatment_effect': treatment_effect,
            'se': treatment_se,
            'pvalue': treatment_pval,
            't_stat': t_stat[3],
            'significant': treatment_pval < 0.05,
            'n_obs': n,
            'r_squared': 1 - (rss / np.sum((y - np.mean(y))**2)),
            'interpretation': (
                f"Treatment effect: {treatment_effect:.4f} "
                f"(SE: {treatment_se:.4f}, p: {treatment_pval:.4f}). "
                f"{'Statistically significant at 5% level.' if treatment_pval < 0.05 else 'Not statistically significant.'}"
            )
        }
    except Exception as e:
        return {'model': 'diff_in_diff', 'error': str(e)}


def run_arima(data, outcome_col, time_col, unit_col=None, forecast_periods=10):
    """
    Run ARIMA forecast on time series data.
    
    If unit_col is provided, aggregate to single time series first.
    
    Args:
        data: pandas DataFrame
        outcome_col: column name for the variable to forecast
        time_col: column name for time
        unit_col: optional column name for grouping units
        forecast_periods: number of periods to forecast (default: 10)
    
    Returns:
    - results: dict with forecast, fitted values, AIC, interpretation
    """
    try:
        # Simple AR(1) model if statsmodels not available
        # Prepare data: sort by time
        df = data[[time_col, outcome_col]].copy() if unit_col is None else data[[unit_col, time_col, outcome_col]].copy()
        df = df.dropna()
        
        # Convert to numeric
        df[outcome_col] = pd.to_numeric(df[outcome_col], errors='coerce')
        df[time_col] = pd.to_numeric(df[time_col], errors='coerce')
        df = df.dropna()
        
        # If multiple units, aggregate (average)
        if unit_col and unit_col in df.columns:
            df = df.groupby(time_col)[outcome_col].mean().reset_index()
        
        # Sort by time
        df = df.sort_values(time_col)
        y = df[outcome_col].values
        
        # Fit simple AR(1): y_t = c + a*y_{t-1} + e_t
        n = len(y)
        if n < 3:
            return {'model': 'arima', 'error': 'Insufficient data for ARIMA'}
        
        # Build design matrix for AR(1)
        X = np.column_stack([np.ones(n-1), y[:-1]])
        y_target = y[1:]
        
        # OLS fit
        beta = np.linalg.lstsq(X, y_target, rcond=None)[0]
        fitted = X @ beta
        residuals = y_target - fitted
        
        # AIC = 2*k - 2*ln(L) ≈ 2*k + n*ln(RSS/n) for normal errors
        rss = np.sum(residuals ** 2)
        aic = 2 * len(beta) + (n - 1) * np.log(rss / (n - 1))
        
        # Forecast multiple periods (dynamic based on request)
        forecasts = []
        last_y = y[-1]
        for h in range(1, forecast_periods + 1):
            if h == 1:
                forecast_h = beta[0] + beta[1] * last_y
            else:
                forecast_h = beta[0] + beta[1] * forecasts[-1]
            forecasts.append(forecast_h)
        
        # Time values for forecast
        time_values = df[time_col].values
        last_time = time_values[-1]
        forecast_times = [last_time + i for i in range(1, forecast_periods + 1)]
        
        return {
            'model': 'arima',
            'ar1_coef': beta[1],
            'intercept': beta[0],
            'forecast_next_period': forecasts[0],
            'forecasts': forecasts,
            'forecast_times': forecast_times,
            'historical_values': y.tolist(),
            'historical_times': time_values.tolist(),
            'aic': aic,
            'n_obs': n,
            'rmse': np.sqrt(np.mean(residuals ** 2)),
            'last_value': last_y,
            'interpretation': (
                f"AR(1) model fitted. Last observed value: {last_y:.4f}. "
                f"Forecast for next period: {forecasts[0]:.4f}. "
                f"AR(1) coefficient: {beta[1]:.4f} (implies {'mean-reverting' if beta[1] < 1 else 'explosive'} dynamics)."
            )
        }
    except Exception as e:
        return {'model': 'arima', 'error': str(e)}
