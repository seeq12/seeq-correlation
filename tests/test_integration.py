import os
import pytest
from typing import Optional
import ipyvuetify
from seeq import spy
import seeq.addons.correlation as correlation
from . import test_common

example_data_url: Optional[str] = None


@pytest.fixture(autouse=True, scope='session')
def setup_module():
    test_common.set_environ_variables()
    test_common.login(url=os.environ.get('seeq_url'),
                      credentials_file=os.environ.get('credentials_file'),
                      data_dir=os.environ.get('seeq_data_dir'))
    wb = test_common.create_worksheet_for_tests()
    global example_data_url
    example_data_url = wb.worksheets[0].url
    pkg_id = correlation.correlation_udfs(spy.client)
    print(f"DONE. Created UDF package with id: {pkg_id}")


@pytest.mark.backend
@pytest.mark.integration
def test_create_worksheet():
    df_pull = correlation._utils.pull_only_signals(example_data_url, grid='auto')
    worksheet_url = correlation._create_worksheet(df_pull, df_pull.columns[0], max_time_shift='auto',
                                                  metadata=None,
                                                  worksheet='From Correlation Results', overwrite=True,
                                                  new_condition=True)
    worksheet_id = spy.utils.get_worksheet_id_from_url(worksheet_url)
    assert spy.utils.is_guid(worksheet_id)


@pytest.mark.backend
@pytest.mark.integration
def test_create_correlation_udf_package():
    test_common.delete_correlation_udfs()
    print("\n\nCreating CrossCorrelation UDFs...")
    pkg_id = correlation.correlation_udfs(spy.client)
    print(f"DONE. Created UDF package with id: {pkg_id}")


@pytest.mark.backend
@pytest.mark.integration
def test_create_worksheet_with_tracking_corr_signals():
    df = spy.search(dict(Path="Example >> Cooling Tower 1 >> Area A"))
    df = df[(df['Name'] == 'Temperature') | (df['Name'] == 'Wet Bulb')]
    ids = [(df['ID'].values[0], df['ID'].values[1])]

    wb = spy.workbooks.Analysis({'Name': 'test_workbook'})
    wb.worksheet('new')
    spy.workbooks.push(wb, include_inventory=False, quiet=True)

    r = correlation.worksheet_corrs_and_time_shifts(ids, wb.id, "new_worksheet",
                                                    '2021-04-27T22:30:37.837000Z', '2021-04-29T14:05:06.789000Z',
                                                    corr_coeff_signals=True, time_shifted_for_correlation=True,
                                                    window_size='24h', period='6h',
                                                    suffix='', time_shifts_signals=True, corr_thrs=0.7,
                                                    output_time_unit='min', max_time_shift='1h',
                                                    condition_id=None, overwrite=True, api_client=spy.client)


@pytest.mark.frontend
@pytest.mark.integration
def test_correlation_iu():
    workbook = test_common.create_worksheet_for_tests()
    worksheet = workbook.worksheets[0]
    jupyter_notebook_url = f'http://seeq.com/data-lab/6AB49411-917E-44CC-BA19-5EE0F903100C/apps/deployment' \
                           f'/correlation_analysis_master.ipynb?workbookId={workbook.id}&worksheetId={worksheet.id}'
    C = correlation.CorrelationHeatmap(sdl_notebook_url=jupyter_notebook_url)
    assert isinstance(C.run(), ipyvuetify.generated.App)
