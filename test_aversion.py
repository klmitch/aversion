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

import collections

import mock
import unittest2
import webob
import webob.exc

import aversion


FakeTypeRule = collections.namedtuple('FakeTypeRule',
                                      ['ctype', 'version', 'params'])


class QuotedSplitTest(unittest2.TestCase):
    def test_simple_comma(self):
        result = list(aversion.quoted_split(",value1,value2 , value 3 ,", ','))

        self.assertEqual(result,
                         ['', 'value1', 'value2 ', ' value 3 '])

    def test_complex_comma(self):
        result = list(aversion.quoted_split(
            'application/example;q=1;version="2,3\\"",'
            'application/example;q=0.5;version="3;4"', ','))

        self.assertEqual(result, [
            'application/example;q=1;version="2,3\\""',
            'application/example;q=0.5;version="3;4"',
        ])

    def test_simple_semicolon(self):
        result = list(aversion.quoted_split(";value1;value2 ; value 3 ;", ';'))

        self.assertEqual(result,
                         ['', 'value1', 'value2 ', ' value 3 '])

    def test_complex_semicolon(self):
        result = list(aversion.quoted_split(
            'application/example;q=1;version="2;3\\""', ';'))

        self.assertEqual(result, [
            'application/example',
            'q=1',
            'version="2;3\\""',
        ])


class UnquoteTest(unittest2.TestCase):
    def test_unquote_noquotes(self):
        result = aversion.unquote('test')

        self.assertEqual(result, 'test')

    def test_unquote_empty(self):
        result = aversion.unquote('')

        self.assertEqual(result, '')

    def test_unquote_onequote(self):
        result = aversion.unquote('"')

        self.assertEqual(result, '')

    def test_unquote_twoquote(self):
        result = aversion.unquote('""')

        self.assertEqual(result, '')

    def test_unquote_quoted(self):
        result = aversion.unquote('"test"')

        self.assertEqual(result, 'test')

    def test_unquote_quoted_embedded(self):
        result = aversion.unquote('"te"st"')

        self.assertEqual(result, 'te"st')


class ParseCtypeTest(unittest2.TestCase):
    def test_parse_ctype(self):
        ctype = 'application/example;a;b=;c=foo;d="bar";e"=baz"'
        res_ctype, res_params = aversion.parse_ctype(ctype)

        self.assertEqual(res_ctype, 'application/example')
        self.assertEqual(res_params, {
            'a': True,
            'b': '',
            'c': 'foo',
            'd': 'bar',
            'e"=baz"': True,
            '_': 'application/example',
        })

    def test_none(self):
        res_ctype, res_params = aversion.parse_ctype('')

        self.assertEqual(res_ctype, '')
        self.assertEqual(res_params, {})


class MatchMaskTest(unittest2.TestCase):
    def test_equal(self):
        self.assertTrue(aversion._match_mask('a/e', 'a/e'))

    def test_notequal(self):
        self.assertFalse(aversion._match_mask('a/e', 'e/a'))

    def test_starslashstar(self):
        self.assertTrue(aversion._match_mask('*/*', 'a/e'))
        self.assertTrue(aversion._match_mask('*/*', 'e/a'))

    def test_starslashother(self):
        self.assertFalse(aversion._match_mask('*/e', 'a/e'))
        self.assertFalse(aversion._match_mask('*/e', 'e/a'))

    def test_otherslashstar_match(self):
        self.assertTrue(aversion._match_mask('a/*', 'a/e'))
        self.assertTrue(aversion._match_mask('e/*', 'e/a'))

    def test_otherslashstar_mismatch(self):
        self.assertFalse(aversion._match_mask('a/*', 'e/a'))
        self.assertFalse(aversion._match_mask('e/*', 'a/e'))


class BestMatchTest(unittest2.TestCase):
    def test_empty(self):
        res_ctype, res_params = aversion.best_match('', ['a/a', 'a/b', 'a/c'])

        self.assertEqual(res_ctype, '')
        self.assertEqual(res_params, {})

    def test_better_fixed_q(self):
        requested = '*/*;q=0.7,a/*;q=0.7,a/c;q=0.7'
        allowed = ['a/a', 'a/b', 'a/c']
        res_ctype, res_params = aversion.best_match(requested, allowed)

        self.assertEqual(res_ctype, 'a/c')
        self.assertEqual(res_params, dict(_='a/c', q='0.7'))

    def test_better_incr_q(self):
        requested = 'a/a;q=0.3,a/b;q=0.5,a/c;q=0.7'
        allowed = ['a/a', 'a/b', 'a/c']
        res_ctype, res_params = aversion.best_match(requested, allowed)

        self.assertEqual(res_ctype, 'a/c')
        self.assertEqual(res_params, dict(_='a/c', q='0.7'))

    def test_better_decr_q(self):
        requested = 'a/a;q=0.7,a/b;q=0.5,a/c;q=0.3'
        allowed = ['a/a', 'a/b', 'a/c']
        res_ctype, res_params = aversion.best_match(requested, allowed)

        self.assertEqual(res_ctype, 'a/a')
        self.assertEqual(res_params, dict(_='a/a', q='0.7'))

    def test_bad_q(self):
        requested = 'a/a;q=spam'
        allowed = ['a/a', 'a/b', 'a/c']
        res_ctype, res_params = aversion.best_match(requested, allowed)

        self.assertEqual(res_ctype, '')
        self.assertEqual(res_params, {})


class TypeRuleTest(unittest2.TestCase):
    def test_init(self):
        tr = aversion.TypeRule('ctype', 'version', 'params')

        self.assertEqual(tr.ctype, 'ctype')
        self.assertEqual(tr.version, 'version')
        self.assertEqual(tr.params, 'params')

    def test_call_fixed(self):
        tr = aversion.TypeRule('ctype', 'version', None)

        ctype, version = tr({})

        self.assertEqual(ctype, 'ctype')
        self.assertEqual(version, 'version')

    def test_call_subs(self):
        tr = aversion.TypeRule('ctype:%(ctype)s', 'version:%(version)s', None)

        ctype, version = tr(dict(ctype='epytc', version='noisrev'))

        self.assertEqual(ctype, 'ctype:epytc')
        self.assertEqual(version, 'version:noisrev')

    def test_call_defaults(self):
        tr = aversion.TypeRule(None, None, None)

        ctype, version = tr(dict(_='ctype/epytc'))

        self.assertEqual(ctype, 'ctype/epytc')
        self.assertEqual(version, None)

    def test_call_badsubs(self):
        tr = aversion.TypeRule('ctype:%(ctype)s', 'version:%(version)s', None)

        ctype, version = tr({})

        self.assertEqual(ctype, None)
        self.assertEqual(version, None)


