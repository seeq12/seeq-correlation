import numpy as np
import pandas as pd
import pickle
import plotly.graph_objs as go
# There is a bug that prevents to correctly memorize a pandas.DataFrame
# Thus, all functions that use the @cached decorator need to accept serialized dataframes (pickle is a good option)
from memoization import cached
from ._config import _cache_max_items
from . import default_preprocessing_wrapper
from . import lags_coeffs

import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_agg import FigureCanvasAgg
import mplcursors
import base64
from io import BytesIO


def heatmap(df, max_time_shift='auto', output_values='coeffs', output_type='plot', time_output_unit='auto',
            bypass_preprocessing=False):
    """
    Creates a heatmap plot of the cross-correlation coefficients between
    signals. The signals can be allowed to shift in time to find the
    maximum cross-correlation between signals.

    Alternatively, a heatmap of the time shifts to maximize correlation of
    signals can be plotted as well.

    Parameters
    ----------
    df: pandas.DataFrame
        A DataFrame that contains a set of signals as columns and date-time as
        the index.
    max_time_shift: {'auto', str, None}, default 'auto'
        Maximum time (e.g. '15s', or '1min') that the signals are allowed to
        slide in order to maximize cross-correlation. For times specified as a
        str, normal time units are accepted.If 'auto' is selected, a default
        maximum time shift is calculated based on the number of samples. If
        None, the raw signals are used and no time shifts are calculated.
    output_values: {'coeffs', 'time_shifts'}, default 'coeffs'
        Values to plot in the heatmap. Either the Pearson's coefficients or
        the time shifts that the signals were shifted to maximize
        cross-correlation.
    output_type: {'plot', 'table'}, default 'plot'
        The heatmap can be outputted either as an (interactive) plot or as a
        DataFrame
    time_output_unit: {'auto', str} default 'auto'
        Specifies the time unit used to display the time shifts. Valid units
        are the ones accepted by pd.Timedelta
    bypass_preprocessing: bool, default False
        Whether the data pre-processing routine is by-passed or not. Setting
        it to True is not recommended unless the data has been pre-processed
        elsewhere.

    Returns
    -------
    Either one of the following
    -: None
        Displays a Plotly figure with either Pearson's coefficients or signal
        time shifts

    table: pandas.DataFrame
        A DataFrame with either Pearson's coefficients or times_shifts of all
        signal pairs

    Examples
    --------
    Create a heatmap plot of the cross-correlation coefficients for the signals
    in a DataFrame allowing for automatic guess of maximum time shifts

    >>> seeq.addons.correlation.heatmap(df,
    >>>                              max_time_shift='auto',
    >>>                              output_values='coeffs',
    >>>                              output_type='plot')

    Create a heatmap plot of the cross-correlation coefficients for the signals
    in a DataFrame specifying a maximum time shift between signals of 1 hour

    >>> seeq.addons.correlation.heatmap(df,
    >>>                              max_time_shift='1h',
    >>>                              output_values='coeffs',
    >>>                              output_type='plot')

    Create a table of the time shifts to maximize cross-correlation of the
    signals in a DataFrame specifying a maximum time shift between signals
    of 1 hour

    >>> seeq.addons.correlation.heatmap(df,
    >>>                              max_time_shift='1h',
    >>>                              output_values='time_shifts',
    >>>                              output_type='table')

    Create a table of the cross-correlation coefficients for the signals in a
    DataFrame using the raw data (no time shift allowed)

    >>> seeq.addons.correlation.heatmap(df,
    >>>                              max_time_shift=None,
    >>>                              output_values='coeffs',
    >>>                              output_type='table')

    """

    if time_output_unit is None:
        raise ValueError('time_output_unit cannot be None. Please specify a valid pd.Timedelta unit')

    heatmap_object = _heatmap(df, max_time_shift=max_time_shift, output_values=output_values, output_type=output_type,
                              time_output_unit=time_output_unit, bypass_preprocessing=bypass_preprocessing)

    if output_type == 'plot':
        heatmap_object.show(config={'displaylogo': False, 'displayModeBar': True})
    else:
        return heatmap_object


