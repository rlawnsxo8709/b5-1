# b5-1 수행 계획 — Mini Redis

> 작성일: 2026-10-04 / 대상: b5-1 「정보를 엄청 빠르게 찾아주는 작은 저장소 만들기」 미션

## 1. 목표와 판단 기준

해시맵·이중 연결 리스트·최소 힙을 **내장 `dict`/`set`/`collections` 없이** 직접 만들고,
그 위에 LRU 제거와 TTL 만료가 동작하는 CLI Mini Redis(`python3 main.py`)를 완성한다.

다음 네 가지를 구현 코드에서 바로 짚어 설명할 수 있어야 한다. (답변은 [EXPLAIN.md](EXPLAIN.md))

1. 해시 함수와 체이닝으로 충돌을 푸는 방식
2. 해시맵 + 이중 연결 리스트로 LRU 추적이 O(1)인 이유
3. 힙이 TTL 만료 관리에 맞는 이유
4. 메모리 한도를 넘었을 때 LRU로 제거하는 전체 흐름 (used_memory 갱신 포함)

그리고 동료평가 Q0(금지 자료형 미사용)을 말이 아니라 **자동 검사**로 보여 줄 수 있어야 한다.

## 2. 산출물 구조

```
answers/                     ← 이 폴더가 곧 rlawnsxo8709/b5-1 저장소의 루트
├── main.py                  진입점 (python3 main.py)
├── mini_redis/
│   ├── __init__.py
│   ├── __main__.py          python3 -m mini_redis 진입점
│   ├── dlist.py             DoublyLinkedList (센티넬 head/tail, 전 연산 O(1))
│   ├── hashmap.py           fnv1a_hash, HashMap (체이닝, 로드 팩터 0.75 초과 시 2배)
│   ├── minheap.py           MinHeap (push/pop/peek/size, _heapify_up/_down)
│   ├── store.py             MiniRedisStore — LRU · TTL · used_memory 엔진
│   ├── errors.py            OOMError
│   ├── parser.py            tokenize (큰따옴표 값, 이스케이프)
│   └── cli.py               execute(명령 테이블 + 출력 포맷), repl
├── tests/                   단위 + E2E + AST 제약 검사 (표준 unittest, 87개)
├── README.md                사용 가이드 · 실제 실행 세션 · 요구사항 체크리스트 · 검증 결과
├── EXPLAIN.md               과제 목표 4문항 + 평가 문항 Q0~Q17 답변
└── PLAN.md                  이 문서
```

의존은 import 기준으로 `cli → store, parser, hashmap, errors`(명령 테이블에 `HashMap`을 직접 쓴다), `store → hashmap, dlist, minheap, errors`, `hashmap → dlist` 한 방향이고 순환이 없다. 자료구조 모듈은 서로를 모르고, `hashmap`만 `dlist`를 버킷으로 재사용한다.

## 3. 핵심 설계 결정