class ResultTest(unittest2.TestCase):
    def test_init(self):
        res = aversion.Result()

        self.assertEqual(res.version, None)
        self.assertEqual(res.ctype, None)
        self.assertEqual(res.orig_ctype, None)

    def test_nonzero(self):
        res = aversion.Result()

        self.assertFalse(res)

        res.version = 'version'

        self.assertFalse(res)

        res.version = None
        res.ctype = 'ctype'

        self.assertFalse(res)

        res.version = 'version'

        self.assertTrue(res)

    def test_set_version_unset(self):
        res = aversion.Result()

        res.set_version('version')

        self.assertEqual(res.version, 'version')

    def test_set_version_set(self):
        res = aversion.Result()
        res.version = 'version'

        res.set_version('noisrev')

        self.assertEqual(res.version, 'version')

    def test_set_ctype_unset(self):
        res = aversion.Result()

        res.set_ctype('ctype')

        self.assertEqual(res.ctype, 'ctype')
        self.assertEqual(res.orig_ctype, None)

    def test_set_ctype_orig_unset(self):
        res = aversion.Result()

        res.set_ctype('ctype', 'orig')

        self.assertEqual(res.ctype, 'ctype')
        self.assertEqual(res.orig_ctype, 'orig')

    def test_set_ctype_set(self):
        res = aversion.Result()
        res.ctype = 'ctype'
        res.orig_ctype = 'orig'

        res.set_ctype('epytc', 'giro')

        self.assertEqual(res.ctype, 'ctype')
        self.assertEqual(res.orig_ctype, 'orig')


class SetKeyTest(unittest2.TestCase):
    @mock.patch.object(aversion.LOG, 'warn')
    def test_duplicate(self, mock_warn):
        result = dict(foo='one')
        aversion._set_key("pfx", result, 'foo', '"two"', 'bar')

        self.assertEqual(result, dict(foo='two'))
        mock_warn.assert_called_once_with(
            "pfx: Duplicate value for bar 'foo'")

    @mock.patch.object(aversion.LOG, 'warn')
    def test_unquoted(self, mock_warn):
        result = {}
        aversion._set_key("pfx", result, 'foo', 'one', 'bar')

        self.assertEqual(result, {})
        mock_warn.assert_called_once_with(
            "pfx: Invalid value 'one' for bar 'foo'")

    @mock.patch.object(aversion.LOG, 'warn')
    def test_noerror(self, mock_warn):
        result = {}
        aversion._set_key("pfx", result, 'foo', '"one"', 'bar')

        self.assertEqual(result, dict(foo='one'))
        self.assertFalse(mock_warn.called)


class ParseVersionRuleTest(unittest2.TestCase):
    @mock.patch.object(aversion.LOG, 'warn')
    def test_invalid_rule(self, mock_warn):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})

        self.assertRaises(ImportError, aversion._parse_version_rule, loader,
                          'v1', '')
        self.assertFalse(loader.get_app.called)
        self.assertFalse(mock_warn.called)

    @mock.patch.object(aversion.LOG, 'warn')
    def test_no_params(self, mock_warn):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})

        result = aversion._parse_version_rule(loader, 'v1', 'api_v1')

        self.assertEqual(result, dict(app='api_v1', name='v1', params={}))
        loader.get_app.assert_called_once_with('api_v1')
        self.assertFalse(mock_warn.called)

    @mock.patch.object(aversion.LOG, 'warn')
    def test_bad_parameter(self, mock_warn):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})

        result = aversion._parse_version_rule(loader, 'v1',
                                              'api_v1 foo=one')

        self.assertEqual(result, dict(app='api_v1', name='v1', params={}))
        loader.get_app.assert_called_once_with('api_v1')
        mock_warn.assert_called_once_with(
            "version.v1: Invalid value 'one' for parameter 'foo'")

    @mock.patch.object(aversion.LOG, 'warn')
    def test_full_parse(self, mock_warn):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})

        result = aversion._parse_version_rule(loader, 'v1',
                                              'api_v1 foo="one"  bar="two"')

        self.assertEqual(result, dict(
            app='api_v1',
            name='v1',
            params=dict(foo='one', bar='two'),
        ))
        loader.get_app.assert_called_once_with('api_v1')
        self.assertFalse(mock_warn.called)

    @mock.patch.object(aversion.LOG, 'warn')
    def test_duplicate_parameter(self, mock_warn):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})

        result = aversion._parse_version_rule(loader, 'v1',
                                              'api_v1 foo="one" foo="two"')

        self.assertEqual(result, dict(
            app='api_v1',
            name='v1',
            params=dict(foo='two'),
        ))
        loader.get_app.assert_called_once_with('api_v1')
        mock_warn.assert_called_once_with(
            "version.v1: Duplicate value for parameter 'foo'")


class ParseAliasRuleTest(unittest2.TestCase):
    @mock.patch.object(aversion.LOG, 'warn')
    def test_invalid_rule(self, mock_warn):
        self.assertRaises(KeyError, aversion._parse_alias_rule, 'v1.1', '')
        self.assertFalse(mock_warn.called)

    @mock.patch.object(aversion.LOG, 'warn')
    def test_no_params(self, mock_warn):
        result = aversion._parse_alias_rule('v1.1', 'v2')

        self.assertEqual(result, dict(alias='v1.1', version='v2', params={}))
        self.assertFalse(mock_warn.called)

    @mock.patch.object(aversion.LOG, 'warn')
    def test_bad_parameter(self, mock_warn):
        result = aversion._parse_alias_rule('v1.1', 'v2 foo=one')

        self.assertEqual(result, dict(alias='v1.1', version='v2', params={}))
        mock_warn.assert_called_once_with(
            "alias.v1.1: Invalid value 'one' for parameter 'foo'")

    @mock.patch.object(aversion.LOG, 'warn')
    def test_full_parse(self, mock_warn):
        result = aversion._parse_alias_rule('v1.1', 'v2 foo="one"  bar="two"')

        self.assertEqual(result, dict(
            alias='v1.1',
            version='v2',
            params=dict(foo='one', bar='two'),
        ))
        self.assertFalse(mock_warn.called)

    @mock.patch.object(aversion.LOG, 'warn')
    def test_duplicate_parameter(self, mock_warn):
        result = aversion._parse_alias_rule('v1.1', 'v2 foo="one" foo="two"')

        self.assertEqual(result, dict(
            alias='v1.1',
            version='v2',
            params=dict(foo='two'),
        ))
        mock_warn.assert_called_once_with(
            "alias.v1.1: Duplicate value for parameter 'foo'")


