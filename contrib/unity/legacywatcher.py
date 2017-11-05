from time import time
from random import random
import dbm
from chainwatcher import ChainWatcher
from decimal import Decimal
from bitcoinrpc.authproxy import JSONRPCException
import heapq


class LegacyChainWatcher(ChainWatcher):

    def __init__(self, cfg, nwatch):
        self.section = "legacy"
        self.cfg = cfg
        self.nwatch = nwatch
        self.start_height = cfg.getint(self.section, "start_height")
        self.require_coinbase_zeroed = cfg.getint(
            self.section, "require_coinbase_zeroed")
        self.blocks_parsed = dbm.open(
            cfg.get(
                self.section,
                "blocks_parsed",
                fallback="legacy_blocks_parsed"),
            "c")

        self.injection_queue = []

        self.parse_result = None

        self.max_injections_per_step = cfg.getint(
            self.section, "maximum_injections_per_step", fallback=100)

        super().__init__(self.section)

    def parseChain(self):
        rpc = self.makeRPC()
        ptr = rpc.getbestblockhash()
        checked = []

        while ptr not in self.blocks_parsed:
            block = rpc.getblock(ptr)
            height = block["height"]
            checked.append(ptr)
            self.log.debug("At block %s / %d", ptr, height)

            if height < self.start_height:
                self.log.debug("All o.k. - checked all the way down.")
                self.mark_blocks(checked, "good")
                return None

            if self.require_coinbase_zeroed:
                coinbase_raw = rpc.getrawtransaction(block["tx"][0])
                cb_decoded = rpc.decoderawtransaction(coinbase_raw)
                for output in cb_decoded["vout"]:
                    if output["value"] > Decimal("0.0"):
                        self.log.debug(
                            "Block has non-zeroed coinbase transaction: %s.",
                            str(cb_decoded))
                        self.mark_blocks(checked, "bad")
                        return block

            transactions = block["tx"][1:]
            for tx in transactions:
                if tx not in self.nwatch.whitelist:
                    self.log.debug("Block has illegal txid %s.", tx)
                    self.mark_blocks(checked, "bad")
                    return block

            ptr = block["previousblockhash"]

        if self.blocks_parsed[ptr] == "bad":
            self.log.debug("Block %s already marked bad.", ptr)
            self.mark_blocks(checked, "bad")
            block = rpc.getblock(ptr)
            return block
        else:
            self.log.debug("Block %s already checked and good.", ptr)
            self.mark_blocks(checked, "good")
            return None

    def mark_blocks(self, checked, mark):
        for ptr in checked:
            self.blocks_parsed[ptr] = mark

    def invalidate(self, blockhash):
        rpc = self.makeRPC()
        self.log.warn("Dropping invalid block %s.", blockhash)
        rpc.invalidateblock(blockhash)

    def whitelist(self):
        rpc = self.makeRPC()
        for txid in self.nwatch.todo_transactions:
            self.log.debug("Whitelisting %s.", txid.decode("ascii"))
            rpc.whitelist(txid.decode("ascii"))

    def update_queue(self):
        self.log.debug(
            "Update injection queue with %d transactions.", len(
                self.nwatch.todo_transactions))
        t = time()
        for txid in self.nwatch.todo_transactions:
            heapq.heappush(self.injection_queue,
                           (time(), 1, txid))
        self.nwatch.todo_transactions = []

    def inject(self):
        self.whitelist()
        self.update_queue()

        rpc = self.makeRPC()
        t_ref = time()
        self.log.debug(
            "Attempting to inject transactions, %d in queue.", len(
                self.injection_queue))

        inj = 0

        while len(self.injection_queue) and inj < self.max_injections_per_step:
            t, dt, txid = heapq.heappop(self.injection_queue)
            if t > t_ref:
                self.log.debug(
                    "Reached end of injection: %f; %f, %d", t, t_ref, inj)
                heapq.heappush(self.injection_queue,
                               (t, dt, txid))
                break

            raw = self.nwatch.whitelist[txid].decode("ascii")

            self.log.debug("Injecting transaction: %f, %d, %s", t, dt, txid)
            try:
                rpc.sendrawtransaction(raw)
            except JSONRPCException as e:
                if "transaction already in block chain" in str(e):
                    self.log.info("Transaction already included. Ignoring.")
                else:
                    heapq.heappush(self.injection_queue,
                                   (t_ref + dt * random(), dt * 2, txid))
                    self.log.info("Injection failed: %s.", str(e))
            inj += 1
