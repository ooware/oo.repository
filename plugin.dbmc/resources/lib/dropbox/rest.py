"""
A simple JSON REST request abstraction layer that is used by the
``dropbox.client`` and ``dropbox.session`` modules. You shouldn't need to use this.
"""

import io
#import pkg_resources
import socket
import ssl
import sys
import urllib

from resources.lib.utils import log, log_debug, NL_

try:
    import json
except ImportError:
    import simplejson as json

try:
   import urllib3
except ImportError:
    raise ImportError('Dropbox python client requires urllib3.')


SDK_VERSION = "2.2.0"

import os
import six
#TRUSTED_CERT_FILE = pkg_resources.resource_filename(__name__, 'trusted-certs.crt')
TRUSTED_CERT_FILE = os.path.join(os.path.dirname(six.__file__), 'trusted-certs.crt')


class RESTResponse(io.IOBase):
    """
    Responses to requests can come in the form of ``RESTResponse``. These are
    thin wrappers around the socket file descriptor.
    :meth:`read()` and :meth:`close()` are implemented.
    It is important to call :meth:`close()` to return the connection
    back to the connection pool to be reused. If a connection
    is not closed by the caller it may leak memory. The object makes a
    best-effort attempt upon destruction to call :meth:`close()`,
    but it's still best to explicitly call :meth:`close()`.
    """

    def __init__(self, resp):
        # arg: A urllib3.HTTPResponse object
        self.urllib3_response = resp
        self.status = resp.status
        self.version = resp.version
        self.reason = resp.reason
        self.strict = resp.strict
        self.is_closed = False

    def __del__(self):
        # Attempt to close when ref-count goes to zero.
        self.close()

    def __exit__(self, typ, value, traceback):
        # Allow this to be used in "with" blocks.
        self.close()

    # -----------------
    # Important methods
    # -----------------
    def read(self, amt=None):
        """
        Read data off the underlying socket.

        Parameters
            amt
              Amount of data to read. Defaults to ``None``, indicating to read
              everything.

        Returns
              Data off the socket. If ``amt`` is not ``None``, at most ``amt`` bytes are returned.
              An empty string when the socket has no data.

        Raises
            ``ValueError``
              If the ``RESTResponse`` has already been closed.
        """
        if self.is_closed:
            raise ValueError('Response already closed')
        return self.urllib3_response.read(amt)

    BLOCKSIZE = 4 * 1024 * 1024 # 4MB at a time just because

    def close(self):
        """Closes the underlying socket."""

        # Double closing is harmless
        if self.is_closed:
            return

        # Read any remaining crap off the socket before releasing the
        # connection. Buffer it just in case it's huge
        while self.read(RESTResponse.BLOCKSIZE):
            pass

        # Mark as closed and release the connection (exactly once)
        self.is_closed = True
        self.urllib3_response.release_conn()

    @property
    def closed(self):
        return self.is_closed


    # ---------------------------------
    # Backwards compat for HTTPResponse
    # ---------------------------------
    def getheaders(self):
        """Returns a dictionary of the response headers."""
        return self.urllib3_response.getheaders()

    def getheader(self, name, default=None):
        """Returns a given response header."""
        return self.urllib3_response.getheader(name, default)

    # Some compat functions showed up recently in urllib3
    try:
        urllib3.HTTPResponse.flush
        urllib3.HTTPResponse.fileno
        def fileno(self):
            return self.urllib3_response.fileno()
        def flush(self):
            return self.urllib3_response.flush()
    except AttributeError:
        pass

def create_connection(address):
    host, port = address
    err = None
    for res in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            sock = socket.socket(af, socktype, proto)
            sock.connect(sa)
            return sock

        except socket.error as e:
            err = e
            if sock is not None:
                sock.close()

    if err is not None:
        raise err
    else:
        raise socket.error("getaddrinfo returns an empty list")

def json_loadb(data):
    if sys.version_info >= (3,):
        data = data.decode('utf8')
    return json.loads(data)


