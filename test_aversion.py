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

import mock
import unittest2

import aversion


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
        tr = aversion.TypeRule('ctype', 'version')

        self.assertEqual(tr.ctype, 'ctype')
        self.assertEqual(tr.version, 'version')

    def test_call_fixed(self):
        tr = aversion.TypeRule('ctype', 'version')

        ctype, version = tr({})

        self.assertEqual(ctype, 'ctype')
        self.assertEqual(version, 'version')

    def test_call_subs(self):
        tr = aversion.TypeRule('ctype:%(ctype)s', 'version:%(version)s')

        ctype, version = tr(dict(ctype='epytc', version='noisrev'))

        self.assertEqual(ctype, 'ctype:epytc')
        self.assertEqual(version, 'version:noisrev')

    def test_call_defaults(self):
        tr = aversion.TypeRule(None, None)

        ctype, version = tr(dict(_='ctype/epytc'))

        self.assertEqual(ctype, 'ctype/epytc')
        self.assertEqual(version, None)

    def test_call_badsubs(self):
        tr = aversion.TypeRule('ctype:%(ctype)s', 'version:%(version)s')

        ctype, version = tr({})

        self.assertEqual(ctype, None)
        self.assertEqual(version, None)


class ResultTest(unittest2.TestCase):
    def test_init(self):
        res = aversion.Result()

        self.assertEqual(res.version, None)
        self.assertEqual(res.ctype, None)

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

    def test_set_ctype_set(self):
        res = aversion.Result()
        res.ctype = 'ctype'

        res.set_ctype('epytc')

        self.assertEqual(res.ctype, 'ctype')


class ParseTypeRuleTest(unittest2.TestCase):
    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_invalid_rule(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'value')

        mock_warn.assert_called_once_with(
            "ctype: Invalid type token 'value'")
        mock_TypeRule.assert_called_once_with(ctype=None, version=None)

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_unknown_token_type(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'value:bar')

        mock_warn.assert_called_once_with(
            "ctype: Unrecognized token type 'value'")
        mock_TypeRule.assert_called_once_with(ctype=None, version=None)

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_bad_token_value(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'type:bar')

        mock_warn.assert_called_once_with(
            "ctype: Unrecognized token value 'bar'")
        mock_TypeRule.assert_called_once_with(ctype=None, version=None)

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_token_parsing(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'type:"bar" version:"baz"')

        self.assertFalse(mock_warn.called)
        mock_TypeRule.assert_called_once_with(ctype='bar', version='baz')

    @mock.patch.object(aversion.LOG, 'warn')
    @mock.patch.object(aversion, 'TypeRule')
    def test_token_parsing_duplicate(self, mock_TypeRule, mock_warn):
        rule = aversion._parse_type_rule('ctype', 'type:"bar" type:"baz"')

        mock_warn.assert_called_once_with(
            "ctype: Duplicate value for token type 'type'")
        mock_TypeRule.assert_called_once_with(ctype='baz', version=None)
