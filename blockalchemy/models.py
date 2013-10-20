__author__ = 'bob'

import binascii
from binascii import hexlify, unhexlify
import time

from serialize import *
from engine import Base, ObeliskRequest, ObeliskResponse

from util import base58_encode, base58_decode

null_hash = '\x00'*32


class OutPoint(object):
    def __init__(self):
        self.hash = None
        self.n = None

    def is_null(self):
        return (len(self.hash) == 0) and (self.n == 0xffffffff)

    def __repr__(self):
        return "Outpoint(hash=%s, n=%i)" % (hexlify(self.hash), self.n)

    def serialize(self):
        return ser_output_point(self)

    @staticmethod
    def deserialize(bytes):
        return deser_output_point(bytes)


class TxOut(object):
    def __init__(self):
        self.value = None
        self.script = None

    def __repr__(self):
        return "TxOut(value=%i.%08i script=%s)" % (self.value // 100000000, self.value % 100000000, binascii.hexlify(self.script))

    def serialize(self):
        return ser_txout(self)

    @staticmethod
    def deserialize(bytes):
        return deser_txout(bytes)


class TxIn(object):
    def __init__(self):
        self.previous_output = OutPoint()
        self.script = None
        self.sequence = 0xffffffff

    def is_final(self):
        return self.sequence == 0xffffffff

    def __repr__(self):
        return "TxIn(previous_output=%s script=%s sequence=%i)" % (repr(self.previous_output), binascii.hexlify(self.script), self.sequence)

    def serialize(self):
        return ser_txin(self)

    @staticmethod
    def deserialize(bytes):
        return deser_txin(bytes)


class Transaction(Base):
    def __init__(self):
        self.version = 1
        self.locktime = 0
        self.inputs = []
        self.outputs = []

    def is_final(self):
        for tin in self.vin:
            if not tin.is_final():
                return False
        return True
    def is_coinbase(self):
        return len(self.vin) == 1 and self.vin[0].prevout.is_null()

    def __repr__(self):
        return "Transaction(version=%i inputs=%s outputs=%s locktime=%i)" % (self.version, repr(self.inputs), repr(self.outputs), self.locktime)

    def serialize(self):
        return ser_tx(self)

    @staticmethod
    def deserialize(bytes):
        return deser_tx(bytes)

    @staticmethod
    def from_hash(txid):
        command = "blockchain.fetch_transaction"
        # Have to reverse bytes before sending the request.
        data = txid[::-1]

        return Base.service.send_command(command, data)



class BlockHeader(Base):
    def __init__(self):
        self.version = 1
        self.previous_block_hash = None
        self.merkle = None
        self.timestamp = 0
        self.bits = 0
        self.nonce = 0

    def __repr__(self):
        return "BlockHeader (version=%i previous_block_hash=%s merkle=%s timestamp=%s bits=%08x nonce=%08x)" % (self.version, hexlify(self.previous_block_hash), hexlify(self.merkle), time.ctime(self.timestamp), self.bits, self.nonce )

    def serialize(self):
        return ser_block_header(self)

    @staticmethod
    def deserialize(bytes):
        return deser_block_header(bytes)

    @staticmethod
    def from_height(height):
        command = "blockchain.fetch_block_header"
        data = height

        return Base.service.send_command(command, data)

    @staticmethod
    def from_hash(hash):
        # Have to reverse bytes before sending the request.
        return BlockHeader.from_height(hash[::-1])


# tx list is a list of Tranaction or a str hash,
# we can auto-magically replace a hash with a transaction, when a user tries to access it.
class TransactionList(Base):

    def __init__(self, initial_list=None):
        if initial_list is None:
            self._txlist = []
        else:
            self._txlist = initial_list

    def __getitem__(self, item):
        if type(item) is not int:
            raise KeyError
        else:
            # If the object isn't an actual transaction, try and query to get it.
            if type(self._txlist[item]) is not Transaction:

                tx = self.service.send_command("blockchain.fetch_transaction", self._txlist[item][::-1])

                self._txlist[item] = tx
                return tx
            else:
                return self._txlist[item]

    def __setitem__(self, key, value):
        if type(value) is Transaction:
            self._txlist[key] = value
        else:
            raise ValueError

    def fetch_all(self):
        pass


    # Not currently working
    ## Returns a list of transaction contained in block hash
    #@staticmethod
    #def from_hash(hash):
    #    hash_list = Base.service.send_command("blockchain.fetch_block_transaction_hashes", hash)
    #    txl = TransactionList(hash_list)
    #
    #    return txl


class Block(Base):
    def __init__(self):
        self.header = BlockHeader()
        self.transactions = TransactionList()

    def serialize(self):
        return ser_block(self)

    @staticmethod
    def deserialize(bytes):
        return deser_block(bytes)

    @staticmethod
    def from_hash(hash):
        b = Block()
        b.header = BlockHeader.from_hash(hash)
        return b

# Keep this simple so it works on both testnet and mainnet,
# defaults to network 0x00, but that can change.
# Does not do key generation, or any cryptography.
class Address(Base):
    def __init__(self, address=None):
        if address is not None:
            decoded = base58_decode(address)

            # Check the checksum before we set any data
            if checksum(decoded[0:21]) != decoded[21:25]:
                raise Exception

            self.version_byte = decoded[0]
            self.pubkey_hash = decoded[1:21]
            #self.checksum = decoded[21:25]

        else:
            self.version_byte = "\x00"
            self.pubkey_hash = "\x00"*20
            #self.checksum = "\x00"*4

    def address_format(self):
        addr = self.version_byte + self.pubkey_hash
        return base58_encode(addr + checksum(addr))

    def history(self, from_height=0):
        # The tuple will auto-magically be serialized
        data = (self.version_byte, self.pubkey_hash[::-1], from_height)
        resp = Base.service.send_command("address.fetch_history", data)

        return resp


    # Subscribe not working yet.
    # subscribe to an address
    # block by yourself if you need to.
    #def subscribe(self):
    #    data = (self.version_byte, self.pubkey_hash[::-1])
    #    callback = addr_callback
    #
    #    self.service.send_subscription("address.subscribe", data, callback)


    def __str__(self):
        return self.address_format()

    def __repr__(self):
         return "Address(address=%s version_byte=%s address_hash=%s)" % (self.address_format(), hexlify(self.version_byte), hexlify(self.address_hash))


def addr_callback(data):
    print data.address_hash
    print data.tx


class address_update(object):
    def __init__(self):
        self.address_version_byte = "\x00"
        self.address_hash = "\x00" * 20
        self.height = -1
        self.block_hash = "\x00" * 32
        self.tx = None

class history_row(object):
    def __init__(self):
        self.output_hash = None
        self.output_index = -1
        self.output_height = -1
        self.value = 0

        self.spend_hash = None
        self.spend_index = -1
        self.spend_height = -1

    def is_unspent(self):
        return self.spend_hash == null_hash

    def __repr__(self):
        if self.is_unspent():
            return "History(Unspent output_hash=%s:%i  output_height=%i value=%i)" % (hexlify(self.output_hash), self.output_index, self.output_height, self.value)
        else:
            return "History(Spent output_hash=%s:%i  output_height=%i value=%i)" % (hexlify(self.output_hash), self.output_index, self.output_height, self.value)


def genesis_block():
    b = BlockHeader.from_height(0)
    return b

