import io, os, subprocess, sys, unittest, pathlib
from mini_redis.cli import execute, repl
from mini_redis.parser import tokenize
from mini_redis.store import MiniRedisStore
ROOT = pathlib.Path(__file__).resolve().parents[1]
UTF8_ENV = dict(os.environ, PYTHONIOENCODING="utf-8")   # 로케일과 무관하게 한글 입출력을 검증한다

def run(store, line): return execute(store, tokenize(line))

class TestExecute(unittest.TestCase):
    def setUp(self): self.s = MiniRedisStore()
    def test_outputs(self):
        s = self.s
        self.assertEqual(run(s, 'set user:1 "Alice"'), "OK")
        self.assertEqual(run(s, "GET user:1"), '"Alice"')
        self.assertEqual(run(s, "GET nope"), "(nil)")
        self.assertEqual(run(s, "EXISTS user:1"), "(integer) 1")
        self.assertEqual(run(s, "DBSIZE"), "(integer) 1")
        self.assertEqual(run(s, "KEYS"), '1. "user:1"')
        self.assertEqual(run(s, "DEL user:1"), "(integer) 1")
        self.assertEqual(run(s, "KEYS"), "(empty array)")
        self.assertEqual(run(s, "TTL user:1"), "(integer) -2")
    def test_errors(self):
        s = self.s
        self.assertEqual(run(s, "HELLO"), "(error) ERR unknown command 'HELLO'")
        self.assertEqual(run(s, "GET"), "(error) ERR wrong number of arguments for 'GET' command")
        self.assertEqual(run(s, "CONFIG SET maxmemory abc"), "(error) ERR value is not an integer or out of range")
        self.assertEqual(run(s, "CONFIG SET maxmemory -1"), "(error) ERR value is not an integer or out of range")
        self.assertEqual(run(s, "EXPIRE k x"), "(error) ERR value is not an integer or out of range")
        self.assertEqual(run(s, "CONFIG SET foo 1"), "(error) ERR Unsupported CONFIG parameter: foo")
        run(s, "CONFIG SET maxmemory 3")
        self.assertEqual(run(s, "SET big value"), "(error) OOM command not allowed when used_memory > 'maxmemory'")
    def test_info_memory(self):
        s = self.s; run(s, "CONFIG SET maxmemory 30")
        self.assertEqual(run(s, "INFO memory"), "used_memory:0\nmaxmemory:30\nevicted_keys:0")
    def test_empty_tokens(self):
        self.assertEqual(execute(self.s, []), "")

    # --- 아래는 plan 테스트 외에 경계를 더 조인 케이스 ---

    def test_command_names_are_case_insensitive_but_errors_echo_input(self):
        s = self.s
        self.assertEqual(run(s, "sEt k v"), "OK"); self.assertEqual(run(s, "gEt k"), '"v"')
        self.assertEqual(run(s, "get"), "(error) ERR wrong number of arguments for 'get' command")
        self.assertEqual(run(s, "hello"), "(error) ERR unknown command 'hello'")

    def test_wrong_number_of_arguments_for_every_command(self):
        s = self.s
        for line, name in [("SET a", "SET"), ("SET a b c", "SET"), ("GET a b", "GET"), ("DEL", "DEL"),
                           ("EXISTS", "EXISTS"), ("DBSIZE x", "DBSIZE"), ("KEYS x", "KEYS"),
                           ("EXPIRE a", "EXPIRE"), ("EXPIRE a 1 2", "EXPIRE"), ("TTL", "TTL"),
                           ("CONFIG", "CONFIG"), ("CONFIG SET maxmemory", "CONFIG"), ("INFO a b", "INFO")]:
            self.assertEqual(run(s, line), f"(error) ERR wrong number of arguments for '{name}' command", line)

    def test_expire_and_ttl_outputs(self):
        s = self.s
        self.assertEqual(run(s, "EXPIRE nope 10"), "(integer) 0")
        run(s, "SET k v")
        self.assertEqual(run(s, "TTL k"), "(integer) -1")
        self.assertEqual(run(s, "EXPIRE k 100"), "(integer) 1")
        self.assertIn(run(s, "TTL k"), ["(integer) 100", "(integer) 99"])
        self.assertEqual(run(s, "EXPIRE k 0"), "(integer) 1")
        self.assertEqual(run(s, "GET k"), "(nil)")

    def test_integer_parsing_is_strict(self):
        s = self.s; err = "(error) ERR value is not an integer or out of range"
        for bad in ["1.5", "+5", "1_0", "0x10", "", " ", "--1", "-", "٣", "99999999999999999999"]:
            self.assertEqual(execute(s, ["EXPIRE", "k", bad]), err, repr(bad))
        run(s, "SET k v")
        self.assertEqual(execute(s, ["EXPIRE", "k", "-5"]), "(integer) 1")      # 음수 seconds 는 즉시 만료
        self.assertEqual(run(s, "EXISTS k"), "(integer) 0")

    def test_config_set_variants(self):
        s = self.s
        self.assertEqual(run(s, "config set MAXMEMORY 10"), "OK")
        self.assertEqual(run(s, "INFO"), "used_memory:0\nmaxmemory:10\nevicted_keys:0")   # 인자 없는 INFO 도 같은 출력
        self.assertEqual(run(s, "CONFIG SET maxmemory 0"), "OK")
        self.assertEqual(run(s, "CONFIG GET maxmemory"), "(error) ERR wrong number of arguments for 'CONFIG' command")
        self.assertEqual(run(s, "CONFIG GET maxmemory x"), "(error) ERR unknown subcommand 'GET' for 'CONFIG' command")
        self.assertEqual(run(s, "INFO cpu"), "(error) ERR Unsupported INFO section: cpu")

    def test_lowering_maxmemory_via_command_evicts(self):
        s = self.s
        for k in ["a", "b", "c"]: run(s, f'SET {k} "1234"')
        run(s, "CONFIG SET maxmemory 10")
        self.assertEqual(run(s, "INFO memory"), "used_memory:10\nmaxmemory:10\nevicted_keys:1")
        self.assertEqual(run(s, "GET a"), "(nil)")

    def test_keys_lists_numbered_lines_in_sorted_order(self):
        s = self.s
        for k in ["user:3", "user:1", "user:2"]: run(s, f"SET {k} v")
        self.assertEqual(run(s, "KEYS"), '1. "user:1"\n2. "user:2"\n3. "user:3"')   # 해시 순서와 무관하게 늘 같은 순서

    def test_values_with_quotes_and_backslashes_round_trip(self):
        s = self.s
        self.assertEqual(run(s, 'SET k "say \\"hi\\" \\\\ ok"'), "OK")
        self.assertEqual(run(s, "GET k"), '"say \\"hi\\" \\\\ ok"')
        self.assertEqual(run(s, 'SET "my key" "한 글"'), "OK")
        self.assertEqual(run(s, 'GET "my key"'), '"한 글"')
        self.assertEqual(run(s, "KEYS"), '1. "k"\n2. "my key"')

    def test_empty_value(self):
        self.assertEqual(run(self.s, 'SET k ""'), "OK")
        self.assertEqual(run(self.s, "GET k"), '""')

