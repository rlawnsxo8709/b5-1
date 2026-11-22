import unittest
from mini_redis import errors
from mini_redis.errors import (InvalidUTF8Error, MiniRedisError, NotIntegerError, OOMError, ParseError,
                               UnknownCommandError, UnknownSubcommandError, UnsupportedError, WrongArgsError)
from mini_redis.parser import tokenize
from mini_redis.store import MiniRedisStore

class TestErrors(unittest.TestCase):
    def test_each_error_carries_the_redis_text(self):
        self.assertEqual(str(UnknownCommandError("HELLO")), "ERR unknown command 'HELLO'")
        self.assertEqual(str(WrongArgsError("get")), "ERR wrong number of arguments for 'get' command")
        self.assertEqual(str(NotIntegerError()), "ERR value is not an integer or out of range")
        self.assertEqual(str(OOMError()), "OOM command not allowed when used_memory > 'maxmemory'")
        self.assertEqual(str(ParseError("unbalanced quotes in request")), "ERR Protocol error: unbalanced quotes in request")
        self.assertEqual(str(UnknownSubcommandError("GET", "CONFIG")), "ERR unknown subcommand 'GET' for 'CONFIG' command")
        self.assertEqual(str(UnsupportedError("CONFIG parameter", "foo")), "ERR Unsupported CONFIG parameter: foo")
        self.assertEqual(str(UnsupportedError("INFO section", "server")), "ERR Unsupported INFO section: server")
        self.assertEqual(str(InvalidUTF8Error()), "ERR invalid UTF-8 input")

    def test_every_user_error_shares_one_parent(self):
        for cls in (UnknownCommandError, WrongArgsError, NotIntegerError, OOMError, ParseError,
                    UnknownSubcommandError, UnsupportedError, InvalidUTF8Error):
            self.assertTrue(issubclass(cls, MiniRedisError), cls.__name__)
        self.assertTrue(issubclass(MiniRedisError, Exception))

    def test_store_and_parser_raise_the_shared_classes(self):
        s = MiniRedisStore(); s.set_maxmemory(3)
        with self.assertRaises(errors.OOMError): s.set("abc", "def")       # store는 사실(OOM)만 던진다
        with self.assertRaises(errors.ParseError) as caught: tokenize('SET k "abc')
        self.assertEqual(caught.exception.reason, "unbalanced quotes in request")
