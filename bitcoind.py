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

"""JSON-RPC implementation for talking to bitcoind."""

import base64
import collections
import decimal
import httplib
import json
import logging
import os

logger = logging.getLogger('bitcoin')


class BitcoindException(Exception):
    """Exception thrown for errors talking to bitcoind."""

    def __init__(self, value):
        """Constructor which also logs the exception."""

        super(BitcoindException, self).__init__(value)
        logger.error(value)


class BitcoindCommand(object):
    """Callable object representing a bitcoind JSON-RPC method."""

    def __init__(self, server, method):
        """Constructor."""

        self.server = server
        self.method = method.lower()

    def __call__(self, *args):
        """JSON-RPC wrapper."""

        return self.server._rpc_call(self.method, *args)


class Bitcoind(object):
    """
    JSON-RPC wrapper for talking to bitcoind.  Methods of instances of this
    object correspond to server commands, e.g. ``Bitcoind().getnewaddress()``.
    """

    DEFAULT_CONFIG_FILENAME = '~/.bitcoin/bitcoin.conf'

    def _parse_config(self, filename=DEFAULT_CONFIG_FILENAME):
        """
        Returns an OrderedDict with the Bitcoin server configuration, which
        by default is located in ``~/.bitcoin/bitcoin.conf``.

        Errors are logged; if the configuration file does not exist or could
        not be read, an empty dictionary will be returned; it's up to the
        caller whether or not this is a fatal error.
        """

        # Note: I would have loved to use Python's ConfigParser for this, but
        # it requires .ini-style section headings.
        config = collections.OrderedDict()
        try:
            with open(os.path.expanduser(filename)) as conf:
                for lineno, line in enumerate(conf):
                    comment = line.find('#')
                    if comment != -1:
                        line = line[:comment]
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        (var, val) = line.split('=')
                    except IndexError:
                        logger.warning('Could not parse line %d of %s, ignored.', lineno, filename)
                        continue

                    var = var.rstrip().lower()

                    val = val.lstrip()
                    if val[0] in ('"', "'") and val[1] in ('"', "'"):
                        val = val[1:-1]

                    config[var] = val

        except Exception, e:
            logger.error('%s reading %s: %s', type(e).__name__, filename, str(e))

        logger.debug('Read %d parameters from %s', len(config), filename)
        return config
                    
    def __init__(self, config_filename=DEFAULT_CONFIG_FILENAME):
        """
        Constructor.  Parses RPC communication details from ``bitcoin.conf``
        and opens a connection to the server.
        """

        config = self._parse_config(config_filename)
        if 'rpcuser' not in config or 'rpcpassword' not in config:
            raise BitcoindException('Unable to read RPC credentials from %s' % config_filename)

        self._rpc_host = config.get('rpcserver', '127.0.0.1')
        self._rpc_port = int(config.get('rpcport', 8332))
        timeout = int(config.get('rpctimeout', 30))
        if config.get('rpcssl', '').lower() in ('1', 'yes', 'true', 'y', 't'):
            logger.debug('Making HTTPS connection to %s:%d', self._rpc_host, self._rpc_port)
            self._rpc_conn = httplib.HTTPSConnection(self._rpc_host, self._rpc_port, timeout=timeout)
        else:
            logger.debug('Making HTTP connection to %s:%d', self._rpc_host, self._rpc_port)
            self._rpc_conn = httplib.HTTPConnection(self._rpc_host, self._rpc_port, timeout=timeout)
        self._rpc_auth = base64.b64encode(':'.join((config['rpcuser'], config['rpcpassword'])).encode('utf8'))
        self._rpc_id = 0

    def __getattr__(self, method):
        """
        Attribute getter.  Assumes the attribute being fetched is the name
        of a JSON-RPC method.
        """

        return BitcoindCommand(self, method)

    def _rpc_call(self, method, *args):
        """Performs a JSON-RPC command on the server and returns the result."""

        # The bitcoin protocol specifies a incrementing sequence for each
        # command.
        self._rpc_id += 1

        logger.debug('Starting "%s" JSON-RPC request', method)
        self._rpc_conn.request(
            method='POST',
            url='/',
            body=json.dumps({
                'version': '1.1',
                'method': method,
                'params': args,
                'id': self._rpc_id,
            }),
            headers={
                'Host': '%s:%d' % (self._rpc_host, self._rpc_port),
                'Authorization': ''.join(('Basic ', self._rpc_auth)),
                'Content-Type': 'application/json',
            }
        )

        response = self._rpc_conn.getresponse()
        if not response:
            raise BitcoindException('No response from bitcoind')
        if response.status != 200:
            raise BitcoindException('%d (%s) response from bitcoind' % (response.status, response.reason))

        response_body = response.read().decode('utf8')
        logger.debug('Got %d byte response from server', len(response_body))
        try:
            response_json = json.loads(response_body, parse_float=decimal.Decimal)
        except ValueError, e:
            raise BitcoindException('Error parsing bitcoind response: %s', str(e))

        if response_json.get('error'):
            raise BitcoindException(response_json['error'])
        elif 'result' in response_json:
            return response_json['result']
        else:
            raise BitcoindException('Invalid response from bitcoind')

# eof

        
