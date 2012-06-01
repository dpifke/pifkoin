#!/usr/bin/env python
#
# Copyright (c) 2012 Dave Pifke.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#

"""Utilities for parsing and interacting with the Bitcoin blockchain."""

import binascii
import contextlib
import datetime
import decimal
import hashlib
import inspect
import pifkoin.bitcoind
import pifkoin.sha256
import socket
import struct
import sys
import time

if sys.version > '3':
    long = int
    unicode = str
    xrange = range


def bytes_to_long(value):
    """Converts the bytestring *value* to a long."""

    # long() doesn't accept base 256, so we have to convert to base 16 first.
    # Seems like there should be a more efficient way to do this.
    return long(binascii.hexlify(value), 16)


def compact(number):
    """
    Returns the compact representation of a large number, such as the
    "bits" field in the block header used to indicate the difficulty.
    """

    base256 = []
    while number:
        number, byte = divmod(long(number), 256)
        base256.insert(0, byte)

    if base256[0] > 127:
        base256.insert(0, 0)

    # Save original length then zero-pad the end
    length = len(base256)
    while len(base256) < 3:
        base256.append(0)

    return bytearray([length] + base256[:3])


def uncompact(value):
    """Returns the value from its compact representation."""

    length, value = value[0], value[1:] # strings don't have pop(0)
    if not isinstance(length, int):
        length = ord(length)
    if len(value) < length:
        value += b'\x00' * (length - len(value))
    return bytes_to_long(value)


# (2 ** (256 - 32) - 1) in compact representation (with requisite loss of
# precision):
MAX_TARGET = uncompact(b'\x1d\x00\xff\xff')


@contextlib.contextmanager
def enough_decimal_precision(digits=len(str(2 ** 256))):
    """
    By default, Python stores ``Decimal()`` objects to 28 places.  This
    isn't enough for the 256-bit numbers we deal with when calculating
    difficulty, so we provide a context manager to wrap code that needs
    more precision.
    """

    orig_context = decimal.getcontext()
    if orig_context.prec < digits:
        new_context = orig_context.copy()
        new_context.prec = digits
        decimal.setcontext(new_context)

    yield

    decimal.setcontext(orig_context)


def bits_to_difficulty(bits):
    """Converts from compact representation of target to difficulty."""

    with enough_decimal_precision():
        return decimal.Decimal(MAX_TARGET) / uncompact(bits)


def difficulty_to_bits(difficulty):
    """Converts difficulty to compact representation of target."""

    with enough_decimal_precision():
        return compact(decimal.Decimal(MAX_TARGET) / decimal.Decimal(difficulty))


def difficulty_to_target(difficulty):
    """Converts difficulty to target."""

    return uncompact(difficulty_to_bits(difficulty))


