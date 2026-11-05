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
    if stage=="model":python("verify.py","model")
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
