import time
import json
import string
import traceback

import pandas as pd

from seeq import spy, sdk
from seeq.spy._errors import *
from dateutil.parser import parse


def get_workbook_and_worksheet(workbook_id, worksheet_id=None, **kwargs):
    """
    Get a workbook and optionally a worksheet by ID

    Parameters
    ----------
    workbook_id : str
        The Seeq ID of the desired workbook
    worksheet_id : str, optional
        The Seeq ID of the desired worksheet within the workbook
    kwargs : dict
        Additional keyword arguments passed to the calls to spy.

    Returns
    -------
    tuple
        spy.workbooks.Analysis, None if no worksheet_id is specified
        spy.workbooks.Analysis, spy.workbooks.Worksheet if worksheet_id is
        specified
    """
    # quiet by default
    if 'quiet' not in kwargs:
        kwargs['quiet'] = True

    search = spy.workbooks.search({'ID': workbook_id}, all_properties=True, **kwargs)

    if search.empty:
        raise RuntimeError(f'Could not find the workbook with Seeq ID "{workbook_id}". ')

    try:
        specific_worksheet_ids = [worksheet_id] if worksheet_id else None
        wb = spy.workbooks.pull(search, specific_worksheet_ids=specific_worksheet_ids,
                                include_referenced_workbooks=False, include_annotations=False,
                                include_images=False, include_inventory=False,
                                include_rendered_content=False, **kwargs)[0]
    except TypeError:
        wb = spy.workbooks.pull(search, include_referenced_workbooks=False, include_annotations=False,
                                include_images=False, include_inventory=False,
                                include_rendered_content=False, **kwargs)[0]
    except Exception as e:
        raise SPyRuntimeError(str(e))

    if worksheet_id is None:
        return wb, None

    try:
        ws = wb.worksheets[worksheet_id]
    except IndexError:
        raise RuntimeError(f'Could not find the worksheet with Seeq ID "{worksheet_id}" '
                           f'in the workbook with ID "{workbook_id}. ')

    return wb, ws


def create_workstep_signals(existing_worksheet, workbook_id, signal_ids, start_time, end_time, condition_id,
                            overwrite, api_client):
    wb, ws = get_workbook_and_worksheet(workbook_id, existing_worksheet.id)
    workstep = ws.current_workstep()
    display_range, investigate_range = ws.display_range, ws.investigate_range
    if not ws.current_workstep() or overwrite:
        workstep = ws.workstep('Correlation Analysis Signals')

    current_display_items = ws.current_workstep().display_items
    previous_highest_lane = max(current_display_items['Lane']) if not current_display_items.empty else 0

    new_items = {"ID": [], "Type": [], "Lane": [], "Axis Auto Scale": []}
    for signal in signal_ids:
        previous_highest_lane += 1
        new_items['ID'].append(signal)
        new_items['Type'].append("Signal")
        new_items['Lane'].append(previous_highest_lane)
        new_items['Axis Auto Scale'].append(True)

    if condition_id is not None:
        previous_highest_lane += 1
        new_items['ID'].append(condition_id)
        new_items['Type'].append("Condition")
        new_items['Lane'].append(previous_highest_lane)
        new_items['Axis Auto Scale'].append(True)

    workstep.display_items = pd.concat([current_display_items, new_items]).\
        drop_duplicates(keep='first', subset=['ID']).reset_index()
    workstep.display_range = display_range
    workstep.investigate_range = investigate_range

    ws.push_current_workstep()


def create_condition(start_time, end_time, workbook_id, api_client, capsule_name='Correlation Analysis'):
    s = parse(start_time).timestamp() * 1000
    e = parse(end_time).timestamp() * 1000
    body = dict(name=capsule_name,
                formula="".join(["condition(", str(e - s + 1), 'ms,', 'capsule(', str(s), 'ms,', str(e), 'ms))']),
                parameters=[],
                scopedTo=workbook_id
                )

    conditions_api = sdk.ConditionsApi(api_client)
    response = conditions_api.create_condition(body=body).to_dict()
    condition_id = response['id']
    return condition_id