class RESTClientObject(object):
    def __init__(self, max_reusable_connections=8, mock_urlopen=None):
        """
        Parameters
            max_reusable_connections
                max connections to keep alive in the pool
            mock_urlopen
                an optional alternate urlopen function for testing

        This class uses ``urllib3`` to maintain a pool of connections. We attempt
        to grab an existing idle connection from the pool, otherwise we spin
        up a new connection. Once a connection is closed, it is reinserted
        into the pool (unless the pool is full).

        SSL settings:
        - Certificates validated using Dropbox-approved trusted root certs
        - TLS v1.0 (newer TLS versions are not supported by urllib3)
        - Default ciphersuites. Choosing ciphersuites is not supported by urllib3
        - Hostname verification is provided by urllib3
        """
        self.mock_urlopen = mock_urlopen
        self.pool_manager = urllib3.PoolManager(
            num_pools=4, # only a handful of hosts. api.dropbox.com, api-content.dropbox.com
            maxsize=max_reusable_connections,
            block=False,
            timeout=60.0, # long enough so datastores await doesn't get interrupted
            cert_reqs=ssl.CERT_REQUIRED,
            ca_certs=TRUSTED_CERT_FILE,
            ssl_version=ssl.PROTOCOL_TLSv1,
        )

    def request(self, method, url, post_params=None, body=None, headers=None, raw_response=False, useJSONParams=True):
        """Performs a REST request. See :meth:`RESTClient.request()` for detailed description."""

        log('>>>> [' + str(method) + '] ' + str(url))
        log_debug(
            NL_('') +
            NL_('#-1-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#') +
            NL_('#-1-# dropbox.rest.RESTClientObject.request() --  `' + str(url) + '`') +
            NL_('#-1-#') +
            NL_('#-1-#       method = ' + str(method)) +
            NL_('#-1-#          url = ' + str(url)) +
            NL_('#-1-#  post_params = ' + str(post_params)) +
            NL_('#-1-#         body = ' + str(body)) +
            NL_('#-1-#      headers = ' + str(headers)) +
            NL_('#-1-# raw_response = ' + str(raw_response)) +
            NL_('#-1-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#')
        )

        post_params = post_params or {}
        headers = headers or {}
        headers['User-Agent'] = 'OfficialDropboxPythonSDK/' + SDK_VERSION

        if post_params:
            if body:
                raise ValueError("body parameter cannot be used with post_params parameter")
            if useJSONParams:
                body = json.dumps(post_params)
                headers["Content-type"] = "application/json"
            else:
                body = params_to_urlencoded(post_params)
                headers["Content-type"] = "application/x-www-form-urlencoded"

        # Handle StringIO instances, because urllib3 doesn't.
        if hasattr(body, 'getvalue'):
            body = str(body.getvalue())
            headers["Content-Length"] = len(body)

        # Reject any headers containing newlines; the error from the server isn't pretty.
        for key, value in headers.items():
            if isinstance(value, basestring) and '\n' in value:
                raise ValueError("headers should not contain newlines (%s: %s)" %
                                 (key, value))

        log_debug(
            NL_('') +
            NL_('#-2-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#') +
            NL_('#-2-# Sending request to Dropbox endpoint `' + str(url) + '`') +
            NL_('#-2-#') +
            NL_('#-2-#  method = ' + str(method)) +
            NL_('#-2-#  body = ' + ('[[binary data]]' if 'Content-Type' in headers and headers['Content-Type'] == 'application/octet-stream' else str(body))) +
            NL_('#-2-# headers = ' + str(headers)) +
            NL_('#-2-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#')
        )

        try:
            # Grab a connection from the pool to make the request.
            # We return it to the pool when caller close() the response
            urlopen = self.mock_urlopen if self.mock_urlopen else self.pool_manager.urlopen
            r = urlopen(
                method=method,
                url=url,
                body=body,
                headers=headers,
                preload_content=False
            )
            r = RESTResponse(r) # wrap up the urllib3 response before proceeding

            log('<<<< [' + str(method) + '] ' + str(url) + ', returned with status=' + str(r.status))
            log_debug(
                NL_('') +
                NL_('#-3-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#') +
                NL_('#-3-# Back from from `' + str(method) + '` to `' + str(url) + '`') +
                NL_('#-3-#') +
                NL_('#-3-#         status = ' + str(r.status)) +
                NL_('#-3-#        version = ' + str(r.version)) +
                NL_('#-3-#         reason = ' + str(r.reason)) +
                NL_('#-3-#         strict = ' + str(r.strict)) +
                NL_('#-3-#      is_closed = ' + str(r.is_closed)) +
                NL_('#-3-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#')
            )

        except socket.error as e:
            raise RESTSocketError(url, e)
        except urllib3.exceptions.SSLError as e:
            raise RESTSocketError(url, "SSL certificate error: %s" % e)

        if r.status not in (200, 206):
            log('...bad return status: ' + str(r.status))
            raise ErrorResponse(r, r.read())

        processed_response = self.process_response(r, raw_response)

        log_debug(
            NL_('') +
            NL_('#-4-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#') +
            NL_('#-4-# processed response for `' + str(method) + '` to `' + str(url) + '` --> ') +
            NL_('#-4-#') +
            NL_('#-4-# ' + repr(processed_response)) +
            NL_('#-4-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#')
        )

        return processed_response

    def process_response(self, r, raw_response):
        if raw_response:
            return r
        else:
            s = r.read()
            try:
                resp = json_loadb(s)
            except ValueError:
                raise ErrorResponse(r, s)
            r.close()

        return resp

    def GET(self, url, headers=None, raw_response=False):
        assert type(raw_response) == bool
        return self.request("GET", url, headers=headers, raw_response=raw_response)

    def POST(self, url, params=None, headers=None, raw_response=False, useJSONParams=True):
        assert type(raw_response) == bool
        if params is None:
            params = {}

        return self.request("POST", url,
                            post_params=params, headers=headers, raw_response=raw_response, useJSONParams=useJSONParams)

    def PUT(self, url, body, headers=None, raw_response=False):
        assert type(raw_response) == bool
        return self.request("PUT", url, body=body, headers=headers, raw_response=raw_response)


