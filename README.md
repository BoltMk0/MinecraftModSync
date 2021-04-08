# ServerSync
Synchronize Minecraft mods between a server and client with minimum effort

![ServerSync Client GUI](https://github.com/BoltMk0/mc_serversync/raw/main/screenshots/serversync_gui.png)

[Download Files][release]

[release]: https://github.com/BoltMk0/mc_serversync/releases/latest

## Getting Started
#### Pre-requesites:
- [Python 3.8](https://www.python.org/downloads/) (Will not work with 3.9)

    To check python version, open up a command prompt and run `python --version`

    IMPORTANT! When installing python, make sure "Add Python to 
environment variables" is checked.

    Quick link: [Download Python 3.8.9](https://www.python.org/ftp/python/3.8.9/python-3.8.9-amd64.exe)

#### Installation Instructions (Client/User)
- [Download the latest release of ServerSync][release]
- **Install ServerSync using pip**
    - Open a command prompt window (right click Start menu and select "Command Prompt")
    - Type "python -m pip install " then drag and drop the .whl file into the cmd window.
    The command should look something like:
    
        `python -m pip install "C:\Users\<user>\Downloads\serversync-0.2-py3-none-any.whl"`
- **Install commands to the context (right click) menu**
    - Open a Command Prompt window **as administrator** (right click Start menu and select "Command Prompt (Admin)")
    - Run `python -m serversync --install`, and enter "1" when prompted.

#### Installation Instructions (Server/Administrator)
- [Download the latest release of ServerSync][release]
- Open a Command Prompt window / terminal
- Install the serversync module using `python -m pip install <path-to-serversync-module>.whl`
- cd into your server mods folder, then run `python -m serversync --server`

The server uses a "Client Profile" to determine which mods are server-side, and which are
client-side (the remainder being shared/required). To set this, open a terminal/command prompt
in your client mods folder, and run `python -m serversync --setProfile`. Upon completion
you will see a summary of any single-sided mods.


## Usage Guide
### Client
To quickly sync your mods with a server, right-click anywhere in your minecraft mods folder, and
select the newly-added "Run ServerSync" from the context menu. If you can't see this,
repeat the steps in Installation Instructions (Client/User).

The client app will show, and automatically start scanning if it can connect to the server.
If it can't see the server, an error message will pop up. Close this, and click the "Settings"
button. Make sure the ip address and port is correct, hit save, and try again.

![ServerSync Settings GUI](https://github.com/BoltMk0/mc_serversync/raw/main/screenshots/serversync_config_gui.png)



After the scan completes, a summary of mods that need to be added, deleted and updated will be shown.
Read through the mods to be deleted (at the top of the list) carefully, some of these could
be client-side mods that you want to keep. If you do want to keep then, uncheck the checkbox.
This will be stored, so at the next sync you won't have to check again.

