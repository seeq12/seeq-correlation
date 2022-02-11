import types
import copy
import pandas as pd
from sklearn.preprocessing import StandardScaler
import numpy as np
import pickle
import warnings
from memoization import cached
# There is a bug that prevents to correctly memorize a pandas.DataFrame
# Thus, all functions that use the @cached decorator need to accept serialized dataframes (pickle is a good option)
from ._config import _cache_max_items

DATAFRAME_METADATA_CONTAINER_FROM_SPY = 'spy'
DATAFRAME_PREPROCESSING_CONTAINER = 'preprocessing'
FUNC_PROP = 'func'
GRID_PROP = 'grid'
SUMMARY_PROP = 'summary'
QUERY_DF_PROP = 'query_df'
KWARGS_PROP = 'kwargs'
START_PROP = 'start'
END_PROP = 'end'
TZ_PROP = 'tz_convert'
STATUS_PROP = 'status'


def _reformat_time_delta(time_delta: pd.Timedelta) -> str:
    days = time_delta.days
    hours, rem = divmod(time_delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)

    total_hours = days * 24 + hours
    return f"{total_hours:02}:{minutes:02}:{seconds:02}"


def _validate_df(df):
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Expecting a dataframe, {} passed".format(type(df)))

    if len(df) <= 0:
        raise ValueError("Dataframe is empty")

    if len(df.columns) == 0:
        raise ValueError("There are zero signals in the dataframe")
    is_number = np.vectorize(lambda x: np.issubdtype(x, np.number))
    col_types = is_number(df.dtypes)
    non_numeric_cols = list(df.columns[list(np.where(~np.array(col_types))[0])])
    if not all(item for item in col_types):
        raise ValueError(f"All columns in dataframe must be numeric. Check columns={non_numeric_cols}")

    if hasattr(df, DATAFRAME_METADATA_CONTAINER_FROM_SPY) and \
            getattr(df, DATAFRAME_METADATA_CONTAINER_FROM_SPY) is None:
        delattr(df, DATAFRAME_METADATA_CONTAINER_FROM_SPY)

    if not hasattr(df, DATAFRAME_METADATA_CONTAINER_FROM_SPY):
        df_spy_properties = {
            'grid': getattr(df, GRID_PROP) if hasattr(df, GRID_PROP) else None,
            'query_df': getattr(df, QUERY_DF_PROP) if hasattr(df, QUERY_DF_PROP) else None,
            'kwargs': getattr(df, KWARGS_PROP) if hasattr(df, KWARGS_PROP) else None,
            'func': getattr(df, FUNC_PROP) if hasattr(df, FUNC_PROP) else None,
            'start': getattr(df, START_PROP) if hasattr(df, START_PROP) else None,
            'end': getattr(df, END_PROP) if hasattr(df, END_PROP) else None,
            'tz_convert': getattr(df, TZ_PROP) if hasattr(df, TZ_PROP) else None,
            'status': getattr(df, STATUS_PROP) if hasattr(df, STATUS_PROP) else None,

            }

        properties = types.SimpleNamespace(**df_spy_properties)
        setattr(df, DATAFRAME_METADATA_CONTAINER_FROM_SPY, properties)
        # noinspection PyProtectedMember
        if DATAFRAME_METADATA_CONTAINER_FROM_SPY not in df._metadata:
            # noinspection PyProtectedMember
            df._metadata.append(DATAFRAME_METADATA_CONTAINER_FROM_SPY)

    namespace = getattr(df, DATAFRAME_METADATA_CONTAINER_FROM_SPY)
    if not namespace.grid:
        warnings.warn(
            "'DataFrame' object has 'spy.grid=None'. An attempt to infer the sampling frequency will be made")
        if not pd.infer_freq(df.index):
            raise ValueError("Sampling period could not be inferred. "
                             "It looks like the dataframe does not have a uniform grid. Try pulling the data using"
                             "spy.pull with a `grid` value and make sure that there are no invalid values in the"
                             "time period of interest")


