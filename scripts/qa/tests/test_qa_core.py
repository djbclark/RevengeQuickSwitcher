import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ocr_locator import locate_phrase, parse_tsv
from qss_events import QA_BRIDGE_PREFIX, find_event, parse_line, scan_lines
from step_runner import Step, run_step, run_steps

# ---- qss_events (mirror of src/qabridge.test.ts) ----

LOGCAT_LINE = (
    '07-19 22:00:00.000  1234  5678 I ReactNativeJS: '
    'QSSQA|{"v":"4.6.0","msg":"navigateToGuild openUrl ok","args":[{"id":"123"}]}'
)


def test_parse_line_mid_line_prefix():
    event = parse_line(LOGCAT_LINE)
    assert event is not None
    assert event.version == "4.6.0"
    assert event.msg == "navigateToGuild openUrl ok"
    assert event.args == [{"id": "123"}]


def test_parse_line_rejects_non_bridge_and_malformed():
    assert parse_line("ReactNativeJS: hello") is None
    assert parse_line(QA_BRIDGE_PREFIX + "{not json") is None
    assert parse_line(QA_BRIDGE_PREFIX + '{"v":"4.6.0"}') is None  # msg required


def test_find_event_version_pinning():
    lines = [
        'I ReactNativeJS: QSSQA|{"v":"4.5.10","msg":"onLoad"}',
        'I ReactNativeJS: QSSQA|{"v":"4.6.0","msg":"onLoad"}',
    ]
    assert find_event(lines, "onLoad", version="4.6.0").version == "4.6.0"
    assert find_event(lines, "onLoad", version="9.9.9") is None
    assert len(list(scan_lines(lines))) == 2


# ---- step_runner ----

def test_run_step_success_and_postcondition_failure():
    ok = run_step(Step("ok", action=lambda: None, postcondition=lambda: True))
    assert ok.ok and ok.phase == "done"

    state = {"recovered": False}
    bad = run_step(
        Step(
            "bad",
            action=lambda: None,
            postcondition=lambda: False,
            recovery=lambda: state.__setitem__("recovered", True),
        )
    )
    assert not bad.ok and bad.phase == "post" and bad.recovered
    assert state["recovered"]


def test_hanging_action_hits_deadline_not_600s():
    start = time.monotonic()
    result = run_step(Step("hang", action=lambda: time.sleep(60), deadline_s=0.3))
    elapsed = time.monotonic() - start
    assert not result.ok and result.phase == "action"
    assert "deadline" in result.error
    assert elapsed < 5  # the v1 hang class: structurally impossible now


def test_run_steps_stops_and_reports():
    report = run_steps(
        [
            Step("first", action=lambda: None),
            Step("boom", action=lambda: (_ for _ in ()).throw(RuntimeError("x"))),
            Step("never", action=lambda: None),
        ]
    )
    assert not report.ok
    assert report.aborted_at == "boom"
    assert [r.name for r in report.results] == ["first", "boom"]
    assert '"aborted_at": "boom"' in report.to_json()


# ---- ocr_locator ----

TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"


def _row(block, line, word, left, top, w, h, conf, text):
    return f"5\t1\t{block}\t1\t{line}\t{word}\t{left}\t{top}\t{w}\t{h}\t{conf}\t{text}"


FIXTURE_TSV = "\n".join(
    [
        TSV_HEADER,
        _row(1, 1, 1, 100, 200, 80, 40, 96.0, "Filter"),
        _row(1, 1, 2, 190, 200, 110, 40, 94.0, "servers"),
        _row(1, 2, 1, 100, 300, 90, 40, 91.0, "Alpha"),
        _row(1, 2, 2, 200, 300, 90, 40, 30.0, "Ghost"),  # below confidence
        _row(2, 1, 1, 100, 900, 80, 40, 88.0, "filter"),  # other block, lower conf
        _row(2, 1, 2, 190, 900, 110, 40, 87.0, "SERVERS"),
        "5\t1\t3\t1\t1\t1\t0\t0\t0\t0\t-1\t",  # empty separator row
    ]
)


def test_parse_tsv_filters_confidence_and_blanks():
    words = parse_tsv(FIXTURE_TSV)
    assert [w.text for w in words] == ["Filter", "servers", "Alpha", "filter", "SERVERS"]


def test_locate_phrase_case_insensitive_best_confidence():
    match = locate_phrase(FIXTURE_TSV, "  filter   SERVERS ")
    assert match is not None
    assert match.text == "Filter servers"  # picks the higher-confidence block
    assert match.box == (100, 200, 300, 240)
    assert match.center == (200, 220)


def test_locate_phrase_requires_same_line_and_order():
    assert locate_phrase(FIXTURE_TSV, "servers Filter") is None
    assert locate_phrase(FIXTURE_TSV, "Filter Alpha") is None
    assert locate_phrase(FIXTURE_TSV, "Ghost") is None  # low-confidence word
