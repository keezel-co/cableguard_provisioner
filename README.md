Wireguard Provisioning Tool
===========================

Requirements
------------

Ansible >= 2.8

New server installer
--------------------

This script will help you to provision a new server to do that you havce simply to type use the environment variables

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
