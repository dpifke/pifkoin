Pifke's Bitcoin API
===================

This module provides a Python API for Bitcoin mining and research.

JSON-RPC Client
---------------

Provided here is yet another JSON-RPC client for talking to a running Bitcoin
daemon.  Example usage:

```python
from pifkoin import bitcoind

bitcoind.getnewaddress() # returns '1GWgcCuuXXZhtmLpofNeNV9sVEXSxCxAM7'
```

It will automatically read the RPC connection information from
`~/.bitcoin/bitcoin.conf` and establish a new connection to the running
`bitcoind` daemon.

Python's standard `logging` module is used for logging, and most error
conditions will result in a `BitcoindException` with a description of the
issue.

To re-use the same connection between commands, or to specify an alternate
location for the configuration file, use:

```python
from pifkoin.bitcoind import Bitcoind, BitcoindException

conn = Bitcoind('/foo/bitcoind.conf') # filename is optional
conn.getnewaddress() # returns '1ESa86bBU7CERCQE4VzWBZfwc1LjoW2FnH'
conn.nonexistantcommand() # raises BitcoindException
```

The latter method of operation can also be used for JSON-RPC methods not
explicitly listed in the module, for instance when talking to an alternate
implementation such as `namecoind`.

When instantiating `Bitcoind` yourself, you can override options from the
configuration file by passing them to the constructor:

```python
from pifkoin.bitcoind import Bitcoind

conn = Bitcoind(rpcuser='foo', rpcpassword='bar')
```

Blockchain Tools
----------------

The `BlockHeader` class provides convenient methods for reading and working
with the blockchain.  Blocks can be obtained from the running daemon as
follows:

```python
from pifkoin.blockchain import BlockHeader

# Using block hash:
bh = BlockHeader.from_blockchain(hash='00000000000006bca5f9613129affe05a1433e45d1087fe3109816aad0156a41')

# Using block height:
bh = BlockHeader.from_blockchain(height=182400)

# Using relative block height:
bh = BlockHeader.from_blockchain(height=-1) # most recent
bh = BlockHeader.from_blockchain(height=-2) # next most recent (and so on)

# For mining:
bh = BlockHeader.from_getwork()
```

`BlockHeader` instances contain properties and methods for converting between
various formats.  For instance, to get the binary string that is hashed as
part of the mining operation:

```python
from pifkoin.blockchain import BlockHeader

bh = BlockHeader.from_blockchain(182400)
bh.bytes
# returns '\x01\x00\x00\x00\xfd-Df=\xb1u\x96\x0bU-d\xa5\x1c\x98\xfe\xfb\x82\xa0\x9c7W\x0f\xc0[\x01\x00\x00\x00\x00\x00\x00\xda?\x03\x1d\xf3\xb6\xaa\xb6\xf4\x1e\xc2\x850\x94\x9ddc.\xc3\xee\xc0\x8ec\xc1Z,\xb7\xe0r\x7f1\xd2c\xba\xc7O_\x8b\n\x1ae@\xc8\x1a'
```

Mining functionality is included for experimentation - it's too slow to be of
practical use, but the source code explains what's going on and can be used
as a basis for tracing, or for testing new algorithms.

```python
bh.calculate_hash() # recalculates hash using current nonce
bh.find_nonces() # iterates over every possible nonce
```

SHA256 Implementation
---------------------

The mining functionality makes use of a pure-Python SHA256 implementation I
wrote from scratch to help gain an understanding of the algorithm.  It's
written for readability and extensibility, not speed; it's orders of magnitude
slower than the version in the Python standard library.

The goals of this implementation are to make it easy to trace register values
between rounds, and to serve as a basis for reduced-round and alternative
algorithms.  For instance, the mining code makes the first few rounds loop
invariant when iterating over possible nonces, and skips the final few rounds
of the algorithm if it determines the resulting hash won't meet the difficulty
target.  This simulates the behavior of most FPGA and GPU miners; the Python
implementation can therefore be used to create test vectors or aid in
debugging.
