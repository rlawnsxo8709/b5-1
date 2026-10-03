"""이중 연결 리스트.

LRU 순서와 해시맵 버킷에 함께 쓰인다. 센티넬(더미) head/tail 노드를 두어
"비어 있음", "맨 앞", "맨 뒤"를 따로 처리하는 분기를 없앴고,
모든 삽입·삭제·이동이 O(1)이다.
"""


class Node:
    """리스트 노드. `data`는 사용자가 넣은 값이고 `prev`/`next`는 이웃 노드다."""

    __slots__ = ("prev", "next", "data")

    def __init__(self, data):
        self.prev = None
        self.next = None
        self.data = data


class DoublyLinkedList:
    """센티넬 기반 이중 연결 리스트. front가 앞(최근), back이 뒤(오래됨)다."""

    def __init__(self):
        self._head = Node(None)
        self._tail = Node(None)
        self._head.next = self._tail
        self._tail.prev = self._head
        self._size = 0

    def _link_after(self, left, node):
        """`left` 바로 뒤에 `node`를 끼워 넣는다."""
        right = left.next
        node.prev = left
        node.next = right
        left.next = node
        right.prev = node

    def _unlink(self, node):
        """`node`를 이웃에서 떼어낸다. 크기는 호출한 쪽이 관리한다."""
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = None
        node.next = None

    def insert_front(self, data):
        """맨 앞에 넣고 만들어진 노드를 돌려준다. O(1)"""
        node = Node(data)
        self._link_after(self._head, node)
        self._size += 1
        return node

    def insert_back(self, data):
        """맨 뒤에 넣고 만들어진 노드를 돌려준다. O(1)"""
        node = Node(data)
        self._link_after(self._tail.prev, node)
        self._size += 1
        return node

    def remove_node(self, node):
        """노드 참조만으로 그 노드를 제거하고 data를 돌려준다. O(1)

        이중 연결이라 앞 노드를 찾으려고 순회할 필요가 없다. 이것이 O(1) LRU의 핵심이다.
        """
        self._unlink(node)
        self._size -= 1
        return node.data

    def remove_front(self):
        """맨 앞 노드를 제거하고 data를 돌려준다. 비었으면 None. O(1)"""
        if self._size == 0:
            return None
        return self.remove_node(self._head.next)

    def remove_back(self):
        """맨 뒤 노드를 제거하고 data를 돌려준다. 비었으면 None. O(1)"""
        if self._size == 0:
            return None
        return self.remove_node(self._tail.prev)

    def move_to_front(self, node):
        """노드를 맨 앞으로 옮긴다. 이미 맨 앞이면 아무것도 하지 않는다. O(1)"""
        if node.prev is self._head:
            return
        self._unlink(node)
        self._link_after(self._head, node)

    def peek_back(self):
        """맨 뒤 data를 제거 없이 본다. 비었으면 None. LRU 후보 확인용이다. O(1)"""
        if self._size == 0:
            return None
        return self._tail.prev.data

    def iter_nodes(self):
        """앞에서 뒤로 노드를 하나씩 내보낸다.

        해시맵이 버킷 안에서 키를 찾은 뒤 `remove_node`로 지울 때 노드 참조가 필요해서 둔다.
        순회 중에 현재 노드를 제거해도 안전하도록 다음 노드를 미리 잡아 둔다.
        """
        node = self._head.next
        while node is not self._tail:
            following = node.next
            yield node
            node = following

    def __len__(self):
        return self._size

    def __iter__(self):
        """앞에서 뒤로 data를 하나씩 내보낸다."""
        for node in self.iter_nodes():
            yield node.data