class ParseTypeRuleTest(unittest2.TestCase):
    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_invalid_rule(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'value')

        mock_warn.assert_called_once_with(
            "ctype: Invalid type token 'value'")
        mock_TypeRule.assert_called_once_with(ctype=None, version=None,
                                              params={})

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_unknown_token_type(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'value:bar')

        mock_warn.assert_called_once_with(
            "ctype: Unrecognized token type 'value'")
        mock_TypeRule.assert_called_once_with(ctype=None, version=None,
                                              params={})

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_bad_token_value(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'type:bar')

        mock_warn.assert_called_once_with(
            "type.ctype: Invalid value 'bar' for token type 'type'")
        mock_TypeRule.assert_called_once_with(ctype=None, version=None,
                                              params={})

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_token_parsing(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'type:"bar"  version:"baz" '
                                         'param:foo="one" param:bar="two"')

        self.assertFalse(mock_warn.called)
        mock_TypeRule.assert_called_once_with(ctype='bar', version='baz',
                                              params=dict(foo='one',
                                                          bar='two'))

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_token_parsing_duplicate(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'type:"bar" type:"baz"')

        mock_warn.assert_called_once_with(
            "type.ctype: Duplicate value for token type 'type'")
        mock_TypeRule.assert_called_once_with(ctype='baz', version=None,
                                              params={})

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_bad_param_value(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'param:foo=bar')

        mock_warn.assert_called_once_with(
            "type.ctype: Invalid value 'bar' for parameter 'foo'")
        mock_TypeRule.assert_called_once_with(ctype=None, version=None,
                                              params={})

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_duplicate_param(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype',
                                         'param:foo="one" param:foo="two"')

        mock_warn.assert_called_once_with(
            "type.ctype: Duplicate value for parameter 'foo'")
        mock_TypeRule.assert_called_once_with(ctype=None, version=None,
                                              params=dict(foo='two'))


class UriNormalizeTest(unittest2.TestCase):
    def test_uri_normalize(self):
        result = aversion._uri_normalize('///foo////bar////baz////')

        self.assertEqual(result, '/foo/bar/baz')


