import math
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ._heatmap import correlation_matrices, rename_signals


PYTHON_PLOTTER_CONFIGURATION = {
    "options": [
        {
            "key": "maxTimeShift",
            "label": "Maximum time shift",
            "type": "select",
            "default": "auto",
            "choices": [
                {"label": "Automatic", "value": "auto"},
                {"label": "No time shift", "value": "none"},
                {"label": "5 minutes", "value": "5min"},
                {"label": "15 minutes", "value": "15min"},
                {"label": "1 hour", "value": "1h"},
                {"label": "4 hours", "value": "4h"},
                {"label": "12 hours", "value": "12h"},
                {"label": "1 day", "value": "1d"},
            ],
        },
        {
            "key": "displayValues",
            "label": "Display",
            "type": "select",
            "default": "coefficients",
            "choices": [
                {"label": "Correlation coefficients", "value": "coefficients"},
                {"label": "Time shifts", "value": "timeShifts"},
            ],
        },
        {
            "key": "outputType",
            "label": "Output type",
            "type": "select",
            "default": "heatmap",
            "choices": [
                {"label": "Heatmap", "value": "heatmap"},
                {"label": "Table", "value": "table"},
            ],
        },
        {
            "key": "timeOutputUnit",
            "label": "Time-shift units",
            "type": "select",
            "default": "auto",
            "choices": [
                {"label": "Automatic", "value": "auto"},
                {"label": "Seconds", "value": "seconds"},
                {"label": "Minutes", "value": "minutes"},
                {"label": "Hours", "value": "hours"},
                {"label": "Days", "value": "days"},
            ],
        },
        {
            "key": "showValues",
            "label": "Show values in cells",
            "type": "boolean",
            "default": False,
        },
        {
            "key": "maxLabelCharacters",
            "label": "Maximum label characters",
            "type": "number",
            "default": 30,
            "min": 8,
            "max": 80,
            "step": 1,
        },
        {
            "key": "coefficientLowerBound",
            "label": "Coefficient lower bound",
            "type": "number",
            "default": -1.0,
            "min": -1.0,
            "max": 1.0,
            "step": 0.01,
        },
        {
            "key": "coefficientUpperBound",
            "label": "Coefficient upper bound",
            "type": "number",
            "default": 1.0,
            "min": -1.0,
            "max": 1.0,
            "step": 0.01,
        },
        {
            "key": "coefficientOuterRange",
            "label": "Use outer coefficient range",
            "type": "boolean",
            "default": False,
        },
        {
            "key": "filterTimeShifts",
            "label": "Filter time shifts",
            "type": "boolean",
            "default": False,
        },
        {
            "key": "timeShiftLowerBound",
            "label": "Time-shift lower bound",
            "type": "number",
            "default": 0.0,
            "step": 0.1,
        },
        {
            "key": "timeShiftUpperBound",
            "label": "Time-shift upper bound",
            "type": "number",
            "default": 0.0,
            "step": 0.1,
        },
        {
            "key": "timeShiftOuterRange",
            "label": "Use outer time-shift range",
            "type": "boolean",
            "default": False,
        },
    ]
}

_ALLOWED_MAX_TIME_SHIFTS = {"auto", "none", "5min", "15min", "1h", "4h", "12h", "1d"}
_ALLOWED_DISPLAY_VALUES = {"coefficients", "timeShifts"}
_ALLOWED_OUTPUT_TYPES = {"heatmap", "table"}
_ALLOWED_TIME_UNITS = {"auto", "seconds", "minutes", "hours", "days"}


def python_plotter_configuration() -> dict[str, list[dict[str, Any]]]:
    """Return the configuration schema consumed by Python Plotter."""
    return PYTHON_PLOTTER_CONFIGURATION


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
    return default


