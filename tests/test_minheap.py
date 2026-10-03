import unittest
from mini_redis.minheap import MinHeap

class TestMinHeap(unittest.TestCase):
    def test_pop_returns_ascending(self):
        h = MinHeap()
        for x in [5, 3, 8, 1, 9, 2, 2]: h.push(x)
        out = []
        while h.size(): out.append(h.pop())
        self.assertEqual(out, [1, 2, 2, 3, 5, 8, 9])

    def test_empty(self):
        h = MinHeap(); self.assertIsNone(h.pop()); self.assertIsNone(h.peek()); self.assertEqual(h.size(), 0)

    def test_peek_does_not_remove(self):
        h = MinHeap(); h.push(4); h.push(1)
        self.assertEqual(h.peek(), 1); self.assertEqual(h.size(), 2)

    def test_tuple_expire_at_key(self):
        h = MinHeap(); h.push((30.0, "b")); h.push((10.0, "a")); h.push((10.0, "0"))
        self.assertEqual(h.pop(), (10.0, "0")); self.assertEqual(h.pop(), (10.0, "a")); self.assertEqual(h.pop(), (30.0, "b"))

    def test_has_heapify_helpers(self):
        h = MinHeap()
        self.assertTrue(callable(h._heapify_up) and callable(h._heapify_down))

    def test_matches_sorted_order_on_pseudo_random_input(self):
        values = []
        x = 12345
        for _ in range(300):
            x = (x * 1103515245 + 12345) % 2147483648   # 결정적인 의사 난수
            values.append(x % 1000)
        h = MinHeap(); smallest = None
        for v in values:
            h.push(v)
            smallest = v if smallest is None else min(smallest, v)
            self.assertEqual(h.peek(), smallest)         # 매 삽입 후 루트가 최솟값
        out = []
        while h.size(): out.append(h.pop())
        self.assertEqual(out, sorted(values))

    def test_interleaved_push_and_pop(self):
        h = MinHeap()
        h.push(5); h.push(2); self.assertEqual(h.pop(), 2)
        h.push(1); h.push(7); self.assertEqual(h.pop(), 1)
        self.assertEqual(h.pop(), 5); self.assertEqual(h.pop(), 7); self.assertIsNone(h.pop())