class AVersionTest(unittest2.TestCase):
    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    def test_init_empty(self):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})

        av = aversion.AVersion(loader, {})

        self.assertEqual(av.overwrite_headers, True)
        self.assertEqual(av.version_app, None)
        self.assertEqual(av.versions, {})
        self.assertEqual(av.aliases, {})
        self.assertEqual(av.types, {})
        self.assertEqual(av.formats, {})
        self.assertEqual(av.uris, [])
        self.assertEqual(av.config, {
            'versions': {},
            'aliases': {},
            'types': {},
        })

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    def test_init(self):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        conf = {
            'overwrite_headers': 'false',
            'version': 'vers_app',
            'version.v1': 'vers_v1',
            'version.v2': 'vers_v2',
            'alias.v1.1': 'v2',
            'uri.///v1.0//': 'v1',
            'uri.//v2////': 'v2',
            'uri.//v3///': 'v3',
            'type.a/a': 'type:"%(_)s" version:"v2"',
            'type.a/b': 'version:"v1"',
            'type.a/c': 'type:"a/a"',
            '.a': 'a/a',
            '.b': 'a/b',
            'ignored': 'ignored',
        }

        av = aversion.AVersion(loader, {}, **conf)

        self.assertEqual(av.overwrite_headers, False)
        self.assertEqual(av.version_app, 'vers_app')
        self.assertEqual(av.versions, {
            'v1': {
                'app': 'vers_v1',
                'name': 'v1',
                'prefixes': ['/v1.0'],
                'params': {},
            },
            'v2': {
                'app': 'vers_v2',
                'name': 'v2',
                'prefixes': ['/v2'],
                'params': {},
            },
        })
        self.assertEqual(av.aliases, {
            'v1.1': {
                'alias': 'v1.1',
                'version': 'v2',
                'params': {},
            },
        })
        self.assertEqual(av.types, {
            'a/a': ('%(_)s', 'v2', {}),
            'a/b': (None, 'v1', {}),
            'a/c': ('a/a', None, {}),
        })
        self.assertEqual(av.formats, {
            '.a': 'a/a',
            '.b': 'a/b',
        })
        self.assertEqual(av.uris, [
            ('/v1.0', 'v1'),
            ('/v2', 'v2'),
            ('/v3', 'v3'),
        ])
        self.assertEqual(av.config, {
            'versions': {
                'v1': {
                    'app': 'vers_v1',
                    'name': 'v1',
                    'prefixes': ['/v1.0'],
                    'params': {},
                },
                'v2': {
                    'app': 'vers_v2',
                    'name': 'v2',
                    'prefixes': ['/v2'],
                    'params': {},
                },
            },
            'aliases': {
                'v1.1': {
                    'alias': 'v1.1',
                    'version': 'v2',
                    'params': {},
                },
            },
            'types': {
                'a/a': dict(name='a/a', params={}, suffixes=['.a']),
                'a/b': dict(name='a/b', params={}, suffixes=['.b']),
                'a/c': dict(name='a/c', params={}),
            },
        })
        loader.assert_has_calls([
            mock.call.get_app('vers_app'),
            mock.call.get_app('vers_v1'),
            mock.call.get_app('vers_v2'),
        ], any_order=True)

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.LOG, 'warn')
    def test_init_overwrite_headers(self, mock_warn):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        trials = {
            'true': True,
            'tRuE': True,
            't': True,
            'on': True,
            'yes': True,
            'enable': True,
            'false': False,
            'fAlSe': False,
            'off': False,
            'no': False,
            'disable': False,
            '0': False,
            '1': True,
            '1000': True,
            'fals': True,
        }

        for value, expected in trials.items():
            av = aversion.AVersion(loader, {}, overwrite_headers=value)
            self.assertEqual(av.overwrite_headers, expected)

        mock_warn.assert_called_once_with(
            "Unrecognized value 'fals' for configuration key "
            "'overwrite_headers'")

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.AVersion, '_process',
                       return_value=mock.Mock(ctype=None, version=None))
    def test_call_noapp(self, mock_process):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={}, environ={})
        av = aversion.AVersion(loader, {})

        result = av(request)

        mock_process.assert_called_once_with(request)
        self.assertFalse(request.get_response.called)
        self.assertIsInstance(result, webob.exc.HTTPInternalServerError)
        self.assertEqual(request.headers, {})
        self.assertEqual(request.environ, {
            'aversion.config': {
                'versions': {},
                'aliases': {},
                'types': {},
            },
            'aversion.version': None,
        })

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.AVersion, '_process',
                       return_value=mock.Mock(ctype='a/a', version='v1',
                                              orig_ctype='a/b'))
    def test_call_app_fallback(self, mock_process):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(**{
            'headers': {},
            'environ': {},
            'get_response.return_value': 'response',
        })
        av = aversion.AVersion(loader, {})
        av.version_app = 'fallback'
        av.versions = dict(v2=dict(app='version2'))

        result = av(request)

        mock_process.assert_called_once_with(request)
        request.get_response.assert_called_once_with('fallback')
        self.assertEqual(result, 'response')
        self.assertEqual(request.headers, {'accept': 'a/a;q=1.0'})
        self.assertEqual(request.environ, {
            'aversion.config': {
                'versions': {},
                'aliases': {},
                'types': {},
            },
            'aversion.version': None,
            'aversion.response_type': 'a/a',
            'aversion.orig_response_type': 'a/b',
            'aversion.accept': None,
        })

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.AVersion, '_process',
                       return_value=mock.Mock(ctype='a/a', version='v1',
                                              orig_ctype='a/b'))
    def test_call_app_selected(self, mock_process):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(**{
            'headers': {},
            'environ': {},
            'get_response.return_value': 'response',
        })
        av = aversion.AVersion(loader, {})
        av.version_app = 'fallback'
        av.versions = dict(v1=dict(app='version1'))

        result = av(request)

        mock_process.assert_called_once_with(request)
        request.get_response.assert_called_once_with('version1')
        self.assertEqual(result, 'response')
        self.assertEqual(request.headers, {'accept': 'a/a;q=1.0'})
        self.assertEqual(request.environ, {
            'aversion.config': {
                'versions': {},
                'aliases': {},
                'types': {},
            },
            'aversion.version': 'v1',
            'aversion.response_type': 'a/a',
            'aversion.orig_response_type': 'a/b',
            'aversion.accept': None,
        })

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.AVersion, '_process',
                       return_value=mock.Mock(ctype='a/a', version='v1.1',
                                              orig_ctype='a/b'))
    def test_call_app_aliased(self, mock_process):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(**{
            'headers': {},
            'environ': {},
            'get_response.return_value': 'response',
        })
        av = aversion.AVersion(loader, {})
        av.version_app = 'fallback'
        av.versions = dict(v1=dict(app='version1'))
        av.aliases = {'v1.1': dict(version='v1')}

        result = av(request)

        mock_process.assert_called_once_with(request)
        request.get_response.assert_called_once_with('version1')
        self.assertEqual(result, 'response')
        self.assertEqual(request.headers, {'accept': 'a/a;q=1.0'})
        self.assertEqual(request.environ, {
            'aversion.config': {
                'versions': {},
                'aliases': {},
                'types': {},
            },
            'aversion.version': 'v1',
            'aversion.response_type': 'a/a',
            'aversion.orig_response_type': 'a/b',
            'aversion.accept': None,
        })

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.AVersion, '_process',
                       return_value=mock.Mock(ctype='a/a', version='v1',
                                              orig_ctype='a/b'))
    def test_call_app_selected_nooverwrite(self, mock_process):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(**{
            'headers': {},
            'environ': {},
            'get_response.return_value': 'response',
        })
        av = aversion.AVersion(loader, {})
        av.version_app = 'fallback'
        av.versions = dict(v1=dict(app='version1'))
        av.overwrite_headers = False

        result = av(request)

        mock_process.assert_called_once_with(request)
        request.get_response.assert_called_once_with('version1')
        self.assertEqual(result, 'response')
        self.assertEqual(request.headers, {})
        self.assertEqual(request.environ, {
            'aversion.config': {
                'versions': {},
                'aliases': {},
                'types': {},
            },
            'aversion.version': 'v1',
            'aversion.response_type': 'a/a',
            'aversion.orig_response_type': 'a/b',
            'aversion.accept': None,
        })

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion, 'Result', return_value='result')
    @mock.patch.object(aversion.AVersion, '_proc_uri')
    @mock.patch.object(aversion.AVersion, '_proc_ctype_header')
    @mock.patch.object(aversion.AVersion, '_proc_accept_header')
    def test_process_with_result(self, mock_proc_accept_header,
                                 mock_proc_ctype_header, mock_proc_uri,
                                 mock_Result):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        av = aversion.AVersion(loader, {})

        result = av._process('request', '')

        self.assertFalse(mock_Result.called)
        mock_proc_uri.assert_called_once_with('request', '')
        mock_proc_ctype_header.assert_called_once_with('request', '')
        mock_proc_accept_header.assert_called_once_with('request', '')
        self.assertEqual(result, '')

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion, 'Result', return_value='result')
    @mock.patch.object(aversion.AVersion, '_proc_uri')
    @mock.patch.object(aversion.AVersion, '_proc_ctype_header')
    @mock.patch.object(aversion.AVersion, '_proc_accept_header')
    def test_process_without_result(self, mock_proc_accept_header,
                                    mock_proc_ctype_header, mock_proc_uri,
                                    mock_Result):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        av = aversion.AVersion(loader, {})

        result = av._process('request')

        mock_Result.assert_called_once_with()
        mock_proc_uri.assert_called_once_with('request', 'result')
        mock_proc_ctype_header.assert_called_once_with('request', 'result')
        mock_proc_accept_header.assert_called_once_with('request', 'result')
        self.assertEqual(result, 'result')

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.Result, 'set_ctype')
    @mock.patch.object(aversion.Result, 'set_version')
    def test_proc_uri_filled_result(self, mock_set_version, mock_set_ctype):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(path_info='/v1/.a', script_name='')
        av = aversion.AVersion(loader, {})
        av.uris = [('/v1', 'v1')]
        av.formats = {'.a': 'a/a'}
        result = aversion.Result()
        result.ctype = 'a/b'
        result.version = 'v2'

        av._proc_uri(request, result)

        self.assertFalse(mock_set_version.called)
        self.assertFalse(mock_set_ctype.called)

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    def test_proc_uri_basic(self):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(path_info='/v1/.a', script_name='')
        av = aversion.AVersion(loader, {})
        av.uris = [('/v1', 'v1')]
        av.formats = {'.a': 'a/a'}
        result = aversion.Result()

        av._proc_uri(request, result)

        self.assertEqual(result.ctype, 'a/a')
        self.assertEqual(result.version, 'v1')

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    def test_proc_uri_empties_uri(self):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(path_info='/v1', script_name='')
        av = aversion.AVersion(loader, {})
        av.uris = [('/v1', 'v1')]
        av.formats = {'.a': 'a/a'}
        result = aversion.Result()

        av._proc_uri(request, result)

        self.assertEqual(result.ctype, None)
        self.assertEqual(result.version, 'v1')

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    def test_proc_uri_nomatch(self):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(path_info='/v2/.b', script_name='')
        av = aversion.AVersion(loader, {})
        av.uris = [('/v1', 'v1')]
        av.formats = {'.a': 'a/a'}
        result = aversion.Result()

        av._proc_uri(request, result)

        self.assertEqual(result.ctype, None)
        self.assertEqual(result.version, None)

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.Result, 'set_ctype')
    @mock.patch.object(aversion.Result, 'set_version')
    @mock.patch.object(aversion, 'parse_ctype',
                       return_value=('a/a', 'v1'))
    def test_proc_ctype_header_filled_result(self, mock_parse_ctype,
                                             mock_set_version, mock_set_ctype):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={'content-type': 'a/b'}, environ={})
        av = aversion.AVersion(loader, {})
        av.types = {'a/a': mock.Mock(return_value=('a/c', 'v2'))}
        result = aversion.Result()
        result.ctype = 'a/d'
        result.version = 'v3'

        av._proc_ctype_header(request, result)

        self.assertFalse(mock_set_version.called)
        self.assertFalse(mock_set_ctype.called)
        self.assertFalse(mock_parse_ctype.called)
        self.assertFalse(av.types['a/a'].called)
        self.assertEqual(request.environ, {})

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.Result, 'set_ctype')
    @mock.patch.object(aversion.Result, 'set_version')
    @mock.patch.object(aversion, 'parse_ctype',
                       return_value=('a/a', 'v1'))
    def test_proc_ctype_header_no_ctype(self, mock_parse_ctype,
                                        mock_set_version, mock_set_ctype):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={})
        av = aversion.AVersion(loader, {})
        av.types = {'a/a': mock.Mock(return_value=('a/c', 'v2'))}
        result = aversion.Result()

        av._proc_ctype_header(request, result)

        self.assertFalse(mock_set_version.called)
        self.assertFalse(mock_set_ctype.called)
        self.assertFalse(mock_parse_ctype.called)
        self.assertFalse(av.types['a/a'].called)

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.Result, 'set_ctype')
    @mock.patch.object(aversion.Result, 'set_version')
    @mock.patch.object(aversion, 'parse_ctype',
                       return_value=('a/a', 'v1'))
    def test_proc_ctype_header_missing_ctype(self, mock_parse_ctype,
                                             mock_set_version, mock_set_ctype):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={'content-type': 'a/b'})
        av = aversion.AVersion(loader, {})
        av.types = {'a/b': mock.Mock(return_value=('a/c', 'v2'))}
        result = aversion.Result()

        av._proc_ctype_header(request, result)

        mock_parse_ctype.assert_called_once_with('a/b')
        self.assertFalse(mock_set_version.called)
        self.assertFalse(mock_set_ctype.called)
        self.assertFalse(av.types['a/b'].called)

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.Result, 'set_ctype')
    @mock.patch.object(aversion, 'parse_ctype',
                       return_value=('a/a', 'v1'))
    def test_proc_ctype_header_basic(self, mock_parse_ctype, mock_set_ctype):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={'content-type': 'a/b'}, environ={})
        av = aversion.AVersion(loader, {})
        av.types = {'a/a': mock.Mock(return_value=('a/c', 'v2'))}
        result = aversion.Result()

        av._proc_ctype_header(request, result)

        mock_parse_ctype.assert_called_once_with('a/b')
        av.types['a/a'].assert_called_once_with('v1')
        self.assertEqual(request.headers, {'content-type': 'a/c'})
        self.assertEqual(request.environ, {
            'aversion.request_type': 'a/c',
            'aversion.orig_request_type': 'a/a',
            'aversion.content_type': 'a/b',
        })
        self.assertFalse(mock_set_ctype.called)
        self.assertEqual(result.version, 'v2')

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.Result, 'set_ctype')
    @mock.patch.object(aversion, 'parse_ctype',
                       return_value=('a/a', 'v1'))
    def test_proc_ctype_header_basic_nooverwrite(self, mock_parse_ctype,
                                                 mock_set_ctype):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={'content-type': 'a/b'}, environ={})
        av = aversion.AVersion(loader, {})
        av.types = {'a/a': mock.Mock(return_value=('a/c', 'v2'))}
        av.overwrite_headers = False
        result = aversion.Result()

        av._proc_ctype_header(request, result)

        mock_parse_ctype.assert_called_once_with('a/b')
        av.types['a/a'].assert_called_once_with('v1')
        self.assertEqual(request.headers, {'content-type': 'a/b'})
        self.assertEqual(request.environ, {
            'aversion.request_type': 'a/c',
            'aversion.orig_request_type': 'a/a',
            'aversion.content_type': 'a/b',
        })
        self.assertFalse(mock_set_ctype.called)
        self.assertEqual(result.version, 'v2')

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.Result, 'set_ctype')
    @mock.patch.object(aversion.Result, 'set_version')
    @mock.patch.object(aversion, 'parse_ctype',
                       return_value=('a/a', 'v1'))
    def test_proc_ctype_header_nomap(self, mock_parse_ctype,
                                     mock_set_version, mock_set_ctype):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={'content-type': 'a/b'})
        av = aversion.AVersion(loader, {})
        av.types = {'a/a': mock.Mock(return_value=('', ''))}
        result = aversion.Result()

        av._proc_ctype_header(request, result)

        mock_parse_ctype.assert_called_once_with('a/b')
        av.types['a/a'].assert_called_once_with('v1')
        self.assertEqual(request.headers, {'content-type': 'a/b'})
        self.assertFalse(mock_set_version.called)
        self.assertFalse(mock_set_ctype.called)

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.Result, 'set_ctype')
    @mock.patch.object(aversion.Result, 'set_version')
    @mock.patch.object(aversion, 'best_match',
                       return_value=('a/a', 'v1'))
    def test_proc_accept_header_filled_result(self, mock_best_match,
                                              mock_set_version,
                                              mock_set_ctype):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={'accept': 'a/b'})
        av = aversion.AVersion(loader, {})
        av.types = {'a/a': mock.Mock(return_value=('a/c', 'v2'))}
        result = aversion.Result()
        result.ctype = 'a/d'
        result.version = 'v3'

        av._proc_accept_header(request, result)

        self.assertFalse(mock_set_version.called)
        self.assertFalse(mock_set_ctype.called)
        self.assertFalse(mock_best_match.called)
        self.assertFalse(av.types['a/a'].called)

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.Result, 'set_ctype')
    @mock.patch.object(aversion.Result, 'set_version')
    @mock.patch.object(aversion, 'best_match',
                       return_value=('a/a', 'v1'))
    def test_proc_accept_header_no_accept(self, mock_best_match,
                                          mock_set_version, mock_set_ctype):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={})
        av = aversion.AVersion(loader, {})
        av.types = {'a/a': mock.Mock(return_value=('a/c', 'v2'))}
        result = aversion.Result()

        av._proc_accept_header(request, result)

        self.assertFalse(mock_set_version.called)
        self.assertFalse(mock_set_ctype.called)
        self.assertFalse(mock_best_match.called)
        self.assertFalse(av.types['a/a'].called)

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.Result, 'set_ctype')
    @mock.patch.object(aversion.Result, 'set_version')
    @mock.patch.object(aversion, 'best_match',
                       return_value=('a/a', 'v1'))
    def test_proc_accept_header_missing_ctype(self, mock_best_match,
                                              mock_set_version,
                                              mock_set_ctype):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={'accept': 'a/b'})
        av = aversion.AVersion(loader, {})
        av.types = {'a/b': mock.Mock(return_value=('a/c', 'v2'))}
        result = aversion.Result()

        av._proc_accept_header(request, result)

        mock_best_match.assert_called_once_with('a/b', ['a/b'])
        self.assertFalse(mock_set_version.called)
        self.assertFalse(mock_set_ctype.called)
        self.assertFalse(av.types['a/b'].called)

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion, 'best_match',
                       return_value=('a/a', 'v1'))
    def test_proc_accept_header_basic(self, mock_best_match):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={'accept': 'a/b'})
        av = aversion.AVersion(loader, {})
        av.types = {'a/a': mock.Mock(return_value=('a/c', 'v2'))}
        result = aversion.Result()

        av._proc_accept_header(request, result)

        mock_best_match.assert_called_once_with('a/b', ['a/a'])
        av.types['a/a'].assert_called_once_with('v1')
        self.assertEqual(result.ctype, 'a/c')
        self.assertEqual(result.version, 'v2')

    @mock.patch.object(aversion, 'TypeRule', FakeTypeRule)
    @mock.patch.object(aversion.Result, 'set_ctype')
    @mock.patch.object(aversion.Result, 'set_version')
    @mock.patch.object(aversion, 'best_match',
                       return_value=('a/a', 'v1'))
    def test_proc_accept_header_nomap(self, mock_best_match,
                                      mock_set_version, mock_set_ctype):
        loader = mock.Mock(**{'get_app.side_effect': lambda x: x})
        request = mock.Mock(headers={'accept': 'a/b'})
        av = aversion.AVersion(loader, {})
        av.types = {'a/a': mock.Mock(return_value=('', ''))}
        result = aversion.Result()

        av._proc_accept_header(request, result)

        mock_best_match.assert_called_once_with('a/b', ['a/a'])
        av.types['a/a'].assert_called_once_with('v1')
        self.assertFalse(mock_set_version.called)
        self.assertFalse(mock_set_ctype.called)


