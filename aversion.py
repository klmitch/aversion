# Copyright 2013 Rackspace
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import copy
import logging
import re

import webob.dec
import webob.exc


LOG = logging.getLogger('aversion')

SLASH_RE = re.compile('/+')


def quoted_split(string, sep, quotes='"'):
    """
    Split a string on the given separation character, but respecting
    double-quoted sections of the string.  Returns an iterator.

    :param string: The string to split.
    :param sep: The character separating sections of the string.
    :param quotes: A string specifying all legal quote characters.

    :returns: An iterator which will iterate over each element of the
              string separated by the designated separator.
    """

    # Initialize the algorithm
    start = None
    escape = False
    quote = False

    # Walk through the string
    for i, c in enumerate(string):
        # Save the start index
        if start is None:
            start = i

        # Handle escape sequences
        if escape:
            escape = False

        # Handle quoted strings
        elif quote:
            if c == '\\':
                escape = True
            elif c == quote:
                quote = False

        # Handle the separator
        elif c == sep:
            yield string[start:i]
            start = None

        # Handle quotes
        elif c in quotes:
            quote = c

    # Yield the last part
    if start is not None:
        yield string[start:]


def unquote(quoted):
    """
    Unquotes a value, as drawn from a header.

    Note: This does not use the real unquoting algorithm, but what
    browsers are actually using for quoting.  Internet Explorer (and
    probably some other browsers) fails to apply the proper quoting
    algorithm.  Thus, the algorithm used is simply to remove the
    quotes.

    :param quoted: The quoted string.

    :returns: The string with the quoting removed.
    """

    if quoted[:1] == '"' and quoted[-1:] == '"':
        return quoted[1:-1]
    return quoted


def parse_ctype(ctype):
    """
    Parse a content type.

    :param ctype: The content type, with corresponding parameters.

    :returns: A tuple of the content type and a dictionary containing
              the content type parameters.  The content type will
              additionally be available in the dictionary as the '_'
              key.
    """

    result_ctype = None
    result = {}
    for part in quoted_split(ctype, ';'):
        # Extract the content type first
        if result_ctype is None:
            result_ctype = part
            result['_'] = part
            continue

        # OK, we have a 'key' or 'key=value' to handle; figure it
        # out...
        equal = part.find('=')
        if equal > 0 and part.find('"', 0, equal) < 0:
            result[part[:equal]] = unquote(part[equal + 1:])
        else:
            # If equal > 0 but it's preceded by a ", it's seriously
            # messed up, but go ahead and be liberal...
            result[part] = True

    # If we failed to parse a content type out, return an empty
    # content type
    if result_ctype is None:
        result_ctype = ''

    return result_ctype, result


def _match_mask(mask, ctype):
    """
    Determine if a content type mask matches a given content type.

    :param mask: The content type mask, taken from the Accept
                 header.
    :param ctype: The content type to match to the mask.
    """

    # Handle the simple cases first
    if '*' not in mask:
        return ctype == mask
    elif mask == '*/*':
        return True
    elif not mask.endswith('/*'):
        return False

    mask_major = mask[:-2]
    ctype_major = ctype.split('/', 1)[0]
    return ctype_major == mask_major


def best_match(requested, allowed):
    """
    Determine the best content type to use for the request.

    :param ctypes: A list of the available content types.

    :returns: A tuple of the best match content type and the
              parameters for that content type.
    """

    requested = [parse_ctype(ctype) for ctype in quoted_split(requested, ',')]

    best_q = -1
    best_ctype = ''
    best_params = {}
    best_match = '*/*'

    # Walk the list of content types
    for ctype in allowed:
        # Compare to the accept list
        for ctype_mask, params in requested:
            try:
                q = float(params.get('q', 1.0))
            except ValueError:
                # Bad quality value
                continue

            if q < best_q:
                # Not any better
                continue
            elif best_q == q:
                # Base on the best match
                if best_match.count('*') <= ctype_mask.count('*'):
                    continue

            # OK, see if we have a match
            if _match_mask(ctype_mask, ctype):
                best_q = q
                best_ctype = ctype
                best_params = params
                best_match = ctype_mask

    # Return the best match
    return best_ctype, best_params


