import os
import configparser
import pandas as pd
from pathlib import Path
from seeq import spy, sdk
from seeq.spy.workbooks import Analysis

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.joinpath('data')

df = pd.read_csv(DATA_DIR.joinpath('cross_correlation.csv'), index_col=0)


def login(url=None, credentials_file=None, data_dir=None):
    if not credentials_file:
        credentials_file = get_server_data_folder(data_dir=data_dir).joinpath('keys', 'agent.key')
    if isinstance(credentials_file, str):
        credentials_file = Path(credentials_file)
    if not credentials_file.is_file():
        raise ValueError(f'Could not find file {credentials_file} to get login credentials'
                         f'You can try passing the Seeq data directory as a "data_dir" kwarg')
    credentials = open(credentials_file, "r").read().splitlines()
    spy.login(credentials[0], credentials[1], url=url)


def get_server_data_folder(data_dir=None):
    if data_dir is not None:
        return data_dir
    cwd = Path().absolute()
    return Path(cwd.drive).joinpath('/ProgramData', 'Seeq', 'data')


def set_environ_variables(configfile=None):
    if configfile is None:
        configfile = BASE_DIR.joinpath('test_config.ini')
    if not Path(configfile).exists():
        raise FileNotFoundError(f"File{configfile} could not be found. "
                                f"Please make sure that ./tests/test_config.ini exists")
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(configfile)
    for section in config.sections():
        print(section)
        for option in config.options(section):
            if config.get(section, option) is not None:
                os.environ[option] = config.get(section, option)


def create_worksheet_for_tests():
    search_results = spy.search({
        'Name': 'Temperature',
        'Path': 'Example >> Cooling Tower 1 >> Area A'
    })

    display_items = pd.DataFrame([{
        'Type': 'Signal',
        'Name': 'Temperature shifted -5h',
        'Formula': '$a.move(-5h)',
        'Formula Parameters': {
            '$a': search_results.iloc[0]
        }
    }, {
        'Type': 'Signal',
        'Name': 'Temperature',
        'Formula': '$a',
        'Formula Parameters': {
            '$a': search_results.iloc[0]
        }
    }, {
        'Type': 'Condition',
        'Name': 'Cold',
        'Formula': '$a.validValues().valueSearch(isLessThan(80))',
        'Formula Parameters': {
            '$a': search_results.iloc[0]
        }
    }, {
        'Type': 'Scalar',
        'Name': 'Constant',
        'Formula': '5',
    }])

    push_df = spy.push(metadata=display_items, workbook=None)

    workbook = Analysis({
        'Name': 'test_items'
    })

    worksheet = workbook.worksheet('shifted signals')
    worksheet.display_range = {
        'Start': '2019-01-01T00:00Z',
        'End': '2019-01-02T00:00Z'
    }
    worksheet.display_items = push_df

    spy.workbooks.push(workbook)

    return workbook


def delete_correlation_udfs():
    formulas_api = sdk.FormulasApi(spy.client)
    r = formulas_api.get_packages()
    package_exists = False
    for item in r.items:
        if item.name == 'CrossCorrelationAddOn':
            package_exists = True
            break
    if package_exists:
        formulas_api.delete_package(package_name='CrossCorrelationAddOn')
