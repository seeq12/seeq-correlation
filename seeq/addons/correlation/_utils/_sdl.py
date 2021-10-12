import re
import seeq
import pandas as pd
from seeq import spy, sdk
from packaging import version
from urllib.parse import urlparse, urlunparse, unquote, parse_qs
from . import add_datalab_project_ace
from . import get_user, get_user_group
from . import print_red

DATA_LAB_PROJECT_ID_REGEX = r'.*/data-lab/([0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}).*'


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
    df.columns = df.query_df['Name']
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


def get_worksheet_url_from_ids(workbook_id, worksheet_id):
    host = spy.client.host.replace('/api', '')
    worksheet_url = f"{host}/workbook/{workbook_id}/worksheet/{worksheet_id}"
    return spy.utils.get_analysis_worksheet_from_url(worksheet_url)


def sanitize_sdl_url(url):
    parsed = urlparse(url)
    project_id_search = re.search(DATA_LAB_PROJECT_ID_REGEX, url, re.IGNORECASE)
    if parsed.scheme == '' or parsed.netloc == '' or parsed.path == '':
        raise ValueError(f"The SDL_url should have the format "
                         f"https://my.seeq.com/data-lab/6AB49411-917E-44CC-BA19-5EE0F903100C/ but got {url}")
    if project_id_search is None:
        raise ValueError(f"Invalid URL. Could not find data-lab project ID. Got URL: {url}")
    id = project_id_search.group(1)
    return urlunparse(parsed).strip(" ").split(id)[0] + id


def get_datalab_project_id(target_url, items_api):
    project_id_search = re.search(DATA_LAB_PROJECT_ID_REGEX, target_url, re.IGNORECASE)
    if project_id_search:
        data_lab_project_id = project_id_search.group(1)
        try:
            items_api.get_item_and_all_properties(id=data_lab_project_id)
            return data_lab_project_id
        except Exception as error:
            print_red(error.body)


def check_spy_version():
    server_version = version.parse(spy.server_version)
    try:
        ver = spy.__version__
    except AttributeError:
        ver = seeq.__version__
    if server_version > version.parse(f"R{ver}"):
        raise RuntimeError(f"The SPy module version doesn't match the Seeq server version. "
                           f"Please update the SPy module to version ~={spy.server_version.split('-')[0]}")


def addon_tool_management(my_tool_config):
    system_api = sdk.SystemApi(spy.client)
    users_api = sdk.UsersApi(spy.client)
    user_groups_api = sdk.UserGroupsApi(spy.client)
    items_api = sdk.ItemsApi(spy.client)
    check_spy_version()
    if hasattr(system_api, 'get_add_on_tools'):
        tools = system_api.get_add_on_tools().add_on_tools
    else:
        tools = system_api.get_external_tools().external_tools

    # Define add-on tools to be added
    # ?workbookId={workbookId}&worksheetId={worksheetId}&workstepId={workstepId}&seeqVersion={seeqVersion}
    # First, do no harm.
    # This extracts the tools that are already there.
    # You can then either modify an item or add to this list.
    tools_config = list()
    for tool in tools:
        tools_config.append({
            "name": tool.name,
            "description": tool.description,
            "iconClass": tool.icon_class,
            "targetUrl": tool.target_url,
            "linkType": tool.link_type,
            "windowDetails": tool.window_details,
            "sortKey": tool.sort_key,
            "reuseWindow": tool.reuse_window,
            "permissions": {
                "groups": list(),
                "users": list()
            }
        })
        tool_acl = items_api.get_access_control(id=tool.id)
        for ace in tool_acl.entries:
            identity = ace.identity
            if identity.type.lower() == "user":
                tools_config[-1]["permissions"]["users"].append(identity.username)
            elif identity.type.lower() == "usergroup":
                tools_config[-1]["permissions"]["groups"].append(identity.name)

    # If the tool is in the list, update it
    if my_tool_config["name"] in [t["name"] for t in tools_config]:
        list_index = [t["name"] for t in tools_config].index(my_tool_config["name"])
        tools_config[list_index].update(my_tool_config)
    # if the tool is not in the list, add it
    else:
        tools_config.append(my_tool_config)

    # Delete all existing add-on tools (only deletes the tools, not what they point to)
    for tool in tools:
        if hasattr(system_api, 'delete_add_on_tool'):
            system_api.delete_add_on_tool(id=tool.id)
        else:
            system_api.delete_external_tool(id=tool.id)

    # Add add-on tools and assign add-on tool and data lab permissions to groups and users

    for tool_with_permissions in tools_config:
        # Create add-on tool
        tool = tool_with_permissions.copy()
        tool.pop("permissions")
        if hasattr(system_api, 'create_add_on_tool'):
            tool_id = system_api.create_add_on_tool(body=tool).id
            tool_type = 'Add-on'
        else:
            tool_id = system_api.create_external_tool(body=tool).id
            tool_type = 'External'

        print(tool["name"])
        print(f'{tool_type} Tool ID - {tool_id}')
        data_lab_project_id = get_datalab_project_id(tool["targetUrl"], items_api)
        if data_lab_project_id:
            print("Target Data Lab Project ID - %s" % data_lab_project_id)
        else:
            print("TargetUrl does not reference a Data Lab project")

        # assign group permissions to add-on tool and data lab project
        groups = tool_with_permissions["permissions"]["groups"]
        for group_name in groups:
            group = get_user_group(group_name, user_groups_api)
            if group:
                ace_input = {'identityId': group.items[0].id, 'permissions': {'read': True}}
                # Add permissions to add-on tool item
                items_api.add_access_control_entry(id=tool_id, body=ace_input)
                # Add permissions to data lab project if target URL references one
                ace_input['permissions']['write'] = True  # Data lab project also needs write permission
                add_datalab_project_ace(data_lab_project_id, ace_input, items_api)
        print("Groups:", end=" "), print(*groups, sep=", ")

        # assign user permissions to add-on tool and data lab project
        users = tool_with_permissions["permissions"]["users"]
        for user_name in users:
            user_ = get_user(user_name, users_api)
            if user_:
                ace_input = {'identityId': user_.users[0].id, 'permissions': {'read': True}}
                items_api.add_access_control_entry(id=tool_id, body=ace_input)
                # Add permissions to data lab project if target URL references one
                ace_input['permissions']['write'] = True  # Data lab project also needs write permission
                add_datalab_project_ace(data_lab_project_id, ace_input, items_api)
        print("Users:", end=" "), print(*users, sep=", ")