class RESTClient(object):
    """
    A class with all static methods to perform JSON REST requests that is used internally
    by the Dropbox Client API. It provides just enough gear to make requests
    and get responses as JSON data (when applicable). All requests happen over SSL.
    """

    IMPL = RESTClientObject()

    @classmethod
    def request(cls, *n, **kw):
        """Perform a REST request and parse the response.

        Parameters
            method
              An HTTP method (e.g. ``'GET'`` or ``'POST'``).
            url
              The URL to make a request to.
            post_params
              A dictionary of parameters to put in the body of the request.
              This option may not be used if the body parameter is given.
            body
              The body of the request. Typically, this value will be a string.
              It may also be a file-like object. The body
              parameter may not be used with the post_params parameter.
            headers
              A dictionary of headers to send with the request.
            raw_response
              Whether to return a :class:`RESTResponse` object. Default ``False``.
              It's best enabled for requests that return large amounts of data that you
              would want to ``.read()`` incrementally rather than loading into memory. Also
              use this for calls where you need to read metadata like status or headers,
              or if the body is not JSON.

        Returns
              The JSON-decoded data from the server, unless ``raw_response`` is
              set, in which case a :class:`RESTResponse` object is returned instead.

        Raises
            :class:`ErrorResponse`
              The returned HTTP status is not 200, or the body was
              not parsed from JSON successfully.
            :class:`RESTSocketError`
              A ``socket.error`` was raised while contacting Dropbox.
        """
        return cls.IMPL.request(*n, **kw)

    @classmethod
    def GET(cls, *n, **kw):
        """Perform a GET request using :meth:`RESTClient.request()`."""
        return cls.IMPL.GET(*n, **kw)

    @classmethod
    def POST(cls, *n, **kw):
        """Perform a POST request using :meth:`RESTClient.request()`."""
        return cls.IMPL.POST(*n, **kw)

    @classmethod
    def PUT(cls, *n, **kw):
        """Perform a PUT request using :meth:`RESTClient.request()`."""
        return cls.IMPL.PUT(*n, **kw)


class RESTSocketError(socket.error):
    """A light wrapper for ``socket.error`` that adds some more information."""

    def __init__(self, host, e):
        msg = "Error connecting to \"%s\": %s" % (host, str(e))
        socket.error.__init__(self, msg)