class TypeRule(object):
    """
    Represents a basic rule for content type interpretation.
    """

    def __init__(self, ctype, version, params):
        """
        Initialize a TypeRule object.

        :param ctype: The resultant content type.  If None, the
                      existing content type will be used; otherwise,
                      the content type will be formed by formatting
                      the string, using the parameter dictionary.
        :param version: The resultant version.  If None, no version
                        will be returned; otherwise, the version will
                        be formed by formatting the string, using the
                        parameter dictionary.
        :param params: Extra parameters.  These are unused by
                       AVersion, but are included in the configuration
                       made available through the 'aversion.config'
                       WSGI environment variable.
        """

        self.ctype = ctype
        self.version = version
        self.params = params

    def __call__(self, params):
        """
        Evaluate a TypeRule.

        :param params: A dictionary of content type parameters.  This
                       dictionary must contain the key '_', which must
                       be the content type being passed in.

        :returns: A tuple of the final content type and version.
        """

        # Determine the desired content type
        try:
            ctype = (self.ctype % params) if self.ctype else params['_']
        except KeyError:
            # Treat it as undefined rather than defaulted
            ctype = None

        # Determine the desired version
        try:
            version = (self.version % params) if self.version else None
        except KeyError:
            version = None

        return ctype, version


class Result(object):
    """
    Helper class to maintain results for the version and content type
    selection algorithm.
    """

    def __init__(self):
        """
        Initialize a Result.
        """

        self.version = None
        self.ctype = None
        self.orig_ctype = None

    def __nonzero__(self):
        """
        Return True only when the Result object is completely
        populated.
        """

        return self.version is not None and self.ctype is not None

    def set_version(self, version):
        """
        Set the selected version.  Will not override the value of the
        version if that has already been determined.

        :param version: The version string to set.
        """

        if self.version is None:
            self.version = version

    def set_ctype(self, ctype, orig_ctype=None):
        """
        Set the selected content type.  Will not override the value of
        the content type if that has already been determined.

        :param ctype: The content type string to set.

        :param orig_ctype: The original content type, as found in the
                           configuration.
        """

        if self.ctype is None:
            self.ctype = ctype
            self.orig_ctype = orig_ctype


def _set_key(log_prefix, result_dict, key, value, desc="parameter"):
    """
    Helper to set a key value in a dictionary.  This function issues a
    warning if the key has already been set, and issues a warning and
    returns without setting the value if the value is not surrounded
    by parentheses.  This is used to eliminate duplicated code from
    the rule parsers below.

    :param log_prefix: A prefix to use in log messages.  This should
                       be the configuration key.
    :param result_dict: A dictionary of results, into which the key
                        and value should be inserted.
    :param key: The dictionary key to insert.
    :param value: The value to insert into the dictionary.
    :param desc: A description of what the dictionary is.  This is
                 used in log messages help the user understand what
                 the log message is referring to.  By default, this
                 description is "parameter", indicating that entries
                 in the dictionary are parameters of something;
                 however, _parse_type_rule() also uses "token type" to
                 help identify its more complex tokens.
    """

    if key in result_dict:
        LOG.warn("%s: Duplicate value for %s %r" %
                 (log_prefix, desc, key))
        # Allow the overwrite

    # Demand the value be quoted
    if len(value) <= 2 or value[0] not in ('"', "'") or value[0] != value[-1]:
        LOG.warn("%s: Invalid value %r for %s %r" %
                 (log_prefix, value, desc, key))
        return

    # Save the value
    result_dict[key] = value[1:-1]


