# Add only the newly identified in-domain floating-point boundary fixture.
set root [file dirname [file normalize [info script]]]
cd $root
open_project csim_proj
open_solution solution1
if {[catch {csim_design -argv "[file join $root data boundary_recheck]"} message]} {
    puts "SCALE_OFFSET_BOUNDARY_RECHECK_FAILED: $message"
    exit 1
}
puts "SCALE_OFFSET_BOUNDARY_RECHECK_COMPLETED"
exit 0
