"""최소 힙.

완전 이진 트리를 배열(리스트)로 표현한다. 인덱스 i의 부모는 (i - 1) // 2,
자식은 2i + 1, 2i + 2다. 루트(인덱스 0)가 항상 최솟값이라 TTL 만료가 가장 빠른 키를
O(1)로 확인(peek)하고 O(log n)으로 꺼낸다(pop).
"""


class MinHeap:
    """비교 가능한 원소를 담는 최소 힙. TTL에서는 (expire_at, key) 튜플을 넣는다."""

    def __init__(self):
        self._items = []

    def size(self):
        return len(self._items)

    def push(self, item):
        """원소를 넣는다. 맨 끝에 붙인 뒤 부모보다 작으면 올려 보낸다. O(log n)"""
        self._items.append(item)
        self._heapify_up(len(self._items) - 1)

    def peek(self):
        """최솟값을 제거 없이 돌려준다. 비었으면 None. O(1)"""
        if not self._items:
            return None
        return self._items[0]

    def pop(self):
        """최솟값을 제거하고 돌려준다. 비었으면 None. O(log n)

        마지막 원소를 루트로 옮긴 뒤 자식보다 크면 내려 보낸다.
        """
        if not self._items:
            return None
        top = self._items[0]
        last = self._items.pop()
        if self._items:
            self._items[0] = last
            self._heapify_down(0)
        return top

    def _heapify_up(self, i):
        """i번 원소를 부모와 비교하며 제자리까지 올린다."""
        items = self._items
        while i > 0:
            parent = (i - 1) // 2
            if items[i] >= items[parent]:
                break
            items[i], items[parent] = items[parent], items[i]
            i = parent

    def _heapify_down(self, i):
        """i번 원소를 더 작은 자식과 비교하며 제자리까지 내린다."""
        items = self._items
        n = len(items)
        while True:
            left = 2 * i + 1
            right = left + 1
            smallest = i
            if left < n and items[left] < items[smallest]:
                smallest = left
            if right < n and items[right] < items[smallest]:
                smallest = right
            if smallest == i:
                break
            items[i], items[smallest] = items[smallest], items[i]
            i = smallest
