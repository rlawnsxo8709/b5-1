import unittest
from mini_redis.dlist import DoublyLinkedList

class TestDoublyLinkedList(unittest.TestCase):
    def test_insert_front_and_back_order(self):
        dl = DoublyLinkedList()
        dl.insert_back("b"); dl.insert_front("a"); dl.insert_back("c")
        self.assertEqual(list(dl), ["a", "b", "c"]); self.assertEqual(len(dl), 3)

    def test_remove_front_back_and_empty(self):
        dl = DoublyLinkedList()
        self.assertIsNone(dl.remove_front()); self.assertIsNone(dl.remove_back())
        for x in "abc": dl.insert_back(x)
        self.assertEqual(dl.remove_front(), "a"); self.assertEqual(dl.remove_back(), "c")
        self.assertEqual(list(dl), ["b"]); self.assertEqual(len(dl), 1)

    def test_remove_node_middle(self):
        dl = DoublyLinkedList(); dl.insert_back("a"); n = dl.insert_back("b"); dl.insert_back("c")
        self.assertEqual(dl.remove_node(n), "b"); self.assertEqual(list(dl), ["a", "c"])

    def test_move_to_front(self):
        dl = DoublyLinkedList(); dl.insert_back("a"); dl.insert_back("b"); n = dl.insert_back("c")
        dl.move_to_front(n); self.assertEqual(list(dl), ["c", "a", "b"])
        dl.move_to_front(n); self.assertEqual(list(dl), ["c", "a", "b"])  # 이미 앞이면 그대로

    def test_peek_back(self):
        dl = DoublyLinkedList(); self.assertIsNone(dl.peek_back())
        dl.insert_front("x"); dl.insert_front("y"); self.assertEqual(dl.peek_back(), "x")

    def test_node_fields(self):
        dl = DoublyLinkedList(); n = dl.insert_back("v")
        self.assertTrue(hasattr(n, "prev") and hasattr(n, "next") and hasattr(n, "data"))

    def test_remove_node_at_both_ends_and_only_node(self):
        dl = DoublyLinkedList()
        first = dl.insert_back("a"); dl.insert_back("b"); last = dl.insert_back("c")
        self.assertEqual(dl.remove_node(first), "a"); self.assertEqual(dl.remove_node(last), "c")
        self.assertEqual(list(dl), ["b"])
        only = dl.insert_front("x"); dl.remove_node(only); dl.remove_front()
        self.assertEqual(len(dl), 0); self.assertEqual(list(dl), [])

    def test_move_to_front_from_back_and_middle_keeps_links_consistent(self):
        dl = DoublyLinkedList()
        nodes = [dl.insert_back(x) for x in "abcd"]
        dl.move_to_front(nodes[3]); dl.move_to_front(nodes[1])
        self.assertEqual(list(dl), ["b", "d", "a", "c"])
        out = []
        while len(dl): out.append(dl.remove_back())   # 뒤에서부터 빼도 같은 순서여야 한다
        self.assertEqual(out, ["c", "a", "d", "b"])
