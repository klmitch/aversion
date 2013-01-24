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


class TypeRule(object):
    def __init__(self, ctype, version):
        self.ctype = ctype
        self.version = version

    def __call__(self, params):
        ctype = (self.ctype % params) if self.ctype else params['_']
        version = (self.version % params) if self.version else None
        return ctype, version


class AVersion(object):
    @staticmethod
    def _parse_type(ctype, typespec):
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

    def __init__(self, loader, global_conf, **local_conf):
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
                # A mapping between URI prefixes and versions
                uris[key[4:]] = value
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
