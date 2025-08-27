import numpy as np
import pandas as pd
import pickle
# There is a bug that prevents to correctly memorize a pandas.DataFrame
# Thus, all functions that use the @cached decorator need to accept serialized dataframes (pickle is a good option)
from memoization import cached
from ._config import _cache_max_items
from . import default_preprocessing_wrapper
from . import lags_coeffs
from ._heatmap_html import build_overlays_html, wrap_heatmap_html
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.transforms import Bbox
import seaborn as sns
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
        Displays a Matplotlib/Seaborn figure with either Pearson's coefficients
        or signal time shifts

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

def _compute_color_limits(primary_array: np.ndarray, lags_plot: bool):
    # Compute color limits and colormap for the heatmap
    if lags_plot:
        flat = primary_array.flatten()
        limit = max(np.nanmax(flat), abs(np.nanmin(flat)))
        cmap = 'RdBu'
    else:
        limit = 1.0
        cmap = 'RdBu'
    center = 0
    return limit, cmap, center

def _prepare_frames(primary_df_serialized, secondary_df_serialized, boolean_df, max_label_chars):
    # Prepare the DataFrames for plotting
    primary_df = pickle.loads(primary_df_serialized)
    secondary_df = pickle.loads(secondary_df_serialized)

    new_names = rename_signals(list(primary_df.columns), max_label_chars)

    # Data used to draw (apply mask if provided)
    if isinstance(boolean_df, pd.DataFrame):
        plot_df = primary_df[boolean_df].copy()
        primary_array = plot_df.values
    else:
        plot_df = primary_df.copy()
        primary_array = plot_df.values

    plot_df.index = new_names
    plot_df.columns = new_names

    # Tooltip values (unmasked)
    primary_vals = primary_df.copy()
    primary_vals.index = new_names
    primary_vals.columns = new_names

    secondary_vals = secondary_df.loc[primary_df.index, primary_df.columns].copy()
    secondary_vals.index = new_names
    secondary_vals.columns = new_names

    return plot_df, primary_array, primary_vals, secondary_vals, new_names

def _draw_heatmap(plot_df: pd.DataFrame, limit, cmap, center):
    # Create the figure and draw the heatmap
    num_signals = len(plot_df)
    base_size = max(4, min(8, num_signals * 0.35))
    fig, ax = plt.subplots(figsize=(base_size, base_size), facecolor='white')

    sns.heatmap(
        plot_df, annot=False, fmt='.2f', cmap=cmap, center=center,
        vmin=-limit, vmax=limit, square=True, linewidths=0.5,
        cbar=False, ax=ax
    )
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    ax.tick_params(axis='x', labelsize=8, pad=6)
    ax.tick_params(axis='y', labelsize=8, pad=4)

    return fig, ax

def _add_colorbar(fig, ax, lags_plot: bool):
    # Create colorbar
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="4%", pad=0.25)
    cbar = fig.colorbar(ax.collections[0], cax=cax)
    if lags_plot:
        cbar.set_label("Time (minutes)", rotation=270, labelpad=12)
    else:
        cbar.set_label("Correlation Coefficient", rotation=270, labelpad=12)
    cbar.ax.yaxis.label.set_size(10)
    cbar.ax.yaxis.label.set_weight('bold')
    return cbar

def _compute_geometry_percentages(fig, ax, pad_inches: float = 0.02):
    # Compute the geometry of the heatmap for CSS positioning
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    tight = fig.get_tightbbox(renderer)  # inches
    x0, y0, x1, y1 = tight.extents
    tight_padded = Bbox.from_extents(x0 - pad_inches, y0 - pad_inches,
                                     x1 + pad_inches, y1 + pad_inches)

    # Keep original display width so the visual size is stable in HTML
    orig_width_px = int(round(tight_padded.width * fig.dpi))

    # Axes bbox in inches
    ab_px = ax.get_window_extent(renderer=renderer)
    ab_in = Bbox.from_extents(ab_px.x0 / fig.dpi, ab_px.y0 / fig.dpi,
                              ab_px.x1 / fig.dpi, ab_px.y1 / fig.dpi)

    # Fractions of the cropped image
    ax_left_frac   = (ab_in.x0 - tight_padded.x0) / tight_padded.width
    ax_top_frac    = (tight_padded.y1 - ab_in.y1) / tight_padded.height
    ax_width_frac  =  ab_in.width                 / tight_padded.width
    ax_height_frac =  ab_in.height                / tight_padded.height

    # Convert to percentages for CSS
    ax_left_pct   = 100.0 * ax_left_frac
    ax_top_pct    = 100.0 * ax_top_frac
    ax_width_pct  = 100.0 * ax_width_frac
    ax_height_pct = 100.0 * ax_height_frac

    return tight_padded, orig_width_px, ax_left_pct, ax_top_pct, ax_width_pct, ax_height_pct

def _export_png_base64(fig, bbox_inches, export_scale: float = 2.0):
    # Export the figure to PNG and encode it in base64
    export_dpi = int(round(fig.dpi * export_scale))
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches=bbox_inches, dpi=export_dpi)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")

@cached(max_size=_cache_max_items)
def _heatmap_plot(primary_df_serialized, secondary_df_serialized, time_unit: str,
                  lags_plot=False, boolean_df=None, max_label_chars=30):

    # Prep frames
    plot_df, primary_array, primary_vals, secondary_vals, _ = _prepare_frames(
        primary_df_serialized, secondary_df_serialized, boolean_df, max_label_chars
    )
    if plot_df.empty:
        return None

    # Color scale
    limit, cmap, center = _compute_color_limits(primary_array, lags_plot)

    # Draw
    fig, ax = _draw_heatmap(plot_df, limit, cmap, center)

    # Colorbar
    _add_colorbar(fig, ax, lags_plot)

    # Geometry (DPI-agnostic percentages + original display width)
    tight_padded, orig_width_px, ax_left_pct, ax_top_pct, ax_width_pct, ax_height_pct = \
        _compute_geometry_percentages(fig, ax, pad_inches=0.02)

    # Build tooltip overlays
    overlays_html = build_overlays_html(
        plot_df=plot_df,
        primary_vals=primary_vals,
        secondary_vals=secondary_vals,
        time_unit=time_unit,
        lags_plot=lags_plot,
        ax_left_pct=ax_left_pct,
        ax_top_pct=ax_top_pct,
        ax_width_pct=ax_width_pct,
        ax_height_pct=ax_height_pct,
    )

    # Export PNG
    png_b64 = _export_png_base64(fig, bbox_inches=tight_padded, export_scale=2.0)

    # Final HTML
    html = wrap_heatmap_html(png_b64=png_b64, overlays_html=overlays_html, orig_width_px=orig_width_px)
    return html