# Dummy class for docstrings, see doco.py.
class _ErrorResponse__doc__(Exception):
    """Exception raised when :class:`DropboxClient` exeriences a problem.

    For example, this is raised when the server returns an unexpected
    non-200 HTTP response.
    """

    _status__doc__ = "HTTP response status (an int)."
    _reason__doc__ = "HTTP response reason (a string)."
    _headers__doc__ = "HTTP response headers (a list of (header, value) tuples)."
    _body__doc__ = "HTTP response body (string or JSON dict)."
    _error_msg__doc__ = "Error message for developer (optional)."
    _user_error_msg__doc__ = "Error message for end user (optional)."


class ErrorResponse(Exception):
    """
    Raised by :meth:`RESTClient.request()` for requests that:

      - Return a non-200 HTTP response, or
      - Have a non-JSON response body, or
      - Have a malformed/missing header in the response.

    Most errors that Dropbox returns will have an error field that is unpacked and
    placed on the ErrorResponse exception. In some situations, a user_error field
    will also come back. Messages under user_error are worth showing to an end-user
    of your app, while other errors are likely only useful for you as the developer.
    """

    def __init__(self, http_resp, body):
        """
        Parameters
            http_resp
                      The :class:`RESTResponse` which errored
            body
                      Body of the :class:`RESTResponse`.
                      The reason we can't simply call ``http_resp.read()`` to
                      get the body, is that ``read()`` is not idempotent.
                      Since it can't be called more than once,
                      we have to pass the string body in separately
        """
        self.status = http_resp.status
        self.reason = http_resp.reason
        self.body = body
        self.headers = http_resp.getheaders()
        self.headerContentType = http_resp.getheader('Content-Type', '')
        self.headerRetryAfter = http_resp.getheader('Retry-After', '')
        http_resp.close() # won't need this connection anymore

        try:
            self.jsonBody = json_loadb(self.body)
        except ValueError:
            self.jsonBody = {}

        self.serverUserMessage   = self.jsonBody.get('user_message')
        self.serverError         = self.jsonBody.get('error')
        self.serverErrorSummary  = self.jsonBody.get('error_summary')
        self.rateLimitReason     = self.jsonBody.get('reason')
        self.rateLimitRetryAfter = self.jsonBody.get('retry_after')

        # LEGACY
        self.user_error_msg = self.serverUserMessage

    def __str__(self):

        msg = 'No details were provided for error.'
        if self.status == 400:
            msg = '[Bad input parameter] %.1000r' % (self.body)
        elif self.status == 401:
            # Bad or expired token

            authErrorMessages = {
                'invalid_access_token': 'The access token is invalid.  Either it is expired or it has been revoked.',
                'invalid_select_user': 'The user specified in \'Dropbox-API-Select-User\' is no longer on the team.',
                'invalid_select_admin': 'The user specified in \'Dropbox-API-Select-Admin\' is not a Dropbox Business team admin.',
                'user_suspended': 'The user has been suspended.'
            }

            authError = self.serverError.get('.tag')
            msg = authErrorMessages.get(authError)
            if not msg:
                if authError:
                    msg = 'Bad or expired token (' + authError + ')'
                else:
                    msg = 'Bad or expired token. (no further information available)'
        elif self.status == 409:
            if 'json' in self.headerContentType.lower():
                if self.serverUserMessage:
                    msg = self.serverUserMessage
                else:
                    msg = "%.1000r" % (self.body)
            else:
                msg = "%.1000r" % (self.body)
        elif self.status == 429:
            if 'json' in self.headerContentType.lower():
                msg = self.rateLimitReason + ' ... Retry after ' + str(self.rateLimitRetryAfter) + ' seconds'
            else:
                msg = self.body + ' ... Retry after ' + str(self.headerRetryAfter) + ' seconds'
        elif self.status in range(500, 599):
            msg = 'An error occurred on the Dropbox servers. Check status.dropbox.com for announcements about Dropbox service issues.'
        elif self.body:
                msg = "%.1000r" % (self.body)

        return "[%d] %s" % (self.status, msg)


def params_to_urlencoded(params):
    """
    Returns a application/x-www-form-urlencoded 'str' representing the key/value pairs in 'params'.
    
    Keys are values are str()'d before calling urllib.urlencode, with the exception of unicode
    objects which are utf8-encoded.
    """
    def encode(o):
        if isinstance(o, unicode):
            return o.encode('utf8')
        else:
            return str(o)
    utf8_params = {encode(k): encode(v) for k, v in params.iteritems()}
    return urllib.urlencode(utf8_params)
