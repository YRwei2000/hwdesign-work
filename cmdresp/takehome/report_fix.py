"""Final seven-section report for the user-authorized v2 correctness revision."""
import json
import re
from pathlib import Path
from verify import ROOT,save,sha,freeze

FIX=ROOT/"evidence/fix_v2"
def load(name):return json.loads((FIX/name).read_text())
def mark(ok):return "PASS" if ok else "FAIL"
def report():
    gate=json.loads((ROOT/"evidence/model_gate.json").read_text())
    assert freeze()==gate["frozen_sources"]
    functional=load("functional_summary.json");policy=load("interface_policy.json")
    synthesis=load("synthesis.json");perf=load("performance.json")
    protocol=load("check_protocol.json");wave=load("check_rtl_wave.json")
    csim=load("check_csim_fix.json");cosim=load("check_cosim_fix.json")
    names=(ROOT/"data/scenarios.txt").read_text().split()
    complete=all(v["pass_"] for d in (protocol,wave,csim,cosim) for v in d.values())
    timing=perf["input_cycle_target_pass"] and perf["no_host_input_pauses"] and perf["no_output_backpressure"] and synthesis["clock_pass"]
    overall=complete and timing and functional["pass_"] and policy["pass_"]
    base="evidence/fix_v2"
    lines=["# Float32 2-D max-pooling results — committed specification v2","",
        f"**Overall: {mark(overall)} for the corrected implementation.** "
        "The original failed interface implementation, first co-simulation and authorized "
        "measurement replay remain preserved in [the initial report](results_initial.md). "
        "The confirmed prompt and numerical/protocol semantics were not changed. No Git commit or push was performed.","",
        "## Interface","",
        "The wire encoding is unchanged: [layout.md](layout.md), "
        "[serialized examples](evidence/layout_examples.json). Six uint32 input words are "
        "`[0x504f4f4c, tx_id, opcode, H, W, K]`; COMPUTE=1 and END=2. The three-word "
        "response is `[tx_id, H/K, W/K]`. Headers end with TLAST. Matrix/result words "
        "carry one original binary32 sample each, row-major, with TLAST only at the end. "
        "END ignores H/W/K, sends nothing and stops the activation.","",
        "AXI-Lite contains control and read-only halted/error/tx_id; status is cleared "
        "per activation. Codes are 0 success, 1 header, 2 opcode, 3 H range, 4 W range, "
        "5 K range, 6 window bounds, 7 divisibility, 8 early payload TLAST, 9 missing "
        "final TLAST. Unavailable tx_id uses 0xffffffff without further reads. "
        "Offsets 0x10/0x20/0x30 are retained in "
        f"[generated control RTL]({base}/synthesis/max_pool_control_s_axi.v).", "",
        "Both final AXIS interfaces have register_mode=off, verified from actual interface "
        "generation messages and absence of the input/output register slices in "
        f"[RTL]({base}/rtl/max_pool.v): [policy verdict]({base}/interface_policy.json).", "",
        "## Design","",
        "[pool.py](pool.py), [oracle.py](oracle.py), scenario intent and "
        "[the kernel body](max_pool_body_impl.tpp) retain their original hashes. "
        "The kernel validates headers word by word, then checks parameters in the required "
        "order. It writes the complete response, buffers and validates the full matrix, "
        "computes/caches row-major strict-greater maxima, then emits the complete result "
        "burst. Payload errors return before result emission. No Python timing model or "
        "performance-optimization rewrite was introduced.", "",
        "The first correction attempt put off directives in project Tcl. They were accepted "
        "as commands but the generated bare AXIS pragmas left both interfaces at the default "
        f"both mode: [failed attempt]({base}/tcl_attempt/verdict.json), "
        f"[actual log]({base}/tcl_attempt/vitis_synth.log). "
        "The minimal effective fix is [generate_fix.py](generate_fix.py): a project-local "
        "Waveflow signature-emitter configuration adds only the two explicit off options "
        "during generation. It does not post-edit generated files or modify the installed "
        "Waveflow package. [The generated boundary](gen_off/max_pool.cpp) otherwise matches "
        "the original byte for byte after removing those options; headers remain identical. "
        f"[Generation diff and guards]({base}/generation.json), "
        f"[effective build log]({base}/off_build.log).", "",
        "The independent [RTL host](rtl_protocol_tb.sv) loads complete serialized fixtures, "
        "advances only on external AXI handshakes, reads status through AXI-Lite and keeps "
        "the next unaccepted beat valid through completion, status reads and the observation "
        "window. It resets the DUT/stream path before cancelling that beat and loading "
        "the next independent activation. A harness watchdog only detects a hung test; "
        "it is not an input timeout or hardware error path.", "",
        "## Targets", "",
        "| Criterion | Required | Measured | Result | Source |",
        "| --- | --- | --- | --- | --- |",
        f"| Device / clock setting | xc7z020clg484-1 / 10 ns | {synthesis['part']} / {synthesis['target_ns']} ns | PASS | [synthesis]({base}/synthesis/max_pool_csynth.xml) |",
        f"| Estimated clock | <10 ns | {synthesis['estimated_ns']} ns | {mark(synthesis['clock_pass'])} | [timing report]({base}/synthesis/max_pool_csynth.rpt) |",
        f"| 64×64 K=2 input transfers, inclusive | ≤8192 cycles | {perf['input_cycles']} cycles | {mark(timing)} | [measurement]({base}/performance.json), [VCD]({base}/cosim.vcd.gz) |",
        f"| First matrix input to final result, inclusive | no target; report | {perf['total_latency_cycles']} cycles = {perf['total_latency_ns']/1000:.2f} us | PASS (reported) | [measurement]({base}/performance.json) |",
        f"| Input throughput over input interval | report | {perf['input_samples_per_cycle']:.6f} samples/cycle = {perf['input_megasamples_per_second']:.6f} Msamples/s | PASS (reported) | [measurement]({base}/performance.json) |",
        f"| Results over total interval | no target; report | {perf['end_to_end_results_per_cycle']:.8f} results/cycle | PASS (reported) | [measurement]({base}/performance.json) |",
        f"| Benchmark host pauses / output backpressure | none | continuously valid={perf['no_host_input_pauses']}; continuously ready={perf['no_output_backpressure']} | PASS | [wave check]({base}/performance.json) |"]
    for n,v in synthesis["resources"].items():
        lines.append(f"| {n} | no target; report | {v} | PASS (reported) | [resource report]({base}/synthesis/max_pool_csynth.xml) |")
    for filename,loops in synthesis["loops"].items():
        for loop in loops:
            if "PipelineII" in loop:
                lines.append(f"| {filename.removesuffix('_csynth.xml')} II | no target; report | {loop['PipelineII']} | PASS (reported) | [loop report]({base}/synthesis/{filename}) |")
    lines += ["", "Timing comes from actual TVALID&&TREADY transfers in this revision's standard "
        "C/RTL co-simulation VCD. Rising edges are sampled using pre-edge stable signal values; "
        "intervals are last-first+1, excluding headers. "
        f"[Signal map]({base}/wave_signals.json), [handshake record]({base}/rtl_handshakes.jsonl.gz). "
        "The estimated-period limit is 10 ns; the default uncertainty margin does not create "
        "a stricter pass criterion. No call-level latency or synthesis II was substituted "
        "for a required waveform measurement.", "",
        "## Verification", "",
        f"The independently validated Python model is retained: **{gate['arithmetic_vectors']}** "
        "arithmetic cases, with hand-worked/bit-literal checks and a separate NumPy reshape/max "
        "reference plus first-equal bit selection. [Arithmetic evidence](evidence/arithmetic.json), "
        "[model gate](evidence/model_gate.json), [model log](evidence/model_validation.log). "
        "Its model/oracle/scenario sources and original evidence hashes remain unchanged; "
        f"[reuse justification]({base}/reuse_validation.json). "
        "C simulation was rerun after boundary regeneration rather than relying on the "
        "earlier C result. The original checker rejection demonstrations remain retained in "
        "[checker_rejections.json](evidence/checker_rejections.json).", "",
        "The repaired standard regression covers all original **66 activations**, including "
        "**29 errors and 29 separate recoveries**. It uses Vitis cosim_design -setup followed "
        "by its generated C-precheck/RTL/C-postcheck runtime; only the simulator launch Tcl "
        "selects first-execution VCD capture through Waveflow's capture helper. No C model, "
        "RTL stimulus or comparison was replaced. "
        f"[Setup]({base}/cosim_setup.log), [full runtime log]({base}/cosim_run.log), "
        f"[capture setup]({base}/capture_configuration.json), "
        f"[C comparison]({base}/check_csim_fix.json), [RTL comparison]({base}/check_cosim_fix.json), "
        f"[direct raw RTL-vector check]({base}/check_raw_rtl_vectors.json).", "",
        "The independent RTL suite covers those same activations using **all** fixture words, "
        "plus backpressured success, backpressured first-payload error and its own fresh "
        "recovery: **69 activations** total. It compares external words/count/order/TLAST, "
        "actual AXI-Lite status reads, exact input stopping positions, reset intervals and "
        "pending data through the observation window. "
        f"[Full-fixture manifest]({base}/protocol_fixture_manifest.json), "
        f"[self-check log]({base}/protocol/simulation.log), "
        f"[independent waveform verdict]({base}/check_protocol.json), "
        f"[raw VCD]({base}/protocol/protocol.vcd.gz), "
        f"[handshakes]({base}/protocol/handshakes.jsonl.gz), "
        f"[signal map]({base}/protocol_signals.json).", "",
        "| Scenario | Model reference | C simulation | Standard RTL co-sim | Full-fixture external RTL | Evidence |",
        "| --- | --- | --- | --- | --- | --- |"]
    for n in names:
        d=f"data/{n}";p=protocol[n]
        lines.append(f"| {n} | PASS (retained) | {mark(csim[n]['pass_'])} | {mark(cosim[n]['pass_'] and wave[n]['pass_'])} | {mark(p['pass_'])}: {p['received_words']}/{p['full_fixture_words']} received | "
            f"[intent]({d}/intent.json), [expected]({d}/expected.json), [model]({d}/model.json), [C]({d}/csim_fix/observed.json), [RTL]({d}/cosim_fix/observed.json), [pins]({base}/check_protocol.json) |")
    for n in ("BP_success","BP_payload_error","R_BP_payload_error"):
        p=protocol[n]
        lines.append(f"| {n} | PASS (same {p['source']} fixture) | source fixture above | source fixture above | {mark(p['pass_'])}: {p['received_words']}/{p['full_fixture_words']} received | [manifest]({base}/protocol_fixture_manifest.json), [status/handshakes]({base}/check_protocol.json), [log]({base}/protocol/summary.txt) |")
    lines += ["", "Response-header last-word backpressure is applied while the complete input "
        "queue remains offered. The following are external handshake cycles; all have "
        "TVALID=TREADY=1 at the listed transfer and response TLAST=1. No payload handshake "
        "occurs during the stalled interval. Protocol-cycle numbering is 1-based with the "
        f"first rising edge at 5 ns: [pin evidence]({base}/check_protocol.json).", "",
        "| Test | TREADY=0 interval before last header word | Response last output | First payload input | Result |",
        "| --- | --- | --- | --- | --- |"]
    for n in ("BP_success","BP_payload_error"):
        bp=protocol[n]["backpressure"]
        lines.append(f"| {n} | {bp['first_stall_cycle']}..{bp['last_stall_cycle']} ({bp['stalled_last_header_cycles']} cycles) | {bp['response_last_cycle']} | {bp['first_payload_cycle']} | {mark(bp['pass_'])}: input strictly later |")
    lines += ["", "Signals are rtl_protocol_tb.dut.m_out_TVALID/TREADY/TDATA/TLAST and "
        "rtl_protocol_tb.dut.s_in_TVALID/TREADY/TDATA/TLAST. Pending-word checks keep "
        "TVALID=1, TREADY=0 and the exact next TDATA/TLAST stable until stream-path reset; "
        "they are not inferred from C shadow stream sizes. Every added error has its own "
        "recovery. For example, malformed-magic and first-payload-error cases are detailed "
        f"in [the waveform verdict]({base}/check_protocol.json), including actual halted, "
        "error and transaction-ID readbacks. Successful prior commands and header-only "
        "payload-error responses remain bit-exact.", "",
        "## Assumptions", "",
        "All delegated wire/status choices remain documented under Interface and layout.md. "
        "No confirmed semantic requirement changed. Installed Vitis remains 2026.1 and "
        "the Python environment remains /home/yw9286/waveflow-venv/bin/python; no packages "
        "were upgraded. License settings and credentials were neither changed nor printed. "
        "Normal execution approval was used for license-service access, as previously "
        "diagnosed in [the initial report](results_initial.md).", "",
        "The protocol test uses a finite observation window after completion/status, then "
        "asserts reset to cancel pending input. The final harness waits 17 falling edges "
        "after the last status read, which covers 16 complete subsequent sampled cycles. "
        "A physical reset is checked after every error or pending-input case and before "
        "each activation. A reset after the final successful, fully consumed activation "
        "is not a recovery requirement and is marked not applicable when simulation ends. "
        "The window and watchdog are test-harness choices, not kernel input timeouts. "
        "Permanent input starvation and unsupported numeric inputs remain outside scope.", "",
        "## Open Items", ""]
    lines += ["None within the confirmed v2 scope. The prior external-order failure and "
        "unverified error-stop behavior are closed by effective interface-policy checks "
        "and full-fixture external RTL tests, including backpressure and recovery."] if overall else ["FAIL: see the failed criteria above and machine-readable evidence; no unrun check is claimed passed."]
    lines += ["", "Historical failures remain failures in their original records: the first "
        "implementation's ordering violation, the ineffective Tcl-only off attempt, and "
        "the first independent-test observation-window mismatch. They are not relabeled "
        "as passes. The corrected run has separate evidence.", "",
        "## Run History", "",
        "| Run / prompt version | Action and authorization | Outcome / evidence |",
        "| --- | --- | --- |",
        "| Original independent model / v2 | User-authorized implementation; hand/NumPy validation first | PASS: [gate](evidence/model_gate.json) |",
        "| Original C simulation / v2 | License-gated attempt, then normal approval retry | PASS after retry: [log](evidence/vitis_csim_license_retry.log), [comparison](evidence/check_csim.json) |",
        "| Original synthesis and FIRST co-simulation / v2 | First kernel, all 66 activations | Functional PASS; external order FAIL: [original report](results_initial.md), [cosim log](evidence/vitis_cosim.log), [wave verdict](evidence/check_rtl_wave.json) |",
        "| Original EXTRA measurement replay / v2 | User explicitly authorized one same-snapshot replay solely for VCD | Same output/status and code snapshot: [authorization](evidence/replay_authorization.json), [replay log](evidence/vcd_replay.log), [original VCD](evidence/ports.vcd.gz) |",
        f"| Correctness revision, Tcl-only attempt / v2 | User authorized both register_mode=off and affected verification; isolated fix_proj | FAIL: actual both mode retained; [attempt]({base}/tcl_attempt/verdict.json), [log/RTL]({base}/tcl_attempt/vitis_synth.log) |",
        f"| Effective interface correction, C simulation and synthesis / v2 | Project-local Waveflow generator policy; isolated off_proj; no arithmetic or performance rewrite | PASS: [generation]({base}/generation.json), [build]({base}/off_build.log), [effective policy]({base}/interface_policy.json), [C]({base}/check_csim_fix.json) |",
        f"| Corrected standard co-simulation / v2 | Full 66 activations; VCD configured before FIRST execution of corrected RTL | PASS: [runtime]({base}/cosim_run.log), [vectors]({base}/check_raw_rtl_vectors.json), [wave]({base}/check_rtl_wave.json), [measurements]({base}/performance.json) |",
        f"| Independent full-fixture RTL test, observation trial / v2 | Full suite plus backpressure cases | DUT self-check passed; post-check FAIL because 16 falling edges gave only 15 full cycles after status: [reason]({base}/protocol_observation_trial/reason.json), [original verdict]({base}/protocol_observation_trial/check_protocol.json), [VCD]({base}/protocol_observation_trial/protocol.vcd.gz) |",
        f"| Independent RTL observation correction / v2 | Only harness wait changed to 17 falling edges; strict 16-full-cycle checker retained; no resynthesis or standard-regression rerun | PASS, all 69 activations: [log]({base}/protocol/simulation.log), [wave check]({base}/check_protocol.json), [unchanged DUT snapshot]({base}/protocol/snapshot.json) |", "",
        "The original co-simulation, its separately authorized measurement replay, the corrected "
        "standard co-simulation and independent protocol executions are distinct. VCD was captured "
        "directly during each new simulation; no additional waveform replay was used for this "
        "correctness revision. The observation-only rerun did not alter the DUT or its timing. "
        "The initial report and all its raw evidence remain retained.", "",
        f"[Current source manifest]({base}/source_manifest.json), "
        f"[integrity audit]({base}/integrity.json), [reproduction](README.md). "
        "The committed prompt, classroom project and old labs were not modified. No Git commit "
        "or push was performed.", ""]
    (ROOT/"results.md").write_text("\n".join(lines))
    paths=[p for pattern in ("*.py","*.tpp","*.cpp","*.hpp","*.tcl","*.sv") for p in ROOT.glob(pattern)]
    paths += [ROOT/n for n in ("prompt.md","README.md","layout.md",".gitignore")]
    paths += [p for directory in ("gen","gen_off","include") for p in (ROOT/directory).glob("*") if p.is_file()]
    save(FIX/"source_manifest.json",{str(p.relative_to(ROOT)):sha(p) for p in paths})
    save(FIX/"final_ready.json",dict(pass_=overall,specification_version="v2",standard_activations=66,
         protocol_activations=69,original_error_activations=29,added_error_activations=1,
         synthesis_clock_pass=synthesis["clock_pass"],timing_pass=timing))
    print("CORRECTED REPORT",mark(overall))
if __name__=="__main__":report()
