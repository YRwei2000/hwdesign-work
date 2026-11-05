set root [file dirname [file normalize [info script]]]
open_project [file join $root off_proj]
open_solution solution1
cd [file join $root off_proj solution1 sim verilog]
source [file join $root evidence fix_v2 run_cosim_capture.tcl]
puts "POOL_FIX_STANDARD_COSIM_FLOW_COMPLETED"
exit 0
