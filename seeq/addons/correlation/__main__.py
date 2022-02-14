import os
import sys
import argparse
import subprocess
from getpass import getpass
from urllib.parse import urlparse
from seeq import sdk, spy
# noinspection PyProtectedMember
from seeq.spy._errors import *
# noinspection PyProtectedMember
from seeq.spy import _url
from ._copy import copy
from .utils import get_user, get_user_group
from . import correlation_udfs

NB_EXTENSIONS = ['widgetsnbextension', 'plotlywidget', 'ipyvuetify', 'ipyvue']
DEPLOYMENT_FOLDER = 'deployment'
CORRELATION_NOTEBOOK = "correlation_analysis_master.ipynb"
DEFAULT_GROUP = ['Everyone']
DEFAULT_USERS = []


def install_app(sdl_url_, *, sort_key='a', permissions_group: list = None, permissions_users: list = None):
    """
    Installs Correlation as an Add-on Tool in Seeq Workbench

    Parameters
    ----------
    sdl_url_: str
        URL of the SDL container.
        E.g. `https://my.seeq.com/data-lab/6AB49411-917E-44CC-BA19-5EE0F903100C/`
    sort_key: str, default 'a'
        A string, typically one character letter. The sort_key determines the
        order in which the Add-on Tools are displayed in the tool panel.
    permissions_group: list
        Names of the Seeq groups that will have access to each tool. If None,
        the "Everyone" group will be used by default.
    permissions_users: list
        Names of Seeq users that will have access to each tool. If None, no
        individual users will be given access to the tool.

    Returns
    --------
    -: None
        Correlation Analysis will appear as Add-on Tool(s) in Seeq
        Workbench
    """

    permissions_group = permissions_group if permissions_group else DEFAULT_GROUP
    permissions_users = permissions_users if permissions_users else DEFAULT_USERS
    add_on_details = {
        "Name": 'Correlation Analysis',
        "Description": "Determine cross correlations and time shifts to maximize correlations among signals",
        "Icon": "fa fa-th",
        "Target URL": f'{sdl_url_}/apps/{DEPLOYMENT_FOLDER}/{CORRELATION_NOTEBOOK}',
        "Link Type": "window",
        "Window Details": "toolbar=0,location=0,left=800,top=400,height=1000,width=1400",
        "Sort Key": sort_key,
        "Reuse Window": True,
        "Groups": permissions_group,
        "Users": permissions_users
        }

    copy(des_folder=DEPLOYMENT_FOLDER, src_folder='deployment_notebook',
         overwrite_folder=False, overwrite_contents=True)
    spy.addons.install(add_on_details, include_workbook_parameters=True, update_tool=True, update_permissions=True)


def install_nbextensions():
    """
    Installs the Jupyter nbextensions required to render the Add-on

    Returns
    -------
    -: None
    """
    for extension in NB_EXTENSIONS:
        subprocess.run(f'jupyter nbextension install --user --py {extension}', cwd=os.path.expanduser('~'), shell=True,
                       check=True)
        subprocess.run(f'jupyter nbextension enable --user --py {extension}', cwd=os.path.expanduser('~'), shell=True,
                       check=True)


def logging_attempts(_user):
    """
    Allows user to re-enter credentials multiple times in the event of
    authentication failure

    Parameters
    ----------
    _user: str
        Seeq username that needs to be authenticated

    Returns
    -------
    -: None
    """
    count = 0
    allowed_attempts = 20
    while count <= allowed_attempts:
        try:
            if _user is None or count >= 1:
                _user = input("\nAccess Key or Username: ")

            passwd = getpass("Access Key Password: ")
            spy.login(username=_user, password=passwd, ignore_ssl_errors=True)
            break
        except (SPyRuntimeError, SPyValueError):
            count += 1
            try_again = "-"
            while try_again != 'yes' and try_again != 'no':
                try_again = input("\nTry again (yes/no)? [yes] ")
                if try_again == '' or try_again.lower() == 'y':
                    try_again = 'yes'
                if try_again.lower() == 'n':
                    try_again = 'no'
            print("-" * 60)
            if try_again.lower() == 'no':
                raise
            if count > allowed_attempts:
                raise RuntimeError("Number of login attempts exceeded")


