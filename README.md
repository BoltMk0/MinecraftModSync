# ServerSync
Synchronize Minecraft mods between a server and client with minimum effort.
Currently only supports Forge mods.


![ServerSync Client GUI](https://github.com/BoltMk0/mc_serversync/raw/main/screenshots/serversync_gui.png)

[Download Files][release]

[Download Windows Installer][installer]

[release]: https://github.com/BoltMk0/mc_serversync/releases/latest

[installer]: https://github.com/BoltMk0/mc_serversync/releases/download/v1.2/serversync_1_2_installer.exe

| :warning: The installer (built with NSIS) has been known to appear as a rootkit virus in some antivirus software. If you have concerns/are uncomfortable letting it through, install using the manual installation instructions below. I have uploaded the NSIS installer script to the repository so you can see what it does. |
|---|

## Getting Started

#### Manual Installation Instructions (Client/User)
- ServerSync requires python 3.8.x or lower (Does not work on 3.9.x yet). If you don't already have it,[Download Python 3.8.9](https://www.python.org/ftp/python/3.8.9/python-3.8.9-amd64.exe) and __be sure the installer adds Python to the system environment variables!__
- [Download the latest release of ServerSync][release]
- **Install ServerSync using pip**
    - Open a command prompt window (Search for "Command Prompt" in start menu)
    - Type "python -m pip install " then drag and drop the .whl file into the cmd window.
    The command should look something like:
        `python -m pip install "C:\Users\<user>\Downloads\serversync-0.3-py3-none-any.whl"`
- **Install commands to the context (right click) menu**
    - Open a Command Prompt window **as administrator** (Search for "Command Prompt" in start menu, right click and select "Run as Administrator")
    - Run `python -m serversync --install`, and enter "1" when prompted.

Done! Now you have access to serversync from any folder by right-clicking and selecting "Run ServerSync". 

*Tip: Serversync stores unique configurations for each folder you use it from (i.e. each mod folder 
you have can sync to a different server).*

#### Installation Instructions (Server/Administrator)
- **Linux**
    - Install python and pip: `apt install python3 python3-pip`
    - Update pip: `pip3 install --upgrade pip`
- **Windows**
    - ServerSync requires python 3.8.x or lower (Does not work on 3.9.x yet). If you don't already have it,[Download Python 3.8.9](https://www.python.org/ftp/python/3.8.9/python-3.8.9-amd64.exe) and __be sure the installer adds Python to the system environment variables!__
- [Download the latest release of ServerSync][release]
- Open a Command Prompt window / terminal
- Install the serversync module using `python -m pip install <path-to-serversync-module>.whl`
    - Linux users: Note you may have to replace "python" with "python3".
- cd into your server mods folder, then run `python -m serversync --server`
    - Linux users: see above note.
- Log into your internet router (instructions will be on the back of the router) and forward TCP traffic for the selected port (default 25567) to your machine from your router.
NOTE: You can change the port used by serversync using the '--port <int>' argument when running the server. 
- (New from 1.3) Forward TCP traffic to selected HTTP server port (default 25568) to machine.
This can be changed from the serversync.conf file

##### Determining server-side and client-side mods
The server uses a "Client Profile" to determine which mods are server-side, and which are
client-side (the remainder being required mods). To set this, open a terminal/command prompt
in your client mods folder, and run `python -m serversync --setProfile`. Upon completion
you will see a summary of any single-sided mods.

##### Passkeys
Server admins can chose to set a passkey to protect the server from unwanted profile changes.
Set the passkey by using the '--passkey <str>' flag when starting the server (once only), and 
use the same flag from the client to attach the passkey to profile set requests. 


## Usage Guide
### Client
To quickly sync your mods with a server, right-click anywhere in your minecraft mods folder, and
select the newly-added "Run ServerSync" from the context menu. If you can't see this,
repeat the steps in Installation Instructions (Client/User).

If there is not serversync configuration file (serversync.conf) in the mods folder, a new
one will be created and it will ask you to enter the server details. Next time out run serversync,
it will automatically run using the defined configuration.

![ServerSync Settings GUI](https://github.com/BoltMk0/mc_serversync/raw/main/screenshots/serversync_config_gui.png)

After the scan completes, a summary of mods that need to be added, deleted and updated will be shown.
Read through the mods to be deleted (at the top of the list) carefully, some of these could
be client-side mods that you want to keep. If you do want to keep then, uncheck the checkbox.
Unchecked items will be stored in the config, so at the next sync you won't have to check again.