def _parse_version_rule(loader, version, verspec):
    """
    Parse a version rule.  The first token is the name of the
    application implementing that API version.  The remaining tokens
    are key="quoted value" pairs that specify parameters; these
    parameters are ignored by AVersion, but may be used by the
    application.

    :param loader: An object with a get_app() method, which will be
                   used to load the actual applications.
    :param version: The version name.
    :param verspec: The version text, described above.

    :returns: A dictionary of three keys: "app" is the application;
              "name" is the version identification string; and
              "params" is a dictionary of parameters.
    """

    result = dict(name=version, params={})
    for token in quoted_split(verspec, ' ', quotes='"\''):
        if not token:
            continue

        # Convert the application
        if 'app' not in result:
            result['app'] = loader.get_app(token)
            continue

        # What remains is key="quoted value" pairs...
        key, _eq, value = token.partition('=')

        # Set the parameter key
        _set_key('version.%s' % version, result['params'], key, value)

    # Make sure we have an application
    if 'app' not in result:
        raise ImportError("Cannot load application for version %r" % version)

    return result


def _parse_alias_rule(alias, alias_spec):
    """
    Parse an alias rule.  The first token is the canonical name of the
    version.  The remaining tokens are key="quoted value" pairs that
    specify parameters; these parameters are ignored by AVersion, but
    may be used by the application.

    :param alias: The alias name.
    :param alias_spec: The alias text, described above.

    :returns: A dictionary of three keys: "alias" is the alias name;
              "version" is the canonical version identification
              string; and "params" is a dictionary of parameters.
    """

    result = dict(alias=alias, params={})
    for token in quoted_split(alias_spec, ' ', quotes='"\''):
        if not token:
            continue

        # Suck out the canonical version name
        if 'version' not in result:
            result['version'] = token
            continue

        # What remains is key="quoted value" pairs...
        key, _eq, value = token.partition('=')

        # Set the parameter key
        _set_key('alias.%s' % alias, result['params'], key, value)

    # Make sure we have a canonical version
    if 'version' not in result:
        raise KeyError("Cannot determine canonical version for alias %r" %
                       alias)

    return result


def _parse_type_rule(ctype, typespec):
    """
    Parse a content type rule.  Unlike the other rules, content type
    rules are more complex, since both selected content type and API
    version must be expressed by one rule.  The rule is split on
    whitespace, then the components beginning with "type:" and
    "version:" are selected; in both cases, the text following the ":"
    character will be treated as a format string, which will be
    formatted using a content parameter dictionary.  Components
    beginning with "param:" specify key="quoted value" pairs that
    specify parameters; these parameters are ignored by AVersion, but
    may be used by the application.

    :param ctype: The content type the rule is for.
    :param typespec: The rule text, described above.

    :returns: An instance of TypeRule.
    """

    params = {'param': {}}
    for token in quoted_split(typespec, ' ', quotes='"\''):
        if not token:
            continue

        tok_type, _sep, tok_val = token.partition(':')

        # Validate the token type
        if not tok_val:
            LOG.warn("%s: Invalid type token %r" % (ctype, token))
            continue
        elif tok_type not in ('type', 'version', 'param'):
            LOG.warn("%s: Unrecognized token type %r" % (ctype, tok_type))
            continue

        # Intercept 'param' clauses
        if tok_type == 'param':
            key, _eq, value = tok_val.partition('=')

            # Set the parameter key
            _set_key('type.%s' % ctype, params['param'], key, value)
            continue

        # Set the token value
        _set_key('type.%s' % ctype, params, tok_type, tok_val,
                 desc="token type")

    return TypeRule(ctype=params.get('type'),
                    version=params.get('version'),
                    params=params['param'])


def _uri_normalize(uri):
    """
    Normalize a URI.  Multiple slashes are collapsed into a single
    '/', a leading '/' is added, and trailing slashes are removed.

    :param uri: The URI to normalize.

    :returns: The normalized URI.
    """

    return '/' + SLASH_RE.sub('/', uri).strip('/')


