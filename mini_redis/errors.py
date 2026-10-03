"""Mini Redis 전용 예외."""


class OOMError(Exception):
    """단일 엔트리(키 + 값)가 maxmemory보다 커서 저장할 수 없을 때 발생한다."""