def attach_summary(df, summary):
    """
    This functions adds the summary of a pre-processing operation as property
    of the DataFrame that contains the data.

    Parameters
    ----------
    df: pandas.DataFrame
        A DataFrame that contains a set of signals as columns and date-time as
        the index.
    summary: pandas.DataFrame
        A DataFrame of exactly one column with the summary of the
        pre-processing step and signal names as index.

    Returns
    -------
    df: pandas.DataFrame
        The input DataFrame with a preprocessing container attached as metadata.


    Notes
    ------
    This function modifies the input DataFrame by adding or updating the
    `preprocessing.summary` property.

    """
    if len(df.columns) > len(summary):
        columns = df.columns
    else:
        columns = summary.index
    try:
        namespace = getattr(df, DATAFRAME_PREPROCESSING_CONTAINER)
        if namespace.summary is not None:
            summary_df = copy.deepcopy(namespace.summary)
            cols = list(summary_df.columns)
        else:
            summary_df = pd.DataFrame(columns=[], index=columns)
            cols = []
    except AttributeError:
        summary_df = pd.DataFrame(columns=[], index=columns)
        cols = []

    if len(summary.columns) != 1:
        raise ValueError("Expecting a dataframe of exactly one column")

    if summary.columns[0] in summary_df:
        new_summary = copy.deepcopy(summary_df)
        new_summary.update(summary)

    else:
        new_summary = summary_df.join(summary)
    if summary.columns[0] not in cols:
        cols += [summary.columns[0]]

    new_summary.replace('', '-', inplace=True)
    new_summary.fillna('-', inplace=True)

    # noinspection PyProtectedMember
    if DATAFRAME_PREPROCESSING_CONTAINER not in df._metadata:
        # noinspection PyProtectedMember
        df._metadata.append(DATAFRAME_PREPROCESSING_CONTAINER)

    # cols helps to keep the order of the columns
    summary_namespace = types.SimpleNamespace(summary=new_summary[cols])
    setattr(df, DATAFRAME_PREPROCESSING_CONTAINER, summary_namespace)


@cached(max_size=_cache_max_items)
def _pickled_standardization(df_serialized):
    df = _pickled_non_numeric(df_serialized, True)
    if df.empty:
        return pd.DataFrame()
    names = df.columns
    index = df.index
    scaler = StandardScaler()
    scaled_df = scaler.fit_transform(df)
    scaled_df = pd.DataFrame(scaled_df, index=index, columns=names)
    # noinspection PyProtectedMember
    for x in df._metadata:
        if x in df.__dict__.keys():
            value = df.__getattr__(x)
            scaled_df.__setattr__(x, value)
            # noinspection PyProtectedMember
            if x not in scaled_df._metadata:
                # noinspection PyProtectedMember
                scaled_df._metadata += [x]

    return scaled_df


@cached(max_size=_cache_max_items)
def _pickled_interpolate(df_serialized, consecutivenans):
    df = pickle.loads(df_serialized)
    if df.empty:
        return pd.DataFrame()
    percentages = df.isna().mean()
    limit = int(len(df) * consecutivenans)
    if limit == 0:
        interpolated_df = copy.deepcopy(df)
    else:
        interpolated_df = df.interpolate(method='linear', limit_direction='both', limit=limit)
    new_percentages = interpolated_df.isna().mean()
    percentages.name = 'Initial Invalid (%)'
    new_percentages.name = 'Invalid after Interpolation (%)'
    attach_summary(interpolated_df, np.round(percentages.to_frame() * 100, 2))
    attach_summary(interpolated_df, np.round(new_percentages.to_frame() * 100, 2))

    return interpolated_df


@cached(max_size=_cache_max_items)
def _pickled_flat_lines(df_serialized):
    # df = pickle.loads(df_serialized)
    df = _pickled_non_numeric(df_serialized, True)
    if df.empty:
        return pd.DataFrame()
    # dff = df.diff()
    keep = list(df.describe().loc['std'][df.describe().loc['std'] != 0].index)
    remove = list(df.describe().loc['std'][df.describe().loc['std'] == 0].index)
    if len(remove) > 0:
        warnings.warn("The signals {} appear to be flat lines and have been removed from the analysis".format(remove))
    df_out = df[keep]

    summary = ["Yes (removed)" if x in remove else "No" for x in df.columns]
    local_summary = pd.DataFrame(data=summary, columns=['Flat Signal?'], index=df.columns)
    attach_summary(df_out, local_summary)
    return df_out


