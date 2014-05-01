import setuptools
import os

with open('requirements.txt') as f:
    required = f.read().splitlines()

setuptools.setup(
    name="monster",
    version="0.1.0",
    description="An OpenStack Deployment/Orchestration Engine",
    packages=setuptools.find_packages(),
    package_data = {
        '': ['*.yaml']
    },
    entry_points={
        "console_scripts": [
            "monster = monster.executable:run"
        ]}
)
