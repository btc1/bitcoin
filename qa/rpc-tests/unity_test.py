#!/usr/bin/env python3
# Copyright (c) 2014-2016 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

#
# Test BitcoinUnity implementation
#
import atexit
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *
from test_framework.script import *
from test_framework.mininode import *
from test_framework.blocktools import *
import subprocess

ini_template = """
[legacy]
rpcuser={legacy_rpcuser}
rpcpass={legacy_rpcpass}
rpcport={legacy_rpcport}
rpchost=127.0.0.1
start_height=211
require_coinbase_zeroed={no_reward}

[new]
rpcuser={new_rpcuser}
rpcpass={new_rpcpass}
rpcport={new_rpcport}
rpchost=127.0.0.1
start_height=211
min_depth=5

[activation]
rpcuser={legacy_rpcuser}
rpcpass={legacy_rpcpass}
rpcport={legacy_rpcport}
rpchost=127.0.0.1
start_height=201
stop_height=210
level=5
lock_in_blocks=5
activation_string={activation_string}
method={activation_method}

[unity]
check_period=0.1
log_file={log_file}
"""


class UnityTest(BitcoinTestFramework):

    def __init__(self):
        super().__init__()
        self.num_nodes = 4
        self.setup_clean_chain = False
        self.unity = None

    def add_options(self, parser):
        parser.add_option(
            "--no-reward",
            dest="no_reward",
            default=False,
            action="store_true",
            help="Test no mining reward")

    def setup_network(self):
        super().setup_network(split=True)

    def setup_nodes(self):
        nodes = []
        # 0,1: btc1
        # 1,2: core
        nodes.append(start_node(0,
                                self.options.tmpdir,
                                ["-debug",
                                 "-reindex",
                                 "-txindex",
                                 "-disablesafemode"],
                                binary="../../src/bitcoind"))
        nodes.append(start_node(1,
                                self.options.tmpdir,
                                ["-debug",
                                 "-reindex",
                                 "-txindex",
                                 "-disablesafemode"],
                                binary="../../src/bitcoind"))

        nodes.append(start_node(2,
                                self.options.tmpdir,
                                ["-debug",
                                 "-reindex",
                                 "-txindex",
                                 "-disablesafemode",
                                 "-acceptnonstdtxn=0"],
                                binary="../../../bitcoin-core/src/bitcoind"))
        nodes.append(start_node(3,
                                self.options.tmpdir,
                                ["-debug",
                                 "-reindex",
                                 "-txindex",
                                 "-disablesafemode"],
                                binary="../../../bitcoin-core/src/bitcoind"))

        self.unity_dir = os.path.join(self.options.tmpdir, "unity")
        self.unity_ini_file = os.path.join(self.unity_dir, "test.ini")

        self.unity_ini_opts = {
            "legacy_rpcuser": rpc_auth_pair(2)[0],
            "legacy_rpcpass": rpc_auth_pair(2)[1],
            "legacy_rpcport": rpc_port(2),
            "no_reward": int(
                self.options.no_reward),
            "new_rpcuser": rpc_auth_pair(0)[0],
            "new_rpcpass": rpc_auth_pair(0)[1],
            "new_rpcport": rpc_port(0),
            "activation_string": "UNITY0" if self.options.no_reward else "UNITY",
            "activation_method": "signalling",
            "log_file": os.path.join(
                self.unity_dir,
                "debug.log")}

        print("unity log file", self.unity_ini_opts["log_file"])
        os.mkdir(self.unity_dir)
        f = open(self.unity_ini_file, "w")
        f.write(ini_template.format(**self.unity_ini_opts))
        f.close()

        if self.unity is not None:
            atexit.unregister(self.unity.kill)
            self.unity.kill()

        self.unity = subprocess.Popen(
            ["../../contrib/unity/unity.py", self.unity_ini_file])
        self.unity_log_pos = 0
        atexit.register(self.unity.kill)

        return nodes

    def run_test(self):
        print("run tests")
        self.test_activation()
        self.test_empty_block_on_core()
        self.test_transaction_whitelisting()

    def read_new_unity_log(self):
        f = open(self.unity_ini_opts["log_file"], "r")
        f.seek(self.unity_log_pos)
        new = f.read()
        f.close()
        self.unity_log_pos += len(new)
        return new

    def make_activate_blocks(self, n):
        tip = int(self.nodes[0].getbestblockhash(), 16)
        height = self.nodes[0].getblockcount() + 1
        cur_time = self.nodes[0].getblock(
            self.nodes[0].getbestblockhash())["mediantime"] + 600
        for i in range(n):
            coinbase = create_coinbase(height)
            if self.options.no_reward:
                coinbase.vin[0] = CTxIn(COutPoint(0, 0xffffffff), ser_string(
                    b"UNITY0") + serialize_script_num(height), 0xffffffff)
            else:
                coinbase.vin[0] = CTxIn(COutPoint(0, 0xffffffff), ser_string(
                    b"UNITY") + serialize_script_num(height), 0xffffffff)

            coinbase.vout[0].nValue = 0
            coinbase.rehash()
            block = create_block(tip, coinbase, cur_time)
            block.nVersion = 0x20000003
            block.rehash()
            block.solve()
            tip = block.sha256
            height += 1
            for node in self.nodes:
                node.submitblock(ToHex(block))
            cur_time += 600

        self.sync_all()

    def test_activation(self):
        # activation
        self.make_activate_blocks(9)
        time.sleep(0.5)
        assert("Soft fork active" not in self.read_new_unity_log())
        self.make_activate_blocks(1)
        time.sleep(0.5)
        assert("Soft fork active" in self.read_new_unity_log())

        # lock-in
        self.make_activate_blocks(5)
        time.sleep(0.5)
        assert("Total number of flagged blocks" in self.read_new_unity_log())
        self.make_activate_blocks(1)
        time.sleep(0.5)
        assert("Total number of flagged blocks" not in self.read_new_unity_log())

    def test_empty_block_on_core(self):
        core_head = self.nodes[2].getbestblockhash()
        self.nodes[2].generate(-1)
        time.sleep(0.5)
        assert(self.nodes[2].getbestblockhash() != core_head)

        # test invalidation of coinbase with reward for UNITY0 variant
        core_head = self.nodes[2].getbestblockhash()
        self.read_new_unity_log()
        self.nodes[2].generate(1)
        time.sleep(0.5)
        if self.options.no_reward:
            assert(self.nodes[2].getbestblockhash() == core_head)
            assert(
                "Block has non-zeroed coinbase transaction" in self.read_new_unity_log())
        else:
            assert(self.nodes[2].getbestblockhash() != core_head)

        self.nodes[2].generate(-2)

    def test_transaction_whitelisting(self):
        self.read_new_unity_log()

        core_head = self.nodes[2].getbestblockhash()

        # create transaction unique to just core chain (-> invalid)
        test_address = self.nodes[2].getnewaddress()
        txid0 = self.nodes[3].sendfrom("", test_address, 1.0)
        time.sleep(1.0)
        assert(self.nodes[2].getmempoolinfo()['bytes'] == 0)
        self.nodes[3].generate(-1)
        time.sleep(1.0)
        node3_head = self.nodes[3].getbestblockhash()
        node2_head = self.nodes[2].getbestblockhash()

        assert(node3_head != core_head)
        assert(("Block has illegal txid " + txid0)
               in self.read_new_unity_log())
        assert(node2_head == core_head)

        # create txn on SegWit2x chain
        txid1 = self.nodes[0].sendfrom("", test_address, 1.0)
        tx1 = self.nodes[0].getrawtransaction(txid1)
        self.nodes[0].generate(4)

        # min_depth not yet reached
        self.nodes[3].sendrawtransaction(tx1)
        time.sleep(1.0)
        assert(self.nodes[2].getmempoolinfo()['bytes'] == 0)
        assert(self.nodes[3].getmempoolinfo()['bytes'] > 0)
        self.nodes[3].generate(-1)
        time.sleep(1.0)
        assert(node2_head == self.nodes[2].getbestblockhash())
        self.nodes[2].generate(-2)

        self.nodes[0].generate(1)
        time.sleep(1.0)
        # min_depth reached
        l = self.read_new_unity_log()
        assert("Extracting 1 txn" in l)
        assert(("Whitelisting " + txid1) in l)

        assert(self.nodes[2].getmempoolinfo()['bytes'] > 0)
        self.nodes[2].generate(-1)
        time.sleep(1.0)

        tip = self.nodes[2].getbestblockhash()
        block = self.nodes[2].getblock(tip)

        assert(len(block["tx"]) == 2)
        txe = block["tx"][1]
        assert(txe == txid1)

if __name__ == '__main__':
    UnityTest().main()
