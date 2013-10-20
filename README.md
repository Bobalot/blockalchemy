# BlockAlchemy

Browse the blockchain.

Unit tests currently only do testnet.
 ```
python -m unittest discover
 ```


 ```python
 from models import *
 from binascii import hexlify, unhexlify

 tx = Transaction.from_hash(unhexlify("4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"))

 block_header = BlockHeader.from_hash(unhexlify("000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"))
 ```


