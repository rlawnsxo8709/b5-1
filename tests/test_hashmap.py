import unittest
from mini_redis.hashmap import HashMap, fnv1a_hash

class TestHashMap(unittest.TestCase):
    def test_put_get_overwrite(self):
        m = HashMap(); m.put("a", 1); m.put("a", 2)
        self.assertEqual(m.get("a"), 2); self.assertEqual(m.size(), 1)
        self.assertIsNone(m.get("zz")); self.assertEqual(m.get("zz", -1), -1)

    def test_remove_and_contains(self):
        m = HashMap(); m.put("k", "v")
        self.assertTrue(m.contains("k")); self.assertTrue(m.remove("k"))
        self.assertFalse(m.contains("k")); self.assertFalse(m.remove("k")); self.assertEqual(m.size(), 0)

    def test_collisions_are_chained(self):
        m = HashMap(capacity=8, hash_func=lambda k: 7)   # 모든 키가 같은 버킷
        for i in range(5): m.put(f"k{i}", i)
        for i in range(5): self.assertEqual(m.get(f"k{i}"), i)
        m.remove("k2"); self.assertFalse(m.contains("k2")); self.assertEqual(m.get("k4"), 4)

    def test_resize_doubles_when_load_factor_exceeds_075(self):
        m = HashMap(capacity=8)
        for i in range(6): m.put(f"k{i}", i)          # 6/8 = 0.75 → 아직 확장 안 함
        self.assertEqual(m.capacity, 8)
        m.put("k6", 6)                                 # 7/8 > 0.75 → 16
        self.assertEqual(m.capacity, 16)
        for i in range(7): self.assertEqual(m.get(f"k{i}"), i)

    def test_keys_returns_all(self):
        m = HashMap()
        for k in ["x", "y", "z"]: m.put(k, 0)
        got = m.keys(); self.assertEqual(len(got), 3)
        for k in ["x", "y", "z"]: self.assertIn(k, got)

    def test_hash_is_deterministic_and_handles_unicode(self):
        self.assertEqual(fnv1a_hash("사과"), fnv1a_hash("사과"))
        self.assertNotEqual(fnv1a_hash("a"), fnv1a_hash("b"))
        self.assertTrue(0 <= fnv1a_hash("키") < 2**32)

    def test_fnv1a_known_vectors(self):
        # FNV-1a 32bit 공개 테스트 벡터: 빈 문자열은 offset basis 그대로
        self.assertEqual(fnv1a_hash(""), 0x811C9DC5)
        self.assertEqual(fnv1a_hash("a"), 0xE40C292C)
        self.assertEqual(fnv1a_hash("foobar"), 0xBF9CF968)

    def test_overwrite_does_not_grow_or_resize(self):
        m = HashMap(capacity=8)
        for i in range(6): m.put(f"k{i}", i)
        for _ in range(20): m.put("k0", 99)
        self.assertEqual(m.size(), 6); self.assertEqual(m.capacity, 8); self.assertEqual(m.get("k0"), 99)

    def test_many_keys_survive_repeated_resizes_and_removals(self):
        m = HashMap(capacity=2)
        for i in range(500): m.put(f"key:{i}", i)
        self.assertEqual(m.size(), 500)
        self.assertTrue(m.size() / m.capacity <= 0.75)
        for i in range(0, 500, 2): self.assertTrue(m.remove(f"key:{i}"))
        self.assertEqual(m.size(), 250)
        for i in range(500): self.assertEqual(m.contains(f"key:{i}"), i % 2 == 1)
        self.assertEqual(len(m.keys()), 250)

    def test_value_none_is_distinguished_from_missing(self):
        m = HashMap(); m.put("n", None)
        self.assertTrue(m.contains("n")); self.assertEqual(m.get("n", "default"), None)
