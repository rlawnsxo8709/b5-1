"""명령 실행과 REPL.

`execute`는 토큰 리스트를 받아 출력 문자열을 돌려준다(입출력 없음). 그래서 테스트하기 쉽다.
명령 이름 → 처리 함수 대응표는 내장 dict 대신 직접 만든 `HashMap`에 등록한다.
오류 문구는 `errors.py`에 있고, 여기서는 `MiniRedisError`를 잡아 `(error) <문구>`로 찍기만 한다.
"""

import sys

from mini_redis.errors import (InvalidUTF8Error, MiniRedisError, NotIntegerError, UnknownCommandError,
                               UnknownSubcommandError, UnsupportedError, WrongArgsError)
from mini_redis.hashmap import HashMap
from mini_redis.parser import tokenize
from mini_redis.store import MiniRedisStore

PROMPT = "mini-redis> "

_INT_MIN = -(2 ** 63)
_INT_MAX = 2 ** 63 - 1
_INT_MAX_DIGITS = len(str(_INT_MAX))   # 19


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
        raise NotIntegerError()
    # 64bit 최댓값 9223372036854775807이 19자리다. 그보다 길면 범위 밖이 확실하고,
    # 4300자리를 넘는 문자열은 int()가 ValueError를 내므로 변환 전에 걸러야 REPL이 죽지 않는다.
    if len(body) > _INT_MAX_DIGITS:
        raise NotIntegerError()
    number = int(text)
    if number < _INT_MIN or number > _INT_MAX:
        raise NotIntegerError()
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
        raise UnknownSubcommandError(sub, "CONFIG")
    if param.lower() != "maxmemory":
        raise UnsupportedError("CONFIG parameter", param)
    limit = _parse_int(value)
    if limit < 0:
        raise NotIntegerError()
    store.set_maxmemory(limit)
    return "OK"


def _cmd_info(store, args):
    if args and args[0].lower() != "memory":
        raise UnsupportedError("INFO section", args[0])
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


def _format_error(error):
    """사용자 오류를 화면 한 줄로 바꾼다. `(error) ` 접두어는 여기 한 곳에서만 붙인다."""
    return f"(error) {error}"


def _run(store, tokens):
    """명령 이름과 인자 개수를 확인하고 처리 함수를 부른다. 문제가 있으면 MiniRedisError를 던진다."""
    name = tokens[0]
    command = _COMMANDS.get(name.upper())
    if command is None:
        raise UnknownCommandError(name)
    args = tokens[1:]
    if len(args) < command.min_args or len(args) > command.max_args:
        raise WrongArgsError(name)
    return command.handler(store, args)


def execute(store, tokens):
    """명령 하나를 실행하고 출력 문자열(여러 줄 가능)을 돌려준다. 토큰이 없으면 빈 문자열."""
    if not tokens:
        return ""
    try:
        return _run(store, tokens)
    except MiniRedisError as error:
        return _format_error(error)


def _read_tokens(line):
    """입력 한 줄을 토큰으로 나눈다. UTF-8이 아니거나 따옴표가 맞지 않으면 MiniRedisError를 던진다."""
    try:
        line.encode("utf-8")
    except UnicodeEncodeError:
        # 잘못된 바이트는 짝 없는 서로게이트로 들어온다. 키·값 크기와 해시는 UTF-8 바이트로 계산하므로 줄째로 거절한다
        raise InvalidUTF8Error() from None
    return tokenize(line)


def repl(stdin=sys.stdin, stdout=sys.stdout, store=None):
    """프롬프트를 띄우고 한 줄씩 읽어 실행한다. 종료 코드 0을 돌려준다.

    `exit`/`quit`이면 `Bye`를 출력하고 끝낸다. EOF(Ctrl-D, 파이프 끝)와 Ctrl-C는
    줄바꿈만 출력하고 예외 없이 끝낸다. 빈 줄은 무시하고, UTF-8이 아닌 줄은 에러를 출력하고 넘어간다.
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
            tokens = _read_tokens(line)
        except MiniRedisError as error:
            stdout.write(_format_error(error) + "\n")
            continue
        if not tokens:
            continue
        if tokens[0].lower() in ("exit", "quit"):
            stdout.write("Bye\n")
            return 0
        stdout.write(execute(store, tokens) + "\n")


def main():
    """`python3 main.py`와 `python3 -m mini_redis`의 공통 진입점."""
    # 기본 설정(strict)이면 잘못된 바이트 하나에 readline()이 UnicodeDecodeError로 죽는다.
    # surrogateescape로 읽어 두면 repl이 그 줄만 에러로 처리하고 계속 진행한다.
    sys.stdin.reconfigure(errors="surrogateescape")
    return repl()
