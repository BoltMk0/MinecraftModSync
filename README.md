# ServerSync
Synchronize Minecraft mods between a server and client with minimum effort.
Currently only supports Forge mods.


![ServerSync Client GUI](https://github.com/BoltMk0/mc_serversync/raw/main/screenshots/serversync_gui.png)

[Download Files][release]

[Download Windows Installer][installer]

[release]: https://github.com/BoltMk0/mc_serversync/releases/latest
[installer]: https://github.com/BoltMk0/mc_serversync/releases/download/v1.2/serversync_1_2_installer.exe

## Getting Started
*UPDATE: ServerSync now has a windows installer to MASSIVELY simplify the installation process! Download [Here][installer].*


#### Manual Installation Instructions (Client/User)

NOTE: ServerSync requires python 3.8.x (Does not work on 3.9.x yet). If you don't already have it,
[Download Python 3.8.9](https://www.python.org/ftp/python/3.8.9/python-3.8.9-amd64.exe) and be sure
the installer adds Python to the system environment variables!

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
- [Download the latest release of ServerSync][release]
- Open a Command Prompt window / terminal
- Install the serversync module using `python -m pip install <path-to-serversync-module>.whl`
- cd into your server mods folder, then run `python -m serversync --server`
- Forward TCP traffic for the selected port (default 25567) to your machine from your router.
You can change this using the '--port <int>' argument when running the server. 

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

The client app will show, and automatically start scanning if it can connect to the server.
If it can't see the server, an error message will pop up. Close this, and click the "Settings"
button. Make sure the ip address and port is correct, hit save, and try again.

![ServerSync Settings GUI](https://github.com/BoltMk0/mc_serversync/raw/main/screenshots/serversync_config_gui.png)



After the scan completes, a summary of mods that need to be added, deleted and updated will be shown.
Read through the mods to be deleted (at the top of the list) carefully, some of these could
be client-side mods that you want to keep. If you do want to keep then, uncheck the checkbox.
This will be stored, so at the next sync you won't have to check again.

