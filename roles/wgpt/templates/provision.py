#!/usr/bin/env python3

import os, sys, requests, base64, ssl, socket, pwd, json

from socket import error as SocketError, timeout as SocketTimeout

from requests import Request, Session
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager, HTTPSConnectionPool
from requests.packages.urllib3.connection import HTTPSConnection
from requests.packages.urllib3.util import connection

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_der_private_key, load_der_public_key
from cryptography.hazmat.backends import default_backend
from cryptography.x509 import load_der_x509_certificate

SSH_DIR = '.ssh'
SSH_AUTHORIZED_KEYS = 'authorized_keys'

WGPT_USER = 'wgpt'
WGPT_DIR = '.wgpt'

WGPT_SERVER_ID = 'server_id'
WGPT_SERVER_HOST = 'host'
WGPT_SERVER_PORT = 'port'
WGPT_TOKEN = '.wgpttoken'

WGPT_CA_CERT = 'ca-cert.pem'
WGPT_CLIENT_CERT = 'client-cert.pem'
WGPT_CLIENT_KEY = 'client-key.pem'

WG_DIR = '/etc/wireguard'
WG_FILE = '/etc/wireguard/wg0.conf'

SSH_GLOBAL_HOSTKEY = '/etc/ssh/ssh_host_ecdsa_key.pub'

token = None
host = None
port = None
dest_ip = None

# Never check any hostnames
class HostNameIgnoringAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(num_pools=connections,
                                       maxsize=maxsize,
                                       block=block,
                                       assert_hostname=False)


class ForcedIPHTTPSAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        self.dest_ip = kwargs.pop('dest_ip', None)
        super(ForcedIPHTTPSAdapter, self).__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **pool_kwargs):
        pool_kwargs['dest_ip'] = self.dest_ip
        self.poolmanager = ForcedIPHTTPSPoolManager(*args, **pool_kwargs)


class ForcedIPHTTPSPoolManager(PoolManager):
    def __init__(self, *args, **kwargs):
        self.dest_ip = kwargs.pop('dest_ip', None)
        super(ForcedIPHTTPSPoolManager, self).__init__(*args, **kwargs)

    def _new_pool(self, scheme, host, port, request_context=None):
            kwargs = self.connection_pool_kw
            assert scheme == 'https'
            kwargs['dest_ip'] = self.dest_ip
            return ForcedIPHTTPSConnectionPool(host, port, **kwargs)


class ForcedIPHTTPSConnectionPool(HTTPSConnectionPool):
    def __init__(self, *args, **kwargs):
        self.dest_ip = kwargs.pop('dest_ip', None)
        super(ForcedIPHTTPSConnectionPool, self).__init__(*args, **kwargs)

    def _new_conn(self):
            self.num_connections += 1

            actual_host = self.host
            actual_port = self.port
            if self.proxy is not None:
                actual_host = self.proxy.host
                actual_port = self.proxy.port

            self.conn_kw = getattr(self, 'conn_kw', {})
            self.conn_kw['dest_ip'] = self.dest_ip
            conn = ForcedIPHTTPSConnection(
                host=actual_host, port=actual_port,
                timeout=self.timeout.connect_timeout,
                strict=self.strict, **self.conn_kw)
            pc = self._prepare_conn(conn)
            return pc

    def __str__(self):
        return '%s(host=%r, port=%r, dest_ip=%s)' % (
            type(self).__name__, self.host, self.port, self.dest_ip)


class ForcedIPHTTPSConnection(HTTPSConnection, object):
    def __init__(self, *args, **kwargs):
        self.dest_ip = kwargs.pop('dest_ip', None)
        super(ForcedIPHTTPSConnection, self).__init__(*args, **kwargs)

    def _new_conn(self):
        extra_kw = {}
        if self.source_address:
            extra_kw['source_address'] = self.source_address

        if getattr(self, 'socket_options', None):
            extra_kw['socket_options'] = self.socket_options

        dest_host = self.dest_ip if self.dest_ip else self.host

        try:
            conn = connection.create_connection(
                (dest_host, self.port), self.timeout, **extra_kw)

        except SocketTimeout as e:
            raise ConnectTimeoutError(
                self, "Connection to %s timed out. (connect timeout=%s)" %
                (self.host, self.timeout))

        except SocketError as e:
            raise NewConnectionError(
                self, "Failed to establish a new connection: %s" % e)

        return conn


def w_file(path, data, bin=False, chmod=0o600):
    with open(path, 'wb' if bin else 'w') as f:
        if chmod:
            os.chmod(path, chmod)

        f.write(data)


def r_file(path):
    with open(path, 'r') as f:
        return f.read()


def m_dir(path, chmod=0o700):
    if not os.path.isdir(path):
        os.mkdir(path, mode=chmod)


def add_to_authorized_hosts(new_key):
    pw_wgpt = pwd.getpwnam(WGPT_USER).pw_dir

    if not os.path.isdir(pw_wgpt + '/' + SSH_DIR):
        os.mkdir(pw_wgpt + '/' + SSH_DIR, mode=0o700)

    authorized_keys_path = pw_wgpt + '/' + SSH_DIR + '/' + SSH_AUTHORIZED_KEYS

    w_file(authorized_keys_path, new_key + '\n')


