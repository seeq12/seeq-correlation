# Installation

The backend of **seeq-correlation** requires **Python 3.7** or later.

## Dependencies

See [`requirements.txt`](https://github.com/seeq12/seeq-correlation/tree/master/requirements.txt) file for a list of
dependencies and versions. Additionally, you will need to install the `seeq` module with the appropriate version that
matches your Seeq server. For more information on the `seeq` module see [seeq at pypi](https://pypi.org/project/seeq/)

## User Installation Requirements (Seeq Data Lab)

If you want to install **seeq-correlation** as a Seeq Add-on Tool, you will need:

- Seeq Data Lab (>= R52.1.5, >=R53.0.2, or >=R54)
- `seeq` module whose version matches the Seeq server version
- Seeq administrator access
- Enable Add-on Tools in the Seeq server

## User Installation (Seeq Data Lab)

The latest build of the project can be found [here](https://pypi.org/project/seeq-correlation/) as a wheel file. The
file is published as a courtesy to the user, and it does not imply any obligation for support from the publisher.

1. Create a **new** Seeq Data Lab project and open the **Terminal** window
2. Run `pip install seeq-correlation`
3. Run `python -m seeq.addons.correlation [--users <users_list> --groups <groups_list>]`

