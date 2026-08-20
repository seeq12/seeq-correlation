import json
from pathlib import Path

import pytest

from seeq.addons import correlation

from . import test_common


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.unit
def test_addon_is_discoverable_by_python_plotter():
    manifest = json.loads((ROOT / 'addon.json').read_text())

    assert manifest['identifier'] == 'com.seeq.addon.correlation.pythonplotter'
    assert manifest['name'] == 'Unofficial Correlation Heatmap for Python Plotter'
    assert 'Python Plotter Add-on must be installed' in manifest['description']
    assert len(manifest['elements']) == 1
    element = manifest['elements'][0]
    assert element['name'] == element['identifier']
    assert element['type'] == 'DataLabFunctions'
    assert '.pythonplotter.plotter.' in element['identifier']
    assert element['path'] == 'python-plotter-functions'


@pytest.mark.unit
def test_correlation_wheel_is_packaged_with_data_lab_functions():
    functions = ROOT / 'python-plotter-functions'
    requirements = (functions / 'requirements.txt').read_text().splitlines()
    local_packages = [line.removeprefix('./') for line in requirements if line.startswith('./')]

    assert len(local_packages) == 1
    assert local_packages[0].endswith('.whl')
    assert (functions / local_packages[0]).is_file()


@pytest.mark.unit
def test_api_notebook_exposes_python_plotter_endpoints():
    notebook = json.loads((ROOT / 'python-plotter-functions' / 'API.ipynb').read_text())
    sources = [''.join(cell.get('source', [])) for cell in notebook['cells']]

    assert any(source.startswith('# GET /configuration') for source in sources)
    assert any(source.startswith('# POST /plot') for source in sources)


@pytest.mark.unit
def test_configuration_uses_supported_python_plotter_controls():
    configuration = correlation.python_plotter_configuration()

    assert configuration['options']
    assert {option['type'] for option in configuration['options']} <= {'select', 'boolean', 'number'}
    assert {option['key'] for option in configuration['options']} == {
        'maxTimeShift',
        'displayValues',
        'outputType',
        'timeOutputUnit',
        'showValues',
        'maxLabelCharacters',
        'coefficientLowerBound',
        'coefficientUpperBound',
        'coefficientOuterRange',
        'filterTimeShifts',
        'timeShiftLowerBound',
        'timeShiftUpperBound',
        'timeShiftOuterRange',
    }


@pytest.mark.plots
@pytest.mark.unit
def test_time_shift_envelope_is_strict_json():
    envelope = correlation.python_plotter_heatmap(
        test_common.df,
        config={
            'maxTimeShift': '15min',
            'displayValues': 'timeShifts',
            'timeOutputUnit': 'minutes',
            'showValues': True,
        },
        width=640,
        height=480,
    )

    encoded = json.dumps(envelope, allow_nan=False)
    assert 'Time shifts (minutes)' in encoded
    assert envelope['spec']['data'][0]['zmin'] == -envelope['spec']['data'][0]['zmax']


@pytest.mark.plots
@pytest.mark.unit
def test_table_output_applies_coefficient_and_time_shift_filters():
    envelope = correlation.python_plotter_heatmap(
        test_common.df,
        config={
            'maxTimeShift': '15min',
            'displayValues': 'coefficients',
            'outputType': 'table',
            'timeOutputUnit': 'minutes',
            'coefficientLowerBound': -0.95,
            'coefficientUpperBound': 0.95,
            'coefficientOuterRange': True,
            'filterTimeShifts': True,
            'timeShiftLowerBound': -10,
            'timeShiftUpperBound': 10,
            'timeShiftOuterRange': False,
        },
        width=640,
        height=480,
    )

    trace = envelope['spec']['data'][0]
    assert trace['type'] == 'table'
    assert trace['header']['values'][0] == 'Signal'
    assert len(trace['cells']['values']) == len(test_common.df.columns) + 1
    assert any(value == '' for column in trace['cells']['values'][1:] for value in column)
    json.dumps(envelope, allow_nan=False)


@pytest.mark.plots
@pytest.mark.unit
def test_heatmap_filters_cells_using_inner_ranges():
    envelope = correlation.python_plotter_heatmap(
        test_common.df,
        config={
            'maxTimeShift': 'none',
            'coefficientLowerBound': -0.93,
            'coefficientUpperBound': -0.90,
        },
    )

    values = envelope['spec']['data'][0]['z']
    assert any(value is None for row in values for value in row)
    assert any(value is not None for row in values for value in row)
