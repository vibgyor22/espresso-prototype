"""
Core unit tests for Espresso.

Run with: python -m pytest tests/ -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
try:
    import pytest
except ImportError:
    # Allow running without pytest installed
    class pytest:
        @staticmethod
        def main(args): pass


# ---------------------------------------------------------------------------
# data_utils
# ---------------------------------------------------------------------------

from data_utils import is_panel_data, treatment_varies, get_year_columns, get_column_samples


def _make_panel():
    """Simple balanced panel: 3 units × 4 periods."""
    return pd.DataFrame({
        'unit':    ['A', 'A', 'A', 'A', 'B', 'B', 'B', 'B', 'C', 'C', 'C', 'C'],
        'year':    [2000, 2001, 2002, 2003] * 3,
        'outcome': np.random.randn(12),
        'treat':   [0, 0, 1, 1,  0, 0, 0, 0,  0, 0, 0, 0],
    })


class TestDataUtils:
    def test_is_panel_data_valid(self):
        df = _make_panel()
        assert is_panel_data(df, 'unit', 'year') is True

    def test_is_panel_data_missing_col(self):
        df = _make_panel()
        assert is_panel_data(df, 'unit', 'nonexistent') is False

    def test_is_panel_data_none(self):
        df = _make_panel()
        assert is_panel_data(df, None, 'year') is False

    def test_treatment_varies_true(self):
        df = _make_panel()
        assert treatment_varies(df, 'treat', 'unit')   # bool-ish truthy

    def test_treatment_varies_constant(self):
        df = _make_panel()
        df['treat'] = 0  # constant — never changes
        assert not treatment_varies(df, 'treat', 'unit')

    def test_get_year_columns(self):
        df = pd.DataFrame({'country': ['A'], '2000': [1], '2010': [2], 'indicator': ['X']})
        years = get_year_columns(df)
        assert '2000' in years and '2010' in years
        assert 'country' not in years and 'indicator' not in years

    def test_get_column_samples_returns_strings(self):
        df = pd.DataFrame({'x': [1, 2, 3], 'y': ['a', 'b', 'a']})
        samples = get_column_samples(df, n=3)
        assert all(isinstance(v, str) for v in samples['x'])
        assert all(isinstance(v, str) for v in samples['y'])


# ---------------------------------------------------------------------------
# selector
# ---------------------------------------------------------------------------

from selector import select_admissible_models
from model_specs import MODEL_SPECS


class TestSelector:
    def _base_intent(self):
        return {
            'question_type': 'causal_effect',
            'outcome': 'outcome',
            'treatment': 'treat',
            'unit': 'unit',
            'time': 'year',
        }

    def test_did_valid(self):
        df = _make_panel()
        intent = self._base_intent()
        valid, rejected = select_admissible_models(intent, df)
        assert 'diff_in_diff' in valid
        assert 'diff_in_diff' not in rejected

    def test_did_missing_field(self):
        df = _make_panel()
        intent = self._base_intent()
        intent['treatment'] = None
        valid, rejected = select_admissible_models(intent, df)
        assert 'diff_in_diff' not in valid
        assert 'diff_in_diff' in rejected

    def test_did_constant_treatment(self):
        df = _make_panel()
        df['treat'] = 0
        intent = self._base_intent()
        valid, rejected = select_admissible_models(intent, df)
        assert 'diff_in_diff' not in valid
        assert 'diff_in_diff' in rejected

    def test_forecast_selects_arima(self):
        df = _make_panel()
        intent = {'question_type': 'forecast', 'outcome': 'outcome', 'time': 'year'}
        valid, _ = select_admissible_models(intent, df)
        assert 'arima' in valid

    def test_association_panel_prefers_panel_ols(self):
        df = _make_panel()
        intent = {
            'question_type': 'association',
            'outcome': 'outcome',
            'treatment': 'treat',
            'unit': 'unit',
            'time': 'year',
        }
        valid, _ = select_admissible_models(intent, df)
        assert 'panel_ols' in valid
        # panel_ols should come before ols
        if 'ols' in valid:
            assert valid.index('panel_ols') < valid.index('ols')

    def test_association_no_panel_uses_ols(self):
        # Cross-section: no unit/time columns
        df = pd.DataFrame({'outcome': np.random.randn(50), 'treat': np.random.randn(50)})
        intent = {
            'question_type': 'association',
            'outcome': 'outcome',
            'treatment': 'treat',
            'unit': None,
            'time': None,
        }
        valid, _ = select_admissible_models(intent, df)
        assert 'ols' in valid
        assert 'panel_ols' not in valid

    def test_unknown_question_type(self):
        df = _make_panel()
        valid, rejected = select_admissible_models({'question_type': 'unknown'}, df)
        assert valid == []
        assert 'error' in rejected

    def test_registry_has_at_least_ten_models(self):
        assert len(MODEL_SPECS) >= 10


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

from models import (
    run_arima,
    run_diff_in_diff,
    run_entity_fixed_effects,
    run_exp_smoothing,
    run_first_difference,
    run_linear_trend,
    run_log_linear,
    run_log_log,
    run_median_quantile,
    run_ols,
    run_panel_ols,
    run_polynomial_ols,
    run_pooled_ols,
    run_random_walk,
    run_time_fixed_effects,
)


class TestARIMA:
    def _ts(self, n=30):
        t = np.arange(n, dtype=float)
        y = 2.0 + 0.5 * t + np.random.randn(n) * 0.5
        return pd.DataFrame({'year': 2000 + t, 'value': y})

    def test_returns_forecasts(self):
        df = self._ts()
        result = run_arima(df, 'value', 'year', forecast_periods=5)
        assert 'error' not in result
        assert len(result['forecasts']) == 5
        assert len(result['forecast_times']) == 5

    def test_ci_bands_present(self):
        df = self._ts(30)
        result = run_arima(df, 'value', 'year', forecast_periods=5)
        assert 'error' not in result
        assert 'ci_lower' in result and 'ci_upper' in result
        assert len(result['ci_lower']) == 5

    def test_insufficient_data(self):
        df = pd.DataFrame({'year': [2000, 2001], 'value': [1.0, 2.0]})
        result = run_arima(df, 'value', 'year')
        assert 'error' in result

    def test_arima_order_field(self):
        df = self._ts(40)
        result = run_arima(df, 'value', 'year', forecast_periods=3)
        assert 'arima_order' in result
        assert isinstance(result['arima_order'], tuple)
        assert len(result['arima_order']) == 3


class TestForecastModels:
    def _ts(self, n=20):
        t = np.arange(n, dtype=float)
        y = 10 + 0.7 * t + np.sin(t / 2)
        return pd.DataFrame({'year': 2000 + t, 'value': y})

    def test_linear_trend_forecast(self):
        result = run_linear_trend(self._ts(), 'value', 'year', forecast_periods=4)
        assert 'error' not in result
        assert len(result['forecasts']) == 4

    def test_exp_smoothing_forecast(self):
        result = run_exp_smoothing(self._ts(), 'value', 'year', forecast_periods=4)
        assert 'error' not in result
        assert len(result['forecasts']) == 4

    def test_random_walk_forecast(self):
        result = run_random_walk(self._ts(), 'value', 'year', forecast_periods=4)
        assert 'error' not in result
        assert result['forecasts'][0] == result['last_value']


class TestDiffInDiff:
    def test_basic_effect(self):
        np.random.seed(42)
        df = _make_panel()
        # Add a clear treatment effect
        df['outcome'] = df['outcome'] + df['treat'] * 5.0
        result = run_diff_in_diff(df, 'outcome', 'treat', 'year', 'unit')
        assert 'error' not in result
        assert 'treatment_effect' in result
        assert 'pvalue' in result
        assert 'ci_lower' in result and 'ci_upper' in result

    def test_se_type_clustered(self):
        df = _make_panel()
        result = run_diff_in_diff(df, 'outcome', 'treat', 'year', 'unit')
        assert 'error' not in result
        assert 'clustered' in result.get('se_type', '').lower()

    def test_fe_type(self):
        df = _make_panel()
        result = run_diff_in_diff(df, 'outcome', 'treat', 'year', 'unit')
        assert 'error' not in result
        assert 'two-way' in result.get('fe_type', '').lower()

    def test_too_few_obs(self):
        df = pd.DataFrame({'unit': ['A'], 'year': [2000], 'outcome': [1.0], 'treat': [0.0]})
        result = run_diff_in_diff(df, 'outcome', 'treat', 'year', 'unit')
        assert 'error' in result


class TestPanelOLS:
    def test_returns_coefficient(self):
        df = _make_panel()
        result = run_panel_ols(df, 'outcome', 'treat', 'year', 'unit')
        assert 'error' not in result
        assert 'treatment_effect' in result

    def test_model_label(self):
        df = _make_panel()
        result = run_panel_ols(df, 'outcome', 'treat', 'year', 'unit')
        assert result.get('model') == 'panel_ols'


class TestOLS:
    def test_slope_and_pvalue(self):
        np.random.seed(0)
        n = 100
        x = np.random.randn(n)
        y = 2.0 + 3.0 * x + np.random.randn(n) * 0.5
        df = pd.DataFrame({'y': y, 'x': x})
        result = run_ols(df, 'y', 'x')
        assert 'error' not in result
        assert abs(result['slope'] - 3.0) < 0.5  # should be close to 3
        assert result['pvalue'] < 0.001           # clearly significant
        assert 'ci_lower' in result and 'ci_upper' in result

    def test_hc1_se_type(self):
        df = pd.DataFrame({'y': np.random.randn(50), 'x': np.random.randn(50)})
        result = run_ols(df, 'y', 'x')
        assert 'hc1' in result.get('se_type', '').lower()

    def test_too_few_obs(self):
        df = pd.DataFrame({'y': [1.0, 2.0], 'x': [1.0, 2.0]})
        result = run_ols(df, 'y', 'x')
        assert 'error' in result


class TestAdditionalEconometricModels:
    def _cross_section(self, n=80):
        np.random.seed(123)
        x = np.linspace(1, 10, n)
        y = 5 + 2 * x + 0.2 * x ** 2 + np.random.randn(n)
        return pd.DataFrame({'y': y, 'x': x})

    def _panel(self):
        rows = []
        for unit in ['A', 'B', 'C', 'D']:
            unit_effect = ord(unit) - ord('A')
            for year in range(2000, 2008):
                x = (year - 1999) + unit_effect
                y = unit_effect + 1.5 * x + 0.1 * (year - 2000)
                rows.append({'unit': unit, 'year': year, 'y': y, 'x': x})
        return pd.DataFrame(rows)

    def test_pooled_ols(self):
        result = run_pooled_ols(self._cross_section(), 'y', 'x')
        assert 'error' not in result
        assert result['model'] == 'pooled_ols'

    def test_log_linear(self):
        result = run_log_linear(self._cross_section(), 'y', 'x')
        assert 'error' not in result
        assert 'semi_elasticity_percent' in result

    def test_log_log(self):
        result = run_log_log(self._cross_section(), 'y', 'x')
        assert 'error' not in result
        assert 'elasticity' in result

    def test_polynomial_ols(self):
        result = run_polynomial_ols(self._cross_section(), 'y', 'x')
        assert 'error' not in result
        assert 'quadratic_term' in result

    def test_median_quantile(self):
        result = run_median_quantile(self._cross_section(), 'y', 'x')
        assert 'error' not in result
        assert result['quantile'] == 0.5

    def test_entity_fixed_effects(self):
        result = run_entity_fixed_effects(self._panel(), 'y', 'x', 'unit')
        assert 'error' not in result
        assert result['model'] == 'entity_fe'

    def test_time_fixed_effects(self):
        result = run_time_fixed_effects(self._panel(), 'y', 'x', 'year')
        assert 'error' not in result
        assert result['model'] == 'time_fe'

    def test_first_difference(self):
        result = run_first_difference(self._panel(), 'y', 'x', 'year', 'unit')
        assert 'error' not in result
        assert result['model'] == 'first_difference'


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------

from diagnostics import (
    check_stationarity, check_kpss, check_ljung_box,
    check_heteroscedasticity, check_normality_of_residuals,
    check_parallel_trends, run_arima_diagnostics, run_did_diagnostics
)


class TestDiagnostics:
    def test_stationarity_stationary(self):
        s = pd.Series(np.random.randn(50))
        result = check_stationarity(s)
        assert 'is_stationary' in result
        assert 'is_violated' in result

    def test_stationarity_nonstationary(self):
        # Random walk — almost certainly non-stationary
        rw = pd.Series(np.cumsum(np.random.randn(100)))
        result = check_stationarity(rw)
        assert 'is_stationary' in result

    def test_heteroscedasticity_fields(self):
        r = np.random.randn(50)
        yf = np.random.randn(50)
        result = check_heteroscedasticity(r, yf)
        assert 'is_violated' in result

    def test_normality_normal(self):
        result = check_normality_of_residuals(np.random.randn(200))
        assert 'is_violated' in result
        assert isinstance(result.get('is_violated'), (bool, np.bool_))

    def test_ljung_box_returns(self):
        r = np.random.randn(50)
        result = check_ljung_box(r)
        assert 'is_violated' in result

    def test_parallel_trends_fields(self):
        df = _make_panel()
        result = check_parallel_trends(df, 'outcome', 'treat', 'year', 'unit')
        assert 'is_violated' in result or 'error' in result

    def test_arima_diagnostics_structure(self):
        df = pd.DataFrame({
            'year': range(2000, 2030),
            'val': np.cumsum(np.random.randn(30))
        })
        result = run_arima_diagnostics(df, 'val', 'year')
        assert 'checks' in result
        assert 'violations' in result
        assert 'corrections' in result

    def test_did_diagnostics_structure(self):
        df = _make_panel()
        result = run_did_diagnostics(df, 'outcome', 'treat', 'year', 'unit')
        assert 'checks' in result
        assert 'violations' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
