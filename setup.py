import setuptools
import monster.info as info

setuptools.setup(
    name=info.__appname__,
    version=info.__version__,
    author=info.__author__,
    author_email=info.__email__,
    description=info.__description__,
    url=info.__url__,
    packages=setuptools.find_packages(),
    package_data={
        '': ['*.yaml']
    },
    entry_points={
        "console_scripts": [
            "monster = monster.executable:run"
        ]}
)
