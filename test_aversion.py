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
            "ctype: Unrecognized token value 'bar'")
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
            "ctype: Duplicate value for token type 'type'")
        mock_TypeRule.assert_called_once_with(ctype='baz', version=None,
                                              params={})

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_bad_param_value(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'param:foo=bar')

        mock_warn.assert_called_once_with(
            "ctype: Invalid parameter value 'bar' for parameter 'foo'")
        mock_TypeRule.assert_called_once_with(ctype=None, version=None,
                                              params={})

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_duplicate_param(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype',
                                         'param:foo="one" param:foo="two"')

        mock_warn.assert_called_once_with(
            "ctype: Duplicate value for parameter 'foo'")
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
        self.assertEqual(av.versions, dict(v1='vers_v1', v2='vers_v2'))
        self.assertEqual(av.aliases, {'v1.1': 'v2'})
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
        ])
        self.assertEqual(av.config, {
            'versions': dict(v1=['/v1.0'], v2=['/v2']),
            'aliases': {'v1.1': 'v2'},
            'types': {
                'a/a': dict(name='a/a', params={}, suffix='.a'),
                'a/b': dict(name='a/b', params={}, suffix='.b'),
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
        av.versions = dict(v2='version2')

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
        av.versions = dict(v1='version1')

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
        av.versions = dict(v1='version1')
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
            'aversion.content-type': 'a/b',
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
            'aversion.content-type': 'a/b',
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