def _as_float(value: Any, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    if not math.isfinite(result):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def _ordered_bounds(lower: float, upper: float) -> tuple[float, float]:
    return (lower, upper) if lower <= upper else (upper, lower)


def _normalized_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    config = config or {}

    max_time_shift = str(config.get("maxTimeShift", "auto"))
    if max_time_shift not in _ALLOWED_MAX_TIME_SHIFTS:
        max_time_shift = "auto"

    display_values = str(config.get("displayValues", "coefficients"))
    if display_values not in _ALLOWED_DISPLAY_VALUES:
        display_values = "coefficients"

    output_type = str(config.get("outputType", "heatmap"))
    if output_type not in _ALLOWED_OUTPUT_TYPES:
        output_type = "heatmap"

    time_output_unit = str(config.get("timeOutputUnit", "auto"))
    if time_output_unit not in _ALLOWED_TIME_UNITS:
        time_output_unit = "auto"

    try:
        max_label_characters = int(config.get("maxLabelCharacters", 30))
    except (TypeError, ValueError):
        max_label_characters = 30
    max_label_characters = max(8, min(max_label_characters, 80))

    coefficient_bounds = _ordered_bounds(
        _as_float(config.get("coefficientLowerBound"), -1.0, -1.0, 1.0),
        _as_float(config.get("coefficientUpperBound"), 1.0, -1.0, 1.0),
    )
    time_shift_bounds = _ordered_bounds(
        _as_float(config.get("timeShiftLowerBound"), 0.0),
        _as_float(config.get("timeShiftUpperBound"), 0.0),
    )

    return {
        "max_time_shift": None if max_time_shift == "none" else max_time_shift,
        "display_values": display_values,
        "output_type": output_type,
        "time_output_unit": time_output_unit,
        "show_values": _as_bool(config.get("showValues"), False),
        "max_label_characters": max_label_characters,
        "coefficient_bounds": coefficient_bounds,
        "coefficient_outer_range": _as_bool(config.get("coefficientOuterRange"), False),
        "filter_time_shifts": _as_bool(config.get("filterTimeShifts"), False),
        "time_shift_bounds": time_shift_bounds,
        "time_shift_outer_range": _as_bool(config.get("timeShiftOuterRange"), False),
    }


def _json_safe_matrix(frame: pd.DataFrame) -> list[list[float | None]]:
    return [
        [float(value) if math.isfinite(float(value)) else None for value in row]
        for row in frame.to_numpy(dtype=float)
    ]


def _text_matrix(frame: pd.DataFrame, decimals: int, show_values: bool) -> list[list[str]] | None:
    if not show_values:
        return None
    return [
        ["" if not np.isfinite(value) else f"{value:.{decimals}f}" for value in row]
        for row in frame.to_numpy(dtype=float)
    ]


def _range_mask(frame: pd.DataFrame, bounds: tuple[float, float], outer_range: bool, decimals: int) -> pd.DataFrame:
    values = frame.round(decimals)
    lower, upper = bounds
    if outer_range:
        return (values <= lower) | (values >= upper)
    return (values >= lower) & (values <= upper)


def _table_trace(displayed: pd.DataFrame, mask: pd.DataFrame, labels: list[str]) -> dict[str, Any]:
    filtered = displayed.where(mask)
    value_columns: list[list[str]] = [labels]
    for column in filtered.columns:
        value_columns.append([
            "" if not np.isfinite(value) else f"{float(value):.2f}"
            for value in filtered[column].to_numpy(dtype=float)
        ])
    return {
        "type": "table",
        "header": {
            "values": ["Signal", *labels],
            "align": "center",
            "fill": {"color": "#007960"},
            "font": {"color": "white"},
        },
        "cells": {
            "values": value_columns,
            "align": "center",
            "fill": {"color": "white"},
        },
    }


def python_plotter_heatmap(
    df: pd.DataFrame,
    config: Mapping[str, Any] | None = None,
    width: int | None = None,
    height: int | None = None,
) -> dict[str, Any]:
    """Build a Python Plotter envelope for a correlation heatmap."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas.DataFrame")
    if len(df.columns) < 2:
        raise ValueError("Correlation heatmap requires at least two signals")

    options = _normalized_config(config)
    coefficients, time_shifts, time_unit = correlation_matrices(
        df,
        max_time_shift=options["max_time_shift"],
        time_output_unit=options["time_output_unit"],
    )

    labels = rename_signals(list(coefficients.columns), options["max_label_characters"])
    coefficient_values = _json_safe_matrix(coefficients)
    time_shift_values = _json_safe_matrix(time_shifts)
    customdata = [
        [[coefficient_values[i][j], time_shift_values[i][j]] for j in range(len(labels))]
        for i in range(len(labels))
    ]

    displaying_time_shifts = options["display_values"] == "timeShifts"
    displayed = time_shifts if displaying_time_shifts else coefficients
    title = f"Time shifts ({time_unit})" if displaying_time_shifts else "Correlation coefficients"
    colorbar_title = time_unit.title() if displaying_time_shifts else "Coefficient"

    mask = _range_mask(
        coefficients,
        options["coefficient_bounds"],
        options["coefficient_outer_range"],
        decimals=2,
    )
    if options["filter_time_shifts"]:
        mask &= _range_mask(
            time_shifts,
            options["time_shift_bounds"],
            options["time_shift_outer_range"],
            decimals=1,
        )

    if options["output_type"] == "table":
        return {
            "chartType": "plotly",
            "spec": {
                "data": [_table_trace(displayed, mask, labels)],
                "layout": {
                    "title": {"text": title, "x": 0.5},
                    "margin": {"l": 10, "r": 10, "t": 50, "b": 10},
                    "autosize": True,
                },
            },
            "config": {"responsive": True, "displaylogo": False},
            "width": width,
            "height": height,
        }

    displayed = displayed.where(mask)
    hovertemplate = (
        "Shifted signal: %{x}<br>"
        "Signal: %{y}<br>"
        "Coefficient: %{customdata[0]:.2f}<br>"
        f"Time ({time_unit}): %{{customdata[1]:.2f}}<extra></extra>"
    )

    trace: dict[str, Any] = {
        "type": "heatmap",
        "x": labels,
        "y": labels,
        "z": _json_safe_matrix(displayed),
        "customdata": customdata,
        "colorscale": "RdBu",
        "reversescale": True,
        "zmid": 0,
        "colorbar": {"title": {"text": colorbar_title}},
        "hovertemplate": hovertemplate,
        "text": _text_matrix(displayed, 2, options["show_values"]),
        "texttemplate": "%{text}" if options["show_values"] else None,
    }

    if displaying_time_shifts:
        finite_values = np.abs(displayed.to_numpy(dtype=float))
        finite_values = finite_values[np.isfinite(finite_values)]
        limit = float(finite_values.max()) if finite_values.size else 1.0
        trace.update({"zmin": -limit, "zmax": limit})
    else:
        trace.update({"zmin": -1.0, "zmax": 1.0})

    layout: dict[str, Any] = {
        "title": {"text": title, "x": 0.5},
        "margin": {"l": 10, "r": 10, "t": 50, "b": 10},
        "xaxis": {"side": "bottom", "automargin": True},
        "yaxis": {"autorange": "reversed", "automargin": True, "scaleanchor": "x"},
        "autosize": True,
    }

    return {
        "chartType": "plotly",
        "spec": {"data": [trace], "layout": layout},
        "config": {"responsive": True, "displaylogo": False},
        "width": width,
        "height": height,
    }


def python_plotter_plot(body: Mapping[str, Any], spy_module: Any) -> dict[str, Any]:
    """Pull Python Plotter request data through SPy and return a plot envelope."""
    signal_payload = body.get("signals") or []
    if len(signal_payload) < 2:
        raise ValueError("Correlation heatmap requires at least two signals in the Details Pane")
    if len(signal_payload) > 30:
        raise ValueError("Correlation heatmap supports at most 30 signals")

    signals = pd.DataFrame(signal_payload).rename(columns={"id": "ID"})
    if "ID" not in signals.columns:
        raise ValueError("Each signal must include an id")

    start = pd.to_datetime(body["start"], unit="ms", utc=True)
    end = pd.to_datetime(body["end"], unit="ms", utc=True)
    search = spy_module.search(signals, all_properties=True, quiet=True)
    pulled = spy_module.pull(search, start=start, end=end, grid=None, header="ID", quiet=True)
    pulled = pulled.replace("Bad", np.nan).apply(pd.to_numeric, errors="coerce")

    name_key = "name" if "name" in signals.columns else "Name" if "Name" in signals.columns else None
    names_by_id = {
        row["ID"]: row[name_key] if name_key and pd.notna(row[name_key]) else str(row["ID"])
        for _, row in signals.iterrows()
    }
    columns = [column for column in pulled.columns if column in names_by_id]
    pulled = pulled.loc[:, columns].rename(columns=names_by_id)

    return python_plotter_heatmap(
        pulled,
        config=body.get("config") or {},
        width=body.get("width"),
        height=body.get("height"),
    )
