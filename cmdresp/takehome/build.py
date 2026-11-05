"""Explicit reproducible stages; no implicit synthesis/cosim from evidence checks."""
import os
from pathlib import Path
import subprocess
import sys
from verify import ROOT,freeze
import json

PYTHON="/home/yw9286/waveflow-venv/bin/python"
VITIS="/eda/xilinx/2026.1/Vitis/bin/vitis-run"
def python(script,*args):
    subprocess.run([PYTHON,str(ROOT/script),*args],cwd=ROOT,check=True)
def main(stage):
    if stage in ("evidence","fix-evidence") and (ROOT/"evidence/fix_v2/final_ready.json").exists():
        python("audit_fix.py")
    elif stage in ("fix-synth","fix-cosim","fix-protocol"):
        if (ROOT/"evidence/fix_v2/final_ready.json").exists():
            raise SystemExit("Corrected run already recorded. Preserve it and select a new run directory for a later authorized revision.")
        if stage=="fix-synth":
            for name in (ROOT/"data/scenarios.txt").read_text().split():
                for suffix in ("csim_fix","cosim_fix","csim_fix_unread","cosim_fix_unread"):
                    (ROOT/"data"/name/suffix).mkdir(exist_ok=True)
            python("generate_fix.py")
            subprocess.run([VITIS,"--mode","hls","--tcl","fix_run.tcl"],cwd=ROOT,
                           env=dict(os.environ,POOL_FIX_STAGE="synth"),check=True)
            python("verify.py","csim_fix")
        elif stage=="fix-cosim":
            subprocess.run([VITIS,"--mode","hls","--tcl","fix_run.tcl"],cwd=ROOT,
                           env=dict(os.environ,POOL_FIX_STAGE="cosim_setup"),check=True)
            python("prepare_fix_sim.py")
            subprocess.run([VITIS,"--mode","hls","--tcl","execute_fix_cosim.tcl"],cwd=ROOT,check=True)
            python("verify.py","cosim_fix");python("verify_fix.py")
        else:
            python("export_protocol_fixtures.py");python("run_protocol.py");python("analyze_protocol.py")
    elif stage=="model":python("verify.py","model")
    elif stage=="generate":python("generate.py")
    elif stage in ("csim","synth","cosim"):
        gate=json.loads((ROOT/"evidence/model_gate.json").read_text())
        assert freeze()==gate["frozen_sources"]
        if stage!="csim":python("verify.py","csim")
        if stage=="cosim" and (ROOT/"evidence/check_cosim.json").exists():
            raise SystemExit("Co-simulation already recorded. Preserve evidence; do not rerun it implicitly.")
        env=dict(os.environ,POOL_STAGE=stage)
        subprocess.run([VITIS,"--mode","hls","--tcl","run.tcl"],cwd=ROOT,env=env,check=True)
        if stage in ("csim","cosim"):python("verify.py",stage)
    elif stage=="evidence":
        python("verify.py","csim");python("verify.py","cosim");python("review.py")
        python("report.py")
    else:raise SystemExit("stage: model | generate | csim | synth | cosim | evidence")
if __name__=="__main__":main(sys.argv[1])