class FakeApplication(object):
    def __init__(self, name):
        self.name = name

    def __call__(self, environ, start_response):
        start_response('200 OK', [])
        yield self.name


# Used for comparing the environment and headers dictionaries
ANY = object()
NOTPRESENT = object()


class FunctionalTest(unittest2.TestCase):
    def construct_stack(self, conf, **versions):
        # Construct all the version applications
        apps = {}
        for version, params in versions.items():
            app_key = '%s_app' % version
            conf_key = ('version' if version == 'version' else
                        'version.%s' % version)
            apps[app_key] = FakeApplication(version)
            conf[conf_key] = app_key

            # Add parameters
            if params:
                conf[conf_key] += ' ' + ' '.join('%s="%s"' % (k, v)
                                                 for k, v in params.items())

        # Set up a loader
        loader = mock.Mock(**{'get_app.side_effect': lambda x: apps[x]})

        # Set up the stack and return it
        return aversion.AVersion(loader, {}, **conf)

    def make_request(self, path, base_url=None,
                     content_type=None, accept=None):
        # Build the headers for the request
        headers = {}
        if content_type:
            headers['content-type'] = content_type
        if accept:
            headers['accept'] = accept

        # Build and return the request object
        return webob.Request.blank(path, base_url=base_url, headers=headers)

    def assertPartialDict(self, actual, expected):
        for key, value in expected.items():
            if value == NOTPRESENT:
                self.assertNotIn(key, actual,
                                 msg="Value for key %r present" % key)
                continue

            self.assertIn(key, actual, msg="No value for key %r" % key)

            if value == ANY:
                continue

            if isinstance(value, dict):
                self.assertPartialDict(actual[key], value)
            else:
                self.assertEqual(actual[key], value,
                                 msg="Value mismatch for key %r" % key)

    def test_assert_partial_dict(self):
        # Check that NOTPRESENT requires the key to not be present
        self.assertRaises(AssertionError, self.assertPartialDict,
                          dict(a=1), dict(a=NOTPRESENT))

        # Check that other than NOTPRESENT requires the key to be
        # present
        self.assertRaises(AssertionError, self.assertPartialDict,
                          {}, dict(a=1))

        # Check that value mismatch is caught
        self.assertRaises(AssertionError, self.assertPartialDict,
                          dict(a=1), dict(a=2))

        # Check that ANY allows any value in that location
        self.assertPartialDict(dict(a=1), dict(a=ANY))
        self.assertPartialDict(dict(a=2), dict(a=ANY))

        # Check that recursion works properly
        self.assertRaises(AssertionError, self.assertPartialDict,
                          dict(a=dict(b=dict(c=1))),
                          dict(a=dict(b=dict(c=2))))
        self.assertPartialDict(dict(a=dict(b=dict(c=1))),
                               dict(a=dict(b=dict(c=1))))

    def test_no_matching_app(self):
        conf = {
            'uri./v1': 'version1',
            'uri./v2': 'version2',
        }
        stack = self.construct_stack(conf, version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        req = self.make_request('/')

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 500)
        self.assertIn("Cannot determine application to serve request",
                      resp.body)
        self.assertEqual(req.script_name, '')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': ['/v1'],
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': ['/v2'],
                    },
                },
                'aliases': {},
                'types': {},
            },
            'aversion.response_type': NOTPRESENT,
            'aversion.orig_response_type': NOTPRESENT,
            'aversion.accept': NOTPRESENT,
            'aversion.request_type': NOTPRESENT,
            'aversion.orig_request_type': NOTPRESENT,
            'aversion.content_type': NOTPRESENT,
            'aversion.version': None,
        })
        self.assertPartialDict(req.headers, {
            'content-type': NOTPRESENT,
            'accept': NOTPRESENT,
        })

    def test_default_app(self):
        conf = {
            'uri./v1': 'version1',
            'uri./v2': 'version2',
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        req = self.make_request('/')

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version", resp.body)
        self.assertEqual(req.script_name, '')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': ['/v1'],
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': ['/v2'],
                    },
                },
                'aliases': {},
                'types': {},
            },
            'aversion.response_type': NOTPRESENT,
            'aversion.orig_response_type': NOTPRESENT,
            'aversion.accept': NOTPRESENT,
            'aversion.request_type': NOTPRESENT,
            'aversion.orig_request_type': NOTPRESENT,
            'aversion.content_type': NOTPRESENT,
            'aversion.version': None,
        })
        self.assertPartialDict(req.headers, {
            'content-type': NOTPRESENT,
            'accept': NOTPRESENT,
        })

    def test_version1_app_urimatch(self):
        conf = {
            'uri./v1': 'version1',
            'uri./v2': 'version2',
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        req = self.make_request('/v1')

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version1", resp.body)
        self.assertEqual(req.script_name, '/v1')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': ['/v1'],
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': ['/v2'],
                    },
                },
                'aliases': {},
                'types': {},
            },
            'aversion.response_type': NOTPRESENT,
            'aversion.orig_response_type': NOTPRESENT,
            'aversion.accept': NOTPRESENT,
            'aversion.request_type': NOTPRESENT,
            'aversion.orig_request_type': NOTPRESENT,
            'aversion.content_type': NOTPRESENT,
            'aversion.version': 'version1',
        })
        self.assertPartialDict(req.headers, {
            'content-type': NOTPRESENT,
            'accept': NOTPRESENT,
        })

    def test_version2_app_urimatch_trailer(self):
        conf = {
            'uri./v1': 'version1',
            'uri./v2': 'version2',
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        req = self.make_request('/v2/foo')

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version2", resp.body)
        self.assertEqual(req.script_name, '/v2')
        self.assertEqual(req.path_info, '/foo')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': ['/v1'],
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': ['/v2'],
                    },
                },
                'aliases': {},
                'types': {},
            },
            'aversion.response_type': NOTPRESENT,
            'aversion.orig_response_type': NOTPRESENT,
            'aversion.accept': NOTPRESENT,
            'aversion.request_type': NOTPRESENT,
            'aversion.orig_request_type': NOTPRESENT,
            'aversion.content_type': NOTPRESENT,
            'aversion.version': 'version2',
        })
        self.assertPartialDict(req.headers, {
            'content-type': NOTPRESENT,
            'accept': NOTPRESENT,
        })

    def test_version1_app_urimatch_withformat(self):
        conf = {
            'uri./v1': 'version1',
            'uri./v2': 'version2',
            '.json': 'application/json',
            '.xml': 'application/xml',
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        req = self.make_request('/v1/.json')

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version1", resp.body)
        self.assertEqual(req.script_name, '/v1')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': ['/v1'],
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': ['/v2'],
                    },
                },
                'aliases': {},
                'types': {
                    'application/json': {
                        'name': 'application/json',
                        'params': {},
                        'suffixes': ['.json'],
                    },
                    'application/xml': {
                        'name': 'application/xml',
                        'params': {},
                        'suffixes': ['.xml'],
                    },
                },
            },
            'aversion.response_type': 'application/json',
            'aversion.orig_response_type': None,
            'aversion.accept': None,
            'aversion.request_type': NOTPRESENT,
            'aversion.orig_request_type': NOTPRESENT,
            'aversion.content_type': NOTPRESENT,
            'aversion.version': 'version1',
        })
        self.assertPartialDict(req.headers, {
            'content-type': NOTPRESENT,
            'accept': 'application/json;q=1.0',
        })

    def test_version1_1_app_urimatch_withalias(self):
        conf = {
            'uri./v1': 'version1',
            'uri./v2': 'version2',
            'uri./v1.1': 'version1.1',
            'alias.version1.1': 'version2 map="1.1->2"',
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        req = self.make_request('/v1.1')

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version2", resp.body)
        self.assertEqual(req.script_name, '/v1.1')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': ['/v1'],
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': ['/v2'],
                    },
                },
                'aliases': {
                    'version1.1': {
                        'alias': 'version1.1',
                        'version': 'version2',
                        'params': dict(map="1.1->2"),
                    },
                },
                'types': {},
            },
            'aversion.response_type': NOTPRESENT,
            'aversion.orig_response_type': NOTPRESENT,
            'aversion.accept': NOTPRESENT,
            'aversion.request_type': NOTPRESENT,
            'aversion.orig_request_type': NOTPRESENT,
            'aversion.content_type': NOTPRESENT,
            'aversion.version': 'version2',
        })
        self.assertPartialDict(req.headers, {
            'content-type': NOTPRESENT,
            'accept': NOTPRESENT,
        })

    def test_version1_app_ctypematch(self):
        conf = {
            'type.application/json': ('version:"version%(v)s" '
                                      'param:type="json"'),
            'type.application/xml': ('version:"version%(v)s" '
                                     'param:type="xml"'),
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        req = self.make_request('/', content_type='application/json;v=1')

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version1", resp.body)
        self.assertEqual(req.script_name, '')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': NOTPRESENT,
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': NOTPRESENT,
                    },
                },
                'aliases': {},
                'types': {
                    'application/json': {
                        'name': 'application/json',
                        'params': dict(type='json'),
                        'suffixes': NOTPRESENT,
                    },
                    'application/xml': {
                        'name': 'application/xml',
                        'params': dict(type='xml'),
                        'suffixes': NOTPRESENT,
                    },
                },
            },
            'aversion.response_type': NOTPRESENT,
            'aversion.orig_response_type': NOTPRESENT,
            'aversion.accept': NOTPRESENT,
            'aversion.request_type': 'application/json',
            'aversion.orig_request_type': 'application/json',
            'aversion.content_type': 'application/json;v=1',
            'aversion.version': 'version1',
        })
        self.assertPartialDict(req.headers, {
            'content-type': 'application/json',
            'accept': NOTPRESENT,
        })

    def test_version1_1_app_ctypematch_withalias(self):
        conf = {
            'type.application/json': ('version:"version%(v)s" '
                                      'param:type="json"'),
            'type.application/xml': ('version:"version%(v)s" '
                                     'param:type="xml"'),
            'alias.version1.1': 'version2 map="1.1->2"',
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        req = self.make_request('/', content_type='application/xml;v=1.1')

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version2", resp.body)
        self.assertEqual(req.script_name, '')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': NOTPRESENT,
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': NOTPRESENT,
                    },
                },
                'aliases': {
                    'version1.1': {
                        'alias': 'version1.1',
                        'version': 'version2',
                        'params': dict(map="1.1->2"),
                    },
                },
                'types': {
                    'application/json': {
                        'name': 'application/json',
                        'params': dict(type='json'),
                        'suffixes': NOTPRESENT,
                    },
                    'application/xml': {
                        'name': 'application/xml',
                        'params': dict(type='xml'),
                        'suffixes': NOTPRESENT,
                    },
                },
            },
            'aversion.response_type': NOTPRESENT,
            'aversion.orig_response_type': NOTPRESENT,
            'aversion.accept': NOTPRESENT,
            'aversion.request_type': 'application/xml',
            'aversion.orig_request_type': 'application/xml',
            'aversion.content_type': 'application/xml;v=1.1',
            'aversion.version': 'version2',
        })
        self.assertPartialDict(req.headers, {
            'content-type': 'application/xml',
            'accept': NOTPRESENT,
        })

    def test_version2_app_ctypematch_typerewrite(self):
        conf = {
            'type.application/vnd.spam': ('version:"version%(v)s" '
                                          'type:"application/%(x)s" '
                                          'param:type="spam"'),
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        ctype = 'application/vnd.spam;v=2;x="xml";y=42'
        req = self.make_request('/', content_type=ctype)

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version2", resp.body)
        self.assertEqual(req.script_name, '')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': NOTPRESENT,
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': NOTPRESENT,
                    },
                },
                'aliases': {},
                'types': {
                    'application/vnd.spam': {
                        'name': 'application/vnd.spam',
                        'params': dict(type='spam'),
                        'suffixes': NOTPRESENT,
                    },
                },
            },
            'aversion.response_type': NOTPRESENT,
            'aversion.orig_response_type': NOTPRESENT,
            'aversion.accept': NOTPRESENT,
            'aversion.request_type': 'application/xml',
            'aversion.orig_request_type': 'application/vnd.spam',
            'aversion.content_type': ctype,
            'aversion.version': 'version2',
        })
        self.assertPartialDict(req.headers, {
            'content-type': 'application/xml',
            'accept': NOTPRESENT,
        })

    def test_version2_app_ctypematch_notyperewrite(self):
        conf = {
            'type.application/vnd.spam': ('version:"version%(v)s" '
                                          'type:"application/%(x)s" '
                                          'param:type="spam"'),
            'overwrite_headers': 'off',
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        ctype = 'application/vnd.spam;v=2;x="xml";y=42'
        req = self.make_request('/', content_type=ctype)

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version2", resp.body)
        self.assertEqual(req.script_name, '')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': NOTPRESENT,
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': NOTPRESENT,
                    },
                },
                'aliases': {},
                'types': {
                    'application/vnd.spam': {
                        'name': 'application/vnd.spam',
                        'params': dict(type='spam'),
                        'suffixes': NOTPRESENT,
                    },
                },
            },
            'aversion.response_type': NOTPRESENT,
            'aversion.orig_response_type': NOTPRESENT,
            'aversion.accept': NOTPRESENT,
            'aversion.request_type': 'application/xml',
            'aversion.orig_request_type': 'application/vnd.spam',
            'aversion.content_type': ctype,
            'aversion.version': 'version2',
        })
        self.assertPartialDict(req.headers, {
            'content-type': ctype,
            'accept': NOTPRESENT,
        })

    def test_version1_app_acceptmatch(self):
        conf = {
            'type.application/json': ('version:"version%(v)s" '
                                      'param:type="json"'),
            'type.application/xml': ('version:"version%(v)s" '
                                     'param:type="xml"'),
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        req = self.make_request('/', accept='application/json;v=1')

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version1", resp.body)
        self.assertEqual(req.script_name, '')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': NOTPRESENT,
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': NOTPRESENT,
                    },
                },
                'aliases': {},
                'types': {
                    'application/json': {
                        'name': 'application/json',
                        'params': dict(type='json'),
                        'suffixes': NOTPRESENT,
                    },
                    'application/xml': {
                        'name': 'application/xml',
                        'params': dict(type='xml'),
                        'suffixes': NOTPRESENT,
                    },
                },
            },
            'aversion.response_type': 'application/json',
            'aversion.orig_response_type': 'application/json',
            'aversion.accept': 'application/json;v=1',
            'aversion.request_type': NOTPRESENT,
            'aversion.orig_request_type': NOTPRESENT,
            'aversion.content_type': NOTPRESENT,
            'aversion.version': 'version1',
        })
        self.assertPartialDict(req.headers, {
            'content-type': NOTPRESENT,
            'accept': 'application/json;q=1.0',
        })

    def test_version1_1_app_acceptmatch_withalias(self):
        conf = {
            'type.application/json': ('version:"version%(v)s" '
                                      'param:type="json"'),
            'type.application/xml': ('version:"version%(v)s" '
                                     'param:type="xml"'),
            'alias.version1.1': 'version2 map="1.1->2"',
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        req = self.make_request('/', accept='application/xml;v=1.1')

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version2", resp.body)
        self.assertEqual(req.script_name, '')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': NOTPRESENT,
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': NOTPRESENT,
                    },
                },
                'aliases': {
                    'version1.1': {
                        'alias': 'version1.1',
                        'version': 'version2',
                        'params': dict(map="1.1->2"),
                    },
                },
                'types': {
                    'application/json': {
                        'name': 'application/json',
                        'params': dict(type='json'),
                        'suffixes': NOTPRESENT,
                    },
                    'application/xml': {
                        'name': 'application/xml',
                        'params': dict(type='xml'),
                        'suffixes': NOTPRESENT,
                    },
                },
            },
            'aversion.response_type': 'application/xml',
            'aversion.orig_response_type': 'application/xml',
            'aversion.accept': 'application/xml;v=1.1',
            'aversion.request_type': NOTPRESENT,
            'aversion.orig_request_type': NOTPRESENT,
            'aversion.content_type': NOTPRESENT,
            'aversion.version': 'version2',
        })
        self.assertPartialDict(req.headers, {
            'content-type': NOTPRESENT,
            'accept': 'application/xml;q=1.0',
        })

    def test_version2_app_acceptmatch_typerewrite(self):
        conf = {
            'type.application/vnd.spam': ('version:"version%(v)s" '
                                          'type:"application/%(x)s" '
                                          'param:type="spam"'),
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        accept = 'application/vnd.spam;v=2;x="xml";y=42'
        req = self.make_request('/', accept=accept)

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version2", resp.body)
        self.assertEqual(req.script_name, '')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': NOTPRESENT,
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': NOTPRESENT,
                    },
                },
                'aliases': {},
                'types': {
                    'application/vnd.spam': {
                        'name': 'application/vnd.spam',
                        'params': dict(type='spam'),
                        'suffixes': NOTPRESENT,
                    },
                },
            },
            'aversion.response_type': 'application/xml',
            'aversion.orig_response_type': 'application/vnd.spam',
            'aversion.accept': accept,
            'aversion.request_type': NOTPRESENT,
            'aversion.orig_request_type': NOTPRESENT,
            'aversion.content_type': NOTPRESENT,
            'aversion.version': 'version2',
        })
        self.assertPartialDict(req.headers, {
            'content-type': NOTPRESENT,
            'accept': 'application/xml;q=1.0',
        })

    def test_version2_app_acceptmatch_notyperewrite(self):
        conf = {
            'type.application/vnd.spam': ('version:"version%(v)s" '
                                          'type:"application/%(x)s" '
                                          'param:type="spam"'),
            'overwrite_headers': 'off',
        }
        stack = self.construct_stack(conf, version={},
                                     version1=dict(v='v1'),
                                     version2=dict(v='v2'))
        accept = 'application/vnd.spam;v=2;x="xml";y=42'
        req = self.make_request('/', accept=accept)

        resp = req.get_response(stack)

        self.assertEqual(resp.status_int, 200)
        self.assertEqual("version2", resp.body)
        self.assertEqual(req.script_name, '')
        self.assertEqual(req.path_info, '/')
        self.assertPartialDict(req.environ, {
            'aversion.config': {
                'versions': {
                    'version1': {
                        'name': 'version1',
                        'app': ANY,
                        'params': dict(v='v1'),
                        'prefixes': NOTPRESENT,
                    },
                    'version2': {
                        'name': 'version2',
                        'app': ANY,
                        'params': dict(v='v2'),
                        'prefixes': NOTPRESENT,
                    },
                },
                'aliases': {},
                'types': {
                    'application/vnd.spam': {
                        'name': 'application/vnd.spam',
                        'params': dict(type='spam'),
                        'suffixes': NOTPRESENT,
                    },
                },
            },
            'aversion.response_type': 'application/xml',
            'aversion.orig_response_type': 'application/vnd.spam',
            'aversion.accept': accept,
            'aversion.request_type': NOTPRESENT,
            'aversion.orig_request_type': NOTPRESENT,
            'aversion.content_type': NOTPRESENT,
            'aversion.version': 'version2',
        })
        self.assertPartialDict(req.headers, {
            'content-type': NOTPRESENT,
            'accept': accept,
        })
