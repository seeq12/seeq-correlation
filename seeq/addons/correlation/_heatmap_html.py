from typing import Iterable, List
import numpy as np
import pandas as pd

"""
HTML + overlay helpers for the correlation heatmap.

This module keeps:
- Tooltip content construction
- Per-cell overlay DIV generation
- Final HTML wrapper (PNG + overlays + CSS)
"""

def _esc(s) -> str:
    """HTML escape for tooltip text."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _to_minutes(val, unit: str):
    """Convert a time-shift value (in unit) to minutes."""
    if pd.isna(val):
        return np.nan
    u = (unit or "").lower()
    factors = {
        "s": 1/60, "sec": 1/60, "secs": 1/60, "second": 1/60, "seconds": 1/60,
        "m": 1, "min": 1, "mins": 1, "minute": 1, "minutes": 1,
        "h": 60, "hr": 60, "hrs": 60, "hour": 60, "hours": 60,
        "d": 1440, "day": 1440, "days": 1440,
        "y": 525600, "yr": 525600, "yrs": 525600, "year": 525600, "years": 525600,
    }
    return float(val) * factors.get(u, 1.0)

def make_tooltip_html(line1: str, line2: str, line3_html: str, line4_html: str) -> str:
    """Build the tooltip HTML for one cell."""
    return (
        '<div class="tip">'
        f'  <div>{line1}</div>'
        f'  <div>{line2}</div>'
        f'  <div>{line3_html}</div>'
        f'  <div>{line4_html}</div>'
        '</div>'
    )

def build_overlays_html(
        *,
        plot_df: pd.DataFrame,
        primary_vals: pd.DataFrame,
        secondary_vals: pd.DataFrame,
        time_unit: str,
        lags_plot: bool,
        ax_left_pct: float,
        ax_top_pct: float,
        ax_width_pct: float,
        ax_height_pct: float,
) -> List[str]:
    """
    Build all <div class="cell-overlay">...</div> strings for the heatmap.

    Geometry:
      - The heatmap axes rectangle in the saved PNG is given by:
          left = ax_left_pct%, top = ax_top_pct%, width = ax_width_pct%, height = ax_height_pct%
      - The grid is uniform within that rectangle, so each cell is a fixed percentage.

    Tooltips:
      - In coefficients mode (lags_plot=False): bold the coefficient line and put time last.
      - In time-shifts mode (lags_plot=True): bold the time line (minutes) and put coefficient last.
    """
    rows, cols = plot_df.shape
    cell_w_pct = ax_width_pct / cols
    cell_h_pct = ax_height_pct / rows

    overlays: List[str] = []

    for i in range(rows):
        for j in range(cols):
            if lags_plot:
                # time-shifts view: primary = shifts, secondary = coeffs
                shift_val = primary_vals.iat[i, j]
                coeff_val = secondary_vals.iat[i, j]
            else:
                # coefficients view: primary = coeffs, secondary = shifts
                coeff_val = primary_vals.iat[i, j]
                shift_val = secondary_vals.iat[i, j]

            coeff_txt = "—" if pd.isna(coeff_val) else f"{float(coeff_val):.2f}"
            shift_m   = _to_minutes(shift_val, time_unit)
            shift_txt = "—" if pd.isna(shift_m) else f"{float(shift_m):.1f}"

            # First two lines
            line1 = f"Shifted signal: {_esc(plot_df.columns[j])}"
            line2 = f"Signal: {_esc(plot_df.index[i])}"

            # Conditional bold + order
            if lags_plot:
                line3_html = f"<strong>Time (minutes): {shift_txt}</strong>"
                line4_html = f"Coefficient: {coeff_txt}"
            else:
                line3_html = f"<strong>Coefficient: {coeff_txt}</strong>"
                line4_html = f"Time (minutes): {shift_txt}"

            tip_html = make_tooltip_html(line1, line2, line3_html, line4_html)

            left = ax_left_pct + j * cell_w_pct
            top  = ax_top_pct  + i * cell_h_pct

            overlays.append(
                f'<div class="cell-overlay" '
                f'style="left:{left:.6f}%; top:{top:.6f}%; '
                f'width:{cell_w_pct:.6f}%; height:{cell_h_pct:.6f}%;">'
                f'{tip_html}'
                f'</div>'
            )

    return overlays

def wrap_heatmap_html(png_b64: str, overlays_html: Iterable[str], orig_width_px: int) -> str:
    """Wrap the PNG + overlays in an HTML container with CSS."""
    overlays_joined = "".join(overlays_html)
    return f"""
<div style="display:inline-block; position:relative; margin:0; padding:0; max-width:100%; overflow-x:hidden;">
  <img src="data:image/png;base64,{png_b64}"
       style="display:block; width:{orig_width_px}px; max-width:100%; height:auto; z-index:1; margin:0; padding:0;">
  <div style="position:absolute; inset:0; z-index:2;">
    <style>
      .cell-overlay {{
        position:absolute;
        pointer-events: auto;
      }}
      .cell-overlay .tip {{
        display: none;
        position: absolute;
        left: 50%;
        top: 100%;
        transform: translateX(-50%);
        background: rgba(0,0,0,0.85);
        color: white;
        padding: 6px 8px;
        border-radius: 6px;
        white-space: nowrap;
        text-align: left;
        font: 12px/1.2 -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
        pointer-events: none;
        z-index: 9999;
        margin-top: 6px;
      }}
      /* Show on hover */
      .cell-overlay:hover .tip {{
        display: block;
      }}
    </style>
    {overlays_joined}
  </div>
</div>
""".strip()