class AVersion(object):
    """
    A composite application for PasteDeploy-based WSGI stacks which
    selects the version of an API and the requested content type based
    on criteria including URI prefix and suffix and content type
    parameters.
    """

    def __init__(self, loader, global_conf, **local_conf):
        """
        Initialize an AVersion object.

        :param loader: An object with a get_app() method, which will
                       be used to load the actual applications.
        :param global_conf: The global configuration.  Ignored.
        :param local_conf: The configuration for this application.
                           See the README.rst for a full discussion of
                           the defined keys and the meaning of their
                           values.
        """

        # Process the configuration
        self.overwrite_headers = True
        self.version_app = None
        self.versions = {}
        self.aliases = {}
        uris = {}
        self.types = {}
        self.formats = {}
        for key, value in local_conf.items():
            if key == 'version':
                # The version application--what we call if no version
                # is specified
                self.version_app = loader.get_app(value)
            elif key == 'overwrite_headers':
                # Alter whether or not we overwrite the headers
                value = value.lower()
                if value in ('true', 't', 'on', 'yes', 'enable'):
                    self.overwrite_headers = True
                elif value in ('false', 'f', 'off', 'no', 'disable'):
                    self.overwrite_headers = False
                else:
                    try:
                        self.overwrite_headers = bool(int(value))
                    except ValueError:
                        LOG.warn("Unrecognized value %r for configuration "
                                 "key 'overwrite_headers'" % value)
            elif key.startswith('version.'):
                # The application for a given version
                self.versions[key[8:]] = _parse_version_rule(loader, key[8:],
                                                             value)
            elif key.startswith('alias.'):
                # An alias for a given version
                self.aliases[key[6:]] = _parse_alias_rule(key[6:], value)
            elif key.startswith('uri.'):
                # A mapping between URI prefixes and versions; note
                # that the URI is normalized
                uris[_uri_normalize(key[4:])] = value
            elif key.startswith('type.'):
                # A mapping between a passed-in content type and the
                # desired version and final content type
                self.types[key[5:]] = _parse_type_rule(key[5:], value)
            elif key[0] == '.':
                # A mapping between a file extension and the desired
                # content type
                self.formats[key] = value

        # We want to search URIs in the correct order
        self.uris = sorted(uris.items(), key=lambda x: len(x[0]),
                           reverse=True)

        # The versioning application may find it useful to have some
        # introspection on the AVersion configuration, so build up a
        # couple of data structures we can add to requests.  We start
        # with adding URI prefixes to the version descriptors...
        for prefix, version in uris.items():
            if version not in self.versions:
                continue

            # Add the prefixes to the version descriptor
            self.versions[version].setdefault('prefixes', [])
            self.versions[version]['prefixes'].append(prefix)

        # Next, set up a list of type information
        types = dict((ctype, dict(name=ctype, params=rule.params))
                     for ctype, rule in self.types.items())

        # Add in information about the formats
        for suffix, ctype in self.formats.items():
            types.setdefault(ctype, dict(name=ctype, params={}))
            types[ctype].setdefault('suffixes', [])
            types[ctype]['suffixes'].append(suffix)

        # Now, build the config dictionary tree we will pass to
        # requests
        self.config = dict(
            versions=self.versions,
            aliases=self.aliases,
            types=types,
        )

    @webob.dec.wsgify
    def __call__(self, request):
        """
        Process a WSGI request, selecting the appropriate application
        to pass the request to.  In addition, if the desired content
        type can be determined, the Accept header will be altered to
        match.

        :param request: The Request object provided by WebOb.
        """

        # Process the request; broken out for easy override and
        # testing
        result = self._process(request)

        # Add the config to the environment; we use a deep copy to
        # avoid accidental overwrite of the data
        request.environ['aversion.config'] = copy.deepcopy(self.config)

        # Set the Accept header
        if result.ctype:
            request.environ['aversion.response_type'] = result.ctype
            request.environ['aversion.orig_response_type'] = result.orig_ctype
            request.environ['aversion.accept'] = request.headers.get('accept')
            if self.overwrite_headers:
                request.headers['accept'] = '%s;q=1.0' % result.ctype

        # Determine the requested version; allows mapping through
        # aliases to a canonical value
        if result.version in self.aliases:
            version = self.aliases[result.version]['version']
        else:
            version = result.version

        # Select the correct application
        try:
            app = self.versions[version]['app']
            request.environ['aversion.version'] = version
        except KeyError:
            app = self.version_app
            request.environ['aversion.version'] = None

        if app:
            return request.get_response(app)
        else:
            return webob.exc.HTTPInternalServerError(
                explanation='Cannot determine application to serve request')

    def _process(self, request, result=None):
        """
        Process the rules for the request.

        :param request: The Request object provided by WebOb.
        :param result: The Result object to store the results in.  If
                       None, one will be allocated.

        :returns: A Result object, containing the selected version and
                  content type.
        """

        # Allocate a result and process all the rules
        result = result if result is not None else Result()
        self._proc_uri(request, result)
        self._proc_ctype_header(request, result)
        self._proc_accept_header(request, result)

        return result

    def _proc_uri(self, request, result):
        """
        Process the URI rules for the request.  Both the desired API
        version and desired content type can be determined from those
        rules.

        :param request: The Request object provided by WebOb.
        :param result: The Result object to store the results in.
        """

        if result:
            # Result has already been fully determined
            return

        # First, determine the version based on the URI prefix
        for prefix, version in self.uris:
            if (request.path_info == prefix or
                    request.path_info.startswith(prefix + '/')):
                result.set_version(version)

                # Update the request particulars
                request.script_name += prefix
                request.path_info = request.path_info[len(prefix):]
                if not request.path_info:
                    request.path_info = '/'
                break

        # Next, determine the content type based on the URI suffix
        for format, ctype in self.formats.items():
            if request.path_info.endswith(format):
                result.set_ctype(ctype)

                # Update the request particulars
                request.path_info = request.path_info[:-len(format)]
                break

    def _proc_ctype_header(self, request, result):
        """
        Process the Content-Type header rules for the request.  Only
        the desired API version can be determined from those rules.

        :param request: The Request object provided by WebOb.
        :param result: The Result object to store the results in.
        """

        if result:
            # Result has already been fully determined
            return

        try:
            ctype = request.headers['content-type']
        except KeyError:
            # No content-type header to examine
            return

        # Parse the content type
        ctype, params = parse_ctype(ctype)

        # Is it a recognized content type?
        if ctype not in self.types:
            return

        # Get the mapped ctype and version
        mapped_ctype, mapped_version = self.types[ctype](params)

        # Update the content type header and set the version
        if mapped_ctype:
            request.environ['aversion.request_type'] = mapped_ctype
            request.environ['aversion.orig_request_type'] = ctype
            request.environ['aversion.content-type'] = \
                request.headers['content-type']
            if self.overwrite_headers:
                request.headers['content-type'] = mapped_ctype
        if mapped_version:
            result.set_version(mapped_version)

    def _proc_accept_header(self, request, result):
        """
        Process the Accept header rules for the request.  Both the
        desired API version and content type can be determined from
        those rules.

        :param request: The Request object provided by WebOb.
        :param result: The Result object to store the results in.
        """

        if result:
            # Result has already been fully determined
            return

        try:
            accept = request.headers['accept']
        except KeyError:
            # No Accept header to examine
            return

        # Obtain the best-match content type and its parameters
        ctype, params = best_match(accept, self.types.keys())

        # Is it a recognized content type?
        if ctype not in self.types:
            return

        # Get the mapped ctype and version
        mapped_ctype, mapped_version = self.types[ctype](params)

        # Set the content type and version
        if mapped_ctype:
            result.set_ctype(mapped_ctype, ctype)
        if mapped_version:
            result.set_version(mapped_version)
