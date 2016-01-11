# CoopServer & Client
Special thanks to Ryan Detzel for his effort on initial CoopDoor
Check also https://github.com/ryanrdetzel !

### Adaptions to Ryans version:
----------
- Enhance logging
- Fixed initial state 
- Eliminate second chance and temperature and push stuff
- Change status message for webclient
- Other email (smtp)
- added webclient (based on bootstrap 3.3.6)
- added /etc/init.d/coopserverctl

## Todo:
-----
* proper config handling
* using any push client api for apps (mobile support)
* propably use checkTime for blinking state instead of extra thread for manual mode (save ressources)
* nice to have: jQuery/AJAX for status updates in webclient

# Coop server
Control the door from any other app:
    Open a connection (telnet 127.0.0.1 55567)

    Valid commands:
        stop, up, down, status, auto, manual, halt

## Configs
#### Adapt coopserver.py
- change your location in the script and the door will open and close at sunrise/sunset
- change times for opening and closing offsets
- change port for commands (default: 55567)
#### Adapt coopserverctl template to your needs 
- see also https://wiki.debian.org/LSBInitScripts, for example install it with sudo update-rc.d coopserverctl defaults, or 
- see https://gist.github.com/naholyr/4275302 or check, if your distribution contains a skeleton at /etc/init.d
- Adapt coopmail.py according your smtp credentials

# Coop client
    Based on bootstrap a simple php index.php and helper files for communication and doing snapshots (using picamera)
    
    webclient/index-de.php
    webclient/index-en.php
        using the getstatus() output of coopserver.py
    webclient/paparazi.py
        simple python script for making a photo with picamera
    webclient/coopclient.php
        simple tcp client to request status or send commands from / to the server


    
