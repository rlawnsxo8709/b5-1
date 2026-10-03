import unittest
from mini_redis.parser import tokenize, ParseError
class TestTokenize(unittest.TestCase):
    def test_plain_and_quoted(self):
        self.assertEqual(tokenize('SET user:1 "Alice Kim"'), ["SET", "user:1", "Alice Kim"])
        self.assertEqual(tokenize('  GET   k  '), ["GET", "k"])
        self.assertEqual(tokenize('SET k "say \\"hi\\""'), ["SET", "k", 'say "hi"'])
        self.assertEqual(tokenize('SET k ""'), ["SET", "k", ""])
        self.assertEqual(tokenize("   "), [])
    def test_unbalanced(self):
        with self.assertRaises(ParseError): tokenize('SET a "abc')

    def test_empty_and_tabs(self):
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize("GET\tk"), ["GET", "k"])

    def test_escaped_backslash_and_unknown_escape(self):
        self.assertEqual(tokenize('SET k "a\\\\"'), ["SET", "k", "a\\"])      # "a\\" → a\
        self.assertEqual(tokenize('SET k "a\\nb"'), ["SET", "k", "a\\nb"])    # \n 은 해석하지 않고 그대로 둔다

    def test_trailing_backslash_inside_quote_is_unbalanced(self):
        with self.assertRaises(ParseError): tokenize('SET k "abc\\')
        with self.assertRaises(ParseError): tokenize('SET k "abc\\"')        # 닫는 따옴표가 이스케이프됨

    def test_quote_must_end_before_next_token(self):
        with self.assertRaises(ParseError): tokenize('SET k "abc"def')

    def test_quote_inside_plain_token_is_literal(self):
        self.assertEqual(tokenize('SET k a"b'), ["SET", "k", 'a"b'])

    def test_adjacent_quoted_tokens(self):
        self.assertEqual(tokenize('SET "a b" "c d"'), ["SET", "a b", "c d"])
        self.assertEqual(tokenize('SET k "한 글"'), ["SET", "k", "한 글"])
