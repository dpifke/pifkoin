What is this?
=============

I've been curious about Bitcoin, mining in particular.  Optimizing the mining
code seems like an interesting chance to play with FPGAs and cryptography.

Bitcoin JSON-RPC Client
-----------------------

The JSON-RPC client contained in `bitcoind.py` is probably the most useful to
others.  Example usage:

```python
import bitcoind

bitcoind.getnewaddress() # returns '1GWgcCuuXXZhtmLpofNeNV9sVEXSxCxAM7'
```

It will automatically read the RPC connection information from
`~/.bitcoin/bitcoin.conf` and establish a new connection to the running
`bitcoind` daemon.  To re-use the same connection between commands, or to
specify an alternate location for the configuration file, use:

```python
from bitcoind import Bitcoind, BitcoindException

conn = Bitcoind('/foo/bitcoind.conf') # filename is optional
conn.getnewaddress() # returns '1ESa86bBU7CERCQE4VzWBZfwc1LjoW2FnH'
conn.nonexistantcommand() # raises BitcoindException
```

The latter method of operation can also be used for JSON-RPC methods not
explicitly listed in the module, for instance when talking to an alternate
implementation such as `namecoind`.

Python's standard `logging` module is used for logging, and most error
conditions will result in a `BitcoindException` with a description of the
issue.

Experimental Tools
------------------

Also contained within this repository is an experimental SHA256 implementation
and some tools for analyzing the SHA algorithm and blockchain.  Probably not
useful for anyone else (read: no big discoveries so far), but feel free to
take a look.
