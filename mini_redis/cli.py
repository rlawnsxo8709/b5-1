"""명령 실행과 REPL.

`execute`는 토큰 리스트를 받아 출력 문자열을 돌려준다(입출력 없음). 그래서 테스트하기 쉽다.
명령 이름 → 처리 함수 대응표는 내장 dict 대신 직접 만든 `HashMap`에 등록한다.
"""

import sys

from mini_redis.errors import OOMError
from mini_redis.hashmap import HashMap
from mini_redis.parser import ParseError, tokenize
from mini_redis.store import MiniRedisStore

PROMPT = "mini-redis> "

_ERR_INTEGER = "ERR value is not an integer or out of range"
_ERR_OOM = "OOM command not allowed when used_memory > 'maxmemory'"
_INT_MIN = -(2 ** 63)
_INT_MAX = 2 ** 63 - 1
_INT_MAX_DIGITS = len(str(_INT_MAX))   # 19


class _CommandError(Exception):
    """처리 함수가 던지는 사용자 오류. 메시지가 `(error) ` 뒤에 그대로 붙는다."""


class _Command:
    """명령 하나의 인자 개수 범위(명령 이름 제외)와 처리 함수."""

    __slots__ = ("min_args", "max_args", "handler")

    def __init__(self, min_args, max_args, handler):
        self.min_args = min_args
        self.max_args = max_args
        self.handler = handler


def _quote(text):
    """값을 `"..."`로 감싼다. 따옴표와 역슬래시는 파서와 같은 규칙으로 이스케이프한다."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _parse_int(text):
    """Redis처럼 엄격하게 정수로 바꾼다. 부호는 `-`만, 숫자는 ASCII 0-9만, 64bit 범위 안이어야 한다."""
    body = text[1:] if text.startswith("-") else text
    if body == "" or not all(ch in "0123456789" for ch in body):
        raise _CommandError(_ERR_INTEGER)
    # 64bit 최댓값 9223372036854775807이 19자리다. 그보다 길면 범위 밖이 확실하고,
    # 4300자리를 넘는 문자열은 int()가 ValueError를 내므로 변환 전에 걸러야 REPL이 죽지 않는다.
    if len(body) > _INT_MAX_DIGITS:
        raise _CommandError(_ERR_INTEGER)
    number = int(text)
    if number < _INT_MIN or number > _INT_MAX:
        raise _CommandError(_ERR_INTEGER)
    return number


def _cmd_set(store, args):
    store.set(args[0], args[1])
    return "OK"


def _cmd_get(store, args):
    value = store.get(args[0])
    return "(nil)" if value is None else _quote(value)


def _cmd_del(store, args):
    return f"(integer) {store.delete(args[0])}"


def _cmd_exists(store, args):
    return f"(integer) {store.exists(args[0])}"


def _cmd_dbsize(store, args):
    return f"(integer) {store.dbsize()}"


def _cmd_keys(store, args):
    # 해시맵의 키 순서는 보장되지 않으므로, 출력만 코드포인트 순으로 정렬해 늘 같은 결과를 보여 준다.
    keys = sorted(store.keys())
    if not keys:
        return "(empty array)"
    lines = []
    for number, key in enumerate(keys, start=1):
        lines.append(f"{number}. {_quote(key)}")
    return "\n".join(lines)


def _cmd_expire(store, args):
    seconds = _parse_int(args[1])
    return f"(integer) {store.expire(args[0], seconds)}"


def _cmd_ttl(store, args):
    return f"(integer) {store.ttl(args[0])}"


def _cmd_config(store, args):
    sub, param, value = args
    if sub.upper() != "SET":
        raise _CommandError(f"ERR unknown subcommand '{sub}' for 'CONFIG' command")
    if param.lower() != "maxmemory":
        raise _CommandError(f"ERR Unsupported CONFIG parameter: {param}")
    limit = _parse_int(value)
    if limit < 0:
        raise _CommandError(_ERR_INTEGER)
    store.set_maxmemory(limit)
    return "OK"


def _cmd_info(store, args):
    if args and args[0].lower() != "memory":
        raise _CommandError(f"ERR Unsupported INFO section: {args[0]}")
    used, limit, evicted = store.info_memory()
    return f"used_memory:{used}\nmaxmemory:{limit}\nevicted_keys:{evicted}"


_COMMANDS = HashMap()
_COMMANDS.put("SET", _Command(2, 2, _cmd_set))
_COMMANDS.put("GET", _Command(1, 1, _cmd_get))
_COMMANDS.put("DEL", _Command(1, 1, _cmd_del))
_COMMANDS.put("EXISTS", _Command(1, 1, _cmd_exists))
_COMMANDS.put("DBSIZE", _Command(0, 0, _cmd_dbsize))
_COMMANDS.put("KEYS", _Command(0, 0, _cmd_keys))
_COMMANDS.put("EXPIRE", _Command(2, 2, _cmd_expire))
_COMMANDS.put("TTL", _Command(1, 1, _cmd_ttl))
_COMMANDS.put("CONFIG", _Command(3, 3, _cmd_config))
_COMMANDS.put("INFO", _Command(0, 1, _cmd_info))


def execute(store, tokens):
    """명령 하나를 실행하고 출력 문자열(여러 줄 가능)을 돌려준다. 토큰이 없으면 빈 문자열."""
    if not tokens:
        return ""
    name = tokens[0]
    command = _COMMANDS.get(name.upper())
    if command is None:
        return f"(error) ERR unknown command '{name}'"
    args = tokens[1:]
    if len(args) < command.min_args or len(args) > command.max_args:
        return f"(error) ERR wrong number of arguments for '{name}' command"
    try:
        return command.handler(store, args)
    except _CommandError as error:
        return f"(error) {error}"
    except OOMError:
        return f"(error) {_ERR_OOM}"


def repl(stdin=sys.stdin, stdout=sys.stdout, store=None):
    """프롬프트를 띄우고 한 줄씩 읽어 실행한다. 종료 코드 0을 돌려준다.

    `exit`/`quit`이면 `Bye`를 출력하고 끝낸다. EOF(Ctrl-D, 파이프 끝)와 Ctrl-C는
    줄바꿈만 출력하고 예외 없이 끝낸다. 빈 줄은 무시한다.
    """
    if store is None:
        store = MiniRedisStore()
    while True:
        stdout.write(PROMPT)
        stdout.flush()
        try:
            line = stdin.readline()
        except KeyboardInterrupt:
            stdout.write("\n")
            return 0
        if line == "":
            stdout.write("\n")
            return 0
        try:
            tokens = tokenize(line)
        except ParseError as error:
            stdout.write(f"(error) ERR Protocol error: {error}\n")
            continue
        if not tokens:
            continue
        if tokens[0].lower() in ("exit", "quit"):
            stdout.write("Bye\n")
            return 0
        stdout.write(execute(store, tokens) + "\n")


def main():
    """`python3 main.py`와 `python3 -m mini_redis`의 공통 진입점."""
    return repl()
