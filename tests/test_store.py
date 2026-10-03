import unittest
from mini_redis.store import MiniRedisStore
from mini_redis.errors import OOMError

class FakeClock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t

class TestStore(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(); self.s = MiniRedisStore(clock=self.clock)

    def test_basic_crud(self):
        s = self.s; s.set("a", "1")
        self.assertEqual(s.get("a"), "1"); self.assertEqual(s.exists("a"), 1)
        self.assertEqual(s.dbsize(), 1); self.assertEqual(s.delete("a"), 1)
        self.assertEqual(s.delete("a"), 0); self.assertIsNone(s.get("a")); self.assertEqual(s.exists("a"), 0)

    def test_mission_example_lru_eviction(self):
        s = self.s; s.set_maxmemory(30)
        s.set("user:1", "Alice"); s.set("user:2", "Bob"); s.set("user:3", "Charlie")
        self.assertIsNone(s.get("user:1"))
        self.assertEqual(s.info_memory(), (22, 30, 1))
        self.assertEqual(len(s.keys()), 2)

    def test_get_refreshes_lru(self):
        s = self.s; s.set_maxmemory(20)
        s.set("a", "123456789")      # 10
        s.set("b", "123456789")      # 20
        s.get("a")                   # 이제 b가 LRU
        s.set("c", "1")              # 22 > 20 → b 제거
        self.assertEqual(s.exists("b"), 0); self.assertEqual(s.exists("a"), 1)

    def test_single_entry_over_limit_is_oom_and_not_stored(self):
        s = self.s; s.set_maxmemory(5); s.set("k", "v")
        with self.assertRaises(OOMError): s.set("big", "123456")
        self.assertEqual(s.exists("big"), 0); self.assertEqual(s.get("k"), "v")

    def test_overwrite_keeps_just_written_key_and_resets_ttl(self):
        s = self.s; s.set_maxmemory(10); s.set("a", "1234"); s.expire("a", 100)
        s.set("a", "123456789")      # 10 바이트, 한도와 같음 → 제거 없음
        self.assertEqual(s.get("a"), "123456789"); self.assertEqual(s.ttl("a"), -1)
        self.assertEqual(s.info_memory()[0], 10)

    def test_used_memory_counts_utf8_bytes(self):
        self.s.set("키", "값값")      # 3 + 6
        self.assertEqual(self.s.info_memory()[0], 9)

    def test_ttl_and_expiry(self):
        s = self.s; s.set("t", "v")
        self.assertEqual(s.ttl("t"), -1); self.assertEqual(s.ttl("none"), -2)
        self.assertEqual(s.expire("t", 3), 1); self.assertEqual(s.ttl("t"), 3)
        self.clock.t += 0.5; self.assertEqual(s.ttl("t"), 2)
        self.clock.t += 3; self.assertIsNone(s.get("t")); self.assertEqual(s.ttl("t"), -2)

    def test_expire_missing_and_nonpositive(self):
        s = self.s; self.assertEqual(s.expire("nope", 10), 0)
        s.set("x", "1"); self.assertEqual(s.expire("x", 0), 1); self.assertEqual(s.exists("x"), 0)

    def test_expired_keys_excluded_from_dbsize_and_keys_and_memory(self):
        s = self.s; s.set("a", "1"); s.set("b", "2"); s.expire("a", 1)
        self.clock.t += 2
        self.assertEqual(s.dbsize(), 1); self.assertEqual(s.keys(), ["b"])
        self.assertEqual(s.info_memory()[0], 2)

    def test_expired_get_does_not_touch_lru(self):
        s = self.s; s.set("a", "1"); s.expire("a", 1); self.clock.t += 2
        self.assertIsNone(s.get("a")); self.assertEqual(s.dbsize(), 0)

    def test_delete_clears_ttl(self):
        s = self.s; s.set("a", "1"); s.expire("a", 5); s.delete("a"); s.set("a", "2")
        self.clock.t += 10; self.assertEqual(s.get("a"), "2")   # 예전 힙 엔트리가 새 키를 지우면 안 됨

    def test_lowering_maxmemory_evicts_immediately(self):
        s = self.s
        for k in ["a", "b", "c"]: s.set(k, "1234")               # 각 5, 합 15
        s.set_maxmemory(10)
        self.assertEqual(s.info_memory(), (10, 10, 1)); self.assertEqual(s.exists("a"), 0)

    def test_zero_maxmemory_is_unlimited(self):
        s = self.s; s.set_maxmemory(0)
        for i in range(50): s.set(f"k{i}", "x" * 10)
        self.assertEqual(s.dbsize(), 50)

    # --- 아래는 plan 테스트 외에 경계를 더 조인 케이스 ---

    def test_overwrite_on_full_memory_evicts_others_never_the_written_key(self):
        s = self.s; s.set_maxmemory(12)
        s.set("a", "1234"); s.set("b", "1234")                   # 각 5, 합 10
        s.set("a", "1234567890")                                 # a=11 → 합 16 > 12, LRU 꼬리 b 제거
        self.assertEqual(s.get("a"), "1234567890"); self.assertEqual(s.exists("b"), 0)
        self.assertEqual(s.info_memory(), (11, 12, 1))

    def test_oom_on_overwrite_keeps_old_value_and_ttl(self):
        s = self.s; s.set_maxmemory(6); s.set("k", "1234"); s.expire("k", 50)
        with self.assertRaises(OOMError): s.set("k", "1234567")  # 8 > 6
        self.assertEqual(s.get("k"), "1234"); self.assertEqual(s.ttl("k"), 50)
        self.assertEqual(s.info_memory(), (5, 6, 0))

    def test_eviction_goes_from_least_recently_used_in_order(self):
        s = self.s; s.set_maxmemory(15)
        for k in ["a", "b", "c"]: s.set(k, "1234")               # 각 5, 합 15
        s.get("a")                                               # LRU 순서: b, c, a
        s.set("d", "123456789")                                  # 11 → b, c 순서로 제거
        self.assertEqual(s.exists("b"), 0); self.assertEqual(s.exists("c"), 0)
        self.assertEqual(s.exists("a"), 1); self.assertEqual(s.exists("d"), 1)
        self.assertEqual(s.info_memory(), (15, 15, 2))

    def test_exists_and_missing_get_do_not_refresh_lru(self):
        s = self.s; s.set_maxmemory(10)
        s.set("a", "1234"); s.set("b", "1234")                   # LRU 꼬리 = a
        s.exists("a"); s.get("nope")
        s.set("c", "1234")                                       # 15 > 10 → a 제거(EXISTS는 갱신 안 함)
        self.assertEqual(s.exists("a"), 0); self.assertEqual(s.exists("b"), 1)

    def test_reexpire_uses_latest_deadline_not_stale_heap_entry(self):
        s = self.s; s.set("a", "1"); s.expire("a", 1); s.expire("a", 100)
        self.clock.t += 5
        self.assertEqual(s.get("a"), "1"); self.assertEqual(s.ttl("a"), 95)
        s.expire("a", 2); s.expire("a", 1000)                    # 짧게 줬다가 길게 연장
        self.clock.t += 10
        self.assertEqual(s.dbsize(), 1)

    def test_expire_then_shorter_expire_fires_at_new_deadline(self):
        s = self.s; s.set("a", "1"); s.expire("a", 100); s.expire("a", 1)
        self.clock.t += 2
        self.assertEqual(s.dbsize(), 0)

    def test_expired_keys_are_purged_before_live_keys_are_evicted(self):
        s = self.s; s.set_maxmemory(10)
        s.set("a", "1234"); s.set("b", "1234"); s.expire("b", 1)  # LRU 꼬리는 살아 있는 a, 만료되는 쪽은 b
        self.clock.t += 2
        s.set("c", "1234")                                        # b 가 만료로 먼저 정리돼야 a 가 억울하게 쫓겨나지 않는다
        self.assertEqual(s.exists("a"), 1); self.assertEqual(s.exists("c"), 1); self.assertEqual(s.exists("b"), 0)
        self.assertEqual(s.info_memory(), (10, 10, 0))            # 만료는 evicted_keys 에 세지 않는다

    def test_del_expired_key_returns_zero(self):
        s = self.s; s.set("a", "1"); s.expire("a", 1); self.clock.t += 2
        self.assertEqual(s.delete("a"), 0)

    def test_expire_on_expired_key_returns_zero(self):
        s = self.s; s.set("a", "1"); s.expire("a", 1); self.clock.t += 2
        self.assertEqual(s.expire("a", 10), 0)

    def test_ttl_floors_remaining_seconds(self):
        s = self.s; s.set("a", "1"); s.expire("a", 10)
        self.clock.t += 0.2; self.assertEqual(s.ttl("a"), 9)     # 9.8 → 9
        self.clock.t += 8.7; self.assertEqual(s.ttl("a"), 1)     # 1.1 → 1
        self.clock.t += 0.5; self.assertEqual(s.ttl("a"), 0)     # 0.6 → 0 (아직 만료 전)

    def test_used_memory_tracks_delete_and_overwrite(self):
        s = self.s
        s.set("ab", "cd"); s.set("e", "f")
        self.assertEqual(s.info_memory()[0], 6)
        s.set("ab", "c"); self.assertEqual(s.info_memory()[0], 5)
        s.delete("e"); self.assertEqual(s.info_memory()[0], 3)

    def test_negative_maxmemory_is_rejected(self):
        with self.assertRaises(ValueError): self.s.set_maxmemory(-1)

    def test_raising_maxmemory_back_to_zero_stops_eviction(self):
        s = self.s; s.set_maxmemory(5)
        s.set("a", "1234"); s.set_maxmemory(0)
        for i in range(10): s.set(f"k{i}", "1234567890")
        self.assertEqual(s.dbsize(), 11); self.assertEqual(s.info_memory()[2], 0)
