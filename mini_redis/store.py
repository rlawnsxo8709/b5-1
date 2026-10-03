"""저장소 엔진: 해시맵 + 이중 연결 리스트(LRU) + 최소 힙(TTL).

세 자료구조가 역할을 나눈다.

* `_data`(HashMap): 키 → `_Entry`. 키로 엔트리를 O(1)에 찾는다.
* `_lru`(DoublyLinkedList): 앞이 최근 사용, 뒤가 가장 오래 쓰지 않은 키.
  엔트리가 자기 노드를 들고 있어서 "찾기(해시) + 앞으로 옮기기(리스트)"가 모두 O(1)이다.
* `_ttl_heap`(MinHeap): `(expire_at, key)`. 가장 빨리 만료될 키가 항상 루트에 있다.
"""

import math
import time

from mini_redis.dlist import DoublyLinkedList
from mini_redis.errors import OOMError
from mini_redis.hashmap import HashMap
from mini_redis.minheap import MinHeap


class _Entry:
    """저장된 키 하나의 모든 부가 정보."""

    __slots__ = ("key", "value", "size", "node", "expire_at")

    def __init__(self, key, value, size, node):
        self.key = key
        self.value = value
        self.size = size          # len(utf8(key)) + len(utf8(value)). used_memory 갱신에 그대로 쓴다.
        self.node = node          # `_lru`에서 이 키의 노드
        self.expire_at = None     # 만료 시각(epoch 초). None이면 만료 없음.


def _entry_size(key, value):
    """used_memory 공식: 키와 값의 UTF-8 바이트 길이 합. 자료구조 오버헤드는 제외한다."""
    return len(key.encode("utf-8")) + len(value.encode("utf-8"))


class MiniRedisStore:
    """LRU 제거와 TTL 만료를 지원하는 문자열 키-값 저장소.

    `clock`은 현재 시각(초)을 돌려주는 함수다. 테스트에서 가짜 시계를 넣어 시간을 조작한다.
    """

    def __init__(self, clock=time.time):
        self._clock = clock
        self._data = HashMap()
        self._lru = DoublyLinkedList()
        self._ttl_heap = MinHeap()
        self._maxmemory = 0       # 0은 무제한
        self._used_memory = 0
        self._evicted_keys = 0

    # ---- 내부 도우미 ----

    def _remove_entry(self, entry):
        """데이터·LRU 구조에서 엔트리를 지우고 used_memory를 되돌린다.

        TTL 힙의 해당 기록은 건드리지 않는다(lazy deletion). 힙에서 꺼낼 때
        "엔트리가 없거나 expire_at이 다르면 낡은 기록"으로 보고 버린다.
        """
        self._lru.remove_node(entry.node)
        self._data.remove(entry.key)
        self._used_memory -= entry.size

    def _is_expired(self, entry):
        return entry.expire_at is not None and self._clock() >= entry.expire_at

    def _purge_if_expired(self, key):
        """키 기반 명령 전에 호출한다. 만료됐으면 지워서 '없는 키'로 만든다."""
        entry = self._data.get(key)
        if entry is not None and self._is_expired(entry):
            self._remove_entry(entry)

    def _purge_expired_all(self):
        """힙 루트부터 보며 만료된 키를 모두 지운다. 만료가 없으면 루트만 보고 끝난다(O(1))."""
        while True:
            top = self._ttl_heap.peek()
            if top is None:
                return
            expire_at, key = top
            entry = self._data.get(key)
            if entry is None or entry.expire_at != expire_at:
                self._ttl_heap.pop()                 # 낡은 기록: 삭제됐거나 TTL이 바뀌었다
            elif self._clock() >= expire_at:
                self._ttl_heap.pop()
                self._remove_entry(entry)
            else:
                return                               # 가장 빠른 유효 만료가 아직 미래다

    def _evict_until_fit(self):
        """used_memory가 maxmemory 이하가 될 때까지 LRU 꼬리부터 제거한다."""
        if self._maxmemory == 0:
            return
        self._purge_expired_all()                    # 이미 만료된 키를 두고 살아 있는 키를 쫓아내지 않는다
        while self._used_memory > self._maxmemory:
            key = self._lru.peek_back()
            if key is None:
                return
            self._remove_entry(self._data.get(key))
            self._evicted_keys += 1

    # ---- String 명령 ----

    def set(self, key, value):
        """키를 저장한다. 이미 있으면 덮어쓰고 TTL을 없앤다.

        엔트리 하나가 maxmemory보다 크면 OOMError를 내고 기존 상태를 그대로 둔다.
        방금 쓴 키는 LRU 맨 앞에 있고 단일 크기가 한도 이하이므로 제거 대상이 되지 않는다.
        """
        self._purge_if_expired(key)
        size = _entry_size(key, value)
        if self._maxmemory > 0 and size > self._maxmemory:
            raise OOMError()
        entry = self._data.get(key)
        if entry is None:
            node = self._lru.insert_front(key)
            self._data.put(key, _Entry(key, value, size, node))
        else:
            self._used_memory -= entry.size
            entry.value = value
            entry.size = size
            entry.expire_at = None
            self._lru.move_to_front(entry.node)
        self._used_memory += size
        self._evict_until_fit()

    def get(self, key):
        """값을 돌려준다. 없거나 만료됐으면 None. 값을 돌려줄 때만 LRU를 갱신한다."""
        self._purge_if_expired(key)
        entry = self._data.get(key)
        if entry is None:
            return None
        self._lru.move_to_front(entry.node)
        return entry.value

    def delete(self, key):
        """키를 지운다. 지웠으면 1, 없었으면 0."""
        self._purge_if_expired(key)
        entry = self._data.get(key)
        if entry is None:
            return 0
        self._remove_entry(entry)
        return 1

    def exists(self, key):
        """키가 있으면 1, 없으면 0. LRU는 갱신하지 않는다."""
        self._purge_if_expired(key)
        return 1 if self._data.contains(key) else 0

    def dbsize(self):
        self._purge_expired_all()
        return self._data.size()

    def keys(self):
        self._purge_expired_all()
        return self._data.keys()

    # ---- 메모리 ----

    def set_maxmemory(self, n):
        """메모리 한도를 바꾼다(0은 무제한). 한도를 낮추면 그 즉시 LRU 제거로 맞춘다."""
        if n < 0:
            raise ValueError("maxmemory must be >= 0")
        self._maxmemory = n
        self._evict_until_fit()

    def info_memory(self):
        """(used_memory, maxmemory, evicted_keys). 만료된 키는 먼저 정리해서 반영한다."""
        self._purge_expired_all()
        return (self._used_memory, self._maxmemory, self._evicted_keys)

    # ---- TTL ----

    def expire(self, key, seconds):
        """만료 시간을 설정한다. 키가 없으면 0, 설정(또는 즉시 삭제)하면 1.

        기존 TTL이 있어도 새 기록만 힙에 더 넣는다. 예전 기록은 expire_at이 달라서
        꺼낼 때 낡은 것으로 걸러진다.
        """
        self._purge_if_expired(key)
        entry = self._data.get(key)
        if entry is None:
            return 0
        if seconds <= 0:
            self._remove_entry(entry)
            return 1
        entry.expire_at = self._clock() + seconds
        self._ttl_heap.push((entry.expire_at, key))
        return 1

    def ttl(self, key):
        """없는 키 -2, 만료 없음 -1, 아니면 남은 초(내림)."""
        self._purge_if_expired(key)
        entry = self._data.get(key)
        if entry is None:
            return -2
        if entry.expire_at is None:
            return -1
        return math.floor(entry.expire_at - self._clock())
