import warnings
import pandas as pd
from IPython import display
from IPython.core.display import HTML
from seeq import spy, sdk
from .utils import create_condition, create_workstep_signals
from . import default_preprocessing_wrapper
from . import lags_coeffs, signals_from_formula

DEFAULT_WORKBOOK_PATH = 'Correlation >> Correlation Analysis'
DEFAULT_WORKBOOK_NAME = DEFAULT_WORKBOOK_PATH.split('>>')[-1].strip()
DEFAULT_WORKSHEET_NAME = 'From Correlation'


def create_lagged_signals(signal_ids, signal_names, workbook_id, time_shifts, time_unit, target, api_client,
                          include_original_signals, suffix):
    if not (len(signal_ids) == len(signal_names) == len(time_shifts)):
        raise RuntimeError("Inconsistent number of signal names, signal ids and signal lags")

    lagged_signals = []
    signals_api = sdk.SignalsApi(api_client)
    for time_shift, signalId, signalName in zip(time_shifts, signal_ids, signal_names):

        if target == signalName:
            continue
        delay_seconds = pd.Timedelta(time_shift, time_unit).value / 1000000000

        payload = dict(name=f"{signalName}.aligned_to.{target}{suffix}",
                       formula=f"$signal.move({delay_seconds}s)",
                       formulaParameters=[f"signal={str(signalId)}"],
                       scopedTo=workbook_id
                       )
        r = signals_api.create_signal_with_http_info(body=payload)[0]

        if include_original_signals:
            lagged_signals.extend([signalId, r.data_id])
        else:
            lagged_signals.append(r.data_id)

    return lagged_signals


def get_existing_worksheet(workbook_id, worksheet_id, api_client):
    workbooks_api = sdk.WorkbooksApi(api_client)
    existing_worksheet = workbooks_api.get_worksheet(workbook_id=workbook_id,
                                                     worksheet_id=worksheet_id)  # type: sdk.WorksheetOutputV1
    return existing_worksheet


def get_workbook(workbook, worksheet, datasource):
    if workbook is None:
        raise ValueError('Either a workbook path or a workbook ID must be supplied')

    if worksheet is None:
        raise ValueError('Either a worksheet name or a worksheet ID must be supplied')

    else:
        if worksheet is None or not isinstance(worksheet, str):
            raise RuntimeError('When workbook is supplied, worksheet must also be supplied as a string')
        if spy.utils.is_guid(workbook):
            primary_workbook = spy.workbooks.pull(pd.DataFrame([{
                'ID': workbook.upper(),
                'Type': 'Workbook',
                'Workbook Type': 'Analysis'
            }]), include_inventory=False, quiet=True)[0]

        else:
            search_query, workbook_name = spy._push.create_analysis_search_query(workbook)
            search_df = spy.workbooks.search(search_query, quiet=True)
            if len(search_df) == 0:
                primary_workbook = spy.workbooks.Analysis({'Name': workbook_name})
                primary_workbook.worksheet(worksheet)
                spy.workbooks.push(primary_workbook, path=None, datasource=datasource,
                                   include_inventory=False, quiet=True)
            else:
                primary_workbook = spy.workbooks.pull(search_df, include_inventory=False, quiet=True)[0]

        if spy.utils.is_guid(worksheet):
            worksheet_id = worksheet
        else:
            primary_worksheet = primary_workbook.worksheet(worksheet)
            spy.workbooks.push(primary_workbook, path=None, datasource=datasource, include_inventory=False,
                               quiet=True)
            worksheet_id = primary_worksheet.id
    # Note: Path is None to cover the case where an admin is pushing data to a single workbook that they don't own.
    # In R51, there's a proper user folder in the path that can be used as the folder_id. In R50 there is no such
    # user folder, so the folder_id will end up being __All__ or __Shared__, which is not viable to use as a parent
    # folder. But in the case where we're pushing to only the primary workbook, then we don't need to supply the
    # folder_id because the workbook is not being moved and we're not adding other sibling workbooks
    # (and therefore we don't need to know the actual folder that the workbook is in).

    return primary_workbook.id, worksheet_id


