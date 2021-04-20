import setuptools
from serversync import VERSION
import os


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setuptools.setup(
    name='serversync',
    author='BoltMk0',
    author_email='marco.r.bolt@gmail.com',
    description='Quickly and effortlessly sync Minecraft mods between a server and client',
    url='https://github.com/BoltMk0/mc_serversync',
    long_description=read('README.md'),
    python_requires='!=3.9.*, >=3',
    version=VERSION,
    install_requires=['toml', 'PyQt5', 'flask', 'requests'],
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts': ['ServerSyncSettings=serversync.config_gui:config_editor_session']
    }
)
