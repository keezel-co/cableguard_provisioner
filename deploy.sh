#!/bin/sh


show_help()
{
  echo -e " "
  echo "Usage: $0 <params> where params can be:"
  echo "       -h To display this help and exit"
  echo "       -t Token to use"
  echo "       -w portunus host/ip from where configuration is downloaded"
  echo "       -s Host/ip of Wireguard server to provision"
  echo "  Optional:"
  echo "       -p portunus port (default 2443)"
  echo "       -u Remote user of wireguard's SSH (root or sudoable user) (default root)"
  echo -e " "
  echo "Example: $0 -t 5feb9792-add8-4d1c-8737-23b6313b4c8f -w portunus.example.com -s wireguard.example.com -u ubuntu"
  echo -e " "
}

while getopts "ht:w:s:p:u:" arg
do
  case $arg in
    h)
      show_help
      exit 1
      ;;
    t)
      export JOIN_TOKEN="${OPTARG}"
      ;;
    w)
      export PORTUNUS_SERVER="${OPTARG}"
      ;;
    s)
      export WIREGUARD_TARGET="${OPTARG}"
      ;;
    p)
      export PORTUNUS_PORT="${OPTARG}"
      ;;
    u)
      export REMOTE_USER="${OPTARG}"
      ;;
  esac
done

if [ -z "$JOIN_TOKEN" ] || [ -z "$WIREGUARD_TARGET" ] || [ -z "$PORTUNUS_SERVER" ]
then
  echo "Missing parameters"
  show_help
  exit 1
fi

if [ -z "$REMOTE_USER" ]
then
  REMOTE_USER='ubuntu'
fi

if [ -z "$PORTUNUS_PORT" ]
then
  export PORTUNUS_PORT='2443'
else
  export PORTUNUS_PORT="$WGPT_PORT"
fi

ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i "${WIREGUARD_TARGET}," -u "${REMOTE_USER}" wgpt.yml
