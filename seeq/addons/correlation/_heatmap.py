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
        new_names = [name[-max_label_chars:] for name in signal_list]
        # TODO: Need to improve the logic of how the long labels are selected
        # labels = []
        # letters = list(string.ascii_uppercase)
        # for i in range(1, 11, 1):
        #     labels.extend([letter * i for letter in letters])
        # new_names = labels[:len(signal_list)]
    else:
        new_names = signal_list
    return new_names


@cached(max_size=_cache_max_items)
def _heatmap_plot(primary_df_serialized, secondary_df_serialized, time_unit: str, lags_plot=False, boolean_df=None,
                  max_label_chars=30):
    primary_df = pickle.loads(primary_df_serialized)
    secondary_df = pickle.loads(secondary_df_serialized)
    if primary_df.empty:
        return go.Figure()

    signal_list = list(primary_df.columns)
    new_names = rename_signals(signal_list, max_label_chars)

    if boolean_df is not None and isinstance(boolean_df, pd.DataFrame):
        primary_array = primary_df[boolean_df].values
    else:
        primary_array = primary_df.values

    x = signal_list
    x_names = new_names
    y = signal_list[::-1]
    y_names = new_names[::-1]
    z = np.flipud(primary_array)
    p_label = np.flipud(primary_df.values)
    s_label = np.flipud(secondary_df.values)
    if lags_plot:
        flat = primary_array.flatten()
        limit = max(np.nanmax(flat), np.abs(np.nanmin(flat)))
        title = "Time (" + time_unit + ")"
    else:
        limit = 1.0
        title = 'Correlation Coefficient'

    hovertext = list()
    for yi, yy in enumerate(y):
        hovertext.append(list())
        for xi, xx in enumerate(x):
            if lags_plot:
                hovertext[-1].append(
                    f'Shifted signal: {xx}<br>'
                    f'Signal: {yy} <br>'
                    f'<b>Time shifted ({time_unit}): {p_label[yi][xi]:.1f}</b> '
                    f'<br>Coefficient: {s_label[yi][xi]:.2f}')

            else:
                hovertext[-1].append(
                    f'Shifted signal: {xx}<br>Signal: {yy} <br><b>Coefficient: {p_label[yi][xi]:.2f}</b> '
                    f'<br>Time shifted ({time_unit}): {s_label[yi][xi]:.1f}')

    colorscale = [[0.0, '#992542'],
                  [0.111, '#C00000'],
                  [0.222, '#FF0000'],
                  [0.333, '#f77e7e'],
                  [0.444, '#ffd1d1'],
                  [0.5, '#D3D3D3'],
                  [0.666, '#9cbbd1'],
                  [0.777, '#6c9ec1'],
                  [0.888, '#4791c6'],
                  [0.999, '#1f7fc4'],
                  [1.0, '#0070C0']]

    # create the raw corr heatmap
    data = go.Heatmap(z=z,
                      # needs to be flipped in order for diagonal to have correct orientation in plotly
                      x=x_names, y=y_names,
                      hoverinfo='text',
                      text=hovertext,
                      colorscale=colorscale, colorbar=dict(title=title), zmin=-limit, zmax=limit, name=''
                      )

    fig = go.Figure(data=data)
    fig.layout.paper_bgcolor = 'rgba(0,0,0,0)'
    fig.layout.plot_bgcolor = 'rgba(0,0,0,0)'
    fig.layout.dragmode = "select"
    fig.layout.modebar = {
        'bgcolor': 'rgba(0, 0, 0, 0)',
        'color': 'rgba(221, 221, 221, 1)',
        'activecolor': 'rgba(0, 121, 96, 1)'
        }
    # this ensures a square plot
    fig.layout.xaxis = {'constrain': 'domain', 'scaleanchor': 'y'}
    fig.layout.yaxis = {'constrain': 'domain'}
    return fig
