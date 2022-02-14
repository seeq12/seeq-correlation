import pandas as pd
from seeq import spy
from urllib.parse import urlparse, unquote, parse_qs


def pull_only_signals(url, grid='auto'):
    """
    Pull only the signals shown in the display pane of a Seeq Analysis
    Worksheet. The time range used for the pull will be taken from the
    display range in the worksheet. Conditions will be disregarded.

    Parameters
    ----------
    url: str
        The url of a Seeq worksheet. On
    grid: str
        The grid of the data pull used in spy.pull

    Returns
    -------
    df: pd. DataFrame
        A dataframe with signal data of the worksheet

    """
    worksheet = spy.utils.get_analysis_worksheet_from_url(url)
    start = worksheet.display_range['Start']
    end = worksheet.display_range['End']

    search_df = spy.search(url, estimate_sample_period=worksheet.display_range, quiet=True)
    if search_df.empty:
        return pd.DataFrame()
    search_signals_df = search_df[search_df['Type'].str.contains('Signal')]

    df = spy.pull(search_signals_df, start=start, end=end, grid=grid, header='ID', quiet=True,
                  status=spy.Status(quiet=True))
    if df.empty:
        return pd.DataFrame()

    if hasattr(df, 'spy') and hasattr(df.spy, 'query_df'):
        df.columns = df.spy.query_df['Name']
    elif hasattr(df, 'query_df'):
        df.columns = df.query_df['Name']
    else:
        raise AttributeError(
            "A call to `spy.pull` was successful but the response object does not contain the `spy.query_df` property "
            "required for `seeq.addons.correlation")
    return df


def parse_url(url):
    unquoted_url = unquote(url)
    return urlparse(unquoted_url)


def get_worksheet_url(jupyter_notebook_url):
    parsed = parse_url(jupyter_notebook_url)
    params = parse_qs(parsed.query)
    return f"{parsed.scheme}://{parsed.netloc}/workbook/{params['workbookId'][0]}/worksheet/{params['worksheetId'][0]}"


def get_workbook_worksheet_workstep_ids(url):
    parsed = parse_url(url)
    params = parse_qs(parsed.query)
    workbook_id = None
    worksheet_id = None
    workstep_id = None
    if 'workbookId' in params:
        workbook_id = params['workbookId'][0]
    if 'worksheetId' in params:
        worksheet_id = params['worksheetId'][0]
    if 'workstepId' in params:
        workstep_id = params['workstepId'][0]
    return workbook_id, worksheet_id, workstep_id
