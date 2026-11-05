# Read-only command/part compatibility probe: no simulation or synthesis.
puts "SCALE_OFFSET_COMPATIBILITY_PROBE"
foreach cmd {open_project set_top add_files open_solution set_part create_clock csim_design} {
    if {[llength [info commands $cmd]] == 0} { error "Required command unavailable: $cmd" }
    puts "AVAILABLE $cmd"
}
exit 0
