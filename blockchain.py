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
import bitcoind
import contextlib
import datetime
import decimal
import sys

if sys.version > '3':
    long = int
    unicode = str


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
        value = b''.join((value, b'\x00' * (length - len(value))))
    return long(binascii.hexlify(value), 16)


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


class BlockHeader(object):
    """Data structure for working with block header information."""

    PARAMETERS = ('height', 'version', 'previousblockhash', 'merkleroot', 'time', 'bits', 'nonce', 'hash')

    @classmethod
    def from_bitcoind(cls, height=None, hash=None):
        """
        Static factory method that returns a new object instance for the
        specified block.

        :param height:
            The block number to return.  If negative, is regarded as an offset
            from the next block.  For instance, specifying height=-1 returns
            the most recently downloaded block.

        :param hash:
            The block hash to return.
        
        """

        assert height or hash, 'Must specify either height or hash'

        conn = bitcoind.Bitcoind()

        # Look up the block hash if not specified in the method args
        h = hash
        if not hash:
            if height < 0:
                height = conn.getblockcount() + height + 1
            h = conn.getblockhash(height)
        assert hash is None or h == hash, 'Must specify height or hash, not both'

        # Construct a new object from the JSON-RPC response
        return cls(**dict([
            (k, cls._cond_unhexlify(v))
            for k, v in conn.getblock(h).items()
            if k in cls.PARAMETERS
        ]))

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
        self.previousblockhash = previousblockhash
        self.merkleroot = merkleroot
        if not isinstance(time, datetime.datetime):
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
        self.hash = None

    @property
    def difficulty(self):
        return bits_to_difficulty(self.bits)

    @difficulty.setter
    def difficulty(self, difficulty):
        self.bits = difficulty_to_bits(difficulty)

    def __repr__(self):
        """Return a string representation of the object."""

        return ''.join((
            'BlockHeader(',
            ', '.join([
                '='.join((param, repr(getattr(self, param))))
                for param in self.PARAMETERS
                if getattr(self, param) is not None
             ]),
            ')',
        ))


if __name__ == '__main__':
    # Test routine: prints the most recent block header.

    print(BlockHeader.from_bitcoind(-1))

# eof
