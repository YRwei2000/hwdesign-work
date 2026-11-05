"""Evidence checks for the interface correction; never invokes a simulator."""
import gzip
import json
from pathlib import Path
import re
import shutil
from analyze import retain_synthesis,analyze_wave
from verify import ROOT,save,sha,freeze

FIX=ROOT/"evidence/fix_v2"
def vectors(path):
    return {int(i):[int(x,16) for x in re.findall(r"0x[0-9a-fA-F]+",body)]
            for i,body in re.findall(r"\[\[transaction\]\]\s+(\d+)\s+(.*?)\[\[/transaction\]\]",path.read_text(),re.S)}

def verify(analyze_timing=True):
    initial=json.loads((FIX/"reuse_validation.json").read_text())
    assert freeze()==initial["model_freeze"]
    assert all(sha(ROOT/n)==v for n,v in initial["reused_source_sha256"].items())
    original_changed=[n for n,v in initial["original_evidence_sha256"].items() if sha(ROOT/n)!=v]
    assert not original_changed,original_changed
    initial.update(reuse_python_model_gate=True,original_csim_preserved=True,csim_fix_rerun=True,
        reuse_csim=False,reason="Arithmetic/model/intent unchanged; C simulation rerun because interface boundary was regenerated with explicit off pragmas")
    save(FIX/"reuse_validation.json",initial)
    log=(FIX/"off_build.log").read_text()
    interface_lines=[s for s in log.splitlines() if "RTGEN 206-500" in s and ("/s_in_V_" in s or "/m_out_V_" in s)]
    rtl=ROOT/"off_proj/solution1/syn/verilog/max_pool.v"
    text=rtl.read_text()
    assert len(interface_lines)==8 and not any("register" in s for s in interface_lines)
    assert "regslice" not in text and "s_in_TREADY = 1'b0" in text
    assert (ROOT/"gen_off/max_pool.cpp").read_text().count("register_mode=off")==2
    dest=FIX/"rtl";dest.mkdir(exist_ok=True)
    for p in rtl.parent.glob("*.v"):shutil.copy2(p,dest/p.name)
    save(FIX/"interface_policy.json",dict(pass_=True,requested={"s_in":"off","m_out":"off"},
        actual={"s_in":"off","m_out":"off"},rtgen_log_lines=interface_lines,
        input_output_regslice_absent=True,kernel_idle_input_ready_zero=True,
        rtl_sha256=sha(rtl),generated_cpp_sha256=sha(ROOT/"gen_off/max_pool.cpp"),
        generator_adapter="generate_fix.py",installed_waveflow_unchanged=True))
    retain_synthesis("off_proj",FIX)
    names=(ROOT/"data/scenarios.txt").read_text().split()
    for stage in ("csim_fix","cosim_fix"):
        checked=json.loads((ROOT/"evidence"/f"check_{stage}.json").read_text())
        assert len(checked)==66 and all(v["pass_"] for v in checked.values())
        save(FIX/f"check_{stage}.json",checked)
    raw=ROOT/"off_proj/solution1/sim/tv/rtldatafile"
    fields={"words":"m_out_V_data_V","last":"m_out_V_last_V","halted":"halted","error":"error","tx_id":"tx_id"}
    decoded={key:vectors(raw/f"rtl.max_pool.autotvout_{field}.dat") for key,field in fields.items()}
    direct={}
    for i,n in enumerate(names):
        expected=json.loads((ROOT/"data"/n/"expected.json").read_text())
        good=decoded["words"][i]==[p[0] for p in expected["words"]] and decoded["last"][i]==[p[1] for p in expected["words"]]
        good=good and all(decoded[k][i]==[expected["status"][k]] for k in ("halted","error","tx_id"))
        direct[n]=dict(pass_=good,transaction=i)
    save(FIX/"check_raw_rtl_vectors.json",direct)
    assert all(v["pass_"] for v in direct.values())
    retained=FIX/"cosim_raw";retained.mkdir(exist_ok=True)
    for p in raw.glob("*.dat"):shutil.copy2(p,retained/p.name)
    for p in (ROOT/"off_proj/solution1/sim/report").rglob("*.rpt"):shutil.copy2(p,retained/p.name)
    if analyze_timing:
        wave=ROOT/"off_proj/solution1/sim/verilog/dump.vcd"
        checks=analyze_wave(wave,FIX)
        assert len(checks)==66 and all(v["pass_"] for v in checks.values())
        with wave.open("rb") as src,gzip.open(FIX/"cosim.vcd.gz","wb") as dst:shutil.copyfileobj(src,dst)
    save(FIX/"functional_summary.json",dict(pass_=True,activations=66,model_reused=True,
          csim_fix_pass=True,cosim_fix_pass=True,raw_rtl_vector_pass=True,
          actual_interface_policy_verified=True,original_evidence_unchanged=True))
    print("FIX FUNCTIONAL/INTERFACE CHECK PASS: 66 activations; original evidence unchanged")
if __name__=="__main__":verify()
