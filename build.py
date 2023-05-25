import sys
import os
import json
import zipfile
import pathlib
import shutil
import argparse
import subprocess
from pathlib import Path
from artifactory import ArtifactoryPath

parser = argparse.ArgumentParser()
parser.add_argument(
    '-d', '--distribute',
    help='Upload the built files to their distribution channels.',
    action='store_true'
)
parser.add_argument(
    '-c', '--compile',
    help='Produce a compiled version of the code in addition to the source version',
    action='store_true'
)
parser.add_argument(
    '-a', '--addon',
    help='Produce a zipped version for installation through the addon manager.',
    action='store_true'
)
args = parser.parse_args()

# build the distribution
distribution_relative_dir = 'dist'
distribution_abs_dir = os.path.join(os.getcwd(), distribution_relative_dir)
if os.path.isdir(distribution_abs_dir):
    shutil.rmtree(distribution_abs_dir)
build_command = ['python3.8', 'setup.py', 'bdist_wheel',
                 '-d', distribution_relative_dir,
                 f'--python-tag=py{sys.version_info.major}{sys.version_info.minor}']
subprocess.run(build_command, cwd=os.getcwd())
source_wheel = max(
    [os.path.join(distribution_abs_dir, f) for f in os.listdir(distribution_abs_dir)],
    key=os.path.getctime
)

source_wheel_name = os.path.split(source_wheel)[-1]
version = source_wheel_name.split('-')[1]

compiled_wheel = None
if args.compile:
    print('Creating pyc file')
    pyc_relative_dir = os.path.join(distribution_relative_dir, 'bin')
    pyc_abs_dir = os.path.join(distribution_abs_dir, 'bin')
    build_command = [sys.executable, 'setup.py', 'bdist_egg',
                     '-d', pyc_relative_dir,
                     '--exclude-source-files',
                     '-m', '+c']
    build_result = subprocess.run(build_command, cwd=os.getcwd(), capture_output=True, text=True)
    wheel_command = ['wheel', 'convert', os.path.join(pyc_relative_dir, '*.egg'), '-d', pyc_relative_dir]
    wheel_result = subprocess.run(wheel_command, cwd=os.getcwd(), capture_output=True, text=True)

    # move the pyc wheel file to the dist dir
    path = Path('.')
    wheel_file = list(path.glob('**/bin/*.whl'))[0]
    wheel_file.rename(Path(wheel_file.parent.parent, wheel_file.name))
    compiled_wheel = os.path.join(wheel_file.parent.parent, wheel_file.name)

    # remove the bin dir
    shutil.rmtree(pyc_abs_dir)

addon_manager_artifacts = []
if args.addon:
    name = 'correlation'
    print(f'Creating {name}.addon')
    # Ensure output folder exists
    bin = os.path.join(os.getcwd(), 'bin')
    if not os.path.exists(bin):
        os.makedirs(bin)

    with open('addon.json') as json_file:
        parsed_json = json.load(json_file)
    parsed_json['version'] = version

    addon = os.path.join(bin, f'{name}.addon')
    addon_meta = os.path.join(bin, f'{name}.addonmeta')

    # Build addon
    with zipfile.ZipFile(addon, 'w') as z:
        z.write(source_wheel, arcname=os.path.join('data-lab-functions', source_wheel_name))
        z.writestr('data-lab-functions/requirements.txt', f"./{source_wheel_name}")
        with z.open("addon.json", "w") as c:
            c.write(json.dumps(parsed_json, indent=2).encode("utf-8"))
        directory = pathlib.Path("./seeq/addons/correlation/deployment_notebook/")
        for file in directory.rglob('*ipynb'):
            z.write(file, arcname=os.path.join('data-lab-functions', file.name))
        directory = pathlib.Path("./additional_content/")
        for file in directory.iterdir():
            z.write(file)
        addon_manager_artifacts.append(addon)
    # Build addonmeta
    print(f'Creating {name}.addonmeta')
    with zipfile.ZipFile(addon_meta, 'w') as z:
        with z.open("addon.json", "w") as c:
            c.write(json.dumps(parsed_json, indent=2).encode("utf-8"))
        directory = pathlib.Path("./additional_content/")
        for file in directory.iterdir():
            z.write(file)
        addon_manager_artifacts.append(addon_meta)

    print('Successfully created.')

if args.distribute:

    # THIS BLOCK OF CODE IS NO MORE IN USE BUT COULD LATER BE USED IN FUTURE PURPOSES
    # if compiled_wheel is not None:
    #     print(f'Distributing compiled wheel {compiled_wheel} to pipy.seeq.com')
    #     command_distribute_compiled = \
    #         ['twine', 'upload',
    #          '--repository-url', 'https://pypi.seeq.com',
    #          '-u', username,
    #          '-p', password,
    #          compiled_wheel]
    #     result = subprocess.run(' '.join(command_distribute_compiled))
    #     if result.stderr:
    #         print(f'There was an error uploading the compiled version: {result.stderr}')
    #
    # print(f'Distributing source wheel {source_wheel} to pypi.seeq.com:8081')
    # command_distribute_source = \
    #     ['twine', 'upload',
    #      '--repository-url', 'https://pypi.seeq.com:8081',
    #      '-u', username,
    #      '-p', password,
    #      source_wheel]
    # result = subprocess.run(' '.join(command_distribute_source))
    # if result.stderr:
    #     print(f'There was an error uploading the source version: {result.stderr}')

    if addon_manager_artifacts:
        print(f'Distributing addon manager artifacts to seeq.jfrog.io')
        api_key = os.getenv('JFROG_API_KEY')
        for artifact in addon_manager_artifacts:
            _, file = os.path.split(artifact)
            path = ArtifactoryPath(f"https://seeq.jfrog.io/artifactory/seeq-add-ons-prod-local/correlation/{file}",
                                   apikey=api_key)
            try:
                path.deploy_file(artifact)
                properties = path.properties
                # Add identifier property
                properties["identifier"] = "com.seeq.addon.correlation"
                path.properties = properties
            except Exception as e:
                print(e)