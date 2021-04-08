import setuptools
from serversync import VERSION

setuptools.setup(
    name='serversync',
    author='BoltMk0',
    email='marco.r.bolt@gmail.com',
    version=VERSION,
    install_requires=['toml', 'PyQt5'],
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts': ['ServerSyncSettings=serversync.config_gui:config_editor_session']
    }
)