def store_ssl_cert(cert, key, ca):
    wgpt_dir = get_wgpt_dir()
    m_dir(wgpt_dir)

    cert_obj = load_der_x509_certificate(cert, default_backend())
    key_obj = load_der_private_key(key, password=None, backend=default_backend())
    ca_obj = load_der_x509_certificate(ca, default_backend())

    cert_pem = cert_obj.public_bytes(encoding=serialization.Encoding.PEM)
    ca_pem = ca_obj.public_bytes(encoding=serialization.Encoding.PEM)

    key_pem = key_obj.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    w_file(wgpt_dir + WGPT_CLIENT_CERT, cert_pem, bin=True)
    w_file(wgpt_dir + WGPT_CLIENT_KEY, key_pem, bin=True)
    w_file(wgpt_dir + WGPT_CA_CERT, ca_pem, bin=True)


def store_server_id(server_id):
    wgpt_dir = get_wgpt_dir()
    m_dir(wgpt_dir)

    w_file(wgpt_dir + WGPT_SERVER_ID, str(server_id))
    w_file(wgpt_dir + WGPT_SERVER_HOST, host)
    w_file(wgpt_dir + WGPT_SERVER_PORT, port)


def get_wgpt_dir():
    wgpt_home = pwd.getpwnam(WGPT_USER).pw_dir
    wgpt_dir = wgpt_home + '/' + WGPT_DIR + "/"

    return wgpt_dir


def download_config():
    global token

    if os.getuid() != 0:
        print("Script must be executed as root")
        sys.exit(1)

    wgpt_dir = get_wgpt_dir()

    m_dir(wgpt_dir)
    server_id = r_file(wgpt_dir + WGPT_SERVER_ID)

    wgpttoken_path = "/root/" + WGPT_TOKEN

    # If token exists at this point means we are in setup stage and must be written to a file accessible only by root
    if token:
        w_file(wgpttoken_path, token, chmod=0o600)
    else:
        token = r_file(wgpttoken_path)

    url = 'https://cd.wgpt:%s/api/servers/get/config/%s' % (port, server_id)
    s = Session()
    s.mount(url, ForcedIPHTTPSAdapter(dest_ip=dest_ip))

    print("URL: %s" % url)

    res = s.post(url,
                 json={'token': token},
                 verify=wgpt_dir + WGPT_CA_CERT,
                 cert=(wgpt_dir + WGPT_CLIENT_CERT, wgpt_dir + WGPT_CLIENT_KEY))

    if res.status_code != 200:
        print("Config request returned error code: %d" % res.status_code)
        sys.exit(2)

    m_dir(WG_DIR)
    w_file(WG_FILE, res.text, chmod=0o600)


def register():
    url = 'https://register.wgpt:%s/api/register' % port
    print('Connecting to: %s' % url)
    with Session() as s:
        s.mount(url, ForcedIPHTTPSAdapter(dest_ip=dest_ip))

        with open(SSH_GLOBAL_HOSTKEY) as f:
            ssh_key = f.read()

        res = s.post(url, json={'server_token': token, 'server_ssh_key': ssh_key}, verify=False)
        if res.status_code != 200:
            print("Server response code: %d" % res.status_code)
            sys.exit(3)

        data = res.json()

    status = data.get("status")
    if status and status != 'success':
        print(" *** Error registering: status=%s message=%s" % (status, data.get("message")))
        sys.exit(6)

    cert = data["cert"]
    key = data["key"]
    ssh = data["ssh"]
    ca = data["ca"]
    server_id = data["server"]

    add_to_authorized_hosts(ssh)
    store_ssl_cert(base64.b64decode(cert), base64.b64decode(key), base64.b64decode(ca))
    store_server_id(server_id)


def get_connection_params_from_args():
    global token, host, port, dest_ip
    token = sys.argv[1]
    host = sys.argv[2]
    port = sys.argv[3]
    dest_ip = socket.gethostbyname(host)


def get_connection_params_from_stored():
    global token, host, port, dest_ip

    wgpt_dir = get_wgpt_dir()

    host = r_file(wgpt_dir + WGPT_SERVER_HOST)
    port = r_file(wgpt_dir + WGPT_SERVER_PORT)
    dest_ip = socket.gethostbyname(host)

    # Token set to None on purpose, will be fetched later by reading file
    token = None


def fork_and_setup():
    pid = os.fork()
    if pid == 0:  # Child
        pw_wgpt = pwd.getpwnam(WGPT_USER)
        os.setgid(pw_wgpt.pw_uid)
        os.setuid(pw_wgpt.pw_gid)
        register()
    else:  # Parent
        ret_code = os.wait()[1]
        if ret_code != 0:
            print("Child process returned error %d, exiting" % ret_code)
            sys.exit(6)

        download_config()


if __name__ == "__main__":
    if os.getuid() != 0:
        print("Script must be executed as root")
        sys.exit(4)

    has_args = len(sys.argv) == 4

    if has_args:
        get_connection_params_from_args()
        fork_and_setup()
    else:
        get_connection_params_from_stored()
        download_config()
