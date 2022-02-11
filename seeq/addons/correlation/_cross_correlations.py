import pandas as pd
import numpy as np
import math
import dask
import pickle
import warnings
import itertools
from pandas.tseries.frequencies import to_offset
# There is a bug that prevents to correctly memorize a pandas.DataFrame
# Thus, all functions that use the @cached decorator need to accept serialized dataframes (pickle is a good option)
from memoization import cached
from ._config import _cache_max_items
from . import _validate_df


def _maxlags(df, sampling, max_time_shift):
    if max_time_shift == 'auto':
        return int(round(12 * (len(df) / 100.) ** (1 / 4.)))
    elif not max_time_shift:
        return None
    else:
        return math.ceil(pd.Timedelta(max_time_shift) / sampling)


def lags_coeffs(df, max_time_shift, time_output_unit):
    """
    Calculates the lags to maximize correlations between signals and the
    cross-correlation coefficients of the shifted signals. If max_time_shift
    is None, the lags are zero (raw data correlations with no time shift).
    This function also returns the sampling period of the signals, either
    inferring from the dataframe or using the property value attached to it

    Parameters
    ----------
    df: pandas.DataFrame
        A DataFrame that contains a set of signals as columns and date-time as
        the index. This function does not call the data preprocessor. Thus,
        make sure the data frame contains cleansed data
    max_time_shift: {'auto', str, None}, default 'auto' Maximum time
         (e.g. '15s', or '1min')  that the signals are allowed to slide in
         order to maximize cross-correlation. For times specified as a str,
         normal time units are accepted.If 'auto' is selected, a default
         maximum time shift is calculated based on the number of samples.
         If None, the raw signals are used and no time shifts are calculated.
    time_output_unit: {'auto', str} default 'auto'
        Specifies the time unit used to display the time shifts. Valid units
        are the ones accepted by pd.Timedelta

    Returns
    -------
    lags: array_like, 2d
        Lags to maximize cross correlations. Not to be confused with time
        shifts. This lags used the opposite sign as the typical convention.
    coeffs: array_like, 2d
        Cross-correlation coefficients for the lagged signals
    sampling: pd.Timedelta
        A pd.Timedelta with the grid of the data in the input DataFrame
    time_unit: str
        A str of a valid pd.Timedelta unit in which the
    maxlags: int
        Numbers of maximum allowable lags to maximize cross correlations


    Examples
    --------
    Get the cross-correlation coefficients and lag delays to maximize
    cross-correlations for a given DataFrame allowing for automatic guess of
    maximum time shifts

    >>> seeq.addons.correlation.lags_coeffs(df, max_time_shift='auto', time_output_unit='auto')

    Get the cross-correlation coefficients for a given DataFrame using the
    raw data (no time shift allowed)

    >>> seeq.addons.correlation.lags_coeffs(df, max_time_shift=None, time_output_unit='sec')

    """
    _validate_df(df)
    grid: float = pd.to_timedelta(to_offset(pd.infer_freq(df.index))).total_seconds()
    sampling = pd.Timedelta(f'{grid}s')

    if not df.spy.grid:
        df.spy.grid = f'{grid}s'
    else:
        grid_old = df.spy.grid
        sampling_old = pd.Timedelta(df.spy.grid)
        if sampling != sampling_old:
            df.spy.grid = f'{grid}s'
            warnings.warn(
                f"DataFrame had a grid property of {grid_old} which is different from the inferred grid period"
                f"of {df.spy.grid}. The grid property has been overwritten. Please double check DataFrame "
                f"for data integrity")

    maxlags = _maxlags(df, sampling, max_time_shift)
    if not maxlags:
        coeffs = cross_corr_matrix_raw(pickle.dumps(df))
        lags = np.zeros((len(df.columns), len(df.columns)))
    else:
        lags, coeffs = cross_corr_matrix_lagged(pickle.dumps(df), lags=int(maxlags))

    time_unit = sampling_in_specified_units(lags, sampling, time_output_unit)
    sampling_time = sampling.total_seconds() / pd.Timedelta(**{time_unit: 1}).total_seconds()
    return lags, coeffs, sampling_time, time_unit, maxlags


