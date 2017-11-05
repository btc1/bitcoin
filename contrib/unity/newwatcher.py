import dbm
from decimal import Decimal
from chainwatcher import ChainWatcher


class NewChainWatcher(ChainWatcher):

    def __init__(self, cfg):
        self.section = "new"
        self.cfg = cfg
        self.start_height = cfg.getint(self.section, "start_height")
        self.min_depth = cfg.getint(self.section, "min_depth")

        self.blocks_parsed = dbm.open(
            cfg.get(
                self.section,
                "blocks_parsed",
                fallback="newchain_blocks_parsed"),
            "c")
        self.whitelist = dbm.open(
            cfg.get(self.section, "whitelist", fallback="whitelist"), "c")

        # initialize transactions to inject with all whitelisted ones
        self.todo_transactions = list(self.whitelist.keys())

        super().__init__(self.section)

    def parseChain(self):
        rpc = self.makeRPC()
        ptr = rpc.getbestblockhash()

        checked = []
        depth = 1
        while depth < self.min_depth:
            self.log.debug("Descending, at block %s", ptr)
            block = rpc.getblock(ptr)
            if "previousblockhash" not in block:
                self.log.debug("No previous block while descending.")
                return
            ptr = block["previousblockhash"]
            depth += 1

        while ptr not in self.blocks_parsed:
            block = rpc.getblock(ptr)
            height = block["height"]
            self.log.debug("Extracting, at block %s / %d", ptr, height)

            if height < self.start_height:
                self.log.debug("Extracted all the way down.")
                return

            transactions = block["tx"][1:]
            self.log.debug("Extracting %d txn from block %s.",
                           len(transactions), ptr)
            for txid in transactions:
                raw = rpc.getrawtransaction(txid)
                self.whitelist[txid] = raw
                self.todo_transactions.append(txid.encode("ascii"))

            self.blocks_parsed[ptr] = "good"
            if "previousblockhash" not in block:
                self.log.debug("No previous block.")
                return
            ptr = block["previousblockhash"]

        self.log.debug("Block %s already extracted.", ptr)
        return None
