# Correlation Heatmap for Python Plotter

This project packages the Seeq Correlation calculations as a Data Lab Functions add-on for [Python Plotter](https://github.com/seeq12/seeq-python-plotter). It does not install a separate Workbench Add-on Tool.

The plot reads numeric signals from Python Plotter's Details Pane payload and uses the Display Pane range. It returns an interactive Plotly heatmap showing either:

- Pearson correlation coefficients
- Time shifts that maximize the absolute cross-correlation

Cell tooltips include both values. Plot options control the maximum allowed shift, displayed values, time units, cell labels, and signal-label length.

## Requirements

- Python Plotter installed on the target Seeq instance
- Seeq Data Lab with Python 3.11
- At least two numeric signals in the Details Pane

## Add-on structure

| Path | Purpose |
| --- | --- |
| `python-plotter-functions/API.ipynb` | `GET /configuration` and `POST /plot` endpoints |
| `python-plotter-functions/README.md` | Help content shown by Python Plotter |
| `seeq/addons/correlation/_python_plotter.py` | Request adapter and Plotly envelope generation |
| `seeq/addons/correlation/_heatmap.py` | Shared correlation-matrix calculations |
| `addon.json` | Data Lab Functions add-on definition |
| `addon.py` | Wheel and add-on packaging |

The build copies the Correlation wheel directly into `python-plotter-functions/` and writes a local `requirements.txt` that points to that wheel. When Add-on Manager creates the Data Lab Functions project, pip processes `requirements.txt`, installs the local wheel, and resolves the wheel's declared dependencies. The Seeq and SPy packages come from the Data Lab environment so their versions continue to match the target Seeq server.

The Data Lab Functions element identifier is:

`com.seeq.addon.correlation.pythonplotter.plotter.correlation_heatmap`

The `.pythonplotter.plotter.` segment makes the project discoverable in Python Plotter's plot selector.

## Development

Install the project and development dependencies:

```shell
uv sync --group dev
```

Run unit tests:

```shell
uv run pytest -m unit
```

Build the wheel, `.addon`, and `.addonmeta` artifacts:

```shell
uv run python addon.py
```

Artifacts are written to `bin/` using the add-on identifier and version.
The packaged wheel and `requirements.txt` remain visible in `python-plotter-functions/` so the Data Lab project contents can be inspected before installing the add-on. Rebuilding replaces stale wheels in that directory.

## Python Plotter contract

`POST /plot` receives Python Plotter's normal request body. The adapter:

1. Validates that 2 to 30 signals were selected.
2. Searches and pulls those signals with SPy for the requested range.
3. Reuses the Correlation preprocessing and matrix calculations.
4. Returns a Plotly envelope with `chartType`, `spec`, dimensions, and responsive renderer configuration.

`GET /configuration` returns options using Python Plotter's `select`, `boolean`, and `number` controls.

## Source

The correlation algorithms and preprocessing originated in [seeq12/seeq-correlation](https://github.com/seeq12/seeq-correlation). This project changes the delivery and rendering path to Python Plotter while retaining the tested calculation code.