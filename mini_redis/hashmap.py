"""해시맵(체이닝 방식).

내장 `dict` 없이 `[None] * capacity` 고정 길이 배열을 버킷 테이블로 쓴다.
같은 버킷에 떨어진 키들은 이중 연결 리스트로 이어 붙인다(체이닝).
"""

from mini_redis.dlist import DoublyLinkedList

_FNV_OFFSET_BASIS = 2166136261
_FNV_PRIME = 16777619
_MASK_32 = 0xFFFFFFFF


def fnv1a_hash(key):
    """32bit FNV-1a 해시. 키를 UTF-8 바이트로 바꿔 한 바이트씩 섞는다.

    1. 해시를 offset basis로 시작한다.
    2. 바이트마다 XOR한 뒤 FNV prime을 곱한다(32bit로 자른다).
    XOR을 곱셈보다 먼저 하는 것이 FNV-1과 다른 점이며, 마지막 바이트까지 비트가 고르게 퍼진다.
    한글처럼 한 글자가 여러 바이트인 키도 바이트 단위로 처리하므로 결과가 항상 같다.
    """
    h = _FNV_OFFSET_BASIS
    for byte in key.encode("utf-8"):
        h ^= byte
        h = (h * _FNV_PRIME) & _MASK_32
    return h


class _Entry:
    """버킷 리스트에 들어가는 (key, value) 한 쌍."""

    __slots__ = ("key", "value")

    def __init__(self, key, value):
        self.key = key
        self.value = value


class HashMap:
    """문자열 키 해시맵. 로드 팩터가 0.75를 넘으면 버킷 수를 2배로 늘리고 재해시한다."""

    def __init__(self, capacity=8, hash_func=fnv1a_hash):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._capacity = capacity
        self._hash = hash_func
        self._buckets = [None] * capacity
        self._size = 0

    @property
    def capacity(self):
        return self._capacity

    def size(self):
        return self._size

    def _index(self, key):
        return self._hash(key) % self._capacity

    def _find_node(self, key):
        """키가 들어 있는 버킷 리스트 노드를 찾는다. 없으면 None. 평균 O(1)."""
        bucket = self._buckets[self._index(key)]
        if bucket is None:
            return None
        for node in bucket.iter_nodes():
            if node.data.key == key:
                return node
        return None

    def put(self, key, value):
        """키에 값을 저장한다. 이미 있으면 덮어쓴다."""
        node = self._find_node(key)
        if node is not None:
            node.data.value = value
            return
        self._insert_entry(self._buckets, self._capacity, _Entry(key, value))
        self._size += 1
        if self._size * 4 > self._capacity * 3:  # size / capacity > 0.75 를 정수로 비교
            self._resize(self._capacity * 2)

    def get(self, key, default=None):
        node = self._find_node(key)
        return default if node is None else node.data.value

    def contains(self, key):
        return self._find_node(key) is not None

    def remove(self, key):
        """키를 지우고 지웠으면 True, 없었으면 False를 돌려준다."""
        node = self._find_node(key)
        if node is None:
            return False
        self._buckets[self._index(key)].remove_node(node)
        self._size -= 1
        return True

    def keys(self):
        """모든 키를 리스트로 돌려준다. 순서는 버킷 순서이며 보장하지 않는다."""
        result = []
        for bucket in self._buckets:
            if bucket is not None:
                for entry in bucket:
                    result.append(entry.key)
        return result

    def _insert_entry(self, buckets, capacity, entry):
        """엔트리를 `buckets`의 알맞은 칸에 넣는다. 칸이 비어 있으면 그때 리스트를 만든다."""
        index = self._hash(entry.key) % capacity
        if buckets[index] is None:
            buckets[index] = DoublyLinkedList()
        buckets[index].insert_back(entry)

    def _resize(self, new_capacity):
        """버킷을 `new_capacity`로 새로 만들고 모든 엔트리를 다시 배치한다.

        인덱스는 `hash % capacity`라서 capacity가 바뀌면 같은 키도 다른 칸으로 가야 한다.
        """
        new_buckets = [None] * new_capacity
        for bucket in self._buckets:
            if bucket is not None:
                for entry in bucket:
                    self._insert_entry(new_buckets, new_capacity, entry)
        self._buckets = new_buckets
        self._capacity = new_capacity