@cached(max_size=_cache_max_items)
def _pickled_gaps(df_serialized, percent_nan):
    df = pickle.loads(df_serialized)
    if df.empty:
        return pd.DataFrame()
    percentages = df.isna().mean()
    marked_for_removal = percentages[percentages > percent_nan]
    cols_to_remove = list(marked_for_removal.index)
    dff = copy.deepcopy(df.drop(labels=cols_to_remove, axis=1))
    if len(cols_to_remove) > 0:
        warnings.warn(f"The signals {cols_to_remove} have been removed from the analysis since they have "
                      f"more than {percent_nan * 100:.2f}% invalid values")

    summary = ["Yes (removed)" if x in cols_to_remove else "No" for x in df.columns]
    local_summary = pd.DataFrame(data=summary, columns=['Gaps in Signal?'], index=df.columns)
    attach_summary(dff, local_summary)
    return dff


@cached(max_size=_cache_max_items)
def _pickled_non_numeric(df_serialized, auto_remove):
    df = pickle.loads(df_serialized)
    if df.empty:
        return pd.DataFrame()
    types = df.infer_objects().dtypes
    types_dict = types.to_dict()
    non_numeric_signals = [k for k, v in types_dict.items() if v.name == 'object']
    if auto_remove:
        summary = ["No (removed)" if v.name == 'object' else "Yes" for k, v in types_dict.items()]
        dff = copy.deepcopy(df.drop(labels=non_numeric_signals, axis=1))
        if len(non_numeric_signals) > 0:
            warnings.warn(
                f"The signals {non_numeric_signals} have been removed from the analysis since they are non-numeric")
    else:
        summary = ["No (retained)" if v.name == 'object' else "Yes" for k, v in types_dict.items()]
        dff = copy.deepcopy(df)
        if len(non_numeric_signals) > 0:
            warnings.warn(
                f"The signals {non_numeric_signals} have been detected as non-numeric but have not been removed."
                f"Use `auto_remove=True` to remove them from the dataframe")

    local_summary = pd.DataFrame(data=summary, columns=['Numeric Signal?'], index=df.columns)
    attach_summary(dff, local_summary)

    return dff


@cached(max_size=_cache_max_items)
def _pickled_duplicated_column_names(df_serialized):
    df = pickle.loads(df_serialized)
    _validate_df(df)
    if df.empty:
        return pd.DataFrame()
    cols = pd.Series(df.columns)

    for dup in cols[cols.duplicated()].unique():
        cols[cols[cols == dup].index.values.tolist()] = [dup + '.' + str(i) if i != 0 else dup for i in
                                                         range(sum(cols == dup))]

    if hasattr(df, DATAFRAME_METADATA_CONTAINER_FROM_SPY):
        namespace = getattr(df, DATAFRAME_METADATA_CONTAINER_FROM_SPY)
        if namespace.query_df is not None:
            if list(df.columns) == list(namespace.query_df['Name'].values):
                namespace.query_df['New Name'] = cols

    # rename the columns with the cols list.
    df.columns = cols
    return df


