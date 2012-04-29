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

import collections
import contextlib
import decimal


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

    length, value = ord(value[0]), value[1:] # strings don't have pop(0)
    if len(value) < length:
        value = b''.join((value, b'\x00' * (length - len(value))))
    return long(value.encode('hex'), 16)


# (2 ** (256 - 32) - 1) in compact representation (with requisite loss of
# precision):
MAX_TARGET = uncompact(b'\x1d\x00\xff\xff')


@contextlib.contextmanager
def enough_decimal_precision():
    """
    By default, Python stores ``Decimal()`` objects to 28 places.  This
    isn't enough for 256-bit numbers we deal with when calculating
    difficulty, so we provide a context manager to wrap code that needs
    more precision.
    """

    orig_context = decimal.getcontext()
    if orig_context.prec < 68:
        new_context = orig_context.copy()
        new_context.prec = 68
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


class BlockHeader(collections.namedtuple('BlockHeader', 'version previousblockhash merkleroot time bits nonce')):
    """Data structure for working with block header information."""

    __slots__ = ()

    def __new__(cls, *args, **kwargs):
        # TODO: deal with optional arguments or alternate forms (such as
        # difficulty vs. bits)
        return super(cls, BlockHeader).__new__(cls, *args, **kwargs)

    # TODO: difficulty getter/setter that handles conversion from/to bits

# eof
