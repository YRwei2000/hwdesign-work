# Resume the existing C simulation project for only changed fixtures.
# No reset, code generation, synthesis, co-simulation, or target change.
set root [file dirname [file normalize [info script]]]
cd $root
open_project csim_proj
open_solution solution1
if {[catch {csim_design -argv "[file join $root data recheck]"} message]} {
    puts "SCALE_OFFSET_RECHECK_FAILED: $message"
    exit 1
}
puts "SCALE_OFFSET_RECHECK_COMPLETED"
exit 0