@cached(max_size=_cache_max_items)
def _pickled_sampling_info(df_serialized, sampling_ratio_threshold, remove=False):
    keyword = 'tagged'
    if remove:
        keyword = 'removed'

    df = pickle.loads(df_serialized)
    _validate_df(df)
    if df.empty:
        return pd.DataFrame()

    dff = copy.deepcopy(df)
    if hasattr(dff, DATAFRAME_METADATA_CONTAINER_FROM_SPY):
        namespace = getattr(df, DATAFRAME_METADATA_CONTAINER_FROM_SPY)
        if namespace.kwargs is None or 'items' not in namespace.kwargs or 'New Name' not in namespace.query_df.columns:
            return dff
        if 'Estimated Sample Period' not in namespace.kwargs['items']:
            return dff
        summary_sampling_period = pd.DataFrame(data=namespace.kwargs['items']['Estimated Sample Period'].values,
                                               columns=['Original Sampling Period'],
                                               index=namespace.query_df['New Name'].values)
        summary_sampling_period['Original Sampling Period'] = summary_sampling_period['Original Sampling Period'].apply(
            _reformat_time_delta)
        attach_summary(dff, summary_sampling_period)
        if hasattr(namespace, GRID_PROP):
            if namespace.grid is None:
                return dff
            grid = pd.Timedelta(namespace.grid)
            ratio_sampling_periods = pd.DataFrame(
                data=namespace.kwargs['items']['Estimated Sample Period'].values / grid,
                columns=['Ratio of sampling periods (raw/gridded)'], index=namespace.query_df['New Name'].values)
            remove_signals = ratio_sampling_periods['Ratio of sampling periods (raw/gridded)'][
                (ratio_sampling_periods['Ratio of sampling periods (raw/gridded)'] > sampling_ratio_threshold) |
                (ratio_sampling_periods['Ratio of sampling periods (raw/gridded)'] < 1 / sampling_ratio_threshold)
                ].index
            remove_signals = [x for x in remove_signals if x in dff.columns]

            summary = [f'{row["Ratio of sampling periods (raw/gridded)"]} ({keyword})' if index in remove_signals else
                       f'{row["Ratio of sampling periods (raw/gridded)"]} (previously removed)'
                       if index not in dff.columns
                       else f'{row["Ratio of sampling periods (raw/gridded)"]}'
                       for index, row in ratio_sampling_periods.iterrows()]

            ratio_sampling_periods['Ratio of sampling periods (raw/gridded)'] = summary
            if remove:
                dff = copy.deepcopy(dff.drop(labels=remove_signals, axis=1))
            attach_summary(dff, ratio_sampling_periods)

    return dff


def standardization(df):
    """
    Scales the data in the DataFrame to zero mean and unit variance

    Parameters
    ----------
    df: pandas.DataFrame
        A pickled DataFrame that contains a set of signals as columns and
        date-time as the index.

    Returns
    --------
    scaled_df: pandas.DataFrame
        A DataFrame that contains a the scaled signals as columns and
        date-time as the index.

    Notes
    ------
    A summary of how this function modified or tagged signals in the dataframe
    can be accessed in the property `scaled_df.preprocessing.summary`.

    """

    return _pickled_standardization(pickle.dumps(df))


def interpolate_nans(df, consecutivenans=0.05):
    """
    Interpolates invalid values (linearly) per signal only if the percentage of
    consecutive invalid values with respect to the total number of samples is
    less than the specified threshold.

    Parameters
    ----------
    df: pandas.DataFrame
        A DataFrame that contains a set of signals as columns and date-time
        as the index.
    consecutivenans: float, default  0.05
        percentage of the total number of samples that the interpolator will
        fill consecutive invalid values.

    Returns
    --------
    interpolated_df: pandas.DataFrame
        A DataFrame with the interpolated values (if applicable)

    Notes
    ------
    A summary of how this function modified or tagged signals in the dataframe
    can be accessed in the property `interpolated_df.preprocessing.summary`.

    """

    return _pickled_interpolate(pickle.dumps(df), consecutivenans)


def remove_flat_lines(df):
    """
    Find signals with zero variance (flat lines) and remove them from the
    input DataFrame

    Parameters
    ----------
    df: pandas.DataFrame
        A DataFrame that contains a set of signals as columns and date-time as
        the index.

    Returns
    ---------
    df_out: pandas.DataFrame
        A DataFrame without the signals that are flat lines

    Notes
    ------
    A summary of how this function modified or tagged signals in the dataframe
    can be accessed in the property `df_out.preprocessing.summary`

    """

    return _pickled_flat_lines(pickle.dumps(df))


def remove_signals_with_missing_data(df, percent_nan=0.4):
    """
    Removes columns from the dataframe that have a high percentage of missing
    data.

    Parameters
    ----------
    df: pandas.DataFrame
        A DataFrame that contains a set of signals as columns and date-time as
        the index.
    percent_nan: float, default 0.4
        Maximum percentage of invalid values (from the total number of samples)
        allowed in order to keep the signal in the DataFrame.

    Returns
    --------
    dff: pandas.DataFrame
        A DataFrame of the signals that have less than percent_nan of missing
        data.

    Notes
    ------
    A summary of how this function modified or tagged signals in the dataframe
    can be accessed in the property `dff.preprocessing.summary`.

    """

    return _pickled_gaps(pickle.dumps(df), percent_nan)


