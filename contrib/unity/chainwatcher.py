from multiprocessing import Process, RLock
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
import logging


class ChainWatcher(object):

    def __init__(self, logger_name):
        self.log = logging.getLogger(logger_name)

    def makeRPC(self):
        user = self.cfg.get(self.section, "rpcuser")
        if user[0] == "@":
            user = open(user[1:]).readline().split(":")[0]

        passwd = self.cfg.get(self.section, "rpcpass")
        if passwd[0] == "@":
            passwd = open(passwd[1:]).readline().split(":")[1]

        return AuthServiceProxy(
            "http://{user}:{passwd}@{host}:{port}".format(
                user=user,
                passwd=passwd,
                host=self.cfg.get(self.section, "rpchost"),
                port=self.cfg.getint(self.section, "rpcport")))