def _heatmap(df, max_time_shift='auto', output_values='coeffs', output_type='plot', time_output_unit='auto',
             bypass_preprocessing=False):
    # We don't want to remove outliers here. Increased the outlier_sensitivity
    df = default_preprocessing_wrapper(df, consecutivenans=0.04, percent_nan=0.0,
                                       bypass_processing=bypass_preprocessing)

    lags, coeffs, sampling_time, time_unit, maxlags = lags_coeffs(df, max_time_shift, time_output_unit)
    lags_to_time = lags * sampling_time
    coeffs_df = pd.DataFrame(data=coeffs, columns=df.columns, index=df.columns)
    time_shifts_df = pd.DataFrame(data=lags_to_time, columns=df.columns, index=df.columns)

    if output_type == 'plot':
        if output_values == 'coeffs':
            fig = _heatmap_plot(pickle.dumps(coeffs_df), pickle.dumps(time_shifts_df),
                                time_unit=time_unit, lags_plot=False)
        elif output_values == 'time_shifts':
            fig = _heatmap_plot(pickle.dumps(time_shifts_df), pickle.dumps(coeffs_df),
                                time_unit=time_unit, lags_plot=True)

        else:
            raise ValueError('Invalid output_type: {}'.format(output_values))

        return fig

    elif output_type == 'table':

        if output_values == 'coeffs':
            return coeffs_df

        elif output_values == 'time_shifts':
            time_shifts_df.columns = [f"{x} ({time_unit})" for x in time_shifts_df.columns]
            return time_shifts_df
        else:
            raise ValueError('Invalid output_values: {}'.format(output_values))
    else:
        raise ValueError('Invalid output_values: {}'.format(output_type))


def rename_signals(signal_list, max_label_chars):
    if np.array([len(x) for x in signal_list]).max() > max_label_chars:
        new_names = []
        size_ = int(max_label_chars/2)
        for i, name in enumerate(signal_list):
            if len(name) > max_label_chars:
                truncated_name = name[:size_] + "..." + name[-(size_-3):]
                if truncated_name in new_names:
                    unique_name = f"{truncated_name[2:]}_{i}"
                else:
                    unique_name = truncated_name
                new_names.append(unique_name)
            else:
                new_names.append(name)

    else:
        new_names = signal_list
    return new_names


@cached(max_size=_cache_max_items)
def _heatmap_plot(primary_df_serialized, secondary_df_serialized, time_unit: str,
                  lags_plot=False, boolean_df=None, max_label_chars=30):
    primary_df = pickle.loads(primary_df_serialized)
    secondary_df = pickle.loads(secondary_df_serialized)
    if primary_df.empty:
        return None

    # Names
    new_names = rename_signals(list(primary_df.columns), max_label_chars)

    # Primary for colors
    if isinstance(boolean_df, pd.DataFrame):
        plot_df = primary_df[boolean_df].copy()
        primary_array = plot_df.values
    else:
        plot_df = primary_df.copy()
        primary_array = plot_df.values
    plot_df.index = new_names
    plot_df.columns = new_names

    # Secondary for tooltips
    sec = secondary_df.loc[primary_df.index, primary_df.columns]
    secondary_plot_df = (sec[boolean_df].copy() if isinstance(boolean_df, pd.DataFrame) else sec.copy())
    secondary_plot_df.index = new_names
    secondary_plot_df.columns = new_names

    # Visuals
    if lags_plot:
        flat = primary_array.flatten()
        limit = max(np.nanmax(flat), abs(np.nanmin(flat)))
        cmap = 'RdBu'
    else:
        limit = 1.0
        cmap = 'RdBu'
    center = 0

    # Figure - fixed size calculation to prevent growth
    num_signals = len(plot_df)
    base_size = max(4, min(8, num_signals * 0.35))
    fig, ax = plt.subplots(figsize=(base_size, base_size), facecolor='white')

    # Heatmap
    sns.heatmap(
        plot_df, annot=False, fmt='.2f', cmap=cmap, center=center,
        vmin=-limit, vmax=limit, square=True, linewidths=0.5,
        cbar_kws={"shrink": 0.8}, ax=ax
    )

    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')

    # Hover tooltips
    quadmesh = ax.collections[0]
    cursor = mplcursors.cursor(quadmesh, hover=True)

    def _fmt_num(x, d): return "NA" if pd.isna(x) else f"{x:.{d}f}"

    @cursor.connect("add")
    def _on_add(sel):
        ncols = plot_df.shape[1]
        r, c = divmod(sel.index, ncols)
        row_label, col_label = plot_df.index[r], plot_df.columns[c]
        primary_val = plot_df.iloc[r, c]
        secondary_val = secondary_plot_df.iloc[r, c]
        if lags_plot:
            text = (f"Shifted signal: {row_label}\n"
                    f"Signal: {col_label}\n"
                    f"Time shifted ({time_unit}): {_fmt_num(primary_val,1)}\n"
                    f"Coefficient: {_fmt_num(secondary_val,2)}")
        else:
            text = (f"Shifted signal: {row_label}\n"
                    f"Signal: {col_label}\n"
                    f"Coefficient: {_fmt_num(primary_val,2)}\n"
                    f"Time shifted ({time_unit}): {_fmt_num(secondary_val,1)}")
        sel.annotation.set_text(text)
        sel.annotation.get_bbox_patch().set(alpha=0.9)

    fig.tight_layout()

    # Prevent automatic display
    plt.ioff()
    return fig