def create_corr_time_shift_signals(signal_pairs, workbook_id, formula_type, api_client, window_size, period,
                                   corr_thrs=None, max_time_shift=None, output_time_unit=None, suffix=''):
    new_signals_ids = []
    for signal in list(signal_pairs):
        r = signals_from_formula(signal[0], signal[1], workbook_id, formula_type=formula_type, window=window_size,
                                 period=period, corr_threshold=corr_thrs, max_time_shift=max_time_shift,
                                 output_time_unit=output_time_unit, suffix=suffix, api_client=api_client)
        new_signals_ids.append(r.data_id)
    return new_signals_ids


def worksheet_corrs_and_time_shifts(signal_pairs_ids: list, workbook_id: str,
                                    worksheet_name: str, start_time: str, end_time: str, corr_coeff_signals=True,
                                    time_shifted_for_correlation=True, output_time_unit=None, max_time_shift=None,
                                    suffix='', time_shifts_signals=True, window_size=None, period=None, corr_thrs=0.5,
                                    condition_id=None, overwrite=True, api_client=None, datasource=None):
    """
    Creates a new Seeq worksheet with the either the cross-correlation
    coefficient signals or the time shifted signals to maximize cross-
    correlation, or both, for each pair of signals passed to the function.
    It can append or overwrite the worksheet if it already exists.

    Parameters
    ----------
    signal_pairs_ids: list
        List of two-item tuples. The items of each tuple are a Seeq signal ID.
        Each pair of signals is used to compute the cross-correlation
        coefficient and, if requested, the time shift to maximize the
        correlation coefficient.
    workbook_id: str
        The ID of the Seeq workbook that the resulting signals will be scoped to.
    worksheet_name: str
        The name of the Seeq worksheet that will be created to display the
        resulting signals.
    start_time: str
        The start time for the display range of the worksheet.
    end_time: str
        The end time for the display range of the worksheet.
    corr_coeff_signals: bool, default True
        Whether a cross-correlation signal for each input signal pair will be
        calculated.
    time_shifted_for_correlation: bool, default True
        Whether to allow time shift that maximizes cross-correlation of each
        input signal pair. This option will not push a time shift signal to
        the Seeq server. It simply allows a time shift calculation behind the
        scenes to calculate the maximum correlation coefficient within the
        allowable max_time_shift.
    output_time_unit: {str, None}, default None
        The time unit of the output time shifted signal
    max_time_shift: {str, None}, default None
        Maximum allowable time shift to maximize cross-correlations of
        each input signal pair.
    suffix: str, default ''
        Suffix added to the names of the resulting signals
    time_shifts_signals: bool, default True
        Whether to calculate a time shifted signal that maximizes cross-
        correlation of each input signal pair.
    window_size: {str, None}, default None
        Size (timeframe) of the rolling window used for the calculations.
    period: {str, None}, default None
        Spacing between rolling windows used for the calculations
    corr_thrs: float, default 0.5
        The minimum acceptable correlation coefficient value for a time
        shift to be valid. When the correlation coefficient is below this
        threshold, the corresponding time shift value will not be considered
        for the final offset. Choose a threshold value between 0-1.
    condition_id: {str, None}, default None
        Seeq condition ID used to tag the analysis
    overwrite: bool, default True
        Overwrite the current worksheet
    api_client: spy.client, default None
        Authenticated Seeq client
    datasource: {str, None}, default None
        The name of the datasource within which to contain all the
        pushed items. Do not create new datasources unless you really
        want to and you have permission from your administrator.

    Returns
    -------
    url: str
        The URL of the Seeq Worksheet where the correlation and time shifted
        signals are displayed.

    """

    all_new_signals = []

    if max_time_shift is None:
        time_shifts_signals = False
        time_shifted_for_correlation = False

    if corr_coeff_signals:
        if time_shifted_for_correlation:
            formula_type = 'pearson_with_time_shifts'
        else:
            formula_type = 'pearson'
        all_new_signals.extend(
            create_corr_time_shift_signals(signal_pairs_ids, workbook_id, formula_type, api_client,
                                           window_size, period, corr_thrs=corr_thrs, max_time_shift=max_time_shift,
                                           output_time_unit=output_time_unit, suffix=suffix))

    if time_shifts_signals:
        all_new_signals.extend(
            create_corr_time_shift_signals(signal_pairs_ids, workbook_id, 'time_shifts', api_client,
                                           window_size, period, corr_thrs=corr_thrs, max_time_shift=max_time_shift,
                                           output_time_unit=output_time_unit, suffix=suffix))

    if condition_id is None:
        condition_id = create_condition(
            start_time, end_time, workbook_id, api_client,
            capsule_name='Correlation Analysis')

    workbook_id, worksheet_id = get_workbook(workbook_id, worksheet_name, datasource)
    existing_worksheet = get_existing_worksheet(workbook_id, worksheet_id, api_client)
    create_workstep_signals(existing_worksheet,
                            workbook_id,
                            all_new_signals,
                            start_time,
                            end_time,
                            condition_id,
                            overwrite,
                            api_client)
    return "/".join([spy.client.host.replace('/api', ""), 'workbook', workbook_id, 'worksheet', existing_worksheet.id])