def sampling_in_specified_units(lags, sampling, time_output_unit):
    if time_output_unit == 'auto':
        max_abs_shift = np.abs(lags * sampling.total_seconds()).max()  # this is in seconds
        if max_abs_shift > 86400:
            time_output_unit = 'days'
        elif max_abs_shift > 3600:
            time_output_unit = 'hours'
        elif max_abs_shift > 60:
            time_output_unit = 'minutes'
        else:
            time_output_unit = 'seconds'

    if time_output_unit.lower() in ['w', 'week', 'weeks']:
        time_output_unit = 'weeks'
    if time_output_unit.lower() in ['d', 'day', 'days']:
        time_output_unit = 'days'
    if time_output_unit.lower() in ['h', 'hr', 'hrs', 'hour', 'hours']:
        time_output_unit = 'hours'
    if time_output_unit.lower() in ['min', 'minute', 'minutes']:
        time_output_unit = 'minutes'
    if time_output_unit.lower() in ['s', 'sec', 'second', 'seconds']:
        time_output_unit = 'seconds'

    return time_output_unit


def array_shifter(arr, lag):
    if lag > 0:
        return arr[:-lag]
    elif lag < 0:
        return arr[-lag:]
    else:
        return arr


@dask.delayed
def cross_corr_target(lags, pair):
    """
    This function calculates the lag that gives the best correlation between
    two signals. The second item in the pair of signals is the one that is
    slided in time.

    Parameters
    ----------
    lags: float
        Max number of lags that signal B can be shifted.
    pair: tuple
        Two arrays of signals.

    Returns
    -------
        (lags, coefficients): tuple

    """

    def cross_corr_lagged(first_signal, second_signal, lag=0):
        first_signal_adj = array_shifter(first_signal, -lag)
        second_signal_lagged = array_shifter(second_signal, lag)
        return np.corrcoef(first_signal_adj, second_signal_lagged)[0, 1]

    signal_a = pair[0]
    signal_b = pair[1]
    coeffs = [cross_corr_lagged(signal_a, signal_b, lag=lag) for lag in range(-int(lags), int(lags + 1))]
    max_corr_lag = range(-int(lags), int(lags + 1))[int(np.argmax(np.abs(coeffs)))]
    max_corr_coeff = coeffs[int(np.argmax(np.abs(coeffs)))]

    return max_corr_lag, max_corr_coeff


@cached(max_size=_cache_max_items)
def cross_corr_matrix_raw(df_serialized):
    """
    Returns the matrix of correlation coefficients for the set of signals.

    Parameters
    ----------
    df_serialized: bytes
        A pickled pd.DataFrame with the signals to cross correlate.

    Returns
    -------
        coefficients_matrix: np.array

    Notes
    ------
    This function requires the input pd.DataFrame to be pickled to take
    advantage of the caching functionality.

    """
    df = pickle.loads(df_serialized)
    return np.corrcoef(df, rowvar=False)


@cached(max_size=_cache_max_items)
def cross_corr_matrix_lagged(df_serialized, lags=100):
    """
    Returns the matrix of lags and coefficients for best cross correlation.

    Parameters
    ----------
    df_serialized: bytes
        A pickled pd.DataFrame with the signals to cross correlate.
    lags: float
        Maximum number of lags to shift the signals.

    Returns
    -------
        (lags, coefficients): tuple

    Notes
    ------
    This function requires the input pd.DataFrame to be pickled to take
    advantage of the caching functionality.
    """

    df = pickle.loads(df_serialized)
    paramlist = list(itertools.product(df.columns, df.columns))
    pairs = [(df[x[0]].values, df[x[1]].values) for x in paramlist]

    cross_shifted_dask = [cross_corr_target(lags, pair) for pair in pairs]
    cross_shifted = dask.compute(*cross_shifted_dask)

    max_lags_shifted = np.array([item[0] for item in cross_shifted]).reshape(len(df.columns), len(df.columns))
    max_coeff_shifted = np.array([item[1] for item in cross_shifted]).reshape(len(df.columns), len(df.columns))
    return max_lags_shifted, max_coeff_shifted
