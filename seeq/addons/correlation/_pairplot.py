import pickle
import pandas as pd
from numpy.linalg.linalg import LinAlgError
import seaborn as sns
from matplotlib.colors import ListedColormap
from matplotlib import pyplot as plt
# There is a bug that prevents to correctly memorize a pandas.DataFrame
# Thus, all functions that use the @cached decorator need to accept serialized dataframes (pickle is a good option)
from memoization import cached
from ._config import _cache_max_items
from . import lags_coeffs
from . import default_preprocessing_wrapper


def pairplot(df, max_time_shift='auto', bypass_preprocessing=False):
    """
    Creates a n x n matrix of static plots for the n-signals in the input
    dataframe with histograms in the diagonal of the matrix and density
    contour plots in the off-diagonal locations.

    The signals can be allowed to slide among each other to find the best
    cross-correlation between signals.

    Parameters
    ----------
    df: pandas.DataFrame
        A DataFrame that contains a set of signals as columns and date-time as
        the index.
    max_time_shift: {'auto', str, None}, default 'auto'
        Maximum time (e.g. '15s', or '1min') that the signals are allowed to
        slide in order to maximize cross-correlation. For times specified as a
        str, normal time units are accepted. If 'auto' is selected, a default
        maximum time shift is calculated based on the number of samples. If None,
        the raw signals are used and no time shifts are calculated.
    bypass_preprocessing: bool, default False
        Whether the data pre-processing routine is by-passed or not. Setting it
        to True is not recommended unless the data has been pre-processed
        elsewhere.

    Returns
    -------
    -: None
        Displays a Plotly figure in Seeq DataLab with plots arrange in a n x n
        matrix.


    Examples
    --------
    Create a plot matrix plot from the signals in the DataFrame allowing for
    automatic guess of maximum time shifts

    >>> seeq.addons.correlation.pairplot(df, max_time_shift='auto')

    Create a plot matrix plot from the signals in the DataFrame specifying a
    maximum time shift
    between signals of 1 hour

    >>> seeq.addons.correlation.pairplot(df, max_time_shift='1h')

    Create a plot matrix plot from the signals in the DataFrame using the raw
    data (no time shift allowed)

    >>> seeq.addons.correlation.pairplot(df, max_time_shift=None)

    """

    df = default_preprocessing_wrapper(df, bypass_processing=bypass_preprocessing)
    if max_time_shift is None:
        lags = None
    else:
        lags, coeffs, sampling_time, time_unit, maxlags = lags_coeffs(df, max_time_shift, 's')
    _contour_matrix_diag_hist_static(pickle.dumps(df), lags_array_serialized=pickle.dumps(lags))


@cached(max_size=_cache_max_items)
def _contour_matrix_diag_hist_static(df_serialized, lags_array_serialized=None):
    """
    This functions generates a contour plot matrix with diagonal histograms.
    If a lags_array is provided, the signal in the x axis (of every subplot) will be shifted by the
    number of lags specified in lags_array

    :param signals_df: [dataframe] signals to plot
    :param width: [int] size of the output figure in pixels
    :param lags_array: [array] matrix (n x n) with the number of lags signals should be slided
    :return: [obj] plotly figure object

    """
    signals_df = pickle.loads(df_serialized)
    if lags_array_serialized is None:
        lags_array = None
    else:
        lags_array = pickle.loads(lags_array_serialized)

    def scatter_shifted(x, y, **kwargs):
        ax = plt.gca()
        color = '#00B0F0'
        j = list(signals_df.columns).index(x.name)
        i = list(signals_df.columns).index(y.name)
        if lags_array is not None:
            x = x.shift(lags_array[i][j])
            color = '#F47B37'
        sns.scatterplot(x=x, y=y, ax=ax, s=5, color=color)

    def contours_shifted(x, y, **kwargs):
        ax1 = plt.gca()
        j = list(signals_df.columns).index(x.name)
        i = list(signals_df.columns).index(y.name)
        shifted_df_pair = pd.concat([x, y], axis=1)
        if lags_array is not None:
            shifted_df_pair[x.name] = x.shift(lags_array[i][j])
            shifted_df_pair.dropna(inplace=True)
        try:
            sns.kdeplot(x=shifted_df_pair[x.name].values, y=shifted_df_pair[y.name].values, ax=ax1, shade=True,
                        thresh=0.05, cmap=ListedColormap(sns.color_palette(colorscale).as_hex()))
        except LinAlgError:
            return scatter_shifted(x, y, **kwargs)

    colorscale = ['#ffffff', '#e8ebef', '#7197B7', '#00B0F0', '#0070C0', '#002060']
    histogram_color = '#068C45'
    grid = sns.PairGrid(data=signals_df, despine=True)
    if lags_array is None:
        grid = grid.map_upper(sns.scatterplot, s=5, color='#00B0F0')
    else:
        grid = grid.map_upper(sns.scatterplot, s=5, color='#00B0F0')
        grid = grid.map_upper(scatter_shifted)
    grid = grid.map_lower(contours_shifted)
    grid = grid.map_diag(sns.histplot, kde=False, color=histogram_color)

    for ax in grid.axes.flatten():
        ax.tick_params(axis='both', which='both', length=0)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)

    return grid
