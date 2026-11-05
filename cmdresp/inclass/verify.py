"""Reproducible model gate and exact C simulation checker; no tolerances."""
import copy
import hashlib
import json
from pathlib import Path
import random
import sys
from datetime import datetime, timezone

import numpy as np
from waveflow.utils.burst_io import StreamBurst, write_bursts, read_bursts
from oracle import evaluate_bits
from scale_offset import bits, from_bits, evaluate, stream_model, CmdHdr, RespHdr, header, Command
from scenarios import scenarios

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def bursts(words):
    result, pending = [], []
    for value, last in words:
        pending.append(value)
        if last:
            result.append(StreamBurst(np.array(pending, dtype=np.uint64), True))
            pending = []
    if pending:
        result.append(StreamBurst(np.array(pending, dtype=np.uint64), False))
    return result


def flatten(path):
    return [[int(w), int(b.tlast and i == len(b.words)-1)]
            for b in read_bursts(path) for i, w in enumerate(b.words)]


def compare(got, expected):
    return [f"{key} mismatch" for key in ("words", "status", "consumed", "unread")
            if got.get(key) != expected[key]]


def arithmetic_gate():
    # Independent literals pin down the oracle AND the numpy model.
    fixed = [
        (0x40000000, 0x3F800000, 0x3F800000, 0x40000000, 0x40400000),
        (0x40000000, 0x3F800000, 0x40000000, 0x40800000, 0x40A00000),
        (0x40000000, 0x3F800000, 0x40400000, 0x40C00000, 0x40E00000),
        (0x40400000, 0xBF800000, 0x3F800000, 0x40400000, 0x40000000),
        (0x40400000, 0xBF800000, 0x40000000, 0x40C00000, 0x40A00000),
        (0x3F800001, 0xBF800000, 0x3F7FFFFE, 0x3F800000, 0),
        (0x3F800000, 0x33800000, 0x3F800000, 0x3F800000, 0x3F800000),
        (0x3F800000, 0x33800000, 0x3F800001, 0x3F800001, 0x3F800002),
        (0x3FC00000, 0, 0x3F800001, 0x3FC00002, 0x3FC00002),
        (0x80000000, 0x80000000, 0x3F800000, 0x80000000, 0x80000000),
        (0x3F800000, 0, 0x80000000, 0x80000000, 0),
        (0x3F800000, 0, 0x00800000, 0x00800000, 0x00800000),
        (0x3F800000, 0, 0x7F7FFFFF, 0x7F7FFFFF, 0x7F7FFFFF),
        (0x00800000, 0, 0x00800000, 0, 0),
        (0x80800000, 0x80000000, 0x00800000, 0x80000000, 0x80000000),
        (0x00800000, 0, 0x3F7FFFFF, 0x00800000, 0x00800000),
    ]
    records = []
    rng = random.Random(20261104)
    vectors = [(a, b, x, (p, y)) for a, b, x, p, y in fixed]
    def normal():
        return (rng.getrandbits(1) << 31) | (rng.randint(90, 164) << 23) | rng.getrandbits(23)
    vectors += [(normal(), normal(), normal(), None) for _ in range(4096)]
    for a, b, x, literal in vectors:
        expected = evaluate_bits(a, b, x)
        got = tuple(bits(v) for v in evaluate(from_bits(a), from_bits(b), from_bits(x)))
        passed = expected == got and (literal is None or expected == literal)
        records.append({"input_hex": [f"{v:08x}" for v in (a, b, x)],
                        "oracle_hex": [f"{v:08x}" for v in expected],
                        "model_hex": [f"{v:08x}" for v in got],
                        "literal_hex": None if literal is None else [f"{v:08x}" for v in literal],
                        "pass": passed})
    save(EVIDENCE / "arithmetic.json", records)
    assert all(r["pass"] for r in records), "Independent arithmetic validation failed"
    return len(records)


def manifest():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [ROOT / n for n in ("prompt.md", "scale_offset.py", "oracle.py", "scenarios.py")]}


