# b5-1 수행 계획 — Mini Redis (초안)

> 작성일: 2026-10-04 / 대상: b5-1 「정보를 엄청 빠르게 찾아주는 작은 저장소 만들기」 미션

## 1. 목표

해시맵·이중 연결 리스트·최소 힙을 **내장 `dict`/`set`/`collections` 없이** 직접 만들고,
그 위에 LRU 제거와 TTL 만료가 동작하는 CLI Mini Redis(`python3 main.py`)를 완성한다.

다음 네 가지를 구현 코드에서 바로 짚어 설명할 수 있어야 한다.

1. 해시 함수와 체이닝으로 충돌을 푸는 방식
2. 해시맵 + 이중 연결 리스트로 LRU 추적이 O(1)인 이유
3. 힙이 TTL 만료 관리에 맞는 이유
4. 메모리 한도를 넘었을 때 LRU로 제거하는 전체 흐름 (used_memory 갱신 포함)

## 2. 구조

```
main.py                  진입점 (python3 main.py)
mini_redis/
├── dlist.py             DoublyLinkedList (센티넬 head/tail, 전 연산 O(1))
├── hashmap.py           HashMap (FNV-1a, 체이닝, 로드 팩터 0.75 초과 시 2배)
├── minheap.py           MinHeap (push/pop/peek/size, _heapify_up/_down)
├── store.py             저장소 엔진 (LRU · TTL · 메모리 한도)
├── errors.py            OOMError
├── parser.py            입력 줄 토크나이저
└── cli.py               명령 실행·출력 포맷, REPL
tests/                   표준 unittest
```

의존 방향은 `cli → store → (hashmap → dlist), dlist, minheap` 한 방향이다.

## 3. 핵심 결정

| 결정 | 선택 |
|---|---|
| 해시 함수 | FNV-1a 32bit, 입력은 키의 UTF-8 바이트 |
| 충돌 해결 | 체이닝. 버킷은 `DoublyLinkedList` |
| 확장 | 로드 팩터가 0.75를 넘으면 버킷을 2배로 늘리고 전체 재해시 |
| TTL 관리 | 최소 힙 + lazy deletion |
| `CONFIG SET maxmemory`로 한도를 낮출 때 | 그 즉시 LRU 제거로 `used ≤ max`를 맞춘다 |
| TTL 반환값 | 남은 초를 내림한다 |
| KEYS 출력 | 미션 예시 형식 `1. "key"` |
