#!/usr/bin/env bash
# 미션 문서 「기능 요구 사항」 1~5절을 항목 순서대로 실제로 실행하고, 그 화면을 로그 파일에 남긴다.
# 사람이 로그를 읽고 요구 사항마다 실제 출력을 눈으로 확인하는 용도라서 기대값과 자동 비교하지 않는다.
#
# 실행: bash tests/test_requirements.sh   (TTL 만료를 실제로 기다려서 6초쯤 걸린다)
# 결과: tests/logs/requirements_<날짜-시각>.log
# 다른 인터프리터: PYTHON=python3.12 bash tests/test_requirements.sh
#
# 로그 읽는 법
#   [그룹] 요구 사항 문구   ← 미션 문서의 항목
#   mini-redis> 명령        ← Mini Redis에 넣은 명령, 다음 줄부터 실제 출력
#   >>> 코드                ← 자료구조 모듈을 직접 부른 파이썬 코드, 다음 줄이 결과
#   $ 명령                  ← 셸에서 실행한 명령, 다음 줄부터 실제 출력
#   # 설명                  ← 무엇을 보면 되는지, 기다린 시간
set -u
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
mkdir -p tests/logs
LOG="tests/logs/requirements_$(date +%Y%m%d-%H%M%S).log"
exec 3>"$LOG"
ITEMS=0
CMDS=0

log() { printf '%s\n' "$@" >&3; }
note() { log "# $*"; }
section() { log "" "" "==================== $1 ===================="; }
item() { ITEMS=$((ITEMS + 1)); log "" "[$1] $2"; }

# 명령을 차례로 REPL에 넣는다. "@sleep N"은 N초 기다린다.
feed() {
  local cmd
  for cmd in "$@"; do
    if [[ $cmd == "@sleep "* ]]; then sleep "${cmd#@sleep }"; else printf '%s\n' "$cmd"; fi
  done
}

