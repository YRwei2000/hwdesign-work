"""Configure capture BEFORE first simulator launch; never change generated RTL."""
from pathlib import Path
import shutil
from waveflow.scripts.xsim_vcd import modify_tcl
from verify import ROOT,save,sha

def prepare():
    sim=ROOT/"off_proj/solution1/sim/verilog"
    evidence=ROOT/"evidence/fix_v2"
    # Waveflow's official capture helper adds open/log/close_vcd to a COPY.
    capture=evidence/"cosim_capture.tcl"
    modify_tcl(str(sim/"max_pool.tcl"),str(capture),"port")
    launch=(sim/"run_xsim.sh").read_text()
    assert launch.count("-tclbatch max_pool.tcl")==1
    launch=launch.replace("-tclbatch max_pool.tcl",f"-tclbatch {capture}")
    (evidence/"run_cosim_capture.sh").write_text(launch)
    # Keep Vitis' entire C precheck / RTL / C postcheck flow. Only select the
    # launcher's capture Tcl before its first execution, not a later replay.
    runtime=(sim/"run_sim.tcl").read_text()
    old="sh ./run_xsim.sh"
    assert runtime.count(old)==1
    runtime=runtime.replace(old,f"sh {evidence/'run_cosim_capture.sh'}")
    (evidence/"run_cosim_capture.tcl").write_text(runtime)
    save(evidence/"capture_configuration.json",dict(first_execution_capture=True,
         generator="waveflow.scripts.xsim_vcd.modify_tcl",rtl_modified=False,
         cpp_testbench_sha256=sha(ROOT/"pool_tb.cpp"),scenarios=66,
         source_runtime_sha256=sha(sim/"run_sim.tcl"),capture_runtime_sha256=sha(evidence/"run_cosim_capture.tcl")))
    print("Configured first-execution VCD capture, full generated co-simulation flow")
if __name__=="__main__":prepare()
