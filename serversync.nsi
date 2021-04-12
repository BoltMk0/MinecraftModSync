; example1.nsi
;
; This script is perhaps one of the simplest NSIs you can make. All of the
; optional settings are left to their default settings. The installer simply 
; prompts the user asking them where to install, and drops a copy of example1.nsi
; there. 
;
; example2.nsi expands on this by adding a uninstaller and start menu shortcuts.

;--------------------------------

; The name of the installer
Name "ServerSync Installer"


; The file to write
OutFile "serversync_1_2_installer.exe"

; Request admin privileges for Windows Vista
RequestExecutionLevel admin

; Build Unicode installer
Unicode True


;--------------------------------

; Pages

Page components
Page instfiles

;--------------------------------

Section "-setup"
  Var /GLOBAL pyver
SectionEnd

; The stuff to install
Section "Python 3.8.9" ;
  ; Set output path to the installation directory.
  
  ; Check python version
  nsExec::ExecToStack 'python --version'
  Pop $0
  Pop $1
  
  ; If python is not installed, goto install_python
  StrCmp $0 "error" install_python 0

  ; If python version is 3.8.x skip section
  StrCpy $pyver $1 3 -7
  StrCmp $pyver "3.8" done 0
  
  install_python:
  
  ; download pyton installer
  inetc::get https://www.python.org/ftp/python/3.8.9/python-3.8.9-amd64.exe $TEMP\python-3.8.9-amd64.exe
  Pop $0
  
  StrCmp $0 "OK" +3
  MessageBox MB_OK "Error when downloading python installer (Returned error code $0)$\n Please install manually from python.org."
  Quit
  
  MessageBox MB_OK "When installing python, make sure 'Add Python to environment variables' is checked!"
  
  ExecWait $TEMP\python-3.8.9-amd64.exe
  
  Delete $TEMP\python-3.8.9-amd64.exe
  
  done:
  
SectionEnd ; end the section

Section "ServerSync Module"

  ; Check python version
  nsExec::ExecToStack 'python --version'
  Pop $0
  Pop $1
  
  ; If python is not installed, goto install_python
  StrCmp $0 "error" 0 install_serversync
  MessageBox MB_OK "Python not found in path. Please (re)install and make sure 'Add Python to environment variables' is checked!"
  Quit
  
  ; If python version is 3.8.x skip section
  StrCpy $pyver $1 3 -7
  StrCmp $pyver "3.8" install_serversync
  MessageBox MB_OK "Default python version ($1) is not 3.8! If Python 3.8 is installed, check environment path variable and make sure it comes above any other python installations!"
  Quit

  install_serversync:

  ; download serversync wheel module
  inetc::get https://github.com/BoltMk0/mc_serversync/releases/download/v1.2/serversync-1.2-py3-none-any.whl $TEMP\serversync-1.2-py3-none-any.whl
  Pop $0
  
  StrCmp $0 "OK" +3
  MessageBox MB_OK "Error when downloading serversync module. Please install manually from https://github.com/BoltMk0/mc_serversync"
  Quit

  nsExec::ExecToStack 'python -m pip install $TEMP\serversync-1.2-py3-none-any.whl'
  Pop $0
  Pop $1
  
  Delete $TEMP\serversync-1.2-py3-none-any.whl
 
  ; Quit if error
  StrCmp $0 "0" done
  MessageBox MB_OK "An unexpected error occored when installing serversync: $1"
  Quit
  
  done:

SectionEnd

Section "Install to Context"
  nsExec::ExecToStack 'python -m serversync --install'
  Pop $0
  Pop $1
  
SectionEnd
