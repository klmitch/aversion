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

import re


SLASH_RE = re.compile('/+')


class TypeRule(object):
    """
    Represents a basic rule for content type interpretation.
    """

    def __init__(self, ctype, version):
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
        """

        self.ctype = ctype
        self.version = version

    def __call__(self, params):
        """
        Evaluate a TypeRule.

        :param params: A dictionary of content type parameters.  This
                       dictionary must contain the key '_', which must
                       be the content type being passed in.

        :returns: A tuple of the final content type and version.
        """

        ctype = (self.ctype % params) if self.ctype else params['_']
        version = (self.version % params) if self.version else None
        return ctype, version


class AVersion(object):
    """
    A composite application for PasteDeploy-based WSGI stacks which
    selects the version of an API and the requested content type based
    on criteria including URI prefix and suffix and content type
    parameters.
    """

    @staticmethod
    def _parse_type(ctype, typespec):
        """
        Parse a content type rule.  Unlike the other rules, content
        type rules are more complex, since both selected content type
        and API version must be expressed by one rule.  The rule is
        split on whitespace, then the components beginning with
        "type:" and "version:" are selected; in both cases, the text
        following the ":" character will be treated as a format
        string, which will be formatted using a content parameter
        dictionary.

        :param ctype: The content type the rule is for.
        :param typespec: The rule text, described above.

        :returns: An instance of TypeRule.
        """

        params = {}
        for token in typespec.split():
            tok_type, _sep, tok_val = token.partition(':')

            # Validate the token type
            if not tok_val:
                LOG.warn("%s: Invalid type token %r" % (ctype, token))
                continue
            elif tok_type not in ('type', 'version'):
                LOG.warn("%s: Unrecognized token type %r" % (ctype, tok_type))
                continue
            elif tok_type in params:
                LOG.warn("%s: Duplicate value for token type %r" %
                         (ctype, tok_type))
                # Allow the overwrite

            # Validate the token value
            if (len(tok_val) <= 2 or tok_val[0] not in ('"', "'") or
                tok_val[0] != tok_val[-1]):
                LOG.warn("Unrecognized token value %r" % tok_val)

            params[tok_type] = tok_val[1:-1]

        return TypeRule(ctype=params.get('type'),
                        version=params.get('version'))

    @staticmethod
    def _uri_normalize(uri):
        """
        Normalize a URI.  Multiple slashes are collapsed into a single
        '/', a leading '/' is added, and trailing slashes are removed.

        :param uri: The URI to normalize.

        :returns: The normalized URI.
        """

        return '/' + SLASH_RE.sub('/', uri).strip('/')

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
        self.version_app = None
        self.versions = {}
        uris = {}
        self.types = {}
        self.formats = {}
        for key, value in local_conf.items():
            if key == 'version':
                # The version application--what we call if no version
                # is specified
                version_app = loader.get_app(value)
            elif key.startswith('version.'):
                # The application for a given version
                self.versions[key[8:]] = loader.get_app(value)
            elif key.startswith('uri.'):
                # A mapping between URI prefixes and versions; note
                # that the URI is normalized
                uris[self._uri_normalize(key[4:])] = value
            elif key.startswith('type.'):
                # A mapping between a passed-in content type and the
                # desired version and final content type
                types[key[5:]] = self._parse_type(key[5:], value)
            elif key[0] == '.':
                # A mapping between a file extension and the desired
                # content type
                formats[key] = value

        # We want to search URIs in the correct order
        self.uris = sorted(uris.items(), key=lambda x: len(x[0]),
                           reverse=True)
