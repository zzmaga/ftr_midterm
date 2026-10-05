# Demonstration in 5 to 10 minutes

Run all commands from the repository root. The experiment commands launch and stop their own systems; the interactive demo uses another port range.

## 1. Show the normal system and duplicate protection

```powershell
.\.venv\Scripts\python -m scripts.local --mode ft
```

Open `http://127.0.0.1:8100`. Show students, service health and transcript. Record a payment of 10 KZT, then press **Record payment** again without changing the key. Expected: the second response says duplicate detected, the ledger has one payment for that key and tuition decreases once. Press **New key** only for a new payment.

Say: «Ключ идентифицирует бизнес-операцию. Повтор запроса возвращает старую запись, поэтому потеря ответа не приводит к повторному списанию. Проверка находится в общей базе, поэтому работает и между репликами».

## 2. Replica failure and recovery

In a second terminal:

```powershell
.\.venv\Scripts\python -m scripts.experiments --trials 1 --scenario crash
```

Expected: baseline has failed requests during the killed process interval; FT serves payment requests through payment2. The tool writes the actual counts and consistency result, then restarts the failed component. Open the new result folder named at completion. In `ft_crash_1.json`, show `workers`, `events` and `requests`; in its gateway log show `downstream_failure` and `retry_backoff`.

Say: «Это реальные отдельные процессы. Скрипт завершает первую реплику, шлюз обнаруживает ошибку соединения и повторяет запрос через вторую. Балансировщик сам не перезапускает процесс: восстановление компонента делает экспериментальный стенд».

## 3. Timeout and circuit breaker

```powershell
.\.venv\Scripts\python -m scripts.experiments --trials 1 --scenario timeout
```

Expected: both modes lose full transcript responses while the 1400 ms delay is active. FT returns an explicitly degraded cached transcript and its breaker changes CLOSED → OPEN → HALF_OPEN → CLOSED. Requests for students and payments still succeed. The raw gateway log contains breaker events; degraded responses count separately from full successes.

Optional live demonstration, while the interactive launcher is running:

```powershell
.\.venv\Scripts\python -m scripts.inject academic --delay-ms 1400
# Load the transcript repeatedly in the browser.
.\.venv\Scripts\python -m scripts.inject academic
# Wait at least one second, then load the transcript again.
```

Say: «Timeout ограничивает ожидание, breaker прекращает бесполезные обращения к неисправному сервису. Устаревшие оценки помечены как degraded, а платежи продолжают работать. HTTP 200 с fallback не означает полноценную доступность transcript».

## 4. Interrupted transaction and lost acknowledgement

```powershell
.\.venv\Scripts\python -m scripts.experiments --trials 1 --scenario interruption --scenario response_loss
```

Expected: baseline loses the balance/ledger invariant or creates duplicate keys. FT keeps `consistent=true`. Show `state_before`, `state_after`, and log events `checkpoint`, `rollback`, `transaction_commit`, `response_lost`. The integration test `test_rollback_restores_exact_pre_transaction_state` also observes the storage state before a retry is allowed to finish.

Say: «Баланс и запись платежа должны изменяться вместе. Savepoint позволяет отменить промежуточное изменение; общая SQL-транзакция даёт атомарность. Если commit уже прошёл, rollback поздно делать — тогда помогает idempotency».

## Finish

Show the report comparison and explain the shared database and gateway as remaining single points of failure. Do not claim real physical node redundancy or production uptime. Stop the interactive system with `Ctrl+C`.

For a single combined command covering the assignment's minimum three demos:

```powershell
.\.venv\Scripts\python -m scripts.experiments --trials 1 --scenario crash --scenario timeout --scenario interruption
```
