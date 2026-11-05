#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
/eda/xilinx/2026.1/Vivado/bin/xsim -testplusarg "UVM_VERBOSITY=UVM_NONE" -testplusarg "UVM_TESTNAME=max_pool_test_lib" -testplusarg "UVM_TIMEOUT=20000000000000" --noieeewarnings max_pool -tclbatch max_pool_vcd.tcl -view max_pool_dataflow_ana.wcfg -protoinst max_pool.protoinst
