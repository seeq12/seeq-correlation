import time
import json
import string
from seeq import sdk
from dateutil.parser import parse


def create_workstep_signals(existing_worksheet, workbook_id, signal_ids, start_time, end_time, condition_id,
                            overwrite, api_client):
    workstep_json = None
    workstep_input = sdk.WorkstepInputV1()
    workbooks_api = sdk.WorkbooksApi(api_client)
    if existing_worksheet.workstep:
        workstep_id = existing_worksheet.workstep.split('/')[-1]
        workstep_output = workbooks_api.get_workstep(workbook_id=workbook_id,
                                                     worksheet_id=existing_worksheet.id,
                                                     workstep_id=workstep_id)  # type: WorkstepOutputV1 # noqa: F821
        workstep_input.data = workstep_output.data

    if workstep_input.data:
        workstep_json = json.loads(workstep_input.data)

    _now = int(round(time.time() * 1000))
    if not workstep_json or overwrite:
        workstep_json = {
            "version": 24,
            "state": {
                "stores": {
                    "sqTrendSeriesStore": {
                        "items": [
                        ]
                    },
                    "sqDurationStore": {
                        "autoUpdate": {
                            "mode": "OFF",
                            "offset": 0,
                            "manualInterval": {
                                "value": 1,
                                "units": "min"
                            }
                        },
                        "displayRange": {
                            "start": _now - (24 * 60 * 60 * 1000),
                            "end": _now
                        },
                        "investigateRange": {
                            "start": _now - (24 * 60 * 60 * 1000),
                            "end": _now
                        }
                    },
                    "sqTrendCapsuleSetStore": {
                        "items": [

                        ]
                    }
                }
            }
        }

    axis = []
    letters = list(string.ascii_uppercase)
    for i in range(1, 11, 1):
        axis.extend([letter * i for letter in letters])

    current_signals = [x['id'] for x in workstep_json['state']['stores']['sqTrendSeriesStore']['items']]
    current_lanes = [x['lane'] for x in workstep_json['state']['stores']['sqTrendSeriesStore']['items']]
    if len(current_lanes) > 0:
        previous_highest_lane = max(current_lanes)
    else:
        previous_highest_lane = 0

    for highest_lane, signal in enumerate(signal_ids):
        if signal in current_signals:
            pass
        else:
            workstep_json['state']['stores']['sqTrendSeriesStore']['items'].append({
                "axisAlign": axis[highest_lane + previous_highest_lane],
                "axisAutoScale": True,
                "id": signal,
                "lane": highest_lane + previous_highest_lane + 1
            })

    if condition_id is not None:
        condition = {
            "autoDisabled": False,
            "id": condition_id,
            "selected": False,
        }
        workstep_json['state']['stores']['sqTrendCapsuleSetStore']['items'].append(condition)

    workstep_json['state']['stores']['sqDurationStore']['displayRange']['start'] = parse(start_time).timestamp() * 1000
    workstep_json['state']['stores']['sqDurationStore']['displayRange']['end'] = parse(end_time).timestamp() * 1000
    workstep_json['state']['stores']['sqDurationStore']['investigateRange']['start'] = parse(
        start_time).timestamp() * 1000
    workstep_json['state']['stores']['sqDurationStore']['investigateRange']['end'] = parse(end_time).timestamp() * 1000

    payload = dict(data=json.dumps(workstep_json))

    response = workbooks_api.create_workstep(workbook_id=workbook_id, worksheet_id=existing_worksheet.id, body=payload)
    return response


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
