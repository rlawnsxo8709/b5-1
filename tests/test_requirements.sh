#!/usr/bin/env bash
# 미션 문서 「기능 요구 사항」 1~5절을 항목 순서대로 실제로 돌려 확인한다.
# 시험 이름 앞 번호(1-1, 2-3 …)는 그 절과 항목 순서다.
# 자료구조(1절)는 모듈을 직접 불러 확인하고, 명령(2~5절)은 `python3 main.py`에 명령을 파이프로 넣어 출력을 비교한다.
# 실행: bash tests/test_requirements.sh   (TTL 만료를 실제로 기다려서 4초쯤 걸린다)
# 다른 인터프리터: PYTHON=python3.12 bash tests/test_requirements.sh
set -u
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
PASS=0
FAIL=0

# REPL 출력에서 프롬프트를 줄바꿈으로 바꾸고 빈 줄을 지워, 명령 하나의 결과가 한 줄(KEYS·INFO는 여러 줄)이 되게 한다.
repl() {
  "$PYTHON" main.py | awk '{ gsub(/mini-redis> /, "\n"); print }' | grep -v '^$'
}

# 파이썬 코드 조각을 저장소 루트 기준으로 실행한다.
py() {
  "$PYTHON" -I -c "import sys; sys.path.insert(0, '.')
$1" 2>&1
}

# check 이름 실제출력 기대출력
check() {
  if [ "$2" == "$3" ]; then
    echo "PASS  $1"
    PASS=$((PASS + 1))
  else
    echo "FAIL  $1  (- 기대, + 실제)"
    diff <(printf '%s\n' "$3") <(printf '%s\n' "$2") | grep '^[<>]' | sed 's/^</  -/; s/^>/  +/'
    FAIL=$((FAIL + 1))
  fi
}

echo "== 1. 기본 자료구조 직접 구현 (내장 Key-Value 컬렉션으로 대체 금지)"

