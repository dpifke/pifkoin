#!/usr/bin/python
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

"""Plots the SHA256 algorithm (as used when mining) as a directional graph."""

# TODO: add attributes to nodes and edges.  Node attributes should indicate
# constant vs. state variable vs. target, edge attributes should indicate
# transformations vs. plain assignment.

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot
import networkx

g = networkx.DiGraph()

# Inputs to first hash, first block
g.add_edge(1, 'w[0][0]') # version
for i in xrange(1, 9):
    g.add_edge('previous_hash', 'w[0][%d]' % i)
for i in xrange(10, 16):
    g.add_edge('merkle_root', 'w[0][%d]' % i)

# Inputs to first hash, second block
g.add_edge('merkle_root', 'w[1][0]')
g.add_edge('timestamp', 'w[1][1]')
g.add_edge('bits', 'w[1][2]')
g.add_edge('nonce', 'w[1][3]')
g.add_edge(0x80000000, 'w[1][4]') # padding
for i in xrange(5, 14): # padding continued
    g.add_edge(0, 'w[1][%d]' % i)
g.add_edge(0, 'w[1][14]') # length (MSB)
g.add_edge(640, 'w[1][15]') # length (LSB)

# Inputs to second hash
for i, register in enumerate(('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h')):
    g.add_edge('%s[1][63]' % register, 'w[2][%d]' % i)
g.add_edge(0x80000000, 'w[2][9]') # padding
for i in xrange(10, 14): # padding continued
    g.add_edge(0, 'w[2][%d]' % i)
g.add_edge(0, 'w[2][14]') # length (MSB)
g.add_edge(256, 'w[2][15]') # length (LSB)

# Message expansion
for i in xrange(3):
    for j in xrange(16, 64):
        g.add_edge('w[%d][%d]' % (i, j - 2), 'w[%d][%d]' % (i, j))
        g.add_edge('w[%d][%d]' % (i, j - 7), 'w[%d][%d]' % (i, j))
        g.add_edge('w[%d][%d]' % (i, j - 15), 'w[%d][%d]' % (i, j))
        g.add_edge('w[%d][%d]' % (i, j - 16), 'w[%d][%d]' % (i, j))

# Constants for first and last round of each SHA256 hash
for register, constant in (
        ('a', 0x6a09e667), ('b', 0xbb67ae85), ('c', 0x3c6ef372),
        ('d', 0xa54ff53a), ('e', 0x510e527f), ('f', 0x9b05688c),
        ('g', 0x1f83d9ab), ('h', 0x5be0cd19),
    ):
    for i, j in ((0, -1), (0, 63), (1, 63), (2, -1), (2, 63)):
        g.add_edge(constant, '%s[%d][%d]' % (register, i, j))

# Connect first and second round of first hash
for register in ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'):
    g.add_edge('%s[0][63]' % register, '%s[1][-1]' % register)

# Constants for rounds
k = (
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
)

# 64 rounds for each block for each hash
for i in xrange(3):
    for j in xrange(64):
        g.add_edge('a[%d][%d]' % (i, j - 1), 'a[%d][%d]' % (i, j))
        g.add_edge('b[%d][%d]' % (i, j - 1), 'a[%d][%d]' % (i, j))
        g.add_edge('c[%d][%d]' % (i, j - 1), 'a[%d][%d]' % (i, j))
        g.add_edge('e[%d][%d]' % (i, j - 1), 'a[%d][%d]' % (i, j))
        g.add_edge('f[%d][%d]' % (i, j - 1), 'a[%d][%d]' % (i, j))
        g.add_edge('g[%d][%d]' % (i, j - 1), 'a[%d][%d]' % (i, j))
        g.add_edge('h[%d][%d]' % (i, j - 1), 'a[%d][%d]' % (i, j))
        g.add_edge(k[j], 'a[%d][%d]' % (i, j))
        g.add_edge('w[%d][%d]' % (i, j), 'a[%d][%d]' % (i, j))

        g.add_edge('a[%d][%d]' % (i, j - 1), 'b[%d][%d]' % (i, j))

        g.add_edge('b[%d][%d]' % (i, j - 1), 'c[%d][%d]' % (i, j))

        g.add_edge('c[%d][%d]' % (i, j - 1), 'd[%d][%d]' % (i, j))

        g.add_edge('d[%d][%d]' % (i, j - 1), 'e[%d][%d]' % (i, j))
        g.add_edge('e[%d][%d]' % (i, j - 1), 'e[%d][%d]' % (i, j))
        g.add_edge('f[%d][%d]' % (i, j - 1), 'e[%d][%d]' % (i, j))
        g.add_edge('g[%d][%d]' % (i, j - 1), 'e[%d][%d]' % (i, j))
        g.add_edge('h[%d][%d]' % (i, j - 1), 'e[%d][%d]' % (i, j))
        g.add_edge(k[j], 'e[%d][%d]' % (i, j))
        g.add_edge('w[%d][%d]' % (i, j), 'e[%d][%d]' % (i, j))

        g.add_edge('e[%d][%d]' % (i, j - 1), 'f[%d][%d]' % (i, j))

        g.add_edge('f[%d][%d]' % (i, j - 1), 'g[%d][%d]' % (i, j))

        g.add_edge('g[%d][%d]' % (i, j - 1), 'h[%d][%d]' % (i, j))

# We care about the first 32-bit word of the final output: is it all zeroes?
g.add_edge('a[2][63]', 'target')

# For now, plot using GraphViz.  The end goal here is to be able to do
# automated analysis using NetworkX, and perhaps some sort of interactive
# web interface.
networkx.draw_graphviz(g)
networkx.write_dot(g, 'sha256.dot')

# To be usable, this needs scaling options, etc:
#networkx.draw(g)
#matplotlib.pyplot.savefig('sha256.png')

# eof
