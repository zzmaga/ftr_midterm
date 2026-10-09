"""Russian companion report; numerical tables are regenerated from the same recorded data."""
import argparse
import html
import json
import os
import statistics
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from scripts.build_report import ROOT, architecture, fmt, mean


def register_fonts(font_dir=None):
    directory = Path(font_dir or Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts")
    for name, filename in [("ReportRU", "arial.ttf"), ("ReportRU-Bold", "arialbd.ttf")]:
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f"Cyrillic font missing: {path}. Supply --font-dir with Arial TTF files.")
        pdfmetrics.registerFont(TTFont(name, str(path)))


def build(dataset, output, font_dir=None):
    register_fonts(font_dir)
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(dataset.glob("*.json")) if p.name != "environment.json"]
    rows = [c["summary"] for c in cases]
    assert len(rows) == 54, "Expected the complete three-trial dataset"
    env = json.loads((dataset / "environment.json").read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    styles = {
        "body": ParagraphStyle("RUBody", fontName="ReportRU", fontSize=9.5, leading=13, spaceAfter=8, textColor=colors.HexColor("#172535")),
        "small": ParagraphStyle("RUSmall", fontName="ReportRU", fontSize=8.2, leading=10.8, spaceAfter=7),
        "title": ParagraphStyle("RUTitle", fontName="ReportRU-Bold", fontSize=25, leading=31, spaceAfter=17, textColor=colors.black),
        "heading": ParagraphStyle("RUHeading", fontName="ReportRU-Bold", fontSize=16, leading=20, spaceBefore=10, spaceAfter=11, keepWithNext=True),
        "subheading": ParagraphStyle("RUSubheading", fontName="ReportRU-Bold", fontSize=12, leading=16, spaceBefore=8, spaceAfter=10, keepWithNext=True),
        "cell": ParagraphStyle("RUCell", fontName="ReportRU", fontSize=8, leading=10.5),
        "headcell": ParagraphStyle("RUHeadCell", fontName="ReportRU-Bold", fontSize=8, leading=10.5, textColor=colors.white),
    }
    story, web, table_data = [], [], []

    def p(text, small=False):
        story.append(Paragraph(html.escape(text), styles["small" if small else "body"]))
        web.append(f"<p>{html.escape(text)}</p>")

    def heading(text, sub=False):
        story.append(Paragraph(html.escape(text), styles["subheading" if sub else "heading"]))
        tag = "h3" if sub else "h2"
        web.append(f"<{tag}>{html.escape(text)}</{tag}>")

    def page():
        story.append(PageBreak())
        web.append('<div class="pagebreak"></div>')

    def table(headers, data, widths):
        table_data.append({"headers": headers, "rows": data})
        cells = [[Paragraph(html.escape(str(c)), styles["headcell" if i == 0 else "cell"]) for c in row]
                 for i, row in enumerate([headers] + data)]
        t = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#203c58")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d9d9")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([t, Spacer(1, 11)])
        web.append("<table><thead><tr>" + "".join(f"<th>{html.escape(str(c))}</th>" for c in headers) +
                   "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) +
                   "</tr>" for row in data) + "</tbody></table>")

    def group(mode, scenario=None):
        return [r for r in rows if r["mode"] == mode and (scenario is None or r["scenario"] == scenario)]

    title = "Отказоустойчивая университетская информационная система"
    story.extend([Spacer(1, 40), Paragraph(title, styles["title"]), Spacer(1, 10)])
    web.append(f"<h1>{title}</h1>")
    p("Fault Tolerant University Information System")
    p("Технический отчёт по midterm | Fault Tolerance and Dependable Computing")
    p("Campus reliability lab | 5 октября 2026 года | Русская версия")
    story.append(Spacer(1, 27))
    p("Студент: Tastan Magzhan")
    p("Группа: CSE-2505M")
    p("Преподаватель: Azamat Serek")
    story.append(Spacer(1, 25))
    p("В компактной работающей университетской системе сравниваются намеренно упрощённая baseline и конфигурация с fault tolerance (FT). Три бизнес-сервиса и общий сервис хранения SQLite позволяют исследовать сбои, recovery и согласованность транзакций в реальных HTTP-экспериментах.")
    p("Набор данных содержит 54 контролируемых запуска: девять сценариев, две конфигурации и три повторения. Измерения проведены на локальных процессах одного компьютера с Windows. Отказ физического узла моделируется остановкой группы процессов; испытания на нескольких физических серверах не проводились.")
    p("Репозиторий: https://github.com/zzmaga/ftr_midterm")
    p("Данные: results/final | Запуск: README.md | Демонстрация: docs/DEMO.md")
    page()

    heading("1 Введение и мотивация проекта")
    p("Университетская платформа не должна повторно учитывать оплату обучения при потере ответа. Доступ к платежам также не должен зависеть от необязательного сервиса transcript. Проект демонстрирует availability и integrity. Небольшая архитектура позволяет проследить каждый механизм защиты в коде и показать его на короткой устной защите.")
    p("Основной результат - fault containment: второй процесс payment сохраняет доступ к платежам при отказе первой реплики, а транзакции и idempotency предотвращают частичное или повторное применение платежа. Отказ общей базы данных по-прежнему прерывает зависящие от неё операции. Redundancy помогает только в пределах реально защищённой области отказов.")
    heading("2 Требования и допущения")
    p("Задание требует baseline, не менее трёх независимых сервисов, пяти реалистичных сценариев отказа, двух инфраструктурных и четырёх программных механизмов защиты, контролируемого сравнения до и после их внедрения, расчётов reliability и демонстрации трёх сценариев recovery. Реализованы все шесть явно перечисленных в задании сценариев и три дополнительных эксперимента по integrity и recovery.")
    p("Критерии учебного стенда: отсутствие неуспешных запросов списка платежей при падении одной payment-реплики в FT; отсутствие расхождений между балансом и ledger и повторяющихся ключей во всех FT-испытаниях; восстановление полноценных ответов после устранения сбоя; наличие записей об обнаружении, восстановлении и запросах. Эти критерии относятся к экспериментам и не являются production SLA.")
    p("У двух вымышленных студентов начальная задолженность составляет по 100000 тиын. Суммы хранятся целыми числами: 100 тиын = 1 KZT. До измерений каждого эксперимента записывается начальный платёж в 100 тиын, поэтому сохранность проверяется на непустых данных. Управление fault injection доступно локально по token. Аутентификация пользователей, интеграция с банком и развёртывание на нескольких хостах не входят в объём проекта.")
    heading("3 Dependability и fault model")
    p("Dependability включает availability, integrity и recoverability. Reliability характеризует непрерывную работу за интервал; availability допускает восстановление и учитывает долю доступного времени. Fault - причина сбоя; error - некорректное внутреннее состояние или результат; failure - нарушение обещанного поведения сервиса.")
    p("Пример: завершение payment1 является fault; отказ соединения в gateway - error; неуспешный клиентский запрос платежа - service failure. В FT gateway может обратиться к payment2 и скрыть ошибку от клиента. Потеря подтверждения представляет собой omission fault: платёж уже может существовать, хотя клиент увидел отказ.")
    p("Модель включает crash-stop, временные задержки и ошибки, потерю ответа после commit и прерывание операции. Совместная остановка процессов моделирует отказ узла до явного восстановления. Byzantine failures, произвольное повреждение диска, потеря всего хоста и вредоносные запросы исключены. Degraded transcript полезен, но не считается полноценным ответом при расчёте availability.")
    page()

    heading("4 Reliability и анализ отказов")
    p("Качественный failure analysis связывает каждый внедряемый fault с внутренней ошибкой, последствиями для клиента и оставшимися рисками. Вероятности возникновения и численные оценки риска без экспериментального обоснования не назначаются.")
    table(["Fault", "Error и последствия", "Защита и ограничения"], [
        ["Application crash", "Payment endpoint не может соединиться с payment1.", "Реплика и failover сохраняют доступ; gateway и база остаются single points of failure."],
        ["Database outage", "Нет соединения со storage; бизнес-API не могут читать и писать.", "Ограниченный retry и контролируемый 503; restart восстанавливает доступ. Реплики базы нет."],
        ["Service timeout", "Ответ academic превышает downstream timeout.", "Circuit breaker ограничивает вызовы; возвращается помеченный cache. Полный transcript недоступен."],
        ["Node A simulation", "Payment1 и academic завершаются вместе.", "Payment2 и student продолжают работу. Потеря всего хоста не покрыта."],
        ["Interrupted payment", "Баланс изменён до вставки записи в ledger.", "FT выполняет rollback; baseline оставляет расхождение."],
        ["Concurrent load", "Очереди и конкуренция за общее storage увеличивают latency.", "Два worker распределяют запросы; общая SQLite выполняет запись последовательно."],
        ["Duplicate / lost reply", "Один запрос платежа доставляется несколько раз.", "Общий unique key и проверка payload возвращают первоначальный платёж."],
        ["Checkpoint restore", "Восстанавливается более раннее состояние базы.", "Backup возвращает согласованное состояние, но теряет записи после checkpoint."],
    ], [94, 181, 200])
    p("Упрощённое fault tree недоступности платежей: отказ gateway OR отказ storage OR (недоступность payment1 AND недоступность payment2) OR общий отказ хоста/сети. В baseline достаточно отказа единственного payment-процесса. Причины потери integrity рассматриваются отдельно: отсутствие atomicity, отсутствие idempotency или возврат к старому checkpoint без reconciliation.")
    p("При иллюстративном допущении независимости две реплики с availability A=0.99 каждая дают 1-(1-A)^2=0.9999. Если availability gateway и storage также равна 0.99, последовательная система даёт 0.99 x 0.99 x 0.9999 = 0.98000199. Это условные числа, а не экспериментальные оценки. Общий хост дополнительно нарушает допущение независимости.")
    page()

    heading("5 Архитектура системы")
    diagram = architecture()
    for shape in diagram.contents:
        if hasattr(shape, "text"):
            if shape.text == "separate process":
                shape.text, shape.fontName = "отдельный процесс", "ReportRU"
            elif shape.text.startswith("All services emit"):
                shape.text, shape.fontName = "Сервисы пишут JSON logs; стенд сохраняет запросы, faults и результаты audit.", "ReportRU"
    story.extend([diagram, Spacer(1, 14)])
    web.append("<pre>Browser / experiments\n        |\nGateway: round robin, retry, timeout, circuit breaker\n        |\nStudent | Payment 1 | Payment 2 | Academic\n        |\nStorage API / SQLite ---- Checkpoint backup\n        |\nJSON logs + HTTP traces + consistency audits</pre>")
    p("Рисунок 1. Каждый бизнес-сервис работает в отдельном HTTP-процессе. В FT добавляется payment2. Gateway реализован небольшим приложением FastAPI, поэтому выбор маршрута и состояние circuit breaker легко проверить в коде. Mermaid-схема находится в docs/architecture.md.")
    p("Порты: gateway - 8100, student - 8101, payment - 8102 и 8105, academic - 8103, storage - 8104. Эксперименты используют 8200-8205, тесты - 8400-8405. Launcher проверяет доступность портов и управляет только собственными деревьями дочерних процессов.")
    p("Все бизнес-сервисы обращаются к одному storage API. Только его процесс открывает SQLite. Единая точка обработки транзакций обеспечивает согласованную проверку ключей между репликами. В gateway хранятся отдельные circuit breaker для endpoint и transcript cache в памяти. Потеря cache после restart допустима: сервис явно возвращает degraded-ответ без сохранённого transcript.")
    p("В моделируемый node A входят payment1 и academic; в node B - payment2 и student. Это логические группы на одном компьютере. Каждый процесс пишет JSON logs, а экспериментальный стенд отдельно сохраняет времена запросов и снимки состояния.")
    page()

    heading("6 Проектирование hardware fault tolerance")
    p("Инфраструктурная защита включает дополнительные payment instances, round-robin routing с failover и восстановление backup. Gateway обходит завершённый payment-процесс. Позднее стенд перезапускает его по сценарию эксперимента; это запланированный restart, а не автономное восстановление production orchestrator.")
    p("SQLite backup создаёт согласованный checkpoint-файл [2]. В restore-эксперименте возврат к checkpoint намеренно удаляет корректный более поздний платёж, наглядно показывая recovery-point loss. Это логическое восстановление на одном диске. В production backup нужно хранить в другой области отказа и согласовывать с последующими транзакциями через reconciliation.")
    p("RAID использует дисковую redundancy для защиты от определённых отказов дисков, но не отменяет логически неверную запись и не заменяет backup. ECC memory обнаруживает и исправляет поддерживаемые ошибки битов памяти, но не исправляет алгоритм приложения. RAID и ECC описаны теоретически; их реализация и измерение в проекте не заявляются.")
    heading("7 Проектирование software fault tolerance")
    table(["Механизм", "Реализация и границы применения"], [
        ["Retry и timeout", "Gateway выполняет максимум 3 попытки с backoff 50/100 ms и HTTPX timeout 300 ms. В baseline одна попытка и защитный timeout 1 s [3]."],
        ["Circuit breaker", "После двух downstream failures цепь для endpoint открывается. Через 1 s одна HALF_OPEN probe может закрыть её или открыть повторно [5]."],
        ["Idempotency", "Unique key SQLite проверяется внутри BEGIN IMMEDIATE. Тот же key и payload возвращают прежнюю запись; другой payload получает 409."],
        ["Checkpoint и rollback", "До изменения баланса создаётся savepoint; interruption вызывает rollback. Общая транзакция выполняет commit баланса и ledger вместе [1]."],
        ["Health и degradation", "Liveness endpoints показывают состояние процессов. При отказе academic возвращается явно помеченный cache; платёж не получает фиктивный success."],
    ], [112, 363])
    heading("8 Реализация")
    p("Python, FastAPI, HTTPX и SQLite позволяют сохранить небольшой объём приложения. app/service.py запускается независимо для трёх ролей. app/database.py управляет storage и audit; app/resilience.py - политикой recovery. В baseline намеренно нет idempotency, а commit баланса выполняется до вставки платежа. Проверка входных данных сохранена в обеих версиях.")
    p("Автоматические тесты проверяют concurrent duplicates между репликами, конфликт payload, потерю ответа после commit, точное состояние после rollback, backup restore, переходы breaker, отсутствие retry для 4xx и расчёты reliability. Успешно пройдены 17 тестов. Compose-конфигурации проверены; контейнеры не запускались, поскольку Docker engine был недоступен [4].")
    page()

    heading("9 Методика экспериментов")
    p(f"Среда выполнения: {env['platform']}; Python {env['python']}. Начало набора измерений (UTC): {env['started_utc']}. Нагрузка направлялась к реальным локальным HTTP-процессам. По три повторения каждого сценария и режима дают 54 изолированных запуска; порядок baseline/FT чередуется между повторениями.")
    p("В каждом запуске используется новая папка базы. Сначала записывается начальный платёж, затем четыре warm-up probes и внедряется fault. В crash/database/node выполняются семь probes при активном сбое; затем процессы перезапускаются, стенд ждёт liveness и 1.05 s cooldown breaker, после чего выполняет пять recovery probes. Между завершёнными запросами выдерживается 80 ms. В timeout выполняются пять probes при сбое и пять после recovery с ожиданием 1.1 s после ремонта.")
    p("Timeout создаётся задержкой сервера на 1400 ms. Node fault одновременно завершает payment1 и academic. Load включает 120 уникальных платежей по 100 тиын с concurrency 30; duplicate - двенадцать одновременных доставок одного ключа. Interruption срабатывает один раз между изменением баланса и вставкой в ledger. Lost response имитирует 503 после commit. Backup возвращает предыдущий checkpoint и проверяет точное совпадение состояния audit.")
    table(["Показатель", "Определение измерения"], [
        ["Detection time", "От fault injection до первого downstream failure, storage error или rollback в logs. Все wall clocks относятся к одному хосту. Если сигнала нет, указывается n/a."],
        ["Service recovery", "От injection до первой последующей полноценной успешной probe. При маскировании через failover это время подтверждения успеха, а не downtime."],
        ["Component restoration", "От injection до отметки о завершении restart/reset в стенде. Восстановление компонента отделено от успешного ответа сервиса."],
        ["Request availability", "Число полноценных успешных ответов / число измеренных запросов. Degraded-ответы academic с HTTP 200 считаются отдельно."],
        ["Consistency", "initial_due - due = SUM(payment.amount); нет duplicate keys; начальный платёж сохранён. HTTP success в baseline может скрывать нарушение данных."],
        ["Recovered requests", "Полноценные успешные запросы клиента, потребовавшие более одной попытки gateway. Ненаблюдаемые downstream retries не учитываются."],
    ], [112, 363])
    p("Для интервалов запросов и событий используется perf_counter; structured logs содержат UTC wall time для сопоставления обнаруженных сбоев. Time availability оценивается по probes, а не непрерывно. Concurrent load-запросы не задают интервалы downtime; probes до и после burst могут пропустить отказ внутри него. Поэтому временные метрики интерпретируются только для crash, database, timeout и node.")
    page()

    heading("10 Результаты и сравнение")
    names = {"crash": "Application crash", "database": "Database outage", "timeout": "Academic timeout", "node": "Node A loss", "interruption": "Interrupted payment", "load": "Concurrent load", "duplicate": "Duplicate delivery", "backup": "Checkpoint restore", "response_loss": "Lost acknowledgement"}
    summary_data = []
    for scenario, name in names.items():
        b, f = group("baseline", scenario), group("ft", scenario)
        def counts(g):
            return f"{sum(r['successful_requests'] for r in g)}/{sum(r['requests'] for r in g)}"
        summary_data.append([name, counts(b), counts(f), f"{sum(r['consistent'] for r in b)}/3", f"{sum(r['consistent'] for r in f)}/3"])
    table(["Сценарий", "Baseline full", "FT full", "B consistent", "FT consistent"], summary_data, [145, 88, 82, 80, 80])
    p("Таблица 1. Объединены три повторения. Full - полноценные успешные ответы / все запросы. Consistent - число повторений, выполнивших оба бизнес-инварианта. Дополнительные проверки student/payment в node и timeout включены в итоги. Backup представляет отдельную проверку recovery; у baseline нет функции восстановления checkpoint.")
    b, f = group("baseline"), group("ft")
    p(f"В смешанной нагрузке baseline дала {sum(r['failed_requests'] for r in b)} неуспешных полноценных ответов из {sum(r['requests'] for r in b)}, FT - {sum(r['failed_requests'] for r in f)} из {sum(r['requests'] for r in f)}. В FT {sum(r['recovered_requests'] for r in f)} запросов восстановились благодаря retry. Итоги описывают только этот набор сценариев и не являются общим availability SLO.")
    p("Replica failover устранил ошибки получения списка платежей при application crash. При node loss в FT academic endpoint всё равно возвращал degraded-ответы, учтённые как потеря полноценной услуги. При storage outage обе версии теряли полноценные ответы зависимых сервисов: storage replication отсутствует. В baseline сценарии duplicate и lost reply могли возвращать HTTP success при нарушении уникальности платежа, поэтому availability и integrity оцениваются отдельно.")
    load_data = []
    for mode in ["baseline", "ft"]:
        subset = group(mode, "load")
        cps = [c for c in cases if c["summary"]["mode"] == mode and c["summary"]["scenario"] == "load"]
        rates = [c["extra"]["load_throughput_rps"] for c in cps]
        load_data.append([mode, fmt(statistics.mean(rates), 1), f"{min(rates):.1f} - {max(rates):.1f}", fmt(mean(subset, "p95_latency_ms"), 1)])
    table(["Режим", "Среднее requests/s", "Диапазон повторений", "Среднее case p95, ms"], load_data, [90, 125, 140, 120])
    p("Таблица 2. Throughput рассчитан по 120 завершённым запросам burst; все они успешны в представленном наборе. p95 - среднее значений nearest-rank latency percentile отдельных запусков, включая probes до и после нагрузки. Трёх повторений недостаточно для статистически устойчивого вывода о преимуществе производительности.")
    page()

    heading("Расчёты reliability к разделу 10", sub=True)
    p("T - интервал от начала первого запроса до итогового audit; D - суммарная длительность объединённых интервалов downtime по probes; U=T-D; F - число эпизодов отказа; C - число завершённых recovery. Эпизод начинается при завершении первой неуспешной полноценной probe и заканчивается при завершении следующей полноценной успешной. Незавершённый в конце наблюдения эпизод ограничивается моментом T.")
    p("Оценка MTTF = U/F; MTTR = сумма завершённых интервалов downtime / C; оценка MTBF = MTTF + MTTR; time availability = U/T; observed failure rate = F/U. Request availability = полноценные успехи / N; retry recovery fraction = успешные запросы с retry / все запросы с retry. Если знаменателя нет, ставится n/a. Оценки MTTF/MTBF для repairable cycle используют ограниченное окно наблюдения и описывают внедрённые отказы, а не естественный срок безотказной работы.")
    metric_data = []
    for scenario in ["crash", "database", "timeout", "node"]:
        for mode in ["baseline", "ft"]:
            g = group(mode, scenario)
            U = sum(r["uptime_s"] for r in g)
            T = sum(r["observation_s"] for r in g)
            F = sum(r["outage_episodes"] for r in g)
            C = sum(r["completed_recoveries"] for r in g)
            mttr = sum(r["mttr_s"] * r["completed_recoveries"] for r in g if r["mttr_s"] is not None) / C if C else None
            mttf = U / F if F else None
            metric_data.append([scenario, mode, fmt(mttf), fmt(mttr), fmt(mttf + mttr if mttf is not None and mttr is not None else None), f"{U/T*100:.1f}%", fmt(F/U)])
    table(["Сценарий", "Режим", "MTTF, s", "MTTR, s", "MTBF, s", "Time A", "Rate /s"], metric_data, [76, 61, 68, 68, 68, 66, 68])
    p("Таблица 3. Объединены время наблюдения и recovery трёх повторений. Для FT node time availability относится к payment probes. Отдельный degraded transcript учтён в таблице 1, но не как payment outage. Поэтому в FT crash и node нет наблюдаемого payment outage, по которому можно оценить MTTF или MTTR.")
    detection = []
    for scenario in ["crash", "database", "timeout", "node", "interruption", "response_loss"]:
        b, f = group("baseline", scenario), group("ft", scenario)
        detection.append([scenario, fmt(mean(b, "detection_ms"), 1), fmt(mean(f, "detection_ms"), 1), fmt(mean(b, "service_recovery_ms"), 1), fmt(mean(f, "service_recovery_ms"), 1)])
    table(["Сценарий", "B detect, ms", "FT detect, ms", "B confirm, ms", "FT confirm, ms"], detection, [99, 92, 92, 96, 96])
    p("Таблица 4. Средние интервалы от injection до detection и первого подтверждённого success. В них входит расписание нагрузки. Более долгие timeout probes в baseline могут задерживать запланированный стендом repair. Поэтому разницу recovery нельзя целиком объяснять более быстрым ремонтом инфраструктуры: на неё также влияет методика запуска.", small=True)
    page()

    heading("11 Обсуждение и ограничения")
    p("Для выбранных FT-сценариев учебные цели availability и integrity выполнены: при каждом single-replica crash сохранены полноценные payment-ответы, все FT audits согласованы, после восстановления возобновились обычные probes. Данные не доказывают непрерывную работу при потере базы или всего хоста. Реальное развёртывание потребовало бы redundant gateway, database replication, отдельных хостов и проверенной политики backup recovery.")
    p("Load test ограничен по объёму; база сериализует платежи с помощью process lock. Поэтому replication в основном защищает от отказа процесса, а не масштабирует запись. В baseline намеренно ослаблены границы транзакции. Сравнение имеет учебную цель и не является сравнением с корректно спроектированной production payment system.")
    p("Параметры timeout и retry выбраны для локального демо. HTTPX timeout ограничивает отдельные сетевые фазы, а не строгий end-to-end deadline [3]. Timeout между сервисом и базой составляет 800 ms. Retry выполняется только в gateway, чтобы избежать многократного умножения попыток. Для production нужны jitter, load shedding, общий deadline, ограниченный cache и tracing между хостами.")
    p("Состояние circuit breaker и transcript cache находятся в одном gateway-процессе. Health endpoints подтверждают liveness, но не readiness базы. Обнаружение отказа пассивное: оно происходит при обращении к неисправному endpoint. Node simulation не воспроизводит сбои CPU, ядра, диска или сетевого коммутатора. Physical hardware redundancy, RAID и ECC не измерялись.")
    p("Доступны только три повторения на одном хосте, конечная нагрузка и искусственно внедрённые faults. Нет оснований заявлять confidence interval или естественную failure rate. Оценки по probes пропускают время до обнаружения первой ошибки и могут не заметить короткий outage между запросами. Отсутствие измерений внутри load burst не считается доказанной availability.")
    p("Restore удаляет платежи и ключи после checkpoint. Его следует выполнять в maintenance/quiescence window с последующим reconciliation. Backup в демо хранится на том же диске. Приложение предназначено для локального обучения, его бизнес-API не имеет пользовательской аутентификации и не должно быть публично доступно.")
    heading("12 Заключение")
    p("Небольшая университетская система позволяет наглядно исследовать fault tolerance. Application replication защищает выбранный сервис при потере процесса; circuit breaker ограничивает повторные обращения к неисправной зависимости; rollback и idempotency сохраняют integrity платежей. Эксперименты показывают и границы защиты: общая база и хост остаются общей областью отказа. Исходные запросы, event logs и снимки audit делают выводы воспроизводимыми.")
    page()

    heading("13 Источники")
    refs = [
        ("1", "SQLite. Atomic Commit in SQLite.", "https://www.sqlite.org/atomiccommit.html"),
        ("2", "SQLite. Online Backup API.", "https://www.sqlite.org/backup.html"),
        ("3", "HTTPX. Timeouts.", "https://www.python-httpx.org/advanced/timeouts/"),
        ("4", "Docker. Control startup and shutdown order in Compose.", "https://docs.docker.com/compose/how-tos/startup-order/"),
        ("5", "Microsoft Learn. Circuit Breaker pattern.", "https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker"),
        ("6", "FastAPI. Deployment concepts.", "https://fastapi.tiangolo.com/deployment/concepts/"),
    ]
    for number, title, url in refs:
        p(f"[{number}] {title} Дата обращения: 5 октября 2026 года.", small=True)
        story.append(Paragraph(f'<link href="{url}" color="#244bc3">{html.escape(url)}</link>', styles["small"]))
        web.append(f'<p><a href="{url}">{url}</a></p>')
    p("Первичная документация [1-6] описывает используемые механизмы и принципы развёртывания. Все измеренные значения получены из экспериментальных записей этого репозитория, а не из примеров в источниках.")
    heading("14 Приложение с кодом конфигурацией logs и дополнительными результатами")
    table(["Материал", "Содержание"], [
        ["app/", "Gateway, управление fault injection, бизнес-сервисы, recovery policy, база и dashboard."],
        ["scripts/", "Launcher дочерних процессов, эксперименты, метрики, проверка данных и сборка отчётов."],
        ["tests/", "17 автоматических unit tests и HTTP integration tests."],
        ["compose.yaml и baseline override", "Топология контейнеров, liveness checks, реплики и раздельные bind-mounted данные."],
        ["results/final/", "54 JSON-сценария, summary.csv, сведения о среде и JSON event logs сервисов."],
        ["docs/", "Архитектура, checklist задания, инструкции для demo и защиты, готовые отчёты."],
    ], [166, 309])
    p("Воспроизведение: python -m pytest -q; python -m scripts.experiments --trials 3; python -m scripts.verify_results results/final. Новые эксперименты создают отдельные папки. Английский отчёт собирается командой python -m scripts.build_report --dataset results/final; русский - python -m scripts.build_report_ru --dataset results/final. Зависимости указаны в requirements-report.txt; русская версия использует Arial TTF с поддержкой кириллицы.", small=True)
    p("В logs записаны request IDs, UTC timestamps, service instance, mode, action, status и latency. Transaction events содержат ключ платежа; поля fault, attempt и recovery добавляются к соответствующим событиям. Отсутствующие поля не заменяются вымышленными измерениями.", small=True)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("ReportRU", 8)
        canvas.setFillColor(colors.HexColor("#68788a"))
        canvas.drawString(60, 30, "Campus reliability lab | Технический отчёт по midterm")
        canvas.drawRightString(A4[0] - 60, 30, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(str(output / "REPORT_RU.pdf"), pagesize=A4, rightMargin=60, leftMargin=60,
                            topMargin=46, bottomMargin=50, title="Отказоустойчивая университетская информационная система",
                            author="Tastan Magzhan", subject="Русская версия midterm report")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    css = "body{font:16px/1.6 Arial,sans-serif;color:#172535;max-width:980px;margin:50px auto;padding:0 25px}h1,h2,h3{color:#000;line-height:1.2}h2{margin-top:35px}table{border-collapse:collapse;width:100%;font-size:14px;margin:20px 0}th,td{border:1px solid #d9d9d9;padding:10px;text-align:left}th{background:#203c58;color:white}tr:nth-child(even){background:#f0f4f8}pre{white-space:pre-wrap;background:#f2f5f8;padding:20px}@media print{body{margin:0;font-size:10pt}.pagebreak{break-before:page}tr{break-inside:avoid}h2,h3{break-after:avoid}a{color:inherit}}"
    (output / "REPORT_RU.html").write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Midterm report на русском</title><style>' + css + '</style><main>' + ''.join(web) + '</main></html>', encoding="utf-8")
    print(f"Created {output / 'REPORT_RU.pdf'} and REPORT_RU.html from {len(rows)} measured cases")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "results" / "final")
    parser.add_argument("--output", type=Path, default=ROOT / "docs")
    parser.add_argument("--font-dir", type=Path)
    args = parser.parse_args()
    build(args.dataset, args.output, args.font_dir)