| 결정 | 선택 | 이유 |
|---|---|---|
| 해시 함수 | FNV-1a 32bit, 입력은 키의 UTF-8 바이트 | 직접 설계 요구를 몇 줄로 충족하고, 한글도 바이트 단위로 일관되게 섞인다. 내장 `hash()`는 실행마다 값이 달라지고 직접 만든 것도 아니라서 쓰지 않는다 |
| 충돌 해결 | 체이닝, 버킷은 `DoublyLinkedList` | 미션 권장 방식이다. 같은 구조를 LRU에도 쓰고, 찾은 노드를 O(1)로 뗄 수 있다 |
| 버킷 테이블 | `[None] * capacity`, 칸은 처음 쓸 때 리스트 생성 | 허용된 고정 길이 배열 + 인덱스 접근. 빈 칸에 리스트를 미리 만들지 않는다 |
| 확장 | 로드 팩터 `size / capacity > 0.75`이면 2배, 전체 재해시. 정수 비교 `size * 4 > capacity * 3` | 부동소수점 오차 없이 경계(6/8은 유지, 7/8은 확장)를 정확히 지킨다 |
| LRU | 해시맵 `key → _Entry`, 엔트리가 리스트 노드를 들고 있음 | 해시로 찾은 즉시 노드를 얻어 이동·제거가 O(1) |
| TTL | 최소 힙 `(expire_at, key)` + lazy deletion | 힙에서 임의 원소 삭제가 비싸서 낡은 기록은 꺼낼 때 `expire_at` 불일치로 거른다 |
| 만료 처리 시점 | 키 기반 명령은 그 키만 확인, `DBSIZE`·`KEYS`·`INFO memory`·제거 직전에는 힙에서 일괄 정리 | 미션 요구(실행 전 만료 확인)를 지키면서, 만료가 없을 때 비용은 힙 루트 확인 O(1) |
| 메모리 한도 | `CONFIG SET`으로 한도를 낮추면 **즉시** LRU 제거 | `used ≤ max`가 항상 성립하게 한다. 미션이 정하지 않은 부분이라 직접 정했다 |
| 제거 순서 | 제거 직전에 만료된 키부터 정리 | 죽은 키를 두고 살아 있는 키를 쫓아내지 않는다. 만료는 `evicted_keys`에 세지 않는다 |
| used_memory | `Σ len(utf8(key)) + len(utf8(value))`, 엔트리마다 `size`를 저장해 가감 | 미션 공식 그대로. 한글은 3바이트. 매번 전체를 다시 더하지 않는다 |
| SET과 OOM | 단일 엔트리가 한도 초과면 OOM, 기존 값·TTL 유지. 덮어쓰기는 TTL 삭제 | 미션 규칙. 방금 쓴 키는 LRU 맨 앞이라 제거 루프가 닿기 전에 멈춘다 |
| TTL 반환값 | 남은 초를 **내림** | 미션 예시(`EXPIRE 3` 직후 `TTL` = 2)와 일치한다 |
| 시계 | `MiniRedisStore(clock=time.time)`로 주입 | 테스트가 시간을 조작해 3초 대기 없이 만료를 검증한다 |
| KEYS 출력 | 미션 예시 형식 `1. "key"`, 비면 `(empty array)`. **정렬해서** 출력 | 순서는 요구되지 않지만, 해시 순서에 기대면 확장 시 출력이 달라진다 |
| 명령 분기 | 직접 만든 `HashMap`에 `"SET" → _Command` 등록, 이름은 대소문자 무시 | 내장 dict 금지 제약을 명령 표에도 지킨다. 에러 메시지엔 입력한 이름을 그대로 쓴다 |
| 정수 파싱 | 부호 `-`와 ASCII 숫자만, 64bit 범위(숫자 19자리 초과는 변환 전에 거절). 음수 maxmemory는 정수 오류 | `int()`는 `+5`, `1_0`, 유니코드 숫자도 받아서 Redis와 달라지고, 4300자리를 넘는 문자열에는 ValueError를 내서 REPL이 죽는다 |
| 따옴표 | `\"` · `\\`만 해석, 토큰 첫 글자의 `"`만 따옴표 시작, 미닫힘은 ParseError | 미션 최소 요구(공백 없는 값 / 큰따옴표 값)보다 조금 넓게, 모호한 입력은 오류로 거절 |
| REPL | 빈 줄 무시, `exit`/`quit` → `Bye`, EOF·Ctrl-C → 줄바꿈 후 정상 종료, 입력이 TTY가 아니어도 프롬프트 출력 | 예외 트레이스백 없이 종료. 단순하게 유지 |

## 4. 하지 않는 것

- 보너스 과제(동적 배열, 스택/큐 문서, 트리, BST, Pub/Sub)는 하지 않는다.
- 네트워크, 영속성, List/Set/Sorted Set, 동시성은 만들지 않는다.
- `KEYS` 패턴 매칭, `SET`의 옵션, 여러 키를 받는 `DEL`/`EXISTS`는 미션 정의에 없어서 구현하지 않는다.

## 5. 검증 방법

1. **단위 테스트 (표준 `unittest`)** — 테스트를 먼저 쓰고 실패(RED)를 확인한 뒤 구현한다.
   - 자료구조: 연산 결과와 경계(빈 리스트, 센티넬, 충돌, 확장 경계 6/8·7/8, 힙 정렬 순서, FNV-1a 공개 벡터).
   - 엔진: 가짜 시계로 LRU 순서, 덮어쓰기와 TTL 초기화, OOM, 한도 하향, 낡은 힙 기록, 만료 후 정리.
2. **명령·REPL** — `execute`의 출력 문자열과 에러 문구, `main.py` subprocess로 미션 예시 세션, 빈 줄, EOF, 따옴표 미닫힘, 한글 값.
3. **AST 검사** — `tests/test_constraints.py`가 `dict`/`set` 리터럴·컴프리헨션·호출과 `collections` import가 0개임을 확인한다.
4. **실제 실행 세션** — 미션 예시 시나리오(TTL 대기는 `sleep`이 든 스크립트)와 에러·경계 시나리오를 파이프로 실행해 출력을 README에 그대로 붙인다.

## 6. 저장소와 브랜치

| 저장소 | 넣는 것 |
|---|---|
| `rlawnsxo8709/b5-1` | 이 폴더가 루트. `main`에 `chore:` 1개 → `feature/mini-redis`에서 `test:` → `feat:` → `docs:` → `--no-ff` 병합 |

푸시와 원격 저장소 생성은 이 단계에서 하지 않는다.