def remove_non_numeric(df, auto_remove=True):
    """
    Removes non-numeric signals from the input DataFrame.

    Parameters
    ----------
    df: pandas.DataFrame
        A DataFrame that contains a set of signals as columns and date-time as
        the index.
    auto_remove: bool, default True
        Removes the non-numeric signals from the DataFrame if set to True.
        Otherwise, it just tags the signals.

    Returns
    --------
    dff: pandas.DataFrame
        A DataFrame of the signals that do not have non-numeric data

    Notes
    ------
    A summary of how this function modified or tagged signals in the dataframe
    can be accessed in the property `dff.preprocessing.summary`.

    """

    return _pickled_non_numeric(pickle.dumps(df), auto_remove)


def duplicated_column_names(df):
    """
    Renames columns that have the same column name

    Parameters
    ----------
    df: pandas.DataFrame
        A DataFrame that contains a set of signals as columns and date-time as
        the index.

    Returns
    --------
    dff: pandas.DataFrame
        A DataFrame of the signals with unique column names

    """

    return _pickled_duplicated_column_names(pickle.dumps(df))


def sampling_info(df, sampling_ratio_threshold, remove):
    """
    Attaches sampling period information if available and removes or tags
    signals that have a high or low ratio of sampling period to gridded period.

    Parameters
    ----------
    df: pandas.DataFrame
        A DataFrame that contains a set of signals as columns and date-time as
        the index.
    sampling_ratio_threshold: float
        Signals with a sampling rate ratio (raw/gridded) above
        sampling_ratio_threshold or below 1/sampling_ratio_threshold will be
        removed from the dataframe.
    remove: bool
        Removes signals whose sampling period is too different (set by
        sampling_ratio_threshold) from the median of sampling rates.

    Returns
    --------
    dff: pandas.DataFrame
        A DataFrame of the signals with unique column names

    """

    return _pickled_sampling_info(pickle.dumps(df), sampling_ratio_threshold, remove)


def default_preprocessing_wrapper(df, consecutivenans=0.04, percent_nan=0.0, remove_disparate_sampled=False,
                                  sampling_ratio_threshold=4, bypass_processing=False):
    """
    Parameters
    ----------
    df: pandas.DataFrame
        A DataFrame that contains a set of signals as columns and date-time as
        the index.
    consecutivenans: float, default 0.01
        percentage of the total number of samples that the interpolator will
        fill consecutive invalid values.
    percent_nan: float, default 0.0
        Maximum percentage of invalid values (from the total number of samples)
        allowed in order to keep the signal in the DataFrame.
    remove_disparate_sampled: bool, default False
        Removes signals whose sampling period is too different (set by
        sampling_ratio_threshold) from the median of sampling rates
    sampling_ratio_threshold: float, default 2.5
        Signals with a sampling rate ratio (raw/gridded) above
        sampling_ratio_threshold or below 1/sampling_ratio_threshold will be
        removed from the dataframe
    bypass_processing: bool, default False
        If true, pre-processing routines in this wrapper are by-passed.
        However, the _validate_df is still run to check that the dataframe
        is valid even if bypass_processing is set to True.

    Returns
    --------
    dff: pandas.DataFrame
        A DataFrame of the cleansed signals

    Notes
    ------
    A summary of how this function modified or tagged signals in the dataframe can be accessed in
    the property `dff.preprocessing.summary`

    """

    df = copy.deepcopy(df)

    df = duplicated_column_names(df)
    df = remove_non_numeric(df)

    if not bypass_processing:
        df = interpolate_nans(df, consecutivenans=consecutivenans)
        df = remove_signals_with_missing_data(df, percent_nan=percent_nan)
        df = remove_flat_lines(df)
        df = standardization(df)
    else:
        df = remove_flat_lines(df)
        df = standardization(df)

    df = sampling_info(df, sampling_ratio_threshold, remove=remove_disparate_sampled)

    _validate_df(df)
    return df
