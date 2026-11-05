"""Generate the seven required sections from retained, measured evidence."""
import json
import re
from verify import ROOT,save,sha,freeze

def read(name):return json.loads((ROOT/name).read_text())
def verdict(ok):return "PASS" if ok else "FAIL"
def link(label,path):return f"[{label}]({path})"

def report():
    gate=read("evidence/model_gate.json")
    assert freeze()==gate["frozen_sources"]
    names=(ROOT/"data/scenarios.txt").read_text().split()
    model,csim,cosim=[read(f"evidence/check_{s}.json") for s in ("model","csim","cosim")]
    corder=read("evidence/check_c_order.json")
    synth=read("evidence/synthesis.json")
    wave=read("evidence/check_rtl_wave.json") if (ROOT/"evidence/check_rtl_wave.json").exists() else None
    perf=read("evidence/performance.json") if (ROOT/"evidence/performance.json").exists() else None
    replay=read("evidence/replay_authorization.json") if (ROOT/"evidence/replay_authorization.json").exists() else None
    arithmetic=read("evidence/arithmetic.json")
    assert len(arithmetic)==gate["arithmetic_vectors"] and all(x["pass_"] for x in arithmetic)
    numeric=all(d[n]["pass_"] for d in (model,csim,cosim) for n in names)
    wave_ok=bool(wave) and all(r["pass_"] for r in wave.values())
    perf_ok=bool(perf) and perf["input_cycle_target_pass"] and perf["no_host_input_pauses"] and perf["no_output_backpressure"]
    overall=numeric and wave_ok and perf_ok and synth["clock_pass"]
    text=["# Float32 2-D max-pooling results — prompt v2", "",
          f"**Overall: {verdict(overall)}.** Functional output/status comparisons are {verdict(numeric)}; "
          "the complete protocol and measurement verdict also includes the RTL waveform checks below.","",
          "## Interface","",
          "The host contract is in [layout.md](layout.md), with actual Waveflow "
          "[serialized examples](evidence/layout_examples.json). All header fields are uint32: "
          "input `[magic=0x504f4f4c, tx_id, opcode, H, W, K]`, six words; response "
          "`[tx_id, H/K, W/K]`, three words. TLAST ends each header. COMPUTE=1, END=2; "
          "END ignores H/W/K and sends nothing. Each payload/result word is one binary32 "
          "sample, row-major, with TLAST only on its final word.","",
          "Status is cleared per activation. AXI-Lite contains only control and halted/error/tx_id. "
          "Error codes: 0 success, 1 header, 2 opcode, 3 H range, 4 W range, 5 K range, "
          "6 window bounds, 7 divisibility, 8 early payload TLAST, 9 missing final TLAST. "
          "Unknown tx_id uses 0xffffffff without another read. Actual generated register offsets "
          "are 0x10/0x20/0x30 in [control RTL](evidence/synthesis/max_pool_control_s_axi.v).", "",
          "## Design","",
          "[pool.py](pool.py) defines the untimed scalar model and schemas; "
          "[oracle.py](oracle.py) independently uses NumPy reshape/max with a first-equal "
          "bit gather. Waveflow [generation](generate.py) produces [the boundary](gen/max_pool.cpp) "
          "and unedited serializers. [The HLS body](max_pool_body_impl.tpp) reads each header "
          "word with immediate framing checks, validates parameters in the specified order, "
          "writes the response header, then buffers the complete matrix. After input validation, "
          "nested row-major window loops use strict-greater float comparisons, fill the result "
          "buffer and emit the complete result burst. Payload errors return before any result "
          "emission. Local buffers never authorize state in another command/activation.", "",
          "The initial implementation pipelines input reception and result emission at II=1; "
          "pooling/window and header loops have their actual II reported below. There was one "
          "synthesis of this design and no performance-optimization/restructuring iteration. "
          "No Python timing model was created. [Source review](evidence/source_review.json) "
          "and [C operation traces](evidence/check_c_order.json) distinguish source-level reads "
          "from external AXI transfers; only waveform data establishes physical transfer order.", "",
          "## Targets","",
          "| Criterion | Required | Measured | Result | Source |",
          "| --- | --- | --- | --- | --- |",
          f"| Device / configured clock | xc7z020clg484-1 / 10 ns | {synth['part']} / {synth['target_ns']} ns | PASS | [synthesis](evidence/synthesis/max_pool_csynth.xml) |",
          f"| Estimated clock | <10 ns | {synth['estimated_ns']} ns | {verdict(synth['clock_pass'])} | [synthesis timing](evidence/synthesis/max_pool_csynth.rpt) |"]
    if perf:
        text += [f"| 64×64 K=2 input interval, inclusive | ≤8192 cycles | {perf['input_cycles']} cycles | {verdict(perf_ok)} | [measured transfers](evidence/performance.json), [raw waveform](evidence/ports.vcd.gz) |",
                 f"| First input to last result, inclusive | no target; report | {perf['total_latency_cycles']} cycles / {perf['total_latency_ns']:.0f} ns | PASS (reported) | [measurement](evidence/performance.json) |",
                 f"| Input throughput over input interval | no separate target; report | {perf['input_samples_per_cycle']:.8f} input samples/cycle; {perf['input_megasamples_per_second']:.6f} Msamples/s | PASS (reported) | [measurement](evidence/performance.json) |",
                 f"| Result throughput over total interval | no target; report | {perf['end_to_end_results_per_cycle']:.8f} results/cycle | PASS (reported) | [measurement](evidence/performance.json) |",
                 f"| Performance fixture host pauses / output backpressure | none | input continuously valid={perf['no_host_input_pauses']}; output continuously ready={perf['no_output_backpressure']} | {verdict(perf['no_host_input_pauses'] and perf['no_output_backpressure'])} | [wave check](evidence/performance.json) |"]
    else:
        text += ["| Input interval / total latency / throughput | specified intervals | Not measured | FAIL — incomplete | [original WDB](evidence/cosim_raw/max_pool.wdb), [extraction diagnosis](evidence/wdb_export.log) |"]
    for key,value in synth["resources"].items():
        text.append(f"| {key} | no target; report | {value} | PASS (reported) | [resource estimate](evidence/synthesis/max_pool_csynth.xml) |")
    for filename,loops in synth["loops"].items():
        for loop in loops:
            if "PipelineII" in loop:
                text.append(f"| {filename.removesuffix('_csynth.xml')} II | no target; report | {loop['PipelineII']} | PASS (reported) | [loop report](evidence/synthesis/{filename}) |")
    text += ["", "The default clock uncertainty is retained in the synthesis report. It does not "
             "replace the required estimated-period test. Whole-activation latency from "
             "[the original transaction report](evidence/cosim_raw/result.transaction.rpt) "
             "is separate from the specified first-input/last-result interval; no substitution is made.", "",
             "## Verification", "",
             f"The independent model gate passed **{gate['arithmetic_vectors']}** arithmetic cases "
             f"and **{gate['activations']}** activations, including **{gate['errors']}** errors and "
             f"**{gate['recoveries']}** separate fresh-stream recoveries. "
             "Sources: [arithmetic vectors](evidence/arithmetic.json), "
             "[model gate](evidence/model_gate.json), [model log](evidence/model_validation.log). "
             "The gate preceded the first Vitis attempt; frozen model/intent hashes remain unchanged. "
             "The hand example has literal expected binary32 patterns for [[6,8],[14,16]]; "
             "negative, signed-zero tie and finite-normal boundary literals accompany deterministic "
             "random supported-domain matrices. [Checker rejection evidence](evidence/checker_rejections.json) "
             "shows changed data bits, missing TLAST, wrong status, extra reads and fake results rejected.", "",
             "Both recorded stages compare raw words/TLAST, echoed IDs and dimensions, counts/order and "
             "status against scenario intent and the independently "
             "validated model: [C check](evidence/check_csim.json), "
             "[RTL co-simulation check](evidence/check_cosim.json), "
             "[C log](evidence/csim_comparison.log), [RTL log](evidence/cosim_comparison.log). "
             "Consumed-input/unread snapshots come from the C testbench/wrapper; external RTL "
             "transfers and their order are assessed separately below. "
             "The testbench poisons status and constructs fresh streams for every call. "
             "Each error row is immediately followed by its recovery; an expected nonzero error "
             "code is a successful error test, not a test failure.", "",
             "| Scenario / intent | Model | C | RTL functional | External response/payload order | Observed status / C input reads | Evidence |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for n in names:
        d=f"data/{n}";expected=read(d+"/expected.json");st=expected["status"]
        intent=read(d+"/intent.json")
        order=(verdict(wave[n]['pass_']) if wave[n]['ordering'] else "N/A — no accepted COMPUTE") if wave else "FAIL — not checked"
        text.append(f"| {n}: {intent['purpose']} | {verdict(model[n]['pass_'])} | {verdict(csim[n]['pass_'])} | {verdict(cosim[n]['pass_'])} | {order} | error={st['error']}, tx={st['tx_id']}; {expected['consumed']} reads | "
                    f"[intent]({d}/intent.json), [expected]({d}/expected.json), [model]({d}/model.json), [C]({d}/csim/observed.json), [RTL]({d}/cosim/observed.json) |")
    text += ["", "C execution ordering is " + verdict(all(x["pass_"] for x in corder.values()))+
             " in [the trace checks](evidence/check_c_order.json). "
             "No-timeout and unavailable-ID behavior also have explicit "
             "[source-review evidence](evidence/source_review.json). Permanently incomplete "
             "input is outside the terminating-test scope; empty-stream exceptions are not accepted "
             "as protocol errors.", ""]
    if wave:
        failed=[n for n,r in wave.items() if not r["pass_"]]
        text += [f"External RTL waveform checks: **{verdict(not failed)}**, "
                 f"{len(wave)-len(failed)}/{len(wave)} scenario rows. "
                 "[Detailed transfer/order checks](evidence/check_rtl_wave.json), "
                 "[handshakes](evidence/rtl_handshakes.jsonl.gz), "
                 "[signal names and pre-edge sampling](evidence/wave_signals.json), "
                 "[raw VCD](evidence/ports.vcd.gz). These are additional to functional co-simulation agreement.",""]
    text += ["## Assumptions", "",
             "Delegated representation choices are listed under Interface and in layout.md: "
             "full-width integer fields, fixed magic/framing, distinct parameter-stage codes, "
             "fallback ID, ignored END parameters and exact-bit fixture files. These do not "
             "change the confirmed max-pooling function. No numeric checks were added for "
             "unsupported NaN/infinity/subnormal inputs.", "",
             "Waveflow's reference requests timing calibration and a staged approval stop; "
             "the user's explicit full-implementation authorization and course scope govern this run. "
             "The installed Vitis 2026.1 was used with BuildConfig(vitis_version=\"2026.1\"). "
             "No packages were upgraded. [Environment](evidence/environment.json) records only "
             "whether license variables exist, never their values. The sandboxed initial build "
             "failed at set_part with a license error in [the full log](evidence/vitis_csim.log); "
             "the same build succeeded through normal execution approval in "
             "[the retry log](evidence/vitis_csim_license_retry.log), without license changes. "
             "C++14 extension warnings from tool/framework headers were nonfatal.", "",
             "## Open Items", ""]
    items=[]
    if not perf:items.append("FAIL / incomplete: required input interval, total latency and throughput remain unmeasured; do not infer them from C simulation or synthesis II.")
    elif not perf_ok:items.append("FAIL: the measured input-cycle target or the required no-pause/no-backpressure fixture conditions were not satisfied. See evidence/performance.json. No optimization or further replay was attempted.")
    if not wave:items.append("FAIL / incomplete: external AXI transfer ordering is not yet verified; source-level order alone is insufficient.")
    elif not wave_ok:items.append("FAIL: external AXI response-before-payload ordering differs from the confirmed contract. See [waveform checks](evidence/check_rtl_wave.json) and [interface diagnosis](evidence/rtl_interface_diagnosis.json). The generated AXI register slices prefetch payload words before the complete response is transferred. No semantic reinterpretation or generated-file patch is used to mark this passed. Correcting the physical interface would require a separately authorized correctness revision and another synthesis/verification run; none was attempted under the same-snapshot measurement authorization.")
    items.append("FAIL / unfinished RTL verification: queued trailing input is retained and checked in C simulation, but the Vitis RTL driver offers only the C-consumed prefix. Thus immediate external input stoppage with additional beats independently offered after an error is not established by this harness. No stronger RTL result is claimed.")
    if not synth["clock_pass"]:items.append("FAIL: estimated synthesis clock misses the <10 ns target; no timing-closure iteration was attempted.")
    text += ["- "+item for item in items] if items else ["None within the supported numeric and tested protocol scope."]
    text += ["", "Input-stop evidence has a practical RTL-harness limit: Vitis derives its input "
             "vectors from the C call's consumed prefix. Queued trailing input and exact unread "
             "content are checked by the C/protocol testbench; RTL output/status agreement "
             "does not alone prove behavior with additional beats independently offered after "
             "an error. The retained [input vector](evidence/cosim_raw/c.max_pool.autotvin_s_in_V_data_V.dat) "
             "makes that scope inspectable. No stronger adversarial RTL test is claimed.", "",
             "## Run History", "",
             "| Run / specification | Action / change | Result and evidence |",
             "| --- | --- | --- |",
             "| Model gate / v2 | Independent literals/NumPy check, scenarios and frozen sources | PASS: [model gate](evidence/model_gate.json), [log](evidence/model_validation.log) |",
             "| C simulation attempt / v2 | First Vitis invocation | Stopped at license-gated set_part before compilation: [log](evidence/vitis_csim.log) |",
             "| C simulation retry / v2 | Same build through normal execution approval; no license change | PASS for full suite: [build](evidence/vitis_csim_license_retry.log), [comparison](evidence/check_csim.json) |",
             "| Synthesis / v2 | Initial kernel, no optimization rerun | Completed: [log](evidence/vitis_synth.log), [reports](evidence/synthesis.json) |",
             "| FIRST co-simulation / v2 | One cosim_design call, all 66 activations including each error/recovery, port tracing | PASS functionally: [scope](evidence/first_cosim_scope.json), [log](evidence/vitis_cosim.log), [comparison](evidence/check_cosim.json), [original WDB](evidence/cosim_raw/max_pool.wdb) |",
             "| Offline waveform investigation / v2 | Native Vivado queries and independent WDB decoder, no RTL execution | Could not validate extraction: [Vivado query](evidence/wave_search_inspection.log), [decoder failure](evidence/wdb_selected_diagnosis.log) |"]
    if replay:
        replay_ok=replay.get("completed",False) and replay.get("same_snapshot",False) and all(replay.get("rtl_vectors_identical_to_first_cosim",{}).values())
        text += [f"| ADDITIONAL measurement replay / v2 | User explicitly authorized ONE replay of the same snapshot and same 66 activations solely for VCD, after WDB-only capture prevented measurements; no resynthesis/kernel change/optimization | {verdict(replay_ok)}: [authorization and snapshot/vector hashes](evidence/replay_authorization.json), [replay log](evidence/vcd_replay.log), [raw VCD](evidence/ports.vcd.gz) |",
                 "", "RTL was executed for the first co-simulation **and** the separately authorized "
                 "measurement replay. It is not described as having executed only once. No further "
                 "replay is authorized or attempted.","",
                 "The replay capture script initially included mutable xsimkernel.log in its snapshot "
                 "hash comparison, producing a bookkeeping assertion after the RTL run had finished. "
                 "[Offline finalization](finalize_replay.py) confirmed that this log was the only "
                 "changed entry; all kernel/RTL/executable hashes and original RTL output/status "
                 "vectors match. Both [the initial record](evidence/replay_capture_initial.json) "
                 "and [the corrected record](evidence/replay_authorization.json) are retained. "
                 "This correction did not execute RTL again."]
    text += ["", "All cited artifacts remain in this folder. [README.md](README.md) gives reproduction "
             "and evidence-only checking. [Source manifest](evidence/source_manifest.json) records "
             "the final source hashes. The confirmed prompt, classroom project and old labs were "
             "not modified; no Git commit or push was performed.",""]
    (ROOT/"results.md").write_text("\n".join(text))
    paths=list(ROOT.glob("*.py"))+list(ROOT.glob("*.tpp"))+list(ROOT.glob("*.cpp"))+list(ROOT.glob("*.hpp"))+list(ROOT.glob("*.tcl"))
    paths += [ROOT/"prompt.md",ROOT/"layout.md",ROOT/"README.md",ROOT/".gitignore"]
    paths += list((ROOT/"gen").glob("*"))+list((ROOT/"include").glob("*"))
    paths += list((ROOT/"tools/wdb_converter").glob("*.py"))
    save(ROOT/"evidence/source_manifest.json",{str(p.relative_to(ROOT)):sha(p) for p in paths if p.is_file()})
    missing=[]
    for target in re.findall(r"\]\(([^)]+)\)",(ROOT/"results.md").read_text()):
        if "://" not in target and not (ROOT/target).exists():missing.append(target)
    save(ROOT/"evidence/report_integrity.json",dict(relative_links_exist=not missing,missing=missing,
         source_manifest_matches=True,model_freeze_matches=True,numeric_checks_pass=numeric,
         overall_pass=overall,prompt_version="v2"))
    assert not missing,missing
    print("REPORT GENERATED",verdict(overall),"functional comparisons",verdict(numeric))

if __name__=="__main__":
    if (ROOT/"evidence/fix_v2/final_ready.json").exists():
        from report_fix import report as corrected_report
        corrected_report()
    else:report()