def worksheet_with_lagged_signals(signal_ids, signal_names, time_shifts, time_unit, target,
                                  workbook_id, worksheet_id, start_time, end_time, overwrite, api_client,
                                  include_original_signals, suffix, condition_id):
    lagged_signals = create_lagged_signals(signal_ids, signal_names, workbook_id, time_shifts, time_unit, target,
                                           api_client, include_original_signals, suffix)

    existing_worksheet = get_existing_worksheet(workbook_id, worksheet_id, api_client)

    if condition_id is None:
        condition_id = create_condition(start_time, end_time, workbook_id, api_client,
                                        capsule_name='Correlation Analysis')

    create_workstep_signals(existing_worksheet,
                            workbook_id,
                            lagged_signals,
                            start_time,
                            end_time,
                            condition_id,
                            overwrite,
                            api_client)

    return "/".join([spy.client.host.replace('/api', ""), 'workbook', workbook_id, 'worksheet', existing_worksheet.id])


def create_worksheet(df, target, max_time_shift='auto', metadata=None, workbook=DEFAULT_WORKBOOK_PATH,
                     worksheet=DEFAULT_WORKSHEET_NAME, datasource=None, overwrite=False, api_client=None,
                     include_original_signals=False, suffix='', new_condition=True, bypass_preprocessing=False):
    """
    Creates a new Seeq worksheet with the signals from the dataframe column names, including the
    time shifted signals based on the time shifts calculated to maximize cross-correlation. This function can
    append or overwrite the worksheet if it already exists.


    Parameters
    -----------
    df: pandas.DataFrame
        The dataframe containing the signals and target that will be included in the worksheet.
    target: str
        Name of the signal (from DataFrame column names) to be used as a target to maximize cross-correlation. All other
        signals in the dataframe will be time shifted with respect to the target to maximize cross-correlations.
    max_time_shift: {'auto', str, None}, default 'auto'
        Maximum time (e.g. '15s', or '1min') that the signals are allowed to slide in time in order to
        maximize cross-correlation. For times specified as a str, normal time units are accepted.If 'auto' is
        selected, a default maximum time shift is calculated based on the number of samples. If None, the raw signals
        are used and no time shifts are calculated.
    metadata: pandas.DataFrame, default None
        A dataframe with at least two columns: Name and ID. This dataframe is typically the output of the
        spy.search() function. If the dataframe was obtained with spy.pull,
        the metadata is already stored in the property 'spy.query_df'. If that is the case this metadata parameter
        might be omitted.
    workbook: {str, None}, default 'Correlation >> Correlation Analysis'
        The path to a workbook (in the form of 'Folder >> Path >> Workbook Name') or an ID that all
        pushed items will be 'scoped to'. Items scoped to a certain workbook will not be visible/searchable
        using the data panel in other workbooks. The ID for a workbook is visible in the URL of Seeq Workbench,
        directly after the "workbook/" part.
    worksheet: str, default 'from Correlation'
        The name of a worksheet within the workbook to create/update that will render the signals that are been pushed
        with their respective time shifted signals based on maximum cross-correlations.
    datasource: str, optional
        The name of the datasource within which to contain all the
        pushed items. By default, all pushed items will be contained in a "Seeq
        Data Lab" datasource. Do not create new datasources unless you really
        want to and you have permission from your administrator.
    overwrite: bool
        Whether the worksheet is overwritten if already exists.
    api_client: {spy.client, None}, default None
        API client use for authentication with the Seeq server
    include_original_signals: bool, default True
        Whether the worksheet will include the original signals along with the shifted signals with respect to a target
        or only the shifted signals.
    suffix: str, default to ""
        Suffix added to the shifted signals tha will be created
    new_condition: bool
        True if a new condition with one capsule for the analysis time range will be created
    bypass_preprocessing: bool, default False
        Whether the data pre-processing routine is by-passed or not. Setting it to True is not recommended
        unless the data has been pre-processed elsewhere.

    Returns
    --------
    -: None
        Creates a Seeq worksheet with the signals in the DataFrame and the lagged signals to maximize cross correlations

    """

    url = _create_worksheet(df, target, max_time_shift=max_time_shift, metadata=metadata, workbook=workbook,
                            worksheet=worksheet, datasource=datasource, overwrite=overwrite, api_client=api_client,
                            include_original_signals=include_original_signals, suffix=suffix,
                            new_condition=new_condition, bypass_preprocessing=bypass_preprocessing)

    worksheet_hyperlink = f'<a href="{url}">{url}</a>'
    # noinspection PyTypeChecker
    display(HTML(worksheet_hyperlink))


