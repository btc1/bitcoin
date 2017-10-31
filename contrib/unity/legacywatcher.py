from chainwatcher import ChainWatcher
from decimal import Decimal
from bitcoinrpc.authproxy import JSONRPCException


class LegacyChainWatcher(ChainWatcher):

    def __init__(self, cfg, nwatch):
        self.section = "legacy"
        self.cfg = cfg
        self.nwatch = nwatch
        self.start_height = cfg.getint(self.section, "start_height")
        self.require_coinbase_zeroed = cfg.getint(
            self.section, "require_coinbase_zeroed")
        self.blocks_ok = set()
        self.blocks_bad = set()
        self.whitelisted = set()
        self.parse_result = None
        super().__init__(self.section)

    def parseChain(self):
        rpc = self.makeRPC()
        ptr = rpc.getbestblockhash()
        checked = []

        while ptr not in self.blocks_ok and ptr not in self.blocks_bad:
            block = rpc.getblock(ptr)
            height = block["height"]
            self.log.debug("At block %s / %d", ptr, height)
            checked.append(ptr)

            if height < self.start_height:
                self.log.debug("All o.k. - checked all the way down.")
                self.blocks_ok.update(checked)
                return None

            if self.require_coinbase_zeroed:
                coinbase_raw = rpc.getrawtransaction(block["tx"][0])
                cb_decoded = rpc.decoderawtransaction(coinbase_raw)
                for output in cb_decoded["vout"]:
                    if output["value"] > Decimal("0.0"):
                        self.log.debug(
                            "Block has non-zeroed coinbase transaction: %s.",
                            str(cb_decoded))
                        self.blocks_bad.update(checked)
                        return block

            transactions = block["tx"][1:]
            for tx in transactions:
                if tx not in self.nwatch.allowed:
                    self.log.debug("Block has illegal txid %s.", tx)
                    self.blocks_bad.update(checked)
                    return block

            ptr = block["previousblockhash"]

        if ptr in self.blocks_bad:
            self.log.debug("Block %s already marked bad.", ptr)
            self.blocks_bad.update(checked)
            block = rpc.getblock(ptr)
            return block
        else:
            self.log.debug("Block %s already checked and good.", ptr)
            self.blocks_ok.update(checked)
            return None

    def invalidate(self, blockhash):
        rpc = self.makeRPC()
        self.log.warn("Dropping invalid block %s.", blockhash)
        rpc.invalidateblock(blockhash)

    def whitelist(self):
        rpc = self.makeRPC()
        for txid, raw in list(self.nwatch.to_whitelist):
            try:
                self.log.debug("Whitelisting %s.", txid)
                if txid not in self.whitelisted:
                    try:
                        rpc.whitelist(txid)
                        rpc.sendrawtransaction(raw)
                        self.nwatch.to_whitelist.remove((txid, raw))
                        self.whitelisted.add(txid)
                    except JSONRPCException as e:
                        self.log.info("Whitelisting failed: %s.", str(e))
            except Exception as e:
                self.log.error(e, exc_info=True)
