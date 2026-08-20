import pickle
import numpy as np
import pandas as pd
import pytest
import seaborn as sns
from seeq.addons import correlation
from seeq.addons.correlation import utils, _config
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
def test_correlation_heatmap(monkeypatch):
    # capture the matrix seaborn plots
    last = {}

    def capture_heatmap_data(*args, **kwargs):
        data = kwargs.get("data", args[0] if args else None)
        last["zsum"] = float(np.nansum(np.asarray(data)))
        return heatmap(*args, **kwargs)

    heatmap = sns.heatmap
    monkeypatch.setattr(sns, "heatmap", capture_heatmap_data)

    def assert_figure_heatmap(figure, array):
        assert isinstance(figure, str)
        assert last["zsum"] == pytest.approx(array.sum())

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
    df = test_common.df[:100].copy()
    # noinspection PyProtectedMember
    lags, coeffs = correlation.cross_corr_matrix_lagged(pickle.dumps(df), lags=5)

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
    html = correlation._heatmap._heatmap(test_common.df, max_time_shift='auto', output_values='coeffs',
                                         output_type='plot')
    assert isinstance(html, str)

    table = correlation.heatmap(test_common.df, max_time_shift='1h', output_values='time_shifts', output_type='table')
    assert isinstance(table, pd.DataFrame)


@pytest.mark.plots
@pytest.mark.unit
def test_python_plotter_heatmap_returns_plotly_envelope():
    envelope = correlation.python_plotter_heatmap(
        test_common.df,
        config={
            'maxTimeShift': 'none',
            'displayValues': 'coefficients',
            'timeOutputUnit': 'auto',
            'showValues': True,
        },
        width=900,
        height=500,
    )

    assert envelope['chartType'] == 'plotly'
    assert envelope['width'] == 900
    assert envelope['height'] == 500
    assert envelope['spec']['data'][0]['type'] == 'heatmap'
    assert np.asarray(envelope['spec']['data'][0]['z']).shape == (4, 4)
    assert envelope['spec']['layout']['title']['text'] == 'Correlation coefficients'


@pytest.mark.plots
@pytest.mark.unit
def test_python_plotter_request_uses_selected_signal_names():
    signal_ids = ['id-a', 'id-b', 'id-c', 'id-d']

    class FakeSpy:
        @staticmethod
        def search(signals, **kwargs):
            assert list(signals['ID']) == signal_ids
            return signals

        @staticmethod
        def pull(search, **kwargs):
            pulled = test_common.df.copy()
            pulled.columns = signal_ids
            return pulled

    body = {
        'start': 1546300800000,
        'end': 1546387200000,
        'signals': [
            {'id': signal_id, 'name': f'Signal {index}'}
            for index, signal_id in enumerate(signal_ids, start=1)
        ],
        'config': {'maxTimeShift': 'none'},
        'width': 800,
        'height': 450,
    }

    envelope = correlation.python_plotter_plot(body, FakeSpy)

    assert envelope['spec']['data'][0]['x'] == ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4']
    assert envelope['spec']['data'][0]['y'] == ['Signal 1', 'Signal 2', 'Signal 3', 'Signal 4']


@pytest.mark.unit
def test_python_plotter_request_requires_two_signals():
    with pytest.raises(ValueError, match='at least two signals'):
        correlation.python_plotter_plot(
            {'signals': [{'id': 'only-one'}]},
            spy_module=None,
        )


@pytest.mark.unit
@pytest.mark.utils
def test_cache_management():
    utils.clear_cache_all()
    pickled_df = pickle.dumps(test_common.df)
    # noinspection PyProtectedMember
    correlation.cross_corr_matrix_lagged(pickled_df, lags=100)
    # noinspection PyProtectedMember
    cache_info = correlation.cross_corr_matrix_lagged.cache_info()
    assert cache_info.hits == 0
    assert cache_info.misses == 1
    assert cache_info.current_size == 1
    # noinspection PyProtectedMember
    assert cache_info.max_size == _config._cache_max_items

    # call the function again and test it hit the cache this time
    # noinspection PyProtectedMember
    correlation.cross_corr_matrix_lagged(pickled_df, lags=100)
    # noinspection PyProtectedMember
    cache_info = correlation.cross_corr_matrix_lagged.cache_info()
    assert cache_info.hits == 1
    assert cache_info.misses == 1
    assert cache_info.current_size == 1

    # call the function again and change one parameter
    # noinspection PyProtectedMember
    correlation.cross_corr_matrix_lagged(pickled_df, lags=101)
    # noinspection PyProtectedMember
    cache_info = correlation.cross_corr_matrix_lagged.cache_info()
    assert cache_info.hits == 1
    assert cache_info.misses == 2
    assert cache_info.current_size == 2
