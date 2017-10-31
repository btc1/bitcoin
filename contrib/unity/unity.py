#!/usr/bin/python3
from sys import argv
from time import sleep, time
import logging
import socket
from configparser import ConfigParser
from legacywatcher import LegacyChainWatcher
from activationwatcher import ActivationWatcher
from newwatcher import NewChainWatcher

log = logging.getLogger("unity")


def unityEnforcement(awatch, nwatch, lwatch):
    active = awatch.parseChain()

    if active:
        log.debug("Soft fork active")
        nwatch.parseChain()
        while True:
            vb = lwatch.parseChain()
            if vb is not None:
                lwatch.invalidate(vb["hash"])
            else:
                break
        lwatch.whitelist()

last = 0
if __name__ == "__main__":
    cfg = ConfigParser()
    if len(argv) > 1:
        cfg.read(argv[1])
    else:
        cfg.read("default.ini")

    logging.getLogger("BitcoinRPC").setLevel(logging.INFO)

    opts = {}
    if cfg.has_option("unity", "log_file"):
        opts["filename"] = cfg.get("unity", "log_file")

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)-15s %(module)-18s %(levelname)-8s %(message)s',
        **opts)

    awatch = ActivationWatcher(cfg)
    nwatch = NewChainWatcher(cfg)
    lwatch = LegacyChainWatcher(cfg, nwatch)

    check_period = cfg.getfloat("unity", "check_period")
    while True:
        t = time()
        if t > last + check_period:
            try:
                unityEnforcement(awatch, nwatch, lwatch)
            except socket.error as exc:
                log.error("Connection problem: %s", str(exc))
            except Exception as exc:
                log.error(exc, exc_info=True)
            last = t
            sleep(check_period / 2.)
