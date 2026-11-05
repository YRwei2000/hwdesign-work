"""Offline port-only extraction from the ORIGINAL WDB; never runs a simulator.

The vendored reader's full-database CLI rejects untraced internal state in this
port-only WDB. Restrict reconstruction to the specified complete port objects;
retain all of the reader's validation for each selected stream. No unknown value
is filled, guessed or suppressed on a selected stream.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"tools/wdb_converter"))
import waveform_converter as converter
from verify import save,sha

PORTS={"ap_clk","s_in_TDATA","s_in_TVALID","s_in_TREADY","s_in_TLAST",
       "m_out_TDATA","m_out_TVALID","m_out_TREADY","m_out_TLAST"}
original=converter._reconstruct_stream
selected=[]
def reconstruct_ports(stream,wdb):
    paths=[obj.path for obj in stream.dbg_objects]
    if any(p.rsplit("/",1)[-1] in PORTS and "/AESL_inst_max_pool/" in p for p in paths):
        print("SELECTED",hex(stream.absolute_addr),stream.payload_bytes,paths,flush=True)
        original(stream,wdb) # strict completeness/alignment/type checks remain in force
        selected.extend(p for p in paths if "/AESL_inst_max_pool/" in p)
    else:
        stream.events=[] # unrelated/untraced internal objects are outside this export
converter._reconstruct_stream=reconstruct_ports

if __name__=="__main__":
    src=ROOT/"pool_proj/solution1/sim/verilog/max_pool.wdb"
    wave=converter.load_wdb([src])
    converter.write_vcd(wave,ROOT/"evidence/ports.vcd",timescale="1ps")
    save(ROOT/"evidence/wdb_reader.json",dict(source="https://github.com/Ross0907/Vivado-WDB-Waveform-Converter",
         source_file="tools/wdb_converter/waveform_converter.py",version=converter.APP_VERSION,
         source_sha256=sha(ROOT/"tools/wdb_converter/waveform_converter.py"),
         original_wdb_sha256=sha(src),offline=True,simulator_rerun=False,
         selected_aliases=selected,selection=sorted(PORTS),
         limitation="Untraced internal states excluded before reconstruction; all selected port states must be complete"))
    print("OFFLINE PORT EXPORT COMPLETE",len(selected),"aliases; no simulation rerun")
