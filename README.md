# Mini Redis — 해시맵·이중 연결 리스트·힙으로 만든 CLI 저장소 (b5-1)

> Redis의 핵심인 **String 명령 · LRU 메모리 제거 · TTL 만료**를 `dict`/`set`/`collections` 없이 직접 구현한 CLI 프로그램.
> 외부 라이브러리 없이 **표준 라이브러리만** 사용한다.

| | |
|---|---|
| 실행 | `python3 main.py` (또는 `python3 -m mini_redis`) |
| 개발 환경 | 미션 요구 Python 3.8 이상 · 실행 검증 3.13.11, 3.12.3 (Linux). 3.8 실행은 해 보지 못했고, 모든 파일이 3.8 문법으로 파싱되는 것만 확인했다 |
| 외부 라이브러리 | **없음** (`math`, `time`, `sys`만 사용. 테스트는 표준 `unittest`) |
| 금지 자료형 | `dict` · `set` · `frozenset` · `collections` **미사용** |
| 미사용 검증 | `tests/test_constraints.py`가 `ast`로 소스를 파싱해 dict/set 리터럴·컴프리헨션, `dict()`/`set()`/`frozenset()` 호출, `collections` import가 0개임을 확인한다 ([검증](#검증)) |
| 테스트 | 87개, 전부 통과 |

설계 결정은 [PLAN.md](PLAN.md), 과제 목표와 평가 문항(Q0~Q17) 답변은 [EXPLAIN.md](EXPLAIN.md)에 있다.

---

## 목차

1. [실행 방법](#실행-방법)
2. [명령](#명령)
3. [출력 규칙과 에러 표준](#출력-규칙과-에러-표준)
4. [실제 실행 세션](#실제-실행-세션)
5. [동작 규칙](#동작-규칙)
6. [폴더 구조](#폴더-구조)
7. [요구사항 체크리스트](#요구사항-체크리스트)
8. [검증](#검증)

---

## 실행 방법

설치 과정이 없다. 저장소 루트에서 바로 실행한다.

```bash
python3 main.py
```

`mini-redis> ` 프롬프트가 뜨면 명령을 입력한다. `exit` 또는 `quit`(대소문자 무시)으로 종료하고, `Ctrl-D`(EOF)나 파이프 입력이 끝나도 예외 없이 종료한다.

스크립트로 명령을 흘려 보낼 수도 있다. 이때는 입력한 줄이 화면에 다시 찍히지 않아서 프롬프트 바로 뒤에 결과가 붙는다.

```bash
printf 'SET a 1\nGET a\nquit\n' | python3 main.py
```

## 명령

| 명령 | 설명 | 출력 |
|---|---|---|
| `SET key value` | 값 저장. 이미 있으면 덮어쓰고 **TTL을 지운다**. 메모리 초과 시 LRU 제거 | `OK` |
| `GET key` | 값 조회. 성공했을 때만 LRU 갱신 | `"value"` / `(nil)` |
| `DEL key` | 키 삭제(데이터·LRU·TTL 모두) | `(integer) 1` / `(integer) 0` |
| `EXISTS key` | 키 존재 여부(LRU는 갱신하지 않는다) | `(integer) 1` / `(integer) 0` |
| `DBSIZE` | 저장된 키 개수(만료된 키 제외) | `(integer) N` |
| `KEYS` | 전체 키 목록. 패턴은 지원하지 않아 인자가 없다 | `1. "key"` 줄 목록 / `(empty array)` |
| `CONFIG SET maxmemory bytes` | 최대 메모리(바이트). `0`은 무제한. 한도를 낮추면 즉시 LRU 제거 | `OK` |
| `INFO memory` | 메모리 사용 현황. 인자 없는 `INFO`도 같은 출력 | `used_memory:N` · `maxmemory:N` · `evicted_keys:N` |
| `EXPIRE key seconds` | 만료 시간(초) 설정. `seconds <= 0`이면 즉시 삭제 | `(integer) 1` / `(integer) 0` |
| `TTL key` | 남은 초(내림) | `(integer) N` / `-1`(만료 없음) / `-2`(없는 키) |
| `exit` / `quit` | 종료 | `Bye` |

- 명령 이름은 대소문자를 구분하지 않는다. 에러 메시지에는 입력한 이름이 그대로 들어간다.
- 값은 공백 없이 쓰거나 큰따옴표로 감싼다(`SET user:1 "Alice Kim"`). 따옴표 안에서 `\"`는 `"`, `\\`는 `\`다. 값은 항상 문자열이다.
- 키는 큰따옴표로 감싸면 공백을 넣을 수 있다(`SET "my key" 1`).

## 출력 규칙과 에러 표준

| 상황 | 출력 |
|---|---|
| 없는 명령 | `(error) ERR unknown command '<cmd>'` |
| 인자 개수 오류 | `(error) ERR wrong number of arguments for '<cmd>' command` |
| 정수 파싱 실패(음수 maxmemory 포함) | `(error) ERR value is not an integer or out of range` |
| 엔트리 하나가 maxmemory보다 큼 | `(error) OOM command not allowed when used_memory > 'maxmemory'` |
| `CONFIG SET`의 알 수 없는 항목 | `(error) ERR Unsupported CONFIG parameter: <param>` |
| 큰따옴표가 닫히지 않음 | `(error) ERR Protocol error: unbalanced quotes in request` |
| 빈 줄 | 아무것도 출력하지 않고 프롬프트로 돌아간다 |

정수는 Redis처럼 엄격하게 받는다. 부호는 `-`만, 숫자는 ASCII `0-9`만 허용하고, `1.5` · `+5` · `1_0` · `0x10` · 64bit 범위 밖의 값은 정수 오류다. 숫자가 19자리(64bit 최댓값의 자릿수)를 넘으면 값을 계산하기 전에 범위 오류로 처리하므로, 아주 긴 숫자를 넣어도 프로그램이 죽지 않는다.

## 실제 실행 세션

아래 출력은 모두 이 저장소에서 **실제로 실행한 결과를 그대로** 붙인 것이다.

### 1. 미션 예시 시나리오 (LRU 제거 + TTL)

TTL 3초를 기다려야 해서 `sleep`이 들어간 셸 스크립트로 실행했다.

```bash
{
  printf 'CONFIG SET maxmemory 30\nSET user:1 "Alice"\nSET user:2 "Bob"\nSET user:3 "Charlie"\nGET user:1\nINFO memory\nKEYS\nEXPIRE user:2 3\nTTL user:2\n'
  sleep 3.2
  printf 'GET user:2\nTTL user:2\nquit\n'
} | python3 main.py
```

```text
mini-redis> OK
mini-redis> OK
mini-redis> OK
mini-redis> OK
mini-redis> (nil)
mini-redis> used_memory:22
maxmemory:30
evicted_keys:1
mini-redis> 1. "user:2"
2. "user:3"
mini-redis> (integer) 1
mini-redis> (integer) 2
mini-redis> (nil)
mini-redis> (integer) -2
mini-redis> Bye
```

입력한 명령과 출력의 대응은 다음과 같다.

| 입력 | 출력 | 일어난 일 |
|---|---|---|
| `CONFIG SET maxmemory 30` | `OK` | 한도 30바이트 |
| `SET user:1 "Alice"` | `OK` | 6 + 5 = 11, used 11 |
| `SET user:2 "Bob"` | `OK` | 6 + 3 = 9, used 20 |
| `SET user:3 "Charlie"` | `OK` | 6 + 7 = 13, used 33 > 30 → 가장 오래된 `user:1`(11) 제거, used 22 |
| `GET user:1` | `(nil)` | 제거되어 없다 |
| `INFO memory` | `used_memory:22` … `evicted_keys:1` | 남은 두 키의 바이트 합 9 + 13 = 22 |
| `KEYS` | `1. "user:2"` / `2. "user:3"` | 출력은 키 순으로 정렬한다 |
| `EXPIRE user:2 3` → `TTL user:2` | `(integer) 1` → `(integer) 2` | 3초 설정 직후라 남은 초를 내림해 2 |
| (3.2초 대기) `GET user:2` → `TTL user:2` | `(nil)` → `(integer) -2` | 만료된 키는 지우고 없는 키로 처리 |

### 2. 에러 처리

```bash
printf 'CONFIG SET maxmemory abc\nGET\nHELLO\nget\nCONFIG SET maxmemory -1\nEXPIRE a x\nCONFIG SET foo 1\nCONFIG SET maxmemory 3\nSET big value\nSET a "abc\nINFO\nquit\n' | python3 main.py
```

```text
mini-redis> (error) ERR value is not an integer or out of range
mini-redis> (error) ERR wrong number of arguments for 'GET' command
mini-redis> (error) ERR unknown command 'HELLO'
mini-redis> (error) ERR wrong number of arguments for 'get' command
mini-redis> (error) ERR value is not an integer or out of range
mini-redis> (error) ERR value is not an integer or out of range
mini-redis> (error) ERR Unsupported CONFIG parameter: foo
mini-redis> OK
mini-redis> (error) OOM command not allowed when used_memory > 'maxmemory'
mini-redis> (error) ERR Protocol error: unbalanced quotes in request
mini-redis> used_memory:0
maxmemory:3
evicted_keys:0
mini-redis> Bye
```

`get`처럼 소문자로 입력하면 에러 메시지에도 `'get'`이 그대로 나온다. 마지막 `INFO`는 `SET big value`(9바이트)가 한도 3을 넘어 저장되지 않았으므로 `used_memory:0`이다.

### 3. 경계 동작 (TTL 초기화 · 즉시 제거 · UTF-8 바이트)

```bash
printf 'SET k v\nEXPIRE k 100\nTTL k\nSET k w\nTTL k\nEXPIRE nope 10\nEXPIRE k 0\nEXISTS k\nSET a 1234\nSET b 1234\nSET c 1234\nCONFIG SET maxmemory 10\nINFO memory\nKEYS\nGET a\nSET 키 "값값"\nINFO memory\nDBSIZE\nDEL 키\nDEL 키\n' | python3 main.py
```

```text
mini-redis> OK
mini-redis> (integer) 1
mini-redis> (integer) 99
mini-redis> OK
mini-redis> (integer) -1
mini-redis> (integer) 0
mini-redis> (integer) 1
mini-redis> (integer) 0
mini-redis> OK
mini-redis> OK
mini-redis> OK
mini-redis> OK
mini-redis> used_memory:10
maxmemory:10
evicted_keys:1
mini-redis> 1. "b"
2. "c"
mini-redis> (nil)
mini-redis> OK
mini-redis> used_memory:9
maxmemory:10
evicted_keys:3
mini-redis> (integer) 1
mini-redis> (integer) 1
mini-redis> (integer) 0
mini-redis> 
```

| 입력 | 확인할 것 |
|---|---|
| `EXPIRE k 100` → `TTL k` → `(integer) 99` | 설정 직후라도 경과 시간이 있어 남은 초를 **내림**하면 99다 |
| `SET k w` → `TTL k` → `(integer) -1` | 덮어쓰면 TTL이 사라진다 |
| `EXPIRE nope 10` → `(integer) 0` | 없는 키 |
| `EXPIRE k 0` → `(integer) 1`, `EXISTS k` → `(integer) 0` | 0 이하면 즉시 삭제 |
| `CONFIG SET maxmemory 10` → `used_memory:10`, `evicted_keys:1`, `KEYS`에 `b`, `c`만 | 5 + 5 + 5 = 15에서 한도를 10으로 낮추자 **즉시** 가장 오래된 `a`가 제거된다 |
| `SET 키 "값값"` → `used_memory:9`, `evicted_keys:3` | `키`(3바이트) + `값값`(6바이트) = 9. 한글은 UTF-8 한 글자 3바이트다 |
| `DEL 키` → `1`, 다시 → `0` | 삭제 성공/없음 |
| 마지막 `mini-redis> ` 뒤 줄바꿈 | `quit` 없이 입력이 끝나도(EOF) 예외 없이 종료 |

## 동작 규칙

- **used_memory** = Σ(`len(utf8(key))` + `len(utf8(value))`). 노드·포인터·버킷 같은 자료구조 오버헤드는 계산에서 제외한다.
- **SET 순서**: ① 엔트리 하나가 maxmemory를 넘으면 OOM 에러(기존 값 유지) → ② 저장(덮어쓰면 TTL 삭제, LRU 맨 앞으로) → ③ `used_memory > maxmemory`인 동안 LRU 꼬리부터 제거하고 `evicted_keys`를 늘린다. 방금 쓴 키는 맨 앞에 있고 단독 크기가 한도 이하라 제거되지 않는다.
- **만료**: 키 기반 명령(`GET` `SET` `DEL` `EXISTS` `EXPIRE` `TTL`)은 실행 전에 그 키의 만료를 확인해 지운다. `DBSIZE` · `KEYS` · `INFO memory` · 메모리 제거 직전에는 TTL 힙에서 만료된 키를 한꺼번에 정리한다. 만료로 사라진 키는 `evicted_keys`에 세지 않는다.
- **GET**은 값을 돌려줄 때만 LRU를 갱신한다. 만료로 지워졌거나 없는 키는 갱신하지 않는다.
- **TTL**은 남은 초를 내림한다. 시계는 주입할 수 있어서 테스트에서 시간을 조작한다.
- `CONFIG SET maxmemory`로 한도를 **낮추면 그 즉시** 같은 방식으로 제거해 `used ≤ max`를 유지한다.

### 미션 문구에 없어서 정한 것

| 항목 | 선택 |
|---|---|
| `KEYS` 순서 | 미션은 순서를 요구하지 않는다. 해시 순서가 바뀌어도 출력이 같도록 정렬해서 보여 준다 |
| `KEYS *` 같은 패턴 | 미구현(미션). 인자가 있으면 인자 개수 오류 |
| `SET`의 옵션(`EX` 등), `DEL`/`EXISTS`의 여러 키 | 미션 정의(`SET key value`, `DEL key`)대로 인자 개수를 정확히 요구한다 |
| `CONFIG GET ...` 같은 다른 하위 명령 | 인자가 3개면 `(error) ERR unknown subcommand '<sub>' for 'CONFIG' command` |
| `INFO` 뒤의 `memory` 외 섹션 | `(error) ERR Unsupported INFO section: <name>` |
| 따옴표 이스케이프 | `\"` · `\\`만 해석하고 `\n` 같은 나머지는 그대로 둔다. 닫는 따옴표 바로 뒤에 글자가 오면 따옴표 오류다 |
| `GET`/`KEYS` 출력의 따옴표 | 값 안의 `"`와 `\`는 입력 규칙과 같게 `\"` · `\\`로 출력한다 |
| 입력이 터미널이 아닐 때 | 프롬프트를 그대로 출력한다(단순하게 유지) |

## 폴더 구조

```
main.py                  진입점 (python3 main.py)
mini_redis/
├── __init__.py
├── __main__.py          python3 -m mini_redis 진입점
├── dlist.py             DoublyLinkedList — 센티넬 head/tail, 전 연산 O(1)
├── hashmap.py           fnv1a_hash, HashMap — 체이닝(버킷=DoublyLinkedList), 로드 팩터 0.75 초과 시 2배
├── minheap.py           MinHeap — push/pop/peek/size, _heapify_up/_down
├── store.py             MiniRedisStore — LRU · TTL(힙 + lazy deletion) · used_memory
├── errors.py            OOMError
├── parser.py            tokenize — 큰따옴표 토크나이저
└── cli.py               execute(명령 테이블=HashMap, 출력 포맷), repl
tests/                   표준 unittest 87개
PLAN.md                  설계 결정
EXPLAIN.md               과제 목표 + 평가 문항 답변
```

의존 방향(import 기준): `cli → store, parser, hashmap, errors` · `store → hashmap, dlist, minheap, errors` · `hashmap → dlist`. `dlist` · `minheap` · `parser` · `errors`는 다른 모듈을 import하지 않는다.

## 요구사항 체크리스트

| 요구사항 | 구현 위치 | 검증 테스트 |
|---|---|---|
| SET / GET / DEL / EXISTS / DBSIZE / KEYS | `cli.py:_cmd_*`, `store.py` | `test_cli: test_outputs`, `test_store: test_basic_crud` |
| `CONFIG SET maxmemory` (0은 무제한) | `cli.py:_cmd_config`, `store.py:set_maxmemory` | `test_cli: test_config_set_variants`, `test_store: test_zero_maxmemory_is_unlimited` |
| `INFO memory` 3항목 | `cli.py:_cmd_info`, `store.py:info_memory` | `test_cli: test_info_memory` |
| `EXPIRE` / `TTL` | `store.py:expire`, `store.py:ttl` | `test_store: test_ttl_and_expiry`, `test_expire_missing_and_nonpositive`, `test_ttl_floors_remaining_seconds` |
| REPL (`mini-redis> `, exit/quit) | `cli.py:repl` | `test_cli: TestRepl`, `TestReplInProcess` |
| 이중 연결 리스트 (prev/next/data, 전 연산 O(1)) | `dlist.py` | `test_dlist` 8개 |
| 해시맵: 직접 설계한 해시 | `hashmap.py:fnv1a_hash` | `test_hashmap: test_fnv1a_known_vectors`, `test_hash_is_deterministic_and_handles_unicode` |
| 해시맵: 체이닝(버킷 = 이중 연결 리스트) | `hashmap.py:HashMap` | `test_hashmap: test_collisions_are_chained` |
| 해시맵: 로드 팩터 0.75 초과 시 2배 확장 | `hashmap.py:HashMap._resize` | `test_hashmap: test_resize_doubles_when_load_factor_exceeds_075`, `test_many_keys_survive_repeated_resizes_and_removals` |
| 최소 힙 (`_heapify_up/_down`, `(expire_at, key)`) | `minheap.py` | `test_minheap` 7개 |
| 키 기반 명령 전 만료 확인 | `store.py:_purge_if_expired` | `test_store: test_expired_get_does_not_touch_lru`, `test_del_expired_key_returns_zero` |
| SET 덮어쓰기 시 TTL 삭제 | `store.py:set` | `test_store: test_overwrite_keeps_just_written_key_and_resets_ttl` |
| GET 성공 시에만 LRU 갱신 | `store.py:get` | `test_store: test_get_refreshes_lru`, `test_exists_and_missing_get_do_not_refresh_lru` |
| DEL이 데이터·TTL·LRU를 함께 제거 | `store.py:_remove_entry` | `test_store: test_delete_clears_ttl` |
| KEYS 출력 / 빈 결과 | `cli.py:_cmd_keys` | `test_cli: test_keys_lists_numbered_lines_in_sorted_order`, `test_outputs` |
| used_memory = UTF-8 바이트 합 | `store.py:_entry_size` | `test_store: test_used_memory_counts_utf8_bytes`, `test_used_memory_tracks_delete_and_overwrite` |
| LRU 제거와 `evicted_keys` | `store.py:_evict_until_fit` | `test_store: test_mission_example_lru_eviction`, `test_eviction_goes_from_least_recently_used_in_order` |
| 단일 엔트리가 한도 초과 → OOM, 저장 안 함 | `store.py:set` | `test_store: test_single_entry_over_limit_is_oom_and_not_stored`, `test_oom_on_overwrite_keeps_old_value_and_ttl` |
| 가득 찬 상태에서 덮어써도 방금 쓴 키 유지 | `store.py:set` | `test_store: test_overwrite_on_full_memory_evicts_others_never_the_written_key` |
| 한도를 낮추면 즉시 제거 | `store.py:set_maxmemory` | `test_store: test_lowering_maxmemory_evicts_immediately` |
| TTL 힙의 낡은 기록(lazy deletion) | `store.py:_purge_expired_all` | `test_store: test_reexpire_uses_latest_deadline_not_stale_heap_entry`, `test_expire_then_shorter_expire_fires_at_new_deadline` |
| 에러 표준 5종 + 따옴표 오류 | `cli.py:execute`, `parser.py:tokenize` | `test_cli: test_errors`, `test_wrong_number_of_arguments_for_every_command`, `test_integer_parsing_is_strict`, `test_huge_digit_strings_are_range_errors_not_crashes`, `test_huge_integer_argument_does_not_crash_the_repl`, `test_unbalanced_quotes_in_repl` |
| 따옴표 값 / 공백 없는 값 | `parser.py:tokenize` | `test_parser` 8개 |
| 미션 예시 시나리오 재현 | — | `test_cli: test_mission_example_session`, `test_store: test_mission_example_lru_eviction` |
| `dict`·`set`·`collections` 금지 | 전 모듈 | `test_constraints: test_no_builtin_dict_set_collections` |
| 자료구조 모듈 분리 + docstring | `dlist.py` `hashmap.py` `minheap.py` | 모든 클래스와 핵심 함수에 docstring |
| 네트워크·영속성·복잡 자료형·동시성 없음 | — | 해당 코드 없음 |
| 보너스 과제 | — | 하지 않음 |

## 검증

### 전체 테스트

```bash
python3 -m unittest discover -s tests -t . -v
```

| 파일 | 개수 | 대상 |
|---|---|---|
| `tests/test_dlist.py` | 8 | 이중 연결 리스트 |
| `tests/test_hashmap.py` | 10 | 해시·체이닝·확장 |
| `tests/test_minheap.py` | 7 | 최소 힙 |
| `tests/test_store.py` | 26 | LRU · TTL · 메모리 |
| `tests/test_parser.py` | 8 | 토크나이저 |
| `tests/test_cli.py` | 27 | 명령 출력·에러·REPL(in-process + subprocess) |
| `tests/test_constraints.py` | 1 | 금지 자료형 AST 검사 |
| 합계 | **87** | |

실제 실행 결과(Python 3.13.11):

```text
----------------------------------------------------------------------
Ran 87 tests in 0.113s

OK
```

Python 3.12.3에서도 같은 명령으로 87개가 통과했다.

### 금지 자료형 미사용 확인

```bash
python3 -m unittest tests.test_constraints -v
```

```text
test_no_builtin_dict_set_collections (tests.test_constraints.TestConstraints.test_no_builtin_dict_set_collections) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.004s

OK
```

이 테스트는 `mini_redis/*.py`와 `main.py`를 파싱해 `ast.Dict` · `ast.Set` · `ast.DictComp` · `ast.SetComp`, `dict()` · `set()` · `frozenset()` 호출, `collections` import의 개수를 센다. 검사 대상 파일이 하나라도 빠지면 실패하도록 파일 목록도 확인한다. 이 검사가 실제로 위반을 잡는지는 위반 코드를 담은 임시 파일을 넣어 확인했다(아홉 종류 모두 보고되었고, 확인 후 파일은 삭제했다).

고정 길이 배열 `[None] * n`과 인덱스 접근은 허용 범위라서 해시맵 버킷 테이블에 쓴다. 최소 힙의 저장소와 `keys()` 결과 같은 순서 있는 목록에는 내장 `list`를 쓴다. `list`는 이번 제약(`dict`·`set`·`collections`)의 대상이 아니다.