def model_gate(reuse_arithmetic=False):
    if reuse_arithmetic:
        # The protocol-only correction does not invalidate arithmetic evidence.
        import ast
        before = (EVIDENCE / "pre_empty_fix/scale_offset.py").read_text()
        after = (ROOT / "scale_offset.py").read_text()
        def arithmetic_ast(text):
            return ast.dump(next(n for n in ast.parse(text).body
                                 if isinstance(n, ast.FunctionDef) and n.name == "evaluate"))
        assert arithmetic_ast(before) == arithmetic_ast(after)
        old = json.loads((EVIDENCE / "pre_empty_fix/model_gate.json").read_text())
        assert old["frozen_sources"]["oracle.py"] == manifest()["oracle.py"]
        records = json.loads((EVIDENCE / "arithmetic.json").read_text())
        assert len(records) == old["arithmetic_vectors"] and all(r["pass"] for r in records)
        count = len(records)
    else:
        count = arithmetic_gate()
    report = {}
    cases = scenarios()
    for case in cases:
        d = ROOT / "data" / case.name
        write_bursts(bursts(case.words), d / "in")
        expected = case.expected()
        # Independent word-count invariant from intent, without any serializer.
        logical_words = sum(2 if a["kind"] == "CONFIG" else
                            2 + a["accepted"] if a["kind"] == "DATA" and a["expected_error"] not in (3, 4)
                            else 0 for a in case.actions)
        assert len(expected["words"]) == logical_words, case.name + ": phantom/missing result words"
        save(d / "intent.json", {"covers": case.covers, "actions": case.actions})
        save(d / "expected.json", expected)
        write_bursts(bursts(expected["words"]), d / "expected")
        got = stream_model(case.words)
        save(d / "model.json", got)
        problems = compare(got, expected)
        report[case.name] = {"pass": not problems, "problems": problems, "covers": case.covers}
        (d / "csim").mkdir(exist_ok=True)
        (d / "unread").mkdir(exist_ok=True)
        print(case.name, "PASS" if not problems else problems)
    (ROOT / "data/scenarios.txt").write_text("\n".join(c.name for c in cases) + "\n")
    save(EVIDENCE / "check_model.json", report)
    # Feed actual corruptions to the same checker used for C simulation.
    wanted = cases[0].expected()
    mutations = {}
    for name in ("result_bit", "output_tlast", "wrong_status", "extra_input_read"):
        wrong = copy.deepcopy(wanted)
        if name == "result_bit":
            wrong["words"][4][0] ^= 1  # first DATA result after two 2-word headers
        elif name == "output_tlast":
            wrong["words"][6][1] = 0
        elif name == "wrong_status":
            wrong["status"]["halted"] = 1
        else:
            wrong["consumed"] += 1
        problems = compare(wrong, wanted)
        mutations[name] = {"rejected": bool(problems), "problems": problems}
    save(EVIDENCE / "checker_rejections.json", mutations)
    assert all(r["rejected"] for r in mutations.values())
    assert all(r["pass"] for r in report.values()), "Model protocol gate failed"
    empty_case = next(c for c in cases if c.name == "E09_first_early").expected()
    wrong = copy.deepcopy(empty_case)
    wrong["words"].append([0, 1])
    mutations["fake_empty_result"] = {"rejected": bool(compare(wrong, empty_case)),
                                      "problems": compare(wrong, empty_case)}
    save(EVIDENCE / "checker_rejections.json", mutations)
    assert mutations["fake_empty_result"]["rejected"]
    layout = {}
    for name, obj in [("CONFIG", header(Command.CONFIG, 0x12345678, a=2, b=1)),
                      ("DATA", header(Command.DATA, 0x89ABCDEF, nsamp=3)),
                      ("END", header(Command.END, 77))]:
        layout[name] = [f"{int(w):08x}" for w in obj.serialize(word_bw=32)]
    save(EVIDENCE / "serialized_layout.json", layout)
    save(EVIDENCE / "model_gate.json", {"pass": True, "arithmetic_vectors": count,
         "activations": len(cases), "arithmetic_reused": reuse_arithmetic,
         "completed_utc": datetime.now(timezone.utc).isoformat(),
         "frozen_sources": manifest()})
    print(f"MODEL_GATE PASS: {count} arithmetic vectors; {len(cases)} activations")


def trace_check(events, expected):
    problems = []
    reads = [e for e in events if e["kind"] in ("HREAD", "PREAD")]
    if len(reads) != expected["consumed"]:
        problems.append("trace input-read count mismatch")
    header_done = None
    for event in events:
        if event["kind"] == "HREAD":
            header_done = None
        elif event["kind"] == "RESP_DONE":
            header_done = event
        elif event["kind"] == "PREAD":
            if header_done is None or header_done["tx"] != event["tx"]:
                problems.append("payload read before matching complete response header")
            elif event["out_count"] < header_done["out_count"]:
                problems.append("response header not enqueued before payload read")
    errors = [i for i, e in enumerate(events) if e["kind"] == "ERROR"]
    if expected["status"]["halted"]:
        if len(errors) != 1:
            problems.append("expected exactly one error event")
        elif any(e["kind"] in ("HREAD", "PREAD") for e in events[errors[0]+1:]):
            problems.append("input read after error")
    elif errors:
        problems.append("unexpected error event")
    return problems


def check_csim():
    gate = json.loads((EVIDENCE / "model_gate.json").read_text())
    assert gate["pass"] and gate["frozen_sources"] == manifest(), "Frozen model inputs changed"
    report = {}
    for case in scenarios():
        d = ROOT / "data" / case.name
        expected = json.loads((d / "expected.json").read_text())
        model = json.loads((d / "model.json").read_text())
        status = json.loads((d / "csim/status.json").read_text())
        got = {"words": flatten(d / "csim"), "status": {k: status[k] for k in ("halted", "error", "tx_id")},
               "consumed": status["consumed"], "unread": flatten(d / "unread")}
        events = [json.loads(line) for line in (d / "csim/trace.jsonl").read_text().splitlines()]
        problems = compare(got, expected) + ["model: " + p for p in compare(got, model)]
        problems += trace_check(events, expected)
        save(d / "csim/observed.json", got)
        report[case.name] = {"pass": not problems, "problems": problems, "covers": case.covers,
                             "trace_events": len(events)}
        print(case.name, "PASS" if not problems else problems)
    save(EVIDENCE / "check_csim.json", report)
    assert all(r["pass"] for r in report.values()), "C simulation comparison failed"
    print(f"CSIM_GATE PASS: {len(report)} activations; exact bits, TLAST, status, unread input, order")


if __name__ == "__main__":
    if sys.argv[1:] == ["model"]:
        model_gate()
    elif sys.argv[1:] == ["model", "--reuse-arithmetic"]:
        model_gate(reuse_arithmetic=True)
    elif sys.argv[1:] == ["csim"]:
        check_csim()
    else:
        raise SystemExit("usage: verify.py model|csim")
