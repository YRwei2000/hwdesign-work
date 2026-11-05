"""Offline finalization only; does NOT launch or rerun any simulation."""
from verify import ROOT,save,sha
import json

if __name__=="__main__":
    path=ROOT/"evidence/replay_authorization.json"
    r=json.loads(path.read_text())
    old=ROOT/"evidence/replay_capture_initial.json"
    if not old.exists():save(old,r)
    a=r["before_sha256"];b=r["after_sha256"]
    changed=[k for k in a.keys()|b.keys() if a.get(k)!=b.get(k)]
    assert changed==["pool_proj/solution1/sim/verilog/xsim.dir/max_pool/xsimkernel.log"],changed
    code_a={k:v for k,v in a.items() if not k.endswith(".log")}
    code_b={k:v for k,v in b.items() if not k.endswith(".log")}
    assert code_a==code_b
    original=ROOT/"evidence/cosim_raw";current=ROOT/"pool_proj/solution1/sim/tv/rtldatafile"
    comparisons={p.name:sha(p)==sha(current/p.name) for p in original.glob("rtl.*.dat")}
    assert comparisons and all(comparisons.values())
    log=(ROOT/"evidence/vcd_replay.log").read_text()
    assert '66 / 66' in log and (ROOT/"evidence/ports.vcd").exists()
    r.update(same_snapshot=True,completed=True,rtl_vectors_identical_to_first_cosim=comparisons,
             vcd_sha256=sha(ROOT/"evidence/ports.vcd"),
             bookkeeping_correction="Initial snapshot assertion included mutable xsimkernel.log; offline review confirms it is the only changed file. All kernel, RTL and executable snapshot hashes match. No second replay.",
             changed_runtime_logs=changed)
    r.pop("error",None)
    save(path,r)
    print("REPLAY VERIFIED OFFLINE: same code snapshot; all original RTL output/status vectors identical")
