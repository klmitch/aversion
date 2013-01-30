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
