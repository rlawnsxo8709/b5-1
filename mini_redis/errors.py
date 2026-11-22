"""Mini Redis 오류 모음.

사용자에게 보여 줄 오류는 모두 `MiniRedisError`를 상속하고, `str(오류)`가 Redis 문구 그대로다.
역할은 셋으로 나눈다.

* 던지는 쪽(store, parser, cli의 처리 함수)은 무슨 일이 났는지만 알린다. 화면 형식은 모른다.
* 문구는 이 파일에만 있다.
* 화면에 `(error) <문구>`로 찍는 일은 cli가 한 곳에서 한다.
"""


class MiniRedisError(Exception):
    """사용자 오류의 공통 부모. cli는 이 타입 하나만 잡아 `(error) <문구>`로 출력한다."""


class UnknownCommandError(MiniRedisError):
    """명령 표에 없는 명령. 문구에는 사용자가 입력한 이름을 그대로 쓴다."""

    def __init__(self, name):
        super().__init__(f"ERR unknown command '{name}'")


class WrongArgsError(MiniRedisError):
    """명령 이름 뒤 인자 개수가 명령의 허용 범위 밖이다."""

    def __init__(self, name):
        super().__init__(f"ERR wrong number of arguments for '{name}' command")


class NotIntegerError(MiniRedisError):
    """정수 자리에 정수가 아니거나 64bit 범위 밖인 값, 또는 음수 maxmemory가 왔다."""

    def __init__(self):
        super().__init__("ERR value is not an integer or out of range")


class OOMError(MiniRedisError):
    """단일 엔트리(키 + 값)가 maxmemory보다 커서 저장할 수 없다. store가 던진다."""

    def __init__(self):
        super().__init__("OOM command not allowed when used_memory > 'maxmemory'")


class ParseError(MiniRedisError):
    """따옴표가 닫히지 않는 등 줄을 토큰으로 나눌 수 없다. `reason`은 Protocol error 뒤에 붙는 이유다."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(f"ERR Protocol error: {reason}")


class UnknownSubcommandError(MiniRedisError):
    """`CONFIG GET`처럼 지원하지 않는 하위 명령."""

    def __init__(self, sub, command):
        super().__init__(f"ERR unknown subcommand '{sub}' for '{command}' command")


class UnsupportedError(MiniRedisError):
    """지원하지 않는 CONFIG 항목이나 INFO 구역. `what`은 "CONFIG parameter", "INFO section"."""

    def __init__(self, what, value):
        super().__init__(f"ERR Unsupported {what}: {value}")


class InvalidUTF8Error(MiniRedisError):
    """입력 줄에 UTF-8로 인코딩할 수 없는 바이트가 있다."""

    def __init__(self):
        super().__init__("ERR invalid UTF-8 input")
