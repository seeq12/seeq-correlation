# Installation

The backend of **seeq-correlation** requires **Python 3.7** or later.

### Dependencies

See [`requirements.txt`](https://github.com/seeq12/seeq-correlation/tree/master/requirements.txt) file for a list of
dependencies and versions. Additionally, you will need to install the `seeq` module with the appropriate version that
matches your Seeq server. For more information on the `seeq` module see [seeq at pypi](https://pypi.org/project/seeq/)


### User Installation Requirements (Seeq Data Lab)

If you want to install **seeq-correlation** as a Seeq Add-on Tool, you will need:

- Seeq Data Lab (>=R56)
- `seeq` module whose version matches the Seeq server version
- Seeq administrator access
- Enable Add-on Tools in the Seeq server


## Installation Steps
### Seeq Add-on Installation via Add-on Manager (Recommended Method)

The **seeq-correlation** Add-on can be installed via the Add-on Manager in the home page of the Seeq server. 
Please refer to our knowledge base for more details on Add-on Manager [here](https://support.seeq.com/kb/latest/cloud/add-on-packaging).

From the Seeq home page, click on the "Add-on" icon at the left of the screen and then click the "Add-on Manager" 
icon in the new buttons displayed.

<br>
<td><img alt="image" src="_static/addon_manager_1.png"></td>
<br>

Now your in the Add-on Manager you will get a list of all the Add-ons available to you. Click on the "Install" button 
next to the **seeq-correlation** Add-on.

<br>
<td><img alt="image" src="_static/addon_manager_2.png"></td>
<br>

After some time the "Install" button will change to "Installed" with a tick next to it and the Add-on will be available to use in Seeq Workbench. 

### Upgrading the **seeq-correlation** Add-on 
If there is a new version of the **seeq-correlation** Add-on available, you will see an "Upgrade" button next to the add-on in the Add-on Manager. Click on the "Upgrade" button to upgrade the add-on to the latest version.

### Seeq Add-on Installation via Terminal Window (Depreciated Method)

The latest build of the project can be found [here](https://pypi.org/project/seeq-correlation/) as a wheel file. The
file is published as a courtesy to the user, and it does not imply any obligation for support from the publisher.

1. Create a **new** Seeq Data Lab project and open the **Terminal** window
2. Run `pip install seeq-correlation`
3. Run `python -m seeq.addons.correlation [--users <users_list> --groups <groups_list>]`