# 명령들을 한 REPL 세션에서 실행하고 `mini-redis> 명령` 다음 줄에 그 명령의 실제 출력을 적는다.
# 파이프 입력은 화면에 다시 찍히지 않으므로, 출력을 프롬프트 단위로 잘라 명령과 순서대로 짝짓는다.
repl() {
  local cmd seg out k=1 sep=$'\x1e'
  local -a segs
  out=$(feed "$@" | "$PYTHON" main.py 2>&1; printf x)
  out=${out%x}
  out=${out//"mini-redis> "/$sep}
  IFS=$sep read -r -d '' -a segs <<< "$out" || true
  for cmd in "$@"; do
    if [[ $cmd == "@sleep "* ]]; then
      note "(${cmd#@sleep }초 기다림)"
      continue
    fi
    log "mini-redis> $cmd"
    seg=${segs[k]-}
    seg=${seg%$'\n'}
    [ -n "$seg" ] && log "$seg"
    k=$((k + 1))
    CMDS=$((CMDS + 1))
  done
}

# 파이썬 코드를 한 줄씩 실행하며 대화형 화면처럼 `>>> 코드`와 결과를 적는다.
PY_DRIVER='
import sys, traceback
sys.path.insert(0, ".")
ns = {}
for line in sys.argv[1:]:
    print(">>> " + line)
    try:
        try:
            code = compile(line, "<log>", "eval")
        except SyntaxError:
            exec(compile(line, "<log>", "exec"), ns)
        else:
            value = eval(code, ns)
            if value is not None:
                print(repr(value))
    except Exception:
        traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()
'
py() {
  "$PYTHON" -I -c "$PY_DRIVER" "$@" >&3 2>&1
  CMDS=$((CMDS + $#))
}

# 셸 명령을 실행하고 `$ 명령`과 출력을 적는다. 첫 인자는 로그에 보일 모습, 둘째 인자가 실제로 실행할 명령이다.
sh_run() {
  log "\$ $1"
  log "$(eval "$2" 2>&1)"
  CMDS=$((CMDS + 1))
}

log "B5-1 Mini Redis 기능 요구 사항 실행 로그"
log "실행 시각: $(date '+%Y-%m-%d %H:%M:%S %Z')"
log "환경: $("$PYTHON" --version 2>&1), $(uname -sr)"
log "기준: 미션 문서 「4. 기능 요구 사항」 1~5절 (금지 자료형은 「7. 제약 사항」)"
log "읽는 법: [그룹] 요구 사항 문구 아래에 실제로 넣은 명령과 출력을 화면 그대로 적었다."
log "         mini-redis> = Mini Redis 명령, >>> = 파이썬 코드, \$ = 셸 명령, # = 설명"

section "1. 기본 자료구조 직접 구현 (내장 Key-Value 컬렉션으로 대체 금지)"

item "이중 연결 리스트" "노드 구조: prev, next, data 필드"
py 'from mini_redis.dlist import Node' 'Node.__slots__' 'n = Node("user:1")' '(n.prev, n.next, n.data)'

item "이중 연결 리스트" "주요 메서드: insert_front, insert_back, remove_front, remove_back, remove_node, move_to_front"
note "list(l)은 앞(front)에서 뒤(back) 순서다."
py 'from mini_redis.dlist import DoublyLinkedList' 'l = DoublyLinkedList()' \
  'a = l.insert_back("a")' 'b = l.insert_back("b")' 'c = l.insert_front("c")' 'list(l)' \
  'l.move_to_front(b)' 'list(l)' 'l.remove_node(c)' 'list(l)' 'l.remove_front()' 'l.remove_back()' \
  '(len(l), l.remove_front(), l.remove_back())'

item "이중 연결 리스트" "모든 삽입/삭제/이동 연산은 O(1)"
note "메서드마다 반복문(for/while) 개수를 센다. 0이면 리스트 길이와 상관없이 이웃 포인터 몇 개만 바꾸고 끝난다."
py 'import ast, inspect' 'from mini_redis.dlist import DoublyLinkedList' \
  'tree = ast.parse(inspect.getsource(DoublyLinkedList))' \
  'names = ("_link_after", "_unlink", "insert_front", "insert_back", "remove_front", "remove_back", "remove_node", "move_to_front")' \
  '[(f.name, sum(isinstance(x, (ast.For, ast.While)) for x in ast.walk(f))) for f in tree.body[0].body if isinstance(f, ast.FunctionDef) and f.name in names]'

item "해시맵 (체이닝 방식)" "주요 메서드: put, get, remove, contains, keys, size"
note "put(\"a\", 3)은 덮어쓰기라 size가 늘지 않는다."
py 'from mini_redis.hashmap import HashMap' 'm = HashMap()' 'm.put("a", 1)' 'm.put("b", 2)' 'm.put("a", 3)' \
  '(m.get("a"), m.contains("b"), m.size(), sorted(m.keys()))' 'm.remove("b")' 'm.remove("b")' \
  '(m.contains("b"), m.get("b"), m.size())'

item "해시맵 (체이닝 방식)" "해시 함수는 직접 설계해야 한다"
note "32bit FNV-1a: 키를 UTF-8 바이트로 바꾸고, 2166136261에서 시작해 바이트마다 XOR 후 16777619를 곱해 32bit로 자른다. 칸 번호는 해시 % 버킷 수."
py 'from mini_redis.hashmap import HashMap, fnv1a_hash' 'list("user:1".encode("utf-8"))' 'fnv1a_hash("user:1")' \
  'fnv1a_hash("user:1") % 8' 'fnv1a_hash("키")' 'HashMap()._hash is fnv1a_hash'

item "해시맵 (체이닝 방식)" "충돌 해결은 체이닝 방식으로 구현 (이중 연결 리스트 재사용)"
note "user:2와 키는 버킷 8개일 때 둘 다 6번 칸이다. 6번 칸의 이중 연결 리스트에 두 키가 이어 붙고, 둘 다 조회된다."
py 'from mini_redis.hashmap import HashMap, fnv1a_hash' 'm = HashMap()' 'm.put("user:2", "Bob")' 'm.put("키", "값")' \
  '(fnv1a_hash("user:2") % m.capacity, fnv1a_hash("키") % m.capacity)' 'bucket = m._buckets[6]' \
  '(type(bucket).__name__, len(bucket), [entry.key for entry in bucket])' '(m.get("user:2"), m.get("키"))'

item "해시맵 (체이닝 방식)" "로드 팩터 0.75 초과 시 버킷을 2배 확장"
note "6/8 = 0.75는 초과가 아니라 그대로, 7번째 키(7/8)에서 16으로, 13번째 키(13/16)에서 32로 커진다. 확장 뒤에도 모든 키가 조회된다."
py 'from mini_redis.hashmap import HashMap' 'm = HashMap()' 'for i in range(1, 7): m.put("k%d" % i, i)' \
  '(m.size(), m.capacity)' 'm.put("k7", 7)' '(m.size(), m.capacity)' 'for i in range(8, 14): m.put("k%d" % i, i)' \
  '(m.size(), m.capacity)' 'all(m.get("k%d" % i) == i for i in range(1, 14))'

item "힙 (최소 힙)" "주요 메서드: push, pop, peek, size / _heapify_up, _heapify_down 구현"
note "_items는 완전 이진 트리를 담은 배열이다. 루트(0번)가 항상 최솟값이고, pop은 작은 순서로 나온다."
py 'from mini_redis.minheap import MinHeap' 'h = MinHeap()' 'for item in [30, 10, 20, 5, 15]: h.push(item)' \
  '(h.size(), h.peek())' 'h._items' '[h.pop() for _ in range(5)]' '(h.pop(), h.peek(), h.size())' \
  '(callable(h._heapify_up), callable(h._heapify_down))'

item "힙 (최소 힙)" "TTL 만료 관리를 위해 (expire_at, key) 형태의 요소를 다룰 수 있어야 한다"
note "튜플은 expire_at으로 먼저 비교하고, 같으면 key로 비교한다."
py 'from mini_redis.minheap import MinHeap' 'h = MinHeap()' \
  'for item in [(1030.0, "c"), (1010.0, "b"), (1020.0, "a"), (1010.0, "a")]: h.push(item)' \
  'h.peek()' '[h.pop() for _ in range(4)]'

item "제약 사항" "dict, set, collections 사용 금지 (내장 컬렉션으로 해시맵/캐시 대체 금지)"
note "tests/test_constraints.py가 mini_redis/*.py와 main.py를 AST로 파싱해 dict/set 리터럴·컴프리헨션, dict()/set()/frozenset() 호출, collections import를 센다."
sh_run "python3 -m unittest -v tests.test_constraints" '"$PYTHON" -m unittest -v tests.test_constraints'

section "2. String 타입 명령어 (Redis 스타일 출력)"

item "공통 규칙" "키 기반 명령어는 실행 전 만료 여부를 먼저 확인 (만료된 키는 삭제 후 없는 키처럼 처리)"
note "a에 1초 만료를 걸고 기다린 뒤 GET·EXISTS·TTL·DEL·EXPIRE 모두 a를 없는 키로 처리하는지 본다."
repl 'SET a 1' 'SET b 2' 'EXPIRE a 1' '@sleep 1.2' 'GET a' 'EXISTS a' 'TTL a' 'DEL a' 'EXPIRE a 10' 'DBSIZE' 'KEYS'

item "공통 규칙" "출력은 Redis 스타일: OK, (nil), (integer) N, (error) ..."
repl 'SET k v' 'GET nope' 'DBSIZE' 'GET k' 'HELLO'

item "SET key value" "성공 시 OK"
repl 'SET user:1 "Alice"' 'GET user:1'

item "SET key value" "메모리 초과 시 LRU 제거를 수행한다"
note "키마다 6바이트. c를 넣으면 18 > 12라 가장 오래 쓰지 않은 a를 지운다."
repl 'CONFIG SET maxmemory 12' 'SET a 11111' 'SET b 22222' 'SET c 33333' 'KEYS' 'INFO memory'

item "SET key value" "기존 키를 덮어쓰는 경우 기존 TTL은 초기화(삭제)"
repl 'SET k v' 'EXPIRE k 100' 'TTL k' 'SET k v2' 'TTL k' 'GET k'

item "GET key" "키가 없거나 만료된 경우 (nil)"
repl 'GET nope' 'SET x 1' 'EXPIRE x 1' '@sleep 1.2' 'GET x'

item "GET key" "존재하는 경우 \"value\" 형태로 반환"
repl 'SET user:1 "Alice"' 'GET user:1' 'SET msg "hello world"' 'GET msg'

item "GET key" "반환이 성공한 경우에만 LRU를 갱신 (만료로 삭제된 경우는 갱신하지 않음)"
note "maxmemory 30. GET user:1 성공으로 user:1이 최근 사용이 되고, 없는 키 GET은 아무것도 바꾸지 않는다. user:3을 넣어 초과하면 user:1 대신 user:2가 지워진다."
repl 'CONFIG SET maxmemory 30' 'SET user:1 "Alice"' 'SET user:2 "Bob"' 'GET user:1' 'GET nope' 'SET user:3 "Charlie"' 'KEYS'
note "만료된 키를 GET하면: 시계를 직접 넣은 저장소로 확인한다. list(s._lru)는 앞이 최근 사용이다. 만료된 old는 앞으로 오지 않고 LRU 리스트에서 빠진다."
py 'from mini_redis.store import MiniRedisStore' 'now = [1000.0]' 's = MiniRedisStore(clock=lambda: now[0])' \
  's.set("old", "1"); s.set("new", "2")' 's.expire("old", 5)' 'list(s._lru)' 'now[0] = 1006.0' 'print(s.get("old"))' 'list(s._lru)'

item "DEL key" "삭제 성공 시 (integer) 1, 없으면 (integer) 0"
repl 'SET d v' 'DEL d' 'DEL d' 'GET d'

item "DEL key" "삭제 시 LRU/TTL 관련 구조에서도 해당 엔트리를 함께 제거"
note "DEL 뒤 TTL이 -2이고, 같은 키를 다시 SET해도 예전 TTL이 남지 않는다(-1)."
repl 'SET d v' 'EXPIRE d 50' 'DEL d' 'TTL d' 'SET d v' 'TTL d'
note "내부 구조: (데이터 수, LRU 리스트, TTL 힙 크기). 힙의 a 기록은 lazy deletion이라 DEL 직후엔 남고, 다음 힙 정리(DBSIZE 등)에서 지워진다."
py 'from mini_redis.store import MiniRedisStore' 's = MiniRedisStore()' 's.set("a", "1"); s.set("b", "2"); s.expire("a", 50)' \
  '(s._data.size(), list(s._lru), s._ttl_heap.size())' 's.delete("a")' '(s._data.size(), list(s._lru), s._ttl_heap.size())' \
  's.dbsize()' 's._ttl_heap.size()'

item "EXISTS key" "존재하면 (integer) 1, 없으면 (integer) 0"
repl 'SET e 1' 'EXISTS e' 'EXISTS nope'

item "DBSIZE" "현재 저장된 키 개수를 (integer) N 으로 반환"
note "a를 덮어써도 키는 2개다."
repl 'DBSIZE' 'SET a 1' 'SET b 2' 'SET a 3' 'DBSIZE'

item "KEYS" "전체 키 목록을 배열 형태로 출력, 키가 없으면 (empty array)"
note "순서는 요구되지 않지만 보기 쉽게 정렬해서 출력한다."
repl 'KEYS' 'SET user:3 x' 'SET user:2 y' 'KEYS'

section "3. 메모리 관리 + LRU 자동 제거"

item "CONFIG SET maxmemory bytes" "bytes는 0 이상의 정수, 0은 무제한"
note "한도 10에서는 longkey(7)+longvalue(9)=16이 OOM이고, 0(무제한)으로 바꾸면 저장된다."
repl 'CONFIG SET maxmemory 10' 'SET longkey longvalue' 'CONFIG SET maxmemory 0' 'SET longkey longvalue' 'INFO memory'

item "CONFIG SET maxmemory bytes" "성공 시 OK, 정수 파싱 실패 시 에러 표준"
repl 'CONFIG SET maxmemory 100' 'CONFIG SET maxmemory abc' 'CONFIG SET maxmemory -1' 'CONFIG SET maxmemory 1.5'

item "INFO memory" "used_memory, maxmemory, evicted_keys 3개 항목 출력"
repl 'CONFIG SET maxmemory 30' 'SET user:1 "Alice"' 'INFO memory'

item "used_memory 산정 기준" "used_memory = Σ(len(utf8(key)) + len(utf8(value))), 자료구조 오버헤드 제외"
note "키·값은 한글 한 글자가 3바이트라 6. user:1(6)+Alice(5)=11을 더해 17. Al로 덮어쓰면 17-5+2=14. 키를 지우면 8."
repl 'SET 키 "값"' 'INFO memory' 'SET user:1 "Alice"' 'INFO memory' 'SET user:1 "Al"' 'INFO memory' 'DEL 키' 'INFO memory'

item "LRU 제거 규칙" "maxmemory > 0 이고 SET 이후 초과하면, maxmemory 이하가 될 때까지 LRU부터 제거"
note "미션 예시: 11+9+13=33 > 30이라 가장 오래된 user:1(11)을 지워 22가 된다."
repl 'CONFIG SET maxmemory 30' 'SET user:1 "Alice"' 'SET user:2 "Bob"' 'SET user:3 "Charlie"' 'GET user:1' 'INFO memory' 'KEYS'
note "여러 개를 지워야 하는 경우: a·b·c가 5바이트씩 15. d(11)를 넣으면 26이라 a, b, c 순서로 지우고 11이 되면 멈춘다."
repl 'CONFIG SET maxmemory 15' 'SET a 1111' 'SET b 2222' 'SET c 3333' 'SET d 1234567890' 'KEYS' 'INFO memory'

item "LRU 제거 규칙" "제거된 키는 evicted_keys에 누적 카운트"
note "한도 10, 키마다 6바이트. b를 넣으면 12 > 10이라 a를 지워 1, c를 넣으면 b를 지워 2가 된다."
repl 'CONFIG SET maxmemory 10' 'SET a 11111' 'SET b 22222' 'INFO memory' 'SET c 33333' 'INFO memory'

item "LRU 제거 규칙" "단일 엔트리(키+값) 자체가 maxmemory를 초과하면 저장하지 않고 에러(OOM)"
note "bigkey(6)+값(18)=24 > 10이라 저장하지 않는다. 기존 k는 그대로 남는다."
repl 'CONFIG SET maxmemory 10' 'SET k v' 'SET bigkey "averyverylongvalue"' 'EXISTS bigkey' 'GET k' 'INFO memory'

section "4. TTL 관리 (힙 기반)"

item "EXPIRE key seconds" "key가 없으면 (integer) 0"
repl 'EXPIRE nope 10'

item "EXPIRE key seconds" "seconds가 0 이하라면 즉시 만료 (존재하면 삭제 후 (integer) 1)"
repl 'SET z 1' 'EXPIRE z 0' 'EXISTS z' 'SET m 1' 'EXPIRE m -5' 'GET m'

item "EXPIRE key seconds" "정상 설정 시 (integer) 1"
note "TTL은 남은 초를 내림해서 10초를 건 직후 9가 나온다."
repl 'SET a 1' 'EXPIRE a 10' 'TTL a'

item "TTL key" "없으면 (integer) -2, 만료 시간이 없으면 (integer) -1, 있으면 남은 초 (integer) N"
note "남은 초는 내림이라 3초를 건 직후 2가 나온다(미션 예시와 같다)."
repl 'TTL nope' 'SET plain x' 'TTL plain' 'SET user:2 "Bob"' 'EXPIRE user:2 3' 'TTL user:2'

item "TTL/LRU 엣지 케이스" "만료된 키는 GET 시 먼저 삭제 후 (nil)을 반환하며, LRU 갱신은 하지 않는다"
note "미션 예시처럼 3초를 실제로 기다린다. LRU를 갱신하지 않는 것은 2절 GET 항목의 내부 구조 확인에 있다."
repl 'SET user:2 "Bob"' 'EXPIRE user:2 3' 'TTL user:2' '@sleep 3.2' 'GET user:2' 'TTL user:2' 'DBSIZE'

item "TTL/LRU 엣지 케이스" "SET이 기존 키를 덮어쓸 때 TTL은 초기화(삭제)한다"
repl 'SET k v' 'EXPIRE k 100' 'SET k v2' 'TTL k'

item "TTL/LRU 엣지 케이스" "EXPIRE를 없는 키에 호출하면 (integer) 0"
repl 'EXPIRE ghost 5' 'EXISTS ghost'

item "TTL/LRU 엣지 케이스" "DEL은 데이터/TTL/LRU 모든 구조에서 엔트리를 함께 제거한다"
note "내부 구조 확인은 2절 DEL 항목에 있다."
repl 'SET d v' 'EXPIRE d 50' 'DEL d' 'TTL d' 'EXISTS d'

item "구현 방식" "힙을 통해 가장 빠른 만료를 빠르게 찾을 수 있어야 한다 (lazy deletion 등은 선택)"
note "시계를 직접 넣은 저장소. 힙 루트가 늘 가장 빠른 만료다. a를 다시 EXPIRE하면 예전 기록(1010, a)은 힙에 남지만, 꺼낼 때 expire_at이 달라 버린다."
py 'from mini_redis.store import MiniRedisStore' 'now = [1000.0]' 's = MiniRedisStore(clock=lambda: now[0])' \
  'for k in ("c", "a", "b"): s.set(k, "v")' 's.expire("c", 30); s.expire("a", 10); s.expire("b", 20)' \
  's._ttl_heap.peek()' 's.expire("a", 50)' 'now[0] = 1015.0' '(sorted(s.keys()), s._ttl_heap.peek())' \
  'now[0] = 1031.0' '(sorted(s.keys()), s.ttl("a"))'

section "5. 에러 처리 표준 + CLI 인터페이스"

item "CLI" "mini-redis> 프롬프트 출력"
note "파이프로 넣은 입력은 화면에 다시 찍히지 않아서, 프롬프트 바로 뒤에 출력이 붙어 보인다."
sh_run "printf 'SET a 1\\nGET a\\nquit\\n' | python3 main.py" "printf 'SET a 1\\nGET a\\nquit\\n' | \"\$PYTHON\" main.py"

item "CLI" "사용자 입력을 읽고 명령어 파싱 및 실행 (반복)"
repl 'SET user:1 "Alice"' 'GET user:1' 'EXISTS user:1' 'DEL user:1' 'GET user:1'

item "CLI" "exit 또는 quit 으로 종료 가능"
note "종료 명령 뒤의 SET a 1은 실행되지 않는다. 종료 코드는 0이다."
sh_run "printf 'exit\\nSET a 1\\n' | python3 main.py; echo \"종료 코드 \$?\"" "printf 'exit\\nSET a 1\\n' | \"\$PYTHON\" main.py; echo \"종료 코드 \$?\""
sh_run "printf 'quit\\n' | python3 main.py; echo \"종료 코드 \$?\"" "printf 'quit\\n' | \"\$PYTHON\" main.py; echo \"종료 코드 \$?\""

item "에러 출력" "잘못된 명령: (error) ERR unknown command '<cmd>'"
repl 'HELLO' 'FOO bar'

item "에러 출력" "인자 개수 오류: (error) ERR wrong number of arguments for '<cmd>' command"
repl 'GET' 'SET onlykey' 'DEL a b' 'DBSIZE extra' 'EXPIRE k'

item "에러 출력" "정수 파싱 실패: (error) ERR value is not an integer or out of range"
repl 'CONFIG SET maxmemory abc' 'SET k v' 'EXPIRE k abc' 'EXPIRE k 1.5'

item "에러 출력" "메모리 초과(OOM): (error) OOM command not allowed when used_memory > 'maxmemory'"
repl 'CONFIG SET maxmemory 5' 'SET longkey longvalue' 'EXISTS longkey'

item "값 파싱" "\"Alice\" 같은 따옴표 입력 허용, 공백이 없는 값과 큰따옴표로 감싼 값 지원"
note "닫히지 않은 따옴표는 에러를 내고 REPL은 계속 동작한다."
repl 'SET name "Alice"' 'GET name' 'SET plain Bob' 'GET plain' 'SET msg "hello world"' 'GET msg' 'SET bad "unclosed' 'GET plain'

exec 3>&-
echo "기능 요구 사항 ${ITEMS}개 항목을 실행해 로그에 남겼습니다 (명령·코드 ${CMDS}줄)."
echo "로그: $LOG"
if grep -q 'Traceback' "$LOG"; then
  echo "주의: 로그에 Traceback이 있습니다. 해당 항목을 확인하세요."
  exit 1
fi
