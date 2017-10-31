from chainwatcher import ChainWatcher
import codecs


class ActivationWatcher(ChainWatcher):

    def __init__(self, cfg):
        self.cfg = cfg
        self.section = "activation"
        self.stop_height = cfg.getint(self.section, "stop_height")
        self.start_height = cfg.getint(self.section, "start_height")
        self.level = cfg.getint(self.section, "level")
        self.act_str = cfg.get(
            self.section,
            "activation_string").encode("utf-8")
        self.method = cfg.get(self.section, "method").encode("utf-8")
        self.lock_in_blocks = cfg.getint(self.section, "lock_in_blocks")
        self.parse_result = None
        if self.method == "always":
            self.parse_result = True
        self.locked_in = False
        self.flagged = {}
        super().__init__(self.section)

    def parseChain(self):
        if self.method == b"always":
            return True
        if self.locked_in:
            return self.parse_result

        rpc = self.makeRPC()
        tip = rpc.getbestblockhash()
        ptr = tip

        while ptr not in self.flagged:
            block = rpc.getblock(ptr)
            height = block["height"]
            self.log.debug("At block %s / %d", ptr, height)
            previous = block["previousblockhash"]

            if height > self.stop_height:
                flag = False
                self.log.debug("Past signalling period.")
            elif height >= self.start_height:
                tx = rpc.getrawtransaction(block["tx"][0])
                decoded = rpc.decoderawtransaction(tx)
                flag = False
                if ("vin" in decoded and len(decoded["vin"]) > 0 and
                        "coinbase" in decoded["vin"][0]):
                    unhexed = codecs.decode(
                        decoded["vin"][0]["coinbase"], "hex")
                    flag = self.act_str in unhexed
            else:
                self.flagged[ptr] = (height, False, None)
                break

            self.flagged[ptr] = (height, flag, previous)
            self.log.debug("Flag at height %d: %d", height, flag)
            ptr = previous

        if self.flagged[tip][0] < self.stop_height:
            self.log.debug(
                "Did not reach end of signalling period yet (%d/%d)",
                self.flagged[tip][0],
                self.stop_height)
            return False

        flagsum = 0
        numblocks = 0
        ptr = tip
        lock_in = False
        while True:
            height, flag, previous = self.flagged[ptr]
            if height <= self.stop_height and height >= self.start_height:
                numblocks += 1
            flagsum += flag
            if not lock_in and height >= self.stop_height + self.lock_in_blocks:
                self.log.debug("Lock in set at %d, %d.", height, numblocks)
                lock_in = True
            elif height <= self.start_height:
                self.log.debug(
                    "Total number of flagged blocks: %d out of %d, lock-in: %d",
                    flagsum, numblocks, lock_in)

                self.locked_in = lock_in
                self.parse_result = flagsum >= self.level
                return self.parse_result
            ptr = previous