actual=$(py 'from mini_redis.dlist import Node
print(Node.__slots__)')
check "1-1 이중 연결 리스트: 노드 구조 prev / next / data" "$actual" "('prev', 'next', 'data')"

actual=$(py 'from mini_redis.dlist import DoublyLinkedList
l = DoublyLinkedList()
a = l.insert_back("a"); b = l.insert_back("b"); c = l.insert_front("c")
print("insert_front/insert_back:", list(l))
l.move_to_front(b); print("move_to_front(b):", list(l))
print("remove_node(c):", l.remove_node(c), list(l))
print("remove_front:", l.remove_front(), "remove_back:", l.remove_back(), "len:", len(l))
print("빈 리스트 remove_front:", l.remove_front(), "remove_back:", l.remove_back())')
check "1-1 이중 연결 리스트: insert_front / insert_back / remove_front / remove_back / remove_node / move_to_front" "$actual" "insert_front/insert_back: ['c', 'a', 'b']
move_to_front(b): ['b', 'c', 'a']
remove_node(c): c ['b', 'a']
remove_front: b remove_back: a len: 0
빈 리스트 remove_front: None remove_back: None"

actual=$(py 'import ast
tree = ast.parse(open("mini_redis/dlist.py", encoding="utf-8").read())
cls = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DoublyLinkedList"][0]
names = ("_link_after", "_unlink", "insert_front", "insert_back", "remove_front", "remove_back", "remove_node", "move_to_front")
for fn in cls.body:
    if isinstance(fn, ast.FunctionDef) and fn.name in names:
        loops = sum(isinstance(x, (ast.For, ast.While)) for x in ast.walk(fn))
        print(fn.name, "반복문", loops)')
check "1-1 이중 연결 리스트: 삽입/삭제/이동 O(1) (메서드 안에 반복문 없음)" "$actual" "_link_after 반복문 0
_unlink 반복문 0
insert_front 반복문 0
insert_back 반복문 0
remove_node 반복문 0
remove_front 반복문 0
remove_back 반복문 0
move_to_front 반복문 0"

actual=$(py 'from mini_redis.hashmap import HashMap
m = HashMap()
m.put("a", 1); m.put("b", 2); m.put("a", 3)
print("get(a):", m.get("a"), "contains(b):", m.contains("b"), "size:", m.size(), "keys:", sorted(m.keys()))
print("remove(b):", m.remove("b"), "다시 remove(b):", m.remove("b"), "contains(b):", m.contains("b"), "get(b):", m.get("b"), "size:", m.size())')
check "1-2 해시맵: put / get / remove / contains / keys / size" "$actual" "get(a): 3 contains(b): True size: 2 keys: ['a', 'b']
remove(b): True 다시 remove(b): False contains(b): False get(b): None size: 1"

actual=$(py 'from mini_redis.hashmap import HashMap, fnv1a_hash
print("fnv1a_hash(user:1):", fnv1a_hash("user:1"), "fnv1a_hash(키):", fnv1a_hash("키"))
print("HashMap 기본 해시 함수가 fnv1a_hash:", HashMap()._hash is fnv1a_hash)')
check "1-2 해시맵: 해시 함수 직접 설계 (32bit FNV-1a, 같은 키는 늘 같은 값)" "$actual" "fnv1a_hash(user:1): 1830439627 fnv1a_hash(키): 2650650782
HashMap 기본 해시 함수가 fnv1a_hash: True"

actual=$(py 'from mini_redis.hashmap import HashMap, fnv1a_hash
from mini_redis.dlist import DoublyLinkedList
m = HashMap()
m.put("user:2", "Bob"); m.put("키", "값")
i, j = fnv1a_hash("user:2") % 8, fnv1a_hash("키") % 8
bucket = m._buckets[i]
print("칸:", i, j, "버킷 종류:", type(bucket).__name__, "버킷 안 키 수:", len(bucket))
print("get:", m.get("user:2"), m.get("키"))')
check "1-2 해시맵: 충돌 해결은 체이닝 (같은 칸 = 이중 연결 리스트에 이어 붙임)" "$actual" "칸: 6 6 버킷 종류: DoublyLinkedList 버킷 안 키 수: 2
get: Bob 값"

actual=$(py 'from mini_redis.hashmap import HashMap
m = HashMap()
prev = m.capacity
for n in range(1, 26):
    m.put("k%d" % n, n)
    if m.capacity != prev:
        print("%d번째 키(로드 팩터 %d/%d)에서 %d -> %d" % (n, n, prev, prev, m.capacity)); prev = m.capacity
print("확장 뒤 모든 키 조회:", all(m.get("k%d" % n) == n for n in range(1, 26)), "size:", m.size())')
check "1-2 해시맵: 로드 팩터 0.75 초과 시 버킷 2배 확장" "$actual" "7번째 키(로드 팩터 7/8)에서 8 -> 16
13번째 키(로드 팩터 13/16)에서 16 -> 32
25번째 키(로드 팩터 25/32)에서 32 -> 64
확장 뒤 모든 키 조회: True size: 25"

actual=$(py 'from mini_redis.minheap import MinHeap
h = MinHeap()
print("_heapify_up/_heapify_down 있음:", callable(h._heapify_up), callable(h._heapify_down))
for item in [(30.0, "c"), (10.0, "a"), (20.0, "b"), (5.0, "z"), (10.0, "0")]:
    h.push(item)
print("size:", h.size(), "peek:", h.peek())
print("pop 순서:", [h.pop() for _ in range(5)])
print("빈 힙 pop:", h.pop(), "peek:", h.peek(), "size:", h.size())')
check "1-3 최소 힙: push / pop / peek / size, _heapify_up / _heapify_down, (expire_at, key) 원소" "$actual" "_heapify_up/_heapify_down 있음: True True
size: 5 peek: (5.0, 'z')
pop 순서: [(5.0, 'z'), (10.0, '0'), (10.0, 'a'), (20.0, 'b'), (30.0, 'c')]
빈 힙 pop: None peek: None size: 0"

if out=$("$PYTHON" -m unittest -q tests.test_constraints 2>&1); then actual=ok; else actual=$out; fi
check "1. 내장 Key-Value 컬렉션 대체 금지 (dict / set / collections 0건, AST 검사)" "$actual" "ok"

echo "== 2. String 타입 명령어 (Redis 스타일 출력)"

actual=$({ printf '%s\n' 'SET a 1' 'SET b 2' 'EXPIRE a 1'; sleep 1.2
  printf '%s\n' 'GET a' 'EXISTS a' 'TTL a' 'DEL a' 'EXPIRE a 10' 'DBSIZE' 'KEYS' 'quit'; } | repl)
check "2-0 공통: 키 기반 명령 전 만료 확인 (만료된 키는 삭제 후 없는 키처럼)" "$actual" 'OK
OK
(integer) 1
(nil)
(integer) 0
(integer) -2
(integer) 0
(integer) 0
(integer) 1
1. "b"
Bye'

actual=$(printf '%s\n' 'SET k v' 'EXPIRE k 100' 'SET k v2' 'TTL k' 'GET k' \
  'CONFIG SET maxmemory 12' 'SET a 11111' 'SET b 22222' 'SET c 33333' 'KEYS' 'quit' | repl)
check "2-1 SET: 성공 시 OK, 덮어쓰면 기존 TTL 삭제, 메모리 초과 시 LRU 제거" "$actual" 'OK
(integer) 1
OK
(integer) -1
"v2"
OK
OK
OK
OK
1. "b"
2. "c"
Bye'

actual=$(printf '%s\n' 'GET nope' 'CONFIG SET maxmemory 30' 'SET user:1 "Alice"' 'SET user:2 "Bob"' 'GET user:1' 'GET nope' \
  'SET user:3 "Charlie"' 'KEYS' 'quit' | repl)
check "2-2 GET: 없으면 (nil), 있으면 \"value\", 반환 성공 시에만 LRU 갱신 (user:1 대신 user:2 제거)" "$actual" '(nil)
OK
OK
OK
"Alice"
(nil)
OK
1. "user:1"
2. "user:3"
Bye'

actual=$({ printf '%s\n' 'SET x 1' 'SET y 2' 'EXPIRE x 1'; sleep 1.2; printf '%s\n' 'GET x' 'DBSIZE' 'INFO memory' 'quit'; } | repl)
check "2-2 GET: 만료된 키는 (nil), 삭제되어 LRU에도 남지 않음" "$actual" 'OK
OK
(integer) 1
(nil)
(integer) 1
used_memory:2
maxmemory:0
evicted_keys:0
Bye'

actual=$(printf '%s\n' 'SET d v' 'EXPIRE d 50' 'DEL d' 'DEL d' 'TTL d' 'SET d v' 'TTL d' 'quit' | repl)
check "2-3 DEL: 삭제 (integer) 1, 없으면 (integer) 0, 다시 SET해도 예전 TTL 없음" "$actual" 'OK
(integer) 1
(integer) 1
(integer) 0
(integer) -2
OK
(integer) -1
Bye'

actual=$(py 'from mini_redis.store import MiniRedisStore
s = MiniRedisStore()
s.set("a", "1"); s.set("b", "2"); s.expire("a", 50)
print("DEL 전 데이터:", s._data.size(), "LRU:", len(s._lru), "TTL 힙:", s._ttl_heap.size())
s.delete("a")
print("DEL 후 데이터:", s._data.size(), "LRU:", len(s._lru), "TTL 힙(lazy):", s._ttl_heap.size())
s.dbsize()
print("힙 정리 후 TTL 힙:", s._ttl_heap.size())')
check "2-3 DEL: 데이터·LRU 구조에서 함께 제거, TTL 힙 기록은 다음 정리 때 제거" "$actual" "DEL 전 데이터: 2 LRU: 2 TTL 힙: 1
DEL 후 데이터: 1 LRU: 1 TTL 힙(lazy): 1
힙 정리 후 TTL 힙: 0"

actual=$(printf '%s\n' 'SET e 1' 'EXISTS e' 'EXISTS nope' 'quit' | repl)
check "2-4 EXISTS: 있으면 (integer) 1, 없으면 (integer) 0" "$actual" 'OK
(integer) 1
(integer) 0
Bye'

actual=$(printf '%s\n' 'DBSIZE' 'SET a 1' 'SET b 2' 'SET a 3' 'DBSIZE' 'quit' | repl)
check "2-5 DBSIZE: 저장된 키 개수 (integer) N" "$actual" '(integer) 0
OK
OK
OK
(integer) 2
Bye'

actual=$(printf '%s\n' 'KEYS' 'SET user:3 x' 'SET user:2 y' 'KEYS' 'quit' | repl)
check "2-6 KEYS: 배열 형태로 전체 키, 없으면 (empty array)" "$actual" '(empty array)
OK
OK
1. "user:2"
2. "user:3"
Bye'

echo "== 3. 메모리 관리 + LRU 자동 제거"

actual=$(printf '%s\n' 'CONFIG SET maxmemory 100' 'CONFIG SET maxmemory 0' 'SET big "this value is longer than one hundred bytes so it only fits when maxmemory is zero which means no limit at all"' \
  'EXISTS big' 'CONFIG SET maxmemory abc' 'CONFIG SET maxmemory -1' 'quit' | repl)
check "3-1 CONFIG SET maxmemory: 0 이상 정수, 0은 무제한, 성공 시 OK, 정수 오류는 표준 에러" "$actual" 'OK
OK
OK
(integer) 1
(error) ERR value is not an integer or out of range
(error) ERR value is not an integer or out of range
Bye'

actual=$(printf '%s\n' 'CONFIG SET maxmemory 30' 'SET user:1 "Alice"' 'INFO memory' 'quit' | repl)
check "3-2 INFO memory: used_memory / maxmemory / evicted_keys 3항목" "$actual" 'OK
OK
used_memory:11
maxmemory:30
evicted_keys:0
Bye'

actual=$(printf '%s\n' 'SET 키 "값"' 'INFO memory' 'SET user:1 "Alice"' 'INFO memory' 'SET user:1 "Al"' 'INFO memory' 'DEL 키' 'INFO memory' 'quit' | repl)
check "3-3 used_memory 공식: Σ(len(utf8(key)) + len(utf8(value))), 덮어쓰기·DEL 때 갱신" "$actual" 'OK
used_memory:6
maxmemory:0
evicted_keys:0
OK
used_memory:17
maxmemory:0
evicted_keys:0
OK
used_memory:14
maxmemory:0
evicted_keys:0
(integer) 1
used_memory:8
maxmemory:0
evicted_keys:0
Bye'

actual=$(printf '%s\n' 'CONFIG SET maxmemory 30' 'SET user:1 "Alice"' 'SET user:2 "Bob"' 'SET user:3 "Charlie"' \
  'GET user:1' 'INFO memory' 'KEYS' 'quit' | repl)
check "3-4 LRU 제거 규칙: SET 뒤 초과하면 LRU부터 제거, evicted_keys 누적 (미션 예시)" "$actual" 'OK
OK
OK
OK
(nil)
used_memory:22
maxmemory:30
evicted_keys:1
1. "user:2"
2. "user:3"
Bye'

actual=$(printf '%s\n' 'CONFIG SET maxmemory 15' 'SET a 1111' 'SET b 2222' 'SET c 3333' 'SET d 1234567890' 'KEYS' 'INFO memory' 'quit' | repl)
check "3-4 LRU 제거 규칙: maxmemory 이하가 될 때까지 여러 개 제거" "$actual" 'OK
OK
OK
OK
OK
1. "d"
used_memory:11
maxmemory:15
evicted_keys:3
Bye'

actual=$(printf '%s\n' 'CONFIG SET maxmemory 10' 'SET k v' 'SET bigkey "averyverylongvalue"' 'EXISTS bigkey' 'GET k' 'INFO memory' 'quit' | repl)
check "3-4 LRU 제거 규칙: 단일 엔트리가 maxmemory 초과면 저장하지 않고 OOM" "$actual" "OK
OK
(error) OOM command not allowed when used_memory > 'maxmemory'
(integer) 0
\"v\"
used_memory:2
maxmemory:10
evicted_keys:0
Bye"

echo "== 4. TTL 관리 (힙 기반)"

actual=$(printf '%s\n' 'EXPIRE nope 10' 'SET a 1' 'EXPIRE a 10' 'SET z 1' 'EXPIRE z 0' 'EXISTS z' 'SET m 1' 'EXPIRE m -5' 'GET m' 'quit' | repl)
check "4-1 EXPIRE: 없는 키 (integer) 0, 정상 설정 (integer) 1, 0 이하는 즉시 만료 (integer) 1" "$actual" '(integer) 0
OK
(integer) 1
OK
(integer) 1
(integer) 0
OK
(integer) 1
(nil)
Bye'

actual=$(printf '%s\n' 'TTL nope' 'SET plain x' 'TTL plain' 'SET user:2 "Bob"' 'EXPIRE user:2 3' 'TTL user:2' 'quit' | repl)
check "4-2 TTL: 없는 키 -2, 만료 없음 -1, 만료 있으면 남은 초 (EXPIRE 3 직후 2)" "$actual" '(integer) -2
OK
(integer) -1
OK
(integer) 1
(integer) 2
Bye'

actual=$({ printf '%s\n' 'SET user:2 "Bob"' 'EXPIRE user:2 1'; sleep 1.2; printf '%s\n' 'GET user:2' 'TTL user:2' 'quit'; } | repl)
check "4-3 엣지: 만료된 키는 GET 때 삭제 후 (nil), 이후 TTL -2" "$actual" 'OK
(integer) 1
(nil)
(integer) -2
Bye'

actual=$(printf '%s\n' 'SET k v' 'EXPIRE k 100' 'SET k v2' 'TTL k' 'EXPIRE ghost 5' 'SET d v' 'EXPIRE d 50' 'DEL d' 'TTL d' 'EXISTS d' 'quit' | repl)
check "4-3 엣지: SET 덮어쓰기는 TTL 초기화, 없는 키 EXPIRE는 0, DEL은 TTL까지 제거" "$actual" 'OK
(integer) 1
OK
(integer) -1
(integer) 0
OK
(integer) 1
(integer) 1
(integer) -2
(integer) 0
Bye'

actual=$(py 'from mini_redis.store import MiniRedisStore
now = [1000.0]
s = MiniRedisStore(clock=lambda: now[0])
for k in ("c", "a", "b"):
    s.set(k, "v")
s.expire("c", 30); s.expire("a", 10); s.expire("b", 20)
print("힙 루트(가장 빠른 만료):", s._ttl_heap.peek())
s.expire("a", 50)
now[0] = 1015.0
print("15초 뒤 남은 키:", sorted(s.keys()), "힙 루트:", s._ttl_heap.peek())
now[0] = 1031.0
print("31초 뒤 남은 키:", sorted(s.keys()), "a의 TTL:", s.ttl("a"))')
check "4-4 힙으로 가장 빠른 만료를 바로 찾음 (다시 EXPIRE한 예전 기록은 무시)" "$actual" "힙 루트(가장 빠른 만료): (1010.0, 'a')
15초 뒤 남은 키: ['a', 'b', 'c'] 힙 루트: (1020.0, 'b')
31초 뒤 남은 키: ['a'] a의 TTL: 19"

echo "== 5. 에러 처리 표준 + CLI 인터페이스"

actual=$(printf '%s\n' 'SET a 1' 'GET a' 'quit' | "$PYTHON" main.py)
check "5-1 CLI: mini-redis> 프롬프트, 입력을 읽어 파싱·실행을 반복" "$actual" 'mini-redis> OK
mini-redis> "1"
mini-redis> Bye'

actual=$( { printf '%s\n' 'exit' 'SET a 1' | "$PYTHON" main.py; echo " [exit $?]"; printf '%s\n' 'QUIT' | "$PYTHON" main.py; echo " [exit $?]"; } )
check "5-1 CLI: exit 또는 quit으로 종료 (종료 뒤 줄은 실행 안 함)" "$actual" 'mini-redis> Bye
 [exit 0]
mini-redis> Bye
 [exit 0]'

actual=$(printf '%s\n' 'HELLO' 'GET' 'SET onlykey' 'DBSIZE extra' 'EXPIRE k abc' 'CONFIG SET maxmemory 1.5' \
  'CONFIG SET maxmemory 5' 'SET longkey longvalue' 'quit' | repl)
check "5-2 에러 출력 표준: 잘못된 명령 / 인자 개수 / 정수 파싱 / OOM" "$actual" "(error) ERR unknown command 'HELLO'
(error) ERR wrong number of arguments for 'GET' command
(error) ERR wrong number of arguments for 'SET' command
(error) ERR wrong number of arguments for 'DBSIZE' command
(error) ERR value is not an integer or out of range
(error) ERR value is not an integer or out of range
OK
(error) OOM command not allowed when used_memory > 'maxmemory'
Bye"

actual=$(printf '%s\n' 'SET name "Alice"' 'GET name' 'SET plain Bob' 'GET plain' 'SET msg "hello world"' 'GET msg' 'SET bad "unclosed' 'GET plain' 'quit' | repl)
check "5-3 값 파싱: 큰따옴표 값, 공백 없는 값, 따옴표 안 공백 (닫히지 않은 따옴표는 에러 후 계속)" "$actual" 'OK
"Alice"
OK
"Bob"
OK
"hello world"
(error) ERR Protocol error: unbalanced quotes in request
"Bob"
Bye'

echo
echo "결과: PASS $PASS, FAIL $FAIL"
[ "$FAIL" -eq 0 ]
