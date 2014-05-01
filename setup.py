import setuptools
import os

with open('requirements.txt') as f:
    required = f.read().splitlines()

setuptools.setup(
    name="monster",
    version="0.1.0",
    description="An OpenStack Deployment/Orchestration Engine",
    install_dir=os.getcwd(),
    packages=setuptools.find_packages(),
    entry_points={
        "console_scripts": ["monster = monster.executable:run"]}
)