def _create_worksheet(df, target, max_time_shift='auto', metadata=None, workbook=DEFAULT_WORKBOOK_PATH,
                      worksheet=DEFAULT_WORKSHEET_NAME, datasource=None, overwrite=False, api_client=None,
                      include_original_signals=False, suffix='', new_condition=True, bypass_preprocessing=False):
    df = default_preprocessing_wrapper(df, bypass_processing=bypass_preprocessing)

    if metadata is None:
        try:
            if df.spy.query_df is None:
                raise ValueError(
                    "Metadata not found. Supply metadata as a dataframe with either the 'metadata' parameter "
                    "or the 'spy.query_df' attribute of the input signals dataframe")
            metadata = df.spy.query_df

        except AttributeError as e:
            warnings.warn(str(e) + "Metadata attribute not found for provided dataframe")
            raise AttributeError("Metadata not found. Supply metadata as a dataframe with either the 'metadata' "
                                 "parameter or the 'spy.query_df' attribute of the input signals dataframe")

    if 'ID' not in metadata:
        raise KeyError('ID not found in metadata. Make sure the metadata dataframe includes '
                       'the IDs of the input signals')

    if not api_client:
        api_client = spy.client

    workbookID, worksheetID = get_workbook(workbook, worksheet, datasource)

    # noinspection PyProtectedMember
    if hasattr(spy, 'session'):
        pd_start, pd_end = spy._login.validate_start_and_end(spy.session, df.index[0], df.index[-1])
    else:
        pd_start, pd_end = spy._login.validate_start_and_end(df.index[0], df.index[-1])
    start_time = pd_start.tz_convert('utc').isoformat().replace('+00:00', 'Z')
    end_time = pd_end.tz_convert('utc').isoformat().replace('+00:00', 'Z')

    lags, coeffs, sampling_time, time_unit, maxlags = lags_coeffs(df, max_time_shift, 's')
    idx = list(df.columns).index(target)
    time_shifts = lags[idx] * sampling_time

    col = 'Renamed Columns' if 'Renamed Columns' in metadata else 'Name'
    if len(metadata[col]) != len(set(metadata[col])):
        raise LookupError(f"Metadata dataframe contains two or more signals with identical names in column {col}"
                          "which results in an ambiguous search")

    signal_ids = [list(metadata['ID'])[list(metadata[col]).index(name)] for name in df.columns]
    signal_names = list(df.columns)

    if new_condition:
        condition_id = create_condition(start_time, end_time, workbookID, api_client,
                                        capsule_name='Correlation Analysis')
    else:
        condition_id = None

    url = worksheet_with_lagged_signals(signal_ids, signal_names, time_shifts, time_unit, target, workbookID,
                                        worksheetID, start_time, end_time, overwrite, api_client,
                                        include_original_signals, suffix, condition_id)

    return url