class TestReplInProcess(unittest.TestCase):
    def go(self, text, store=None):
        out = io.StringIO()
        code = repl(stdin=io.StringIO(text), stdout=out, store=store)
        return code, out.getvalue()

    def test_prompt_and_bye(self):
        code, out = self.go("SET a 1\nquit\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, "mini-redis> OK\nmini-redis> Bye\n")

    def test_exit_and_quit_are_case_insensitive(self):
        for word in ["exit", "EXIT", "Quit", "QUIT"]:
            code, out = self.go(f"{word}\nSET a 1\n")
            self.assertEqual((code, out), (0, "mini-redis> Bye\n"), word)

    def test_eof_prints_newline_and_exits_cleanly(self):
        code, out = self.go("GET a\n")
        self.assertEqual(code, 0)
        self.assertEqual(out, 'mini-redis> (nil)\nmini-redis> \n')

    def test_blank_lines_print_nothing_but_the_prompt(self):
        code, out = self.go("\n   \n\t\nquit\n")
        self.assertEqual(out, "mini-redis> mini-redis> mini-redis> mini-redis> Bye\n")

    def test_unbalanced_quote_does_not_stop_the_session(self):
        code, out = self.go('SET a "abc\nSET a 1\nGET a\n')
        self.assertIn("(error) ERR Protocol error: unbalanced quotes in request\n", out)
        self.assertIn('"1"\n', out)

    def test_uses_given_store(self):
        s = MiniRedisStore(); s.set("pre", "set")
        _, out = self.go("GET pre\n", store=s)
        self.assertIn('"set"', out)

    def test_ctrl_c_exits_cleanly(self):
        class Interrupting:
            def readline(self): raise KeyboardInterrupt
        out = io.StringIO()
        self.assertEqual(repl(stdin=Interrupting(), stdout=out), 0)
        self.assertEqual(out.getvalue(), "mini-redis> \n")

class TestRepl(unittest.TestCase):
    def repl(self, text):
        return subprocess.run([sys.executable, "main.py"], input=text, capture_output=True, text=True, encoding="utf-8", env=UTF8_ENV, cwd=ROOT, timeout=10)
    def test_mission_example_session(self):
        p = self.repl('CONFIG SET maxmemory 30\nSET user:1 "Alice"\nSET user:2 "Bob"\nSET user:3 "Charlie"\nGET user:1\nINFO memory\nquit\n')
        self.assertEqual(p.returncode, 0)
        for line in ["(nil)", "used_memory:22", "maxmemory:30", "evicted_keys:1", "mini-redis> "]:
            self.assertIn(line, p.stdout)
    def test_eof_and_blank_lines(self):
        p = self.repl("\n   \nSET a 1\n")
        self.assertEqual(p.returncode, 0); self.assertIn("OK", p.stdout); self.assertEqual(p.stderr, "")
    def test_unbalanced_quotes_in_repl(self):
        p = self.repl('SET a "abc\nEXIT\n')
        self.assertIn("(error) ERR Protocol error: unbalanced quotes in request", p.stdout)

    def test_module_entry_point_and_korean_value(self):
        p = subprocess.run([sys.executable, "-m", "mini_redis"], input='SET 키 "값 값"\nGET 키\nINFO memory\nquit\n',
                           capture_output=True, text=True, encoding="utf-8", env=UTF8_ENV, cwd=ROOT, timeout=10)
        self.assertEqual(p.returncode, 0); self.assertEqual(p.stderr, "")
        self.assertIn('"값 값"', p.stdout); self.assertIn("used_memory:10", p.stdout)   # 키 3 + 값 값(3+1+3)
