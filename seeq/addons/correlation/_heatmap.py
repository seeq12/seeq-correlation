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
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
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

    # Color limits
    if lags_plot:
        flat = primary_array.flatten()
        limit = max(np.nanmax(flat), abs(np.nanmin(flat)))
        cmap = 'RdBu'
    else:
        limit = 1.0
        cmap = 'RdBu'
    center = 0

    # Figure
    num_signals = len(plot_df)
    base_size = max(4, min(8, num_signals * 0.35))
    fig, ax = plt.subplots(figsize=(base_size, base_size), facecolor='white')

    # Heatmap
    sns.heatmap(
        plot_df, annot=False, fmt='.2f', cmap=cmap, center=center,
        vmin=-limit, vmax=limit, square=True, linewidths=0.5,
        cbar=False, ax=ax
    )
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    ax.tick_params(axis='x', labelsize=8, pad=6)
    ax.tick_params(axis='y', labelsize=8, pad=4)

    # Colorbar matches heatmap height
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="4%", pad=0.10)  # tweak pad/size as desired
    fig.colorbar(ax.collections[0], cax=cax)

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()

    # Build a tight bbox that includes ALL text (y labels, cbar ticks, etc.)
    pad_inches = 0.02
    tight = fig.get_tightbbox(renderer)  # in inches
    x0, y0, x1, y1 = tight.extents
    tight_padded = Bbox.from_extents(x0 - pad_inches, y0 - pad_inches,
                                     x1 + pad_inches, y1 + pad_inches)

    # Compute overlay geometry relative to the image
    dpi = fig.dpi
    img_w = tight_padded.width  * dpi
    img_h = tight_padded.height * dpi

    # Axes bbox in screen pixels (relative to full canvas)
    ab = ax.get_window_extent(renderer=renderer)
    ax_x0_full, ax_y0_full, ax_w_px, ax_h_px = ab.x0, ab.y0, ab.width, ab.height

    # Offset by the tight-crop origin (in pixels)
    crop_left_px   = tight_padded.x0 * dpi
    crop_bottom_px = tight_padded.y0 * dpi
    ax_x0 = ax_x0_full - crop_left_px
    ax_y0 = ax_y0_full - crop_bottom_px

    # Percentages relative to the PNG
    ax_left_pct   = 100.0 * (ax_x0 / img_w)
    ax_top_pct    = 100.0 * ((img_h - (ax_y0 + ax_h_px)) / img_h)  # invert Y
    ax_width_pct  = 100.0 * (ax_w_px / img_w)
    ax_height_pct = 100.0 * (ax_h_px / img_h)

    # Per-cell overlay sizes inside the axes rectangle
    rows, cols = plot_df.shape
    cell_w_pct = ax_width_pct  / cols
    cell_h_pct = ax_height_pct / rows

    # Convert a time-shift value (in 'time_unit') to minutes for the tooltip
    def _to_minutes(val, unit):
        u = (unit or "").lower()
        factors = {
            "s": 1/60, "sec": 1/60, "secs": 1/60, "second": 1/60, "seconds": 1/60,
            "m": 1, "min": 1, "mins": 1, "minute": 1, "minutes": 1,
            "h": 60, "hr": 60, "hrs": 60, "hour": 60, "hours": 60,
            "d": 1440, "day": 1440, "days": 1440,
            "y": 525600, "yr": 525600, "yrs": 525600, "year": 525600, "years": 525600,
        }
        # Default to minutes if unit is unknown
        return float(val) * factors.get(u, 1.0)

    # Build tooltip overlays
    overlays_html = []
    for i in range(rows):
        for j in range(cols):
            left = ax_left_pct + j * cell_w_pct
            top  = ax_top_pct  + i * cell_h_pct
            if lags_plot:
                coeff_val = float(secondary_plot_df.iat[i, j])               # coeffs in secondary
                shift_min = _to_minutes(plot_df.iat[i, j], time_unit)        # shifts in primary
            else:
                coeff_val = float(plot_df.iat[i, j])                         # coeffs in primary
                shift_min = _to_minutes(secondary_plot_df.iat[i, j], time_unit)

            tip = (
                f"Shifted signal: {plot_df.columns[j]}\n"
                f"Signal: {plot_df.index[i]}\n"
                f"Coefficient: {coeff_val:.2f}\n"
                f"Time shifted (minutes): {shift_min:.1f}"
            )
            tip = tip.replace('"', '&quot;')

            overlays_html.append(
                f'<div class="cell-overlay" data-tip="{tip}" '
                f'style="left:{left:.6f}%; top:{top:.6f}%; '
                f'width:{cell_w_pct:.6f}%; height:{cell_h_pct:.6f}%;"></div>'
            )

    # Save the figure to PNG with tight bbox
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches=tight_padded)
    plt.close(fig)
    buf.seek(0)
    png_b64 = base64.b64encode(buf.read()).decode("ascii")

    # HTML wrapper
    html = f"""
    <div style="display:inline-block; position:relative; margin:0; padding:0; max-width:100%; overflow-x:hidden;">
      <img src="data:image/png;base64,{png_b64}" style="display:block; width:auto; max-width:100%; height:auto; z-index:1; margin:0; padding:0;">
      <div style="position:absolute; inset:0; z-index:2;">
        <style>
          .cell-overlay {{
            position:absolute;
            pointer-events: auto;
          }}
          .cell-overlay[data-tip]:hover::after {{
            content: attr(data-tip);
            position: absolute;
            left: 50%;
            top: 100%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.85);
            color: white;
            padding: 6px 8px;
            border-radius: 6px;
            white-space: pre;
            text-align: left;
            font: 12px/1.2 -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
            pointer-events: none;
            z-index: 9999;
            margin-top: 6px;
          }}
        </style>
        {''.join(overlays_html)}
      </div>
    </div>
    """
    return html

