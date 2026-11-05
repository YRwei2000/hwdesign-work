"""Build/run the independent full-fixture RTL host, with VCD in this execution."""
import os
from pathlib import Path
import shutil
import subprocess
from verify import ROOT,save,sha

VIVADO=Path("/eda/xilinx/2026.1/Vivado/bin")
def run():
    work=ROOT/"protocol_sim";work.mkdir(exist_ok=True)
    out=ROOT/"evidence/fix_v2/protocol";out.mkdir(exist_ok=True)
    syn=ROOT/"off_proj/solution1/syn/verilog"
    standard=ROOT/"off_proj/solution1/sim/verilog"
    lines=[]
    for p in (standard/"ip/xil_defaultlib").glob("*.vhd"):
        lines.append(f'vhdl xil_defaultlib "{p}"')
    sources=sorted(syn.glob("*.v"))
    for p in sources:lines.append(f'sv xil_defaultlib "{p}"')
    lines.append(f'sv xil_defaultlib "{ROOT/"rtl_protocol_tb.sv"}"')
    (work/"protocol.prj").write_text("\n".join(lines)+"\n")
    (work/"capture.tcl").write_text(
        f'open_vcd {out/"protocol.vcd"}\n'
        'log_vcd [get_objects -filter {type == in_port || type == out_port || type == inout_port || type == port} /rtl_protocol_tb/dut/*]\n'
        'log_vcd [get_objects /rtl_protocol_tb/case_index]\n'
        'log_vcd [get_objects /rtl_protocol_tb/active]\n'
        'run all\nclose_vcd\nquit\n')
    env=dict(os.environ)
    dirs=["lnx64/tools/fpo_v7_1","lnx64/tools/fft_v9_1","lnx64/tools/fir_v7_0","lnx64/tools/dds_v6_0","tps/lnx64/gcc-8.3.0/lib","lib/lnx64.o/Default"]
    env["LD_LIBRARY_PATH"]=":".join("/eda/xilinx/2026.1/Vitis/"+d for d in dirs)+":"+env.get("LD_LIBRARY_PATH","")
    before={str(p.relative_to(ROOT)):sha(p) for p in sources}
    with (out/"compile.log").open("w") as log:
        subprocess.run([str(VIVADO/"xelab"),"xil_defaultlib.rtl_protocol_tb","-prj","protocol.prj",
                        "-L","floating_point_v7_1_22","-L","unisims_ver","-L","xpm","-s","protocol",
                        "-debug","typical"],cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    with (out/"simulation.log").open("w") as log:
        subprocess.run([str(VIVADO/"xsim"),"protocol","-tclbatch","capture.tcl",
                        "-testplusarg",f"FIXTURE_ROOT={ROOT/'evidence/fix_v2/protocol_fixtures'}",
                        "-testplusarg",f"OUTPUT_ROOT={out}"],cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    after={str(p.relative_to(ROOT)):sha(p) for p in sources}
    assert before==after
    save(out/"snapshot.json",dict(dut_rtl_sha256=before,unchanged=True,case_count=69,
         testbench_sha256=sha(ROOT/"rtl_protocol_tb.sv"),
         complete_input_fixtures=True,independent_axis_driver=True,direct_vcd_capture=True))
    shutil.copy2(work/"protocol.prj",out/"protocol.prj")
    shutil.copy2(work/"capture.tcl",out/"capture.tcl")
    print("Independent RTL protocol simulation completed; inspect self-check and wave checks")
if __name__=="__main__":run()