class BlockHeader(object):
    """Data structure for working with block header information."""

    PARAMETERS = ('height', 'version', 'previousblockhash', 'merkleroot', 'time', 'bits', 'nonce', 'hash')

    @staticmethod
    def _get_bitcoind(**bitcoind_args):
        """
        Returns a connection to bitcoind.  The caller can specify an existing
        connection to use, or one will be created.

        :param bitcoind:
            The existing connection to use.  Must be the only argument if
            present.  If omitted, any remaining arguments will be passed to
            the bitcoind constructor.

        """

        if 'bitcoind' in bitcoind_args:
            conn = pifkoin.bitcoind.args.pop('bitcoind')
            assert not bitcoind_args, 'Can specify bitcoind connection or options, not both'
        else:
            conn = pifkoin.bitcoind.Bitcoind(**bitcoind_args)

        return conn

    @classmethod
    def from_blockchain(cls, height=None, hash=None, **bitcoind_args):
        """
        Static factory method that returns a new object instance for the
        specified block, which will be retrieved from the running bitcoind.

        :param height:
            The block number to return.  If negative, is regarded as an offset
            from the next block.  For instance, specifying height=-1 returns
            the most recently downloaded block.

        :param hash:
            The block hash to return.

        """

        assert height or hash, 'Must specify either height or hash'

        conn = cls._get_bitcoind(**bitcoind_args)

        # Look up the block hash if not specified in the method args
        h = hash
        if not hash:
            if height < 0:
                height = conn.getblockcount() + height + 1
            h = conn.getblockhash(height)
        assert hash is None or h == hash, 'Must specify height or hash, not both'

        # Construct a new object from the JSON-RPC response
        return cls.from_dict(conn.getblock(h))

    @classmethod
    def from_dict(cls, d):
        """
        Static factory method that returns a new object instance built from
        a dictionary.

        :param d:
            The dictionary of values.

        """

        return cls(**dict([
            (k, cls._cond_unhexlify(v))
            for k, v in d.items()
            if k in cls.PARAMETERS
        ]))

    @classmethod
    def from_getwork(cls, **bitcoind_args):
        """
        Static factory method which returns a new object instance based upon
        a getwork request to the running bitcoind.
        """

        # The byte ordering returned from getwork is bizarre.  You have to
        # reverse the byte order of every 4-byte word.
        hexdata = cls._get_bitcoind(**bitcoind_args).getwork()['data']
        return cls.from_bytes(b''.join([
            binascii.unhexlify(hexdata[i:i+8])[::-1]
            for i in xrange(0, len(hexdata), 8)
        ]))

    @classmethod
    def from_bytes(cls, data):
        """
        Static factory method which returns a new object instance with the
        decoded parameters from *data*.

        :param data:
            Bytestring to decode.

        """

        return cls(
            version=struct.unpack('<L', data[:4])[0],
            previousblockhash=data[4:36][::-1],
            merkleroot=data[36:68][::-1],
            time=struct.unpack('<L', data[68:72])[0],
            bits=data[72:76][::-1],
            nonce=struct.unpack('<L', data[76:80])[0]
        )

    @property
    def bytes(self):
        """The block header as a bytestring, suitable for hashing."""

        return b''.join((
            struct.pack('<L', self.version),
            self.previousblockhash[::-1],
            self.merkleroot[::-1],
            struct.pack('<L', time.mktime(self.time.timetuple())),
            self.bits[::-1],
            struct.pack('<L', self.nonce),
        ))

    @staticmethod
    def _cond_unhexlify(value):
        """
        Un-"hexlifies" a value, but only if it is a string or unicode instance.
        Used for converting values returned in hex format from the bitcoind
        JSON-RPC calls.
        """

        if isinstance(value, (unicode, str)):
            value = binascii.unhexlify(value)
        return value

    def __init__(self, height=None, version=1, previousblockhash=None, merkleroot=None, time=None, bits=None, difficulty=None, nonce=None, hash=None):
        """Constructor."""

        self.height = height
        self.version = version
        assert previousblockhash is None or len(previousblockhash) == 32, 'Previous block hash should be 256 bits long (got %d)' % (len(previousblockhash) * 8)
        self.previousblockhash = previousblockhash
        assert merkleroot is None or len(merkleroot) == 32, 'Merkle root should be 256 bits long (got %d)' % (len(merkleroot) * 8)
        self.merkleroot = merkleroot
        if time and not isinstance(time, datetime.datetime):
            time = datetime.datetime.fromtimestamp(time)
        self.time = time
        if bits:
            assert not difficulty, 'Can specify bits or difficulty, not both'
            self.bits = bits
        elif difficulty:
            self.difficulty = difficulty
        else:
            self.bits = None
        self.nonce = nonce
        assert hash is None or len(hash) == 32, 'Block hash should be 256 bits long (got %d)' % (len(hash) * 8)
        self.hash = hash

    @property
    def difficulty(self):
        return bits_to_difficulty(self.bits)

    @difficulty.setter
    def difficulty(self, difficulty):
        self.bits = difficulty_to_bits(difficulty)

    def __repr__(self):
        """Return a string representation of the object."""

        return ''.join((
            type(self).__name__,
            '(',
            ', '.join([
                '='.join((param, repr(getattr(self, param))))
                for param in self.PARAMETERS
                if getattr(self, param) is not None
             ]),
            ')',
        ))

    def calculate_hash(self, sha_impl=hashlib.sha256):
        """
        (Re-)calculates block hash, returning the new hash value.  Raises
        ValueError (without modifying the existing hash value) if the
        resulting hash does not meet the required difficulty.

        :param sha_impl:
            SHA256 implementation to use.  Defaults to the one from the
            Python standard library, but can be overridden for tracing or
            experimentation.

        """

        assert (self.version and self.previousblockhash and self.merkleroot and self.time and self.bits and self.nonce is not None), 'Must define all block header values prior to hashing'

        # Our SHA256 implementation takes a "round offset" constructor argument
        # for reporting purposes, which we don't want to include if using
        # a different implementation.
        args = { 'round_offset': 128 } if inspect.isclass(sha_impl) and issubclass(sha_impl, pifkoin.sha256.SHA256) else {}

        # See https://en.bitcoin.it/wiki/Block_hashing_algorithm:
        h = sha_impl(sha_impl(self.bytes).digest(), **args).digest()[::-1]

        if bytes_to_long(h) > uncompact(self.bits):
            raise ValueError, 'Hash does not meet required difficulty'

        self.hash = h
        return self.hash

    def find_nonces(self, start=0, end=0xffffffff, difficulty=1, sha_impl=pifkoin.sha256.SHA256):
        """
        Generator which yields additional instances of this block header
        with nonces that meet *difficulty*.

        This function comprises the mining operation, although it's way too
        slow to use for practical mining.

        :param start:
            The first nonce to try, defaults to 0.

        :param end:
            The final nonce to try, defaults to 2**32.

        :param difficulty:
            The minimum difficulty to return.  This may differ from the
            difficulty specified in the block header, to support mining pools
            which want to see "shares" rather than just mined blocks.  By
            default we yield all shares with difficulty 1 (the minimum).

        :param sha_impl:
            SHA256 implementation to use.  It must support the ability to
            run individual rounds via the same API as our implementation,
            probably because it's a subclass of it.

        """

        assert (self.version and self.previousblockhash and self.merkleroot and self.time and self.bits), 'Must define all block header values prior to hashing'

        target = difficulty_to_target(difficulty)

        # The first block of the first hash gets processed normally:
        midstate = sha_impl._process_block(self.bytes[:64])

        # For the second block, the first few rounds are loop-invariant, so we
        # need to work at a lower level.  Construct the message array with the
        # ramaining data to be hashed plus pading, and calculate hash state up
        # to where the nonce appears:
        message2 = (
            [
                struct.unpack('<L', self.merkleroot[:4])[0],
                socket.htonl(int(time.mktime(self.time.timetuple()))),
                struct.unpack('<L', self.bits)[0],
                0, # to be filled in later
                0x80000000, # terminating 1 bit plus padding
            ] +
            [0] * 9 + # padding
            [
                0, # length of message in bits (MSB)
                640, # length of message in bits (LSB)
            ]
        )
        midstate2 = midstate
        for i in xrange(3):
            midstate2 = sha_impl._round(64+i, message2[i], midstate2)

        # Now we loop over every nonce:
        for nonce in xrange(start, end+1):
            # We can now insert the nonce into the message to be hashed and
            # expand the message into the w array
            message2[3] = socket.htonl(nonce)
            w = sha_impl._expand_message(message2)

            # Calculate the remainder of the first hash
            state = midstate2
            for i in xrange(3, 64):
                state = sha_impl._round(64+i, w[i], state)
            state = sha_impl._finalize(state, midstate)

            # Now we want the hash of the hash:
            w = sha_impl._expand_message(
                list(state) +
                [ 0x80000000 ] + # terminating 1 bit plus padding
                [ 0 ] * 5 + # padding
                [
                    0, # length in bits (MSB)
                    256, # length in bits (LSB)
                ]
            )

            # The final 3 rounds will shift the e register down to h without
            # modifying it, and h must be all zeros post-_finalize(), so in
            # most cases we can bypass those rounds.  Calculate the second
            # hash up until that point:
            state = sha_impl.INITIAL_STATE
            for i in xrange(61):
                state = sha_impl._round(128+i, w[i], state)

            # Go no further if we don't meet the minimum difficulty
            if state[4] != 0xa41f32e7: # 0xa41f32e7 + INITIAL_STATE.h == 0
                continue

            # Calculate the remainder of the second hash:
            for i in xrange(61, 64):
                state = sha_impl._round(128+i, w[i], state)
            state = sha_impl._finalize(state)
            h = struct.pack('>LLLLLLLL', *state)[::-1]

            # We know we meet the minimum difficulty, but target may be more
            # stringent, so only yield this hash if it's desired:
            if bytes_to_long(h) < target:
                yield type(self)(
                    version=self.version,
                    previousblockhash=self.previousblockhash,
                    merkleroot=self.merkleroot,
                    time=self.time,
                    bits=self.bits,
                    nonce=nonce,
                    hash=h
                )


if __name__ == '__main__':
    # Can be called from commandline to fetch and print a given block.

    try:
        height = int(sys.argv[1])
    except (IndexError, ValueError):
        try:
            hash = sys.argv[1]
        except IndexError:
            height = -1
            hash = None
        else:
            height = None
    else:
        hash = None

    bh = BlockHeader.from_blockchain(height, hash)
    print(bh)

    # Also run some tests:
    assert BlockHeader.from_bytes(bh.bytes).bytes == bh.bytes, 'Failed to convert to or from bytes'
    bh.calculate_hash() # raises ValueError if something's wrong
    assert len(list(bh.find_nonces(bh.nonce-1, bh.nonce+1))) >= 1, 'Failed to find nonce'

# eof
