"""Retain trace checks and the explicit source review required by prompt v2."""
import json
from verify import ROOT,save,sha

def review():
    names=(ROOT/"data/scenarios.txt").read_text().split();report={}
    for name in names:
        d=ROOT/"data"/name
        events=[json.loads(s) for s in (d/"csim/trace.jsonl").read_text().splitlines()]
        seen=set();valid=set();problems=[];stopped=False
        for e in events:
            if stopped and e["kind"] in ("HREAD","PREAD"):problems.append("Read after ERROR/END")
            if e["kind"]=="RESP_DONE":seen.add(e["tx"])
            if e["kind"]=="INPUT_VALID":valid.add(e["tx"])
            if e["kind"]=="PREAD" and e["tx"] not in seen:problems.append("Payload read before response")
            if e["kind"]=="RESULT" and e["tx"] not in valid:problems.append("Result before input validation")
            if e["kind"] in ("ERROR","END"):stopped=True
        report[name]=dict(pass_=not problems,problems=problems)
    save(ROOT/"evidence/check_c_order.json",report)
    assert all(r["pass_"] for r in report.values())
    findings=[
        dict(requirement="No input timeout",source="max_pool_body_impl.tpp",
             observation="Blocking s_in.read and generated blocking lane reader; no empty-input status, timer or timeout path"),
        dict(requirement="Parameter precedence and safe arithmetic",source="max_pool_body_impl.tpp",
             observation="Ordered early returns in parameter_error; dimensions used for products, indexing and division only after success"),
        dict(requirement="Per-activation reset and fresh stream recovery",source="pool_tb.cpp",
             observation="New streams inside scenario loop; poisoned status before each call; kernel clears status at entry"),
        dict(requirement="Unknown transaction ID",source="max_pool_body_impl.tpp",
             observation="Fixed 0xffffffff until second word received; no read follows a detectable header violation"),
        dict(requirement="Full result buffering and payload-error discard",source="max_pool_body_impl.tpp",
             observation="All input validated before pooling and results array filled before emit_loop; any payload error returns before that loop"),
        dict(requirement="Whole scenario suite in first cosim",source="run.tcl",
             observation="No scenario argument/filter; same data/scenarios.txt for C simulation and sole cosim_design call"),
    ]
    save(ROOT/"evidence/source_review.json",dict(review_type="manual source review with retained source hashes; no RTL timing claim",
         findings=findings,source_sha256={n:sha(ROOT/n) for n in ("max_pool_body_impl.tpp","pool_tb.cpp","run.tcl")},
         c_order_all_pass=True,python_timing_model=False))
    print("C ORDER CHECK PASS",len(report),"activations; source review retained")

if __name__=="__main__":review()
