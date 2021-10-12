import pickle
import numpy as np
import pandas as pd
import plotly.graph_objs as go
import pytest
import seaborn as sns
from seeq.addons import correlation
from . import test_common


@pytest.mark.backend
@pytest.mark.unit
def test_cross_correlations():
    lags_results = np.array([[0, -18, -12, -6],
                             [18, 0, 11, -4],
                             [12, -11, 0, -13],
                             [6, 4, 13, 0]])

    coeffs_results = np.array([[1., -0.91670625, -0.897399, -0.90981232],
                               [-0.91670625, 1., 0.88829847, 0.98194075],
                               [-0.897399, 0.88829847, 1., 0.89063471],
                               [-0.90981232, 0.98194075, 0.89063471, 1.]])

    # noinspection PyProtectedMember
    lags, coeffs = correlation.cross_corr_matrix_lagged(pickle.dumps(test_common.df), lags=100)
    assert (lags == lags_results).all()
    assert np.allclose(coeffs, coeffs_results)


@pytest.mark.backend
@pytest.mark.unit
def test_lags_coeffs():
    lags, coeffs, sampling, time_unit, maxlags = correlation.lags_coeffs(test_common.df, '1min', 'auto')
    assert isinstance(lags, np.ndarray)
    assert isinstance(coeffs, np.ndarray)
    assert isinstance(sampling, float)
    assert lags.size == len(test_common.df.columns) ** 2
    assert coeffs.size == len(test_common.df.columns) ** 2


@pytest.mark.plots
@pytest.mark.unit
def test_correlation_heatmap():
    def assert_figure_heatmap(figure, array):
        assert isinstance(figure, go.Figure)
        assert isinstance(figure.data[0], go.Heatmap)
        assert isinstance(figure.layout, go.Layout)
        assert figure.data[0].z.sum() == array.sum()

    sampling_rate = 20
    time_unit = 'seconds'

    # noinspection PyProtectedMember
    lags, coeffs = correlation.cross_corr_matrix_lagged(pickle.dumps(test_common.df), lags=100)
    time_shifts = lags * sampling_rate
    coeffs_df = pd.DataFrame(data=coeffs, columns=test_common.df.columns, index=test_common.df.columns)
    time_shifts_df = pd.DataFrame(data=time_shifts, columns=test_common.df.columns, index=test_common.df.columns)
    # noinspection PyProtectedMember
    fig = correlation._heatmap_plot(pickle.dumps(coeffs_df), pickle.dumps(time_shifts_df), time_unit)
    assert_figure_heatmap(fig, coeffs)

    # noinspection PyProtectedMember
    coeffs_raw = correlation.cross_corr_matrix_raw(pickle.dumps(test_common.df))
    coeffs_raw_df = pd.DataFrame(data=coeffs_raw, columns=test_common.df.columns, index=test_common.df.columns)
    # noinspection PyProtectedMember
    fig = correlation._heatmap_plot(pickle.dumps(coeffs_raw_df), pickle.dumps(time_shifts_df), time_unit)
    assert_figure_heatmap(fig, coeffs_raw)

    zero_lags = np.zeros((len(test_common.df.columns), len(test_common.df.columns)))
    zero_lags_df = pd.DataFrame(data=zero_lags, columns=test_common.df.columns, index=test_common.df.columns)
    # noinspection PyProtectedMember
    fig = correlation._heatmap_plot(pickle.dumps(zero_lags_df), pickle.dumps(time_shifts_df), time_unit)
    assert_figure_heatmap(fig, zero_lags)

    # noinspection PyProtectedMember
    fig = correlation._heatmap_plot(pickle.dumps(time_shifts_df), pickle.dumps(coeffs_df), time_unit, lags_plot=True)
    assert_figure_heatmap(fig, time_shifts)


@pytest.mark.plots
@pytest.mark.unit
def test_pair_plot():
    target = 'signal1'
    df = test_common.df[:100].copy()
    # noinspection PyProtectedMember
    lags, coeffs = correlation.cross_corr_matrix_lagged(pickle.dumps(df), lags=5)
    idx = list(df.columns).index(target)

    # noinspection PyProtectedMember
    figure = correlation._pairplot._contour_matrix_diag_hist_static(pickle.dumps(df))
    assert isinstance(figure, sns.PairGrid)
    assert figure.square_grid
    assert set(figure.x_vars) == set(df.columns)
    assert set(figure.y_vars) == set(df.columns)

    # noinspection PyProtectedMember
    fig_lagged = correlation._pairplot._contour_matrix_diag_hist_static(pickle.dumps(test_common.df),
                                                                        pickle.dumps(lags))
    assert isinstance(figure, sns.PairGrid)
    assert fig_lagged.square_grid
    assert set(fig_lagged.x_vars) == set(test_common.df.columns)
    assert set(fig_lagged.y_vars) == set(test_common.df.columns)


@pytest.mark.plots
@pytest.mark.unit
def test_heatmap_wrapper():
    fig = correlation._heatmap._heatmap(test_common.df, max_time_shift='auto', output_values='coeffs',
                                        output_type='plot')
    assert isinstance(fig, go.Figure)
    assert isinstance(fig.data[0], go.Heatmap)
    assert isinstance(fig.layout, go.Layout)

    table = correlation.heatmap(test_common.df, max_time_shift='1h', output_values='time_shifts', output_type='table')
    assert isinstance(table, pd.DataFrame)

