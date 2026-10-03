"""입력 한 줄을 토큰 리스트로 나누는 파서."""


class ParseError(Exception):
    """따옴표가 닫히지 않는 등 줄을 토큰으로 나눌 수 없을 때 발생한다."""


def tokenize(line):
    """공백으로 토큰을 나눈다. 큰따옴표 안의 공백은 보존한다.

    * 큰따옴표는 토큰의 첫 글자일 때만 따옴표 시작으로 본다(`a"b`의 따옴표는 그냥 문자).
    * 따옴표 안에서 `\\"`는 `"`, `\\\\`는 `\\`로 바꾼다. 그 밖의 `\\x`는 해석하지 않고 그대로 둔다.
    * 닫는 따옴표 바로 뒤에는 공백이나 줄 끝만 올 수 있다. 따옴표가 닫히지 않으면 ParseError다.
    """
    tokens = []
    chars = []
    in_token = False      # 빈 문자열 토큰("")과 토큰 없음을 구분한다
    in_quote = False
    closed_quote = False  # 방금 닫는 따옴표를 읽었다: 다음은 공백이어야 한다
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if in_quote:
            if ch == "\\" and i + 1 < n and line[i + 1] in '"\\':
                chars.append(line[i + 1])
                i += 2
                continue
            if ch == '"':
                in_quote = False
                closed_quote = True
            else:
                chars.append(ch)
        elif ch.isspace():
            if in_token:
                tokens.append("".join(chars))
                chars = []
                in_token = False
                closed_quote = False
        elif closed_quote:
            raise ParseError("unbalanced quotes in request")
        elif ch == '"' and not in_token:
            in_token = True
            in_quote = True
        else:
            in_token = True
            chars.append(ch)
        i += 1
    if in_quote:
        raise ParseError("unbalanced quotes in request")
    if in_token:
        tokens.append("".join(chars))
    return tokens
