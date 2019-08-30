Cableguard Provisioner      
===========================

This Ansible script will install Wireguard on a server and register that server with the Cableguard API for automatic provisioning.

Requirements
------------

Ansible >= 2.8
Cableguard API instance
Server token from Cableguard API

New server installer
--------------------

This script will help you to provision a new server. To do that you simply add your server to your Cableguard API instance, get the `server_token` after registration and use them as parameters when executing the script:

```
Usage: ./deploy.sh <params> where params can be:
       -h To display this help and exit
       -t Token to use
       -w Cableguard host/ip from where configuration is downloaded
       -s Host/ip of Wireguard server to provision
  Optional:
       -p Cableguard port (default 2443)
       -u Remote user of wireguard's SSH (root or sudoable user) (default root)

Example: ./deploy.sh -t 5feb9792-add8-4d1c-8737-23b6313b4c8f -h cableguard.example.com -w wireguard.example.com -u ubuntu
```

Testing with Vagrant
--------------------

You can test the deployment in a vagrant virtual machine using the provided Vagrantfile