def create_udfs(api_client, *, permissions_groups: list = None, permissions_users: list = None):
    """
    Creates the required Formula UDFs for the Correlation app

    Parameters
    ----------
    api_client: seeq.sdk.api_client.ApiClient
        The seeq.sdk API client that handles the client-server
        communication
    permissions_groups: list
        Names of the Seeq groups that will have access to each tool
    permissions_users: list
        Names of Seeq users that will have access to each tool
    Returns
    --------
    -: None
        The Correlation UDFs will be available in Seeq Workbench
    """

    permissions_groups = permissions_groups if permissions_groups else DEFAULT_GROUP
    permissions_users = permissions_users if permissions_users else DEFAULT_USERS
    print("\n\nCreating CrossCorrelation UDFs...")
    user_groups_api = sdk.UserGroupsApi(api_client)
    users_api = sdk.UsersApi(spy.client)
    items_api = sdk.ItemsApi(api_client)
    pkg_id = correlation_udfs(api_client)

    # assign group permissions
    for group_name in permissions_groups:
        group = get_user_group(group_name, user_groups_api)
        if group:
            ace_input = sdk.AceInputV1(identity_id=group.items[0].id, permissions=sdk.PermissionsV1(read=True))
            items_api.add_access_control_entry(id=pkg_id, body=ace_input)

    # assign user permissions
    for user_name in permissions_users:
        current_user = get_user(user_name, users_api)
        if current_user:
            ace_input = sdk.AceInputV1(identity_id=current_user.users[0].id,
                                       permissions=sdk.PermissionsV1(read=True))
            items_api.add_access_control_entry(id=pkg_id, body=ace_input)

    print("DONE")


def cli_interface():
    """ Command line utility to install the Correlation Add-on Tool """
    parser = argparse.ArgumentParser(description='Install Correlation as a Seeq Add-on Tool')
    parser.add_argument('--nbextensions_only', action='store_true',
                        help='Only installs the nbextensions without installing or updating the Add-on Tools'
                             'links')
    parser.add_argument('--skip_formula_package', action='store_true',
                        help='Skips the installation of the Formula UDF package. Not recommended for most '
                             'installations')
    parser.add_argument('--username', type=str,
                        help='Username or Access Key of Seeq admin user installing the tool(s) ')
    parser.add_argument('--seeq_url', type=str, nargs='?',
                        help="Seeq hostname URL with the format https://my.seeq.com/ or https://my.seeq.com:34216")
    parser.add_argument('--users', type=str, nargs='*', default=[],
                        help="List of the Seeq users to will have access to the Correlation Add-on Tool,"
                             " default: %(default)s")
    parser.add_argument('--groups', type=str, nargs='*', default=['Everyone'],
                        help="List of the Seeq groups to will have access to the Correlation Add-on Tool, "
                             "default: %(default)s")
    return parser.parse_args()


if __name__ == '__main__':

    args = cli_interface()

    if args.nbextensions_only:
        print("\n\nInstalling and enabling nbextensions")
        install_nbextensions()
        sys.exit(0)
    user = args.username
    logging_attempts(user)
    seeq_url = args.seeq_url
    if seeq_url is None:
        seeq_url = input(f"\n Seeq base URL [{spy.client.host.split('/api')[0]}]: ")
        if seeq_url == '':
            seeq_url = spy.client.host.split('/api')[0]
    url_parsed = urlparse(seeq_url)
    seeq_url_base = f"{url_parsed.scheme}://{url_parsed.netloc}"

    project_id = spy.utils.get_data_lab_project_id()
    sdl_url = f'{seeq_url_base}/data-lab/{project_id}'
    if project_id is None:
        print("\nThe project ID could not be found. Please provide the SDL project URL with the format "
              "https://my.seeq.com/data-lab/6AB49411-917E-44CC-BA19-5EE0F903100C/\n")
        sdl_url = input("Seeq Data Lab project URL: ")
        project_id = spy.utils.get_data_lab_project_id_from_url(sdl_url)
        if not project_id:
            raise RuntimeError('Could not install "seeq-correlation" because the SDL project ID could not be found')
    sdl_url_sanitized = _url.SeeqURL.parse(sdl_url).url

    print(f"\nThe Correlation Tool will be installed on the SDL notebook: {sdl_url_sanitized}\n"
          f"If this is not your intent, you can quit the installation now ")
    print('\n[enter] to continue or type "quit" to exit installation')
    choice = None
    while choice != '' and choice != 'quit':
        choice = input()
        if choice == '':
            print("\n\nInstalling and enabling nbextensions")
            install_nbextensions()
            if not args.skip_formula_package:
                create_udfs(spy.client, permissions_groups=args.groups, permissions_users=args.users)
            install_app(sdl_url_sanitized, permissions_group=args.groups, permissions_users=args.users)
        elif choice == 'quit':
            print("\nExited installation")
        else:
            print(f'\nCommand "{choice}" is not valid')
            print('\n[enter] to continue the installation or type "quit" to exit installation')
