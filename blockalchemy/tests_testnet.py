#This is for testnet3 only

import unittest

from binascii import hexlify, unhexlify
from models import *

class Test_alchemy(unittest.TestCase):
    def test_fetch_transaction(self):
        tx1_hash = "935a4ea478eb3f8c01ea541fcd6e49fb291efce9007ee122d45fa4719eac5f6d"
        tx1 = Transaction.from_hash(unhexlify(tx1_hash))
        self.assertEqual(hash_transaction(tx1), unhexlify(tx1_hash))

    def test_fetch_block_header(self):
        bh1_hash = "000000000933ea01ad0ee984209779baaec3ced90fa3f408719526f8d77f4943"
        bh1 = BlockHeader.from_hash(unhexlify(bh1_hash))
        self.assertEqual(hash_block_header(bh1), unhexlify(bh1_hash))

    def test_fetch_address_history(self):
        addr = Address("mpXwg4jMtRhuSpVq4xS3HFHmCmWp9NyGKt")
        history_list = addr.history()

        # Pretty bad test, but there should be at least 4 well confirmed tx on this address
        self.assertTrue(len(history_list) >= 4)

