"""ONE user-authorized replay of the existing snapshot solely to capture VCD."""
import json
import os
from pathlib import Path
import shutil
from datetime import datetime,timezone
from verify import ROOT,save,sha
from waveflow.scripts.xsim_vcd import run_xsim_vcd

def hashes():
    paths=[ROOT/"max_pool_body_impl.tpp",ROOT/"gen/max_pool.cpp",ROOT/"pool_tb.cpp"]
    paths+=list((ROOT/"pool_proj/solution1/sim/verilog").glob("*.v"))
    paths+=list((ROOT/"pool_proj/solution1/sim/verilog/xsim.dir/max_pool").glob("xsimk*"))
    # xsimkernel.log is a runtime log, not executable snapshot content.
    return {str(p.relative_to(ROOT)):sha(p) for p in paths if p.is_file() and p.suffix!=".log"}

if __name__=="__main__":
    evidence=ROOT/"evidence/replay_authorization.json"
    if evidence.exists():raise SystemExit("Authorized replay already attempted; no repeat permitted")
    before=hashes()
    record=dict(utc=datetime.now(timezone.utc).isoformat(),prompt_version="v2",replay_number=1,
        authorization="User explicitly authorized one additional same-snapshot, all-66-activation replay for VCD and required cycle measurements only",
        reason="Initial full-suite cosim saved WDB only; offline WDB extraction could not be validated",
        no_resynthesis=True,no_kernel_changes=True,no_optimization=True,scope="All 66 original activations",
        before_sha256=before)
    save(evidence,record) # guard set BEFORE launch: even a failure cannot silently retry
    # Match the existing Vitis-generated simulation process library search paths.
    dirs=["lnx64/tools/fpo_v7_1","lnx64/tools/fft_v9_1","lnx64/tools/fir_v7_0",
          "lnx64/tools/dds_v6_0","tps/lnx64/gcc-8.3.0/lib","lib/lnx64.o/Default"]
    os.environ["LD_LIBRARY_PATH"]=":".join("/eda/xilinx/2026.1/Vitis/"+d for d in dirs)+":"+os.environ.get("LD_LIBRARY_PATH","")
    try:
        path=run_xsim_vcd(top="max_pool",comp="pool_proj",out="ports.vcd",soln="solution1",
                          trace_level="port",workdir=ROOT)
        shutil.copy2(path,ROOT/"evidence/ports.vcd")
        record["after_sha256"]=hashes()
        record["same_snapshot"]=record["after_sha256"]==before
        assert record["same_snapshot"]
        record["vcd_sha256"]=sha(ROOT/"evidence/ports.vcd")
        original=ROOT/"evidence/cosim_raw"
        current=ROOT/"pool_proj/solution1/sim/tv/rtldatafile"
        compared={p.name:sha(p)==sha(current/p.name) for p in original.glob("rtl.*.dat")}
        record["rtl_vectors_identical_to_first_cosim"]=compared
        assert compared and all(compared.values())
        record["completed"]=True
    except Exception as exc:
        record.update(completed=False,error=repr(exc))
        raise
    finally:
        save(evidence,record)
