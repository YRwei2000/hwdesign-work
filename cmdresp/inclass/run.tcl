# C simulation only. There is deliberately no synthesis/co-simulation branch.
set root [file dirname [file normalize [info script]]]
cd $root
open_project -reset csim_proj
set_top scale_offset
set flags "-I$root -std=c++14 -ffp-contract=off -fno-fast-math"
puts "SCALE_OFFSET_CFLAGS $flags"
add_files [file join $root gen scale_offset.cpp] -cflags $flags
add_files -tb [file join $root scale_offset_tb.cpp] -cflags $flags
open_solution -reset solution1
set_part {xc7z020clg484-1}
create_clock -period 10
if {[catch {csim_design -clean -argv "[file join $root data]"} message]} {
    puts "SCALE_OFFSET_CSIM_FAILED: $message"
    exit 1
}
puts "SCALE_OFFSET_CSIM_COMPLETED"
exit 0
