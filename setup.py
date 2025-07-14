# coding: utf-8
import re
from parver import Version, ParseError
import setuptools
import pathlib
import tomllib

# Use the following command from a terminal window to generate the whl with source code
# python setup.py bdist_wheel

namespace = 'seeq.*'

with open("README.md", "r") as fh:
    long_description = fh.read()

version_scope = {'__builtins__': None}
with open("seeq/addons/correlation/_version.py", "r+") as f:
    version_file = f.read()
    version_line = re.search(r"__version__ = (.*)", version_file)
    if version_line is None:
        raise ValueError(f"Invalid version. Expected __version__ = 'xx.xx.xx', but got \n{version_file}")
    version = version_line.group(1).replace(" ", "").strip('\n').strip("'").strip('"')
    print(f"version: {version}")
    try:
        Version.parse(version)
        exec(version_line.group(0), version_scope)
    except ParseError as e:
        print(str(e))
        raise

def read_requirements():
    toml_path = pathlib.Path(__file__).with_name("pyproject.toml")
    with toml_path.open("rb") as f:
        data = tomllib.load(f)
    deps = data["tool"]["poetry"]["dependencies"]
    reqs = []
    for pkg, spec in deps.items():
        if pkg.lower() == "python":
            continue
        if isinstance(spec, str):
            reqs.append(f"{pkg}{'' if spec == '*' else spec}")
        elif isinstance(spec, dict) and "version" in spec:
            reqs.append(f"{pkg}{spec['version']}")
    return reqs

setup_args = dict(
    name='seeq-correlation',
    version=version_scope['__version__'],
    author="Seeq Corporation",
    author_email="applied.research@seeq.com",
    license='Apache License 2.0',
    platforms=["Linux", "Windows"],
    description="Correlation analysis of time series data in Seeq",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/seeq12/seeq-correlation",
    packages=setuptools.find_namespace_packages(include=[namespace]),
    include_package_data=True,
    zip_safe=False,
    install_requires=read_requirements(),
    classifiers=[
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)

setuptools.setup(**setup_args)
