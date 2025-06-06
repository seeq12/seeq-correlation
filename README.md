[![Build Status](https://teamcity.seeq-labs.com/app/rest/builds/buildType:(id:AppliedResearch_correlation)/statusIcon)](https://github.com/seeq12/seeq-correlation/)

<br>
<p>
  <a href="https://www.seeq.com" rel="nofollow">
    <img src="https://support.seeq.com/__assets-afb914a3-20be-451d-8157-92db51387860/image/seeq_logo.png" alt="seeq" width="22%">
  </a>
</p>

<p align="center">
  <a href="https://seeq12.github.io/seeq-correlation/index.html" rel="nofollow">
    <img src="https://seeq12.github.io/seeq-correlation/_static/LargeMatrixExample.png" alt="">
  </a>
</p>

----

**seeq-correlation** is a Python module to calculate and monitor cross-correlations among time-series signals. It also
calculates the time shifts (lead or lag) that maximize the cross-correlations of each signal pair. The module includes a
user interface (UI) designed to interact with the Seeq server. Specifically, the UI can be installed as an Add-on Tool
in Seeq Workbench.

----

# Documentation

The documentation for **seeq-correlation** can be found
[**here**](https://seeq12.github.io/seeq-correlation/index.html).

----

# User Guide

[**seeq-correlation User Guide**](https://seeq12.github.io/seeq-correlation/user_guide.html)
provides a more in-depth explanation of correlation analysis and how seeq-correlation works. Examples of typical types
of analyses using **seeq-correlation** can be found in the
section [Use Cases](https://seeq12.github.io/seeq-correlation/examples.html).


-----

# Installation

The easiest way to install **seeq-correlation** is to use Add-on Manager from Seeq Workbench. 
Correlation is included in the default list of available Add-ons. Simply search for "Correlation" in the manager
and click "Install".

## Manual Installation
If you want to install **seeq-correlation** manually or Add-on Manager is not available, you can do so by 
following the steps below.

### Dependencies

The backend of **seeq-correlation** requires **Python 3.7** or later.

See [`requirements.txt`](https://github.com/seeq12/seeq-correlation/tree/master/requirements.txt) file for a list of
dependencies and versions. Additionally, you will need to install the `seeq` module with the appropriate version that
matches your Seeq server. For more information on the `seeq` module see [seeq at pypi](https://pypi.org/project/seeq/)

### User Installation Requirements (Seeq Data Lab)

If you want to install **seeq-correlation** as a Seeq Add-on Tool, you will need:

- Seeq Data Lab (>= R52.1.5, >=R53.0.2, or >=R54)
- `seeq` module whose version matches the Seeq server version
- Seeq administrator access
- Enable Add-on Tools in the Seeq server

### User Installation (Seeq Data Lab)

The latest build of the project can be found [here](https://pypi.org/project/seeq-correlation/) as a wheel file. The
file is published as a courtesy to the user, and it does not imply any obligation for support from the publisher.

1. Create a **new** Seeq Data Lab project and open the **Terminal** window
2. Run `pip install seeq-correlation`
3. Run `python -m seeq.addons.correlation [--users <users_list> --groups <groups_list>]`

----

# Development

We welcome new contributors of all experience levels. The **Development Guide** has detailed information about
contributing code, documentation, tests, etc.

## Important links

* Official source code repo: https://github.com/seeq12/seeq-correlation
* Issue tracker: https://github.com/seeq12/seeq-correlation/issues

## Source code

You can get started by cloning the repository with the command:

```shell
git clone git@github.com:seeq12/seeq-correlation.git
```

## Installation from source

For development work, it is highly recommended creating a python virtual environment and install the package in that
working environment. If you are not familiar with python virtual environments, you can take a
look [here](https://docs.python.org/3.8/tutorial/venv.html)

Once your virtual environment is activated, you can install **seeq-correlation** from source with:

```shell
python setup.py install
```

## Testing

There are several types of testing available for **seeq-correlation**

### Automatic Testing

After installation, you can launch the test suite from the root directory of the project (i.e. `seeq-correlation`
directory). You will need to have pytest >= 5.0.1 installed

To run all tests:

```shell
pytest
```

There are several pytest markers set up in the project. You can find the description of the marks in the `pytest.ini`
file. You can use the `-m` flag to run only a subset of tests. For example, to run only the `backend` tests, you can
use:

```shell
pytest -m backend
```

The integration tests requires a connection to a Seeq server. The tests are configured to try to access a local Seeq
server with the data directory set up in `ProgramData/Seeq/data` of the local drive. However, you can set the
`seeq_url`, `credentials_file` configuration options in the `test_config.ini` file to run the integration tests on a
remote Seeq server, or change the local seeq data directory with `data_dir`.

*Note:* Remember that the `seeq` module version in your local environment should match the Seeq server version

### User Interface Testing

To test the UI, use the `developer_notebook.ipynb` in the `development` folder of the project. This notebook can also be
used while debugging from your IDE. You can also create a whl first, install it on your virtual environment, and then
run `developer_notebook.ipynb` notebook there.

----

# Changelog

The changelog can be found [**here**](https://seeq12.github.io/seeq-correlation/changelog.html)


----

# Support

Code related issues (e.g. bugs, feature requests) can be created in the
[issue tracker](https://github.com/seeq12/seeq-correlation/issues)

Maintainer: Alberto Rivas


----

# Citation

Please cite this work as:

```shell
seeq-correlation
Seeq Corporation, 2021
https://github.com/seeq12/seeq-correlation
```






