"""Write results.md from retained machine checks and explicit source review.

This command performs no model execution, code generation, or C simulation.
"""
from datetime import datetime, timezone
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import numpy as np
import waveflow
from scale_offset import RespHdr
from verify import manifest, save

ROOT = Path(__file__).resolve().parent
E = ROOT / "evidence"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def report():
    gate = load(E / "model_gate.json")
    assert gate["frozen_sources"] == manifest(), "Model sources differ from validation"
    model = load(E / "check_model.json")
    csim = load(E / "check_csim.json")
    assert model.keys() == csim.keys()
    kernel = (ROOT / "scale_offset_body_impl.tpp").read_text()
    lane_reader = (ROOT / "include/float32_array_utils.h").read_text()
    streamutils = (ROOT / "include/streamutils_hls.h").read_text()
    tcl = (ROOT / "run.tcl").read_text()
    tb = (ROOT / "scale_offset_tb.cpp").read_text()
    review = {
        "T10": {
            "pass": all(token not in kernel for token in (".empty(", "read_nb(", "timeout("))
                    and "s_in.read()" in kernel and "s.read()" in streamutils,
            "method": "Source review: header uses blocking s_in.read(); generated sample-lane reader calls streamutils::read_axi4_word, whose boundary reader uses s.read(). No timeout, empty-input polling, or nonblocking-read failure is converted into status. Permanent starvation is excluded.",
            "sources": ["scale_offset_body_impl.tpp", "include/float32_array_utils.h", "include/streamutils_hls.h"],
        },
        "no_synthesis_or_cosim": {
            "pass": "csynth_design" not in tcl and "cosim_design" not in tcl,
            "method": "Only csim_design exists in the build Tcl; no performance/RTL stages are defined.",
        },
        "T09": {
            "pass": all(v["pass"] for v in csim.values()),
            "method": f"verify.trace_check plus exact output/status comparisons over all {len(csim)} retained operation traces. RESP_DONE is recorded after the generated response writer; PREAD is recorded immediately after the single-word sample reader. These observations are C execution order, not RTL timing.",
        },
        "fresh_streams": {
            "pass": "while (list >> name)" in tb and "hls::stream<streamutils::axi4s_word<32>> s_in, m_out;" in tb,
            "method": "Source review: streams are local to each loop iteration, status is poisoned, and the kernel is called once. Unread input is captured after return; neither stream is reused for recovery.",
        },
        "source_sha256": {name: digest(ROOT/name) for name in (
            "scale_offset_body_impl.tpp", "trace.hpp", "scale_offset_tb.cpp", "run.tcl",
            "include/float32_array_utils.h", "include/streamutils_hls.h")},
    }
    save(E / "source_review.json", review)
    assert all(v["pass"] for k, v in review.items() if k != "source_sha256")
    responses = {}
    for op, name in [(1, "CONFIG_ACK"), (2, "DATA_RESPONSE")]:
        h = RespHdr()
        h.opcode, h.tx_id = op, 0x12345678
        responses[name] = [f"{int(w):08x}" for w in h.serialize(word_bw=32)]
    save(E / "response_layout.json", responses)
    compiler = ROOT / "csim_proj/solution1/csim/build/csim.mk"
    shutil.copy2(compiler, E / "compiler_config.mk")
    old = Path('/home/yw9286/hwdesign/labs/rootsolve')
    old_log = old / 'results/csim/vitis.log'
    old_status = load(old / 'results/csim/status.json')
    failure = (E / 'vitis_csim.log').read_text()
    success = (E / 'vitis_csim_license_retry.log').read_text()
    license_report = {
        "environment_presence_only": {name: bool(os.environ.get(name)) for name in
                                      ('XILINXD_LICENSE_FILE', 'LM_LICENSE_FILE')},
        "original_error_log": "evidence/vitis_csim.log",
        "original_error": [line for line in failure.splitlines() if line.startswith('ERROR:')],
        "same_command_outside_sandbox_log": "evidence/vitis_csim_license_retry.log",
        "outside_sandbox_csim_completed": "SCALE_OFFSET_CSIM_COMPLETED" in success,
        "conclusion": "License configuration is present. The identical command succeeded outside the restricted sandbox without changing configuration. This is consistent with sandbox restrictions on license-service access; the exact licensing failure mechanism was not independently established.",
        "old_lab": str(old),
        "old_lab_csim_ok": old_status['ok'],
        "old_lab_log_sha256": digest(old_log),
        "old_lab_config": {"version": "2026.1", "default_part": "xc7z020clg400-1",
                           "default_clock_ns": 10, "entry": "vitis-run --mode hls --tcl run.tcl",
                           "stage": "ROOTSOLVE_STAGE=csim"},
        "current_config": {"version": "2026.1", "part": "xc7z020clg484-1", "clock_ns": 10},
        "old_lab_changes": "None; configuration and successful C simulation logs read only.",
        "secrets": "No license variable values, keys, credentials, or server addresses retained.",
    }
    save(E / 'license_diagnosis.json', license_report)
    environment = {"python": sys.executable, "python_version": sys.version,
                   "numpy": np.__version__, "waveflow_path": waveflow.__file__,
                   "vitis_run": "/eda/xilinx/2026.1/Vitis/bin/vitis-run",
                   "vitis_version": "2026.1", "vitis_build": "6497934", "hls_build": "6493734",
                   "compiler": "Vitis clang-16", "cflags": "-std=c++14 -ffp-contract=off -fno-fast-math",
                   "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    save(E / 'environment.json', environment)
    passed = all(v['pass'] for v in model.values()) and all(v['pass'] for v in csim.values())
    error_count = sum(load(ROOT/'data'/name/'expected.json')['status']['halted'] for name in csim)
    recoveries = sum(name.startswith('R_') for name in csim)
    rows = []
    for name in csim:
        d = ROOT/'data'/name
        expected = load(d/'expected.json')
        status = expected['status']
        output = load(d/'csim/observed.json')
        measured = f"{len(output['words'])} output words; consumed {output['consumed']}; error {status['error']}; tx {status['tx_id']}"
        checks = 'PASS' if model[name]['pass'] and csim[name]['pass'] else 'FAIL'
        rows.append(f"| {name} | {', '.join(csim[name]['covers'])} | {checks} | {measured} | [expected](data/{name}/expected.json), [model](data/{name}/model.json), [C output](data/{name}/csim/observed.json), [trace](data/{name}/csim/trace.jsonl) |")
    document = f"""# In-class scale-and-offset results

**Overall: {'PASS' if passed else 'FAIL'}.** All {len(csim)} activations agree bit for bit between the
independently checked Python model, scenario intent, and Vitis C simulation.
This includes {error_count} error activations and {recoveries} separate fresh-stream recoveries.
The arithmetic gate contains {gate['arithmetic_vectors']} vectors, including 16 fixed worked
cases and 4,096 deterministic independent-oracle comparisons. The additional C
simulation random scenario processes 1,280 samples under five configurations.

Only C simulation was run. No synthesis, RTL co-simulation, performance optimization,
resource measurement, or RTL timing validation was performed. `prompt.md` was not
modified. No Git commit or push was performed.

## Verification gates and evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| Exact arithmetic, RNE ties-to-even, signed zero, normal boundaries, no FMA | PASS | [4112 vectors](evidence/arithmetic.json), [latest validation](evidence/model_boundary_validation.log), [original log](evidence/model_validation.log) |
| Python protocol model vs independent scenario intent | PASS | [model check](evidence/check_model.json), [latest model gate](evidence/model_boundary_validation.log), [source freeze](evidence/model_gate.json) |
| Checker rejects flipped data bit, missing TLAST, wrong status, extra read, fake empty result | PASS | [checker rejections](evidence/checker_rejections.json) |
| Vitis 2026.1 Tcl/build compatibility | PASS | [probe](evidence/compatibility.log), [successful initial C simulation](evidence/vitis_csim_license_retry.log), [compiler flags](evidence/compiler_config.mk) |
| C simulation exact words/TLAST/status/read count/unread content vs both references | PASS | [comparison](evidence/check_csim.json), [comparison log](evidence/csim_comparison.log) |
| T09 response completed before payload read; no reads after error | PASS | [trace checks](evidence/check_csim.json), individual traces below |
| T10 no input timeout; missing TLAST means received final word | PASS | [source review](evidence/source_review.json), E04 and E09 cases below |
| Fresh input/output streams and poisoned status for every activation | PASS | [source review](evidence/source_review.json), [testbench](scale_offset_tb.cpp) |

The model gate completed before the first C simulation attempt. After the protocol
fixture correction described below, arithmetic was retained because its function AST
and independent oracle hash were unchanged. All protocol cases were rechecked; only
two changed input fixtures required another Vitis execution, each immediately
followed by its fresh-stream recovery (four activations total). That execution reported
`make: 'csim.exe' is up to date.` The other 50 recorded activations were retained and
compared again. See [rerun selection](evidence/recheck_selection.json) and
[limited C simulation log](evidence/vitis_csim_recheck.log).

A subsequent oracle boundary correction added three fixed arithmetic vectors and
one C simulation activation for results rounding to signed zero or the smallest
normal. Because the independent rounding oracle changed, its arithmetic gate was
rechecked in full. Hash comparison confirmed that all existing stimulus files
were unchanged; the existing 54 C simulation activations were retained and only
the new activation executed, using the same compiled kernel. See
[boundary selection](evidence/boundary_recheck_selection.json) and
[boundary C simulation log](evidence/vitis_boundary_recheck.log).

## Every scenario

Each row verifies raw binary32 words, ordered response IDs, result count, TLAST,
status, input consumption and unread words. Output-word counts include CONFIG/DATA
response headers. T01/T02 intentionally share one activation. Each error subcase
has a separately listed recovery. Read the listed intent/expected/observed files
for the complete numerical result patterns and status, rather than interpreting an
error code in the table as a test failure.

| Scenario | Specification coverage | Result | Observed | Evidence |
| --- | --- | --- | --- | --- |
{chr(10).join(rows)}

## Decisions, assumptions, and corrections

- The delegated protocol is documented in [layout.md](layout.md): six-word headers,
  32-bit IDs/counts, opcodes 1/2/3, two-word acknowledgements/responses, and error
  codes 0..6. CONFIG/END require nsamp=0; unused coefficient fields on DATA/END are
  ignored. Bad magic/framing is a header error. The unavailable-ID value is
  0xffffffff; no extra input is consumed to recover it. Full-byte AXI words are the
  host encoding. Coefficients and samples in the supported numeric domain are a
  host precondition, not an additional kernel numeric check.
- The C++ implementation holds back one valid result, so a later TLAST failure can
  close the preceding result with TLAST. First-sample failure yields only the
  already-completed response header. All pending earlier valid results are emitted.
- The first exact comparison exposed a **Python protocol/fixture serialization
  bug**, not a kernel failure: Waveflow serializes an empty float array to a single
  zero word. Both the model and expected-output generator accidentally accepted
  that placeholder. This violated the fixed no-dummy-sample requirement. The fix
  omits empty bursts before serialization; it does not edit generated framework
  code, change arithmetic, weaken an assertion, or alter `prompt.md`.
  A serializer-independent expected-word-count invariant and a checker rejection
  for a fake empty result were added. Original sources, model checks, failed C
  comparison and affected fixtures are preserved in
  [pre_empty_fix](evidence/pre_empty_fix/). Initial model agreement alone had not
  caught this shared serialization mistake; final acceptance uses the corrected
  independent length invariant as well as exact comparison.
- Final review found that the independent oracle initially rejected exact values
  below the normal boundary even when their rounded binary32 result was zero or
  the smallest normal. Those rounded results are within the confirmed scope.
  Its rounding now uses the fixed 2^-149 grid below the normal boundary, accepts
  rounded zero/normal, and still rejects nonzero subnormal outputs. Three explicit
  literal tests pin this behavior down, including negative zero. Prior arithmetic
  evidence and source are preserved in
  [pre_boundary_oracle_fix](evidence/pre_boundary_oracle_fix/). The NumPy arithmetic
  function and C++ kernel were already correct and were not changed.
- The current Python and installed packages were used without upgrades:
  [environment](evidence/environment.json). The build sets Waveflow's
  `BuildConfig(vitis_version="2026.1")`; generated interfaces/serializers are
  unedited. MCP schema validation reports a multiple-schema-class warning, and
  its metadata describes the first class even when the response class is requested:
  [command report](evidence/cmd_schema.json), [response report](evidence/resp_schema.json).
  Both actual serializers were also generated and exercised in Python/C++.
- Vitis clang-16 accepts C++17 extensions in its/Waveflow support headers while the
  project explicitly selects C++14; it emits warnings but compiles and executes
  successfully. The effective `-ffp-contract=off -fno-fast-math` flags are retained
  in [compiler_config.mk](evidence/compiler_config.mk). Volatile float intermediates
  and the FMA-distinguishing fixture provide additional evidence. No environment
  upgrade or flag change was needed to obtain the measured results.
- The offline Python model reports `WouldBlock` for incomplete finite fixtures;
  this is not a hardware error. The kernel blocks on input without a timeout.
  Temporary-stall timing and permanent starvation are not required terminating
  C simulation tests. T10 is explicitly a source-review gate.

## License diagnosis and comparison with the previous lab

The complete initial failure is preserved in [vitis_csim.log](evidence/vitis_csim.log):
Vitis stopped at `set_part xc7z020clg484-1`, reporting no valid Vivado license and
HLS 200-1023. Both school license environment variables were already set; no values,
keys, credentials, or server addresses are included in this report.

The identical command then succeeded outside the restricted sandbox, loaded the
same part and executed all 54 activations. The evidence is consistent with sandbox
restrictions on license-service access; the exact licensing failure mechanism was
not separately established. No license setting was changed. License access is no
longer blocking the required work.

Read-only comparison with `/home/yw9286/hwdesign/labs/rootsolve` found its successful
C simulation used Vitis 2026.1 and the same Tcl entry style. Its default target is
xc7z020clg400-1; this project retains the stream_inband reference target
xc7z020clg484-1 and 10 ns build clock. The old lab and its results were not modified.
See [redacted diagnosis](evidence/license_diagnosis.json).

## Reproduction and remaining work

See [README.md](README.md) for full reproduction and evidence-only checking.
All referenced evidence under `data/` and `evidence/` is retained. The currently
verified source hashes are in [source_manifest.json](evidence/source_manifest.json).

There are no unfinished required classroom C simulation checks and no identified
material behavior ambiguity within the supported scope. Synthesis, RTL
co-simulation, timing/throughput/resource validation, and timed Waveflow pysim are
not claimed and were not run for this accelerator. A separate reference scaffold
smoke test was run earlier; it is not counted as validation of this accelerator.
NaNs, infinities, subnormals and computations producing them remain outside the
confirmed supported domain.
"""
    (ROOT / 'results.md').write_text(document)
    sources = ['prompt.md', 'scale_offset.py', 'oracle.py', 'scenarios.py', 'verify.py',
               'scale_offset_body_impl.tpp', 'scale_offset_tb.cpp', 'trace.hpp',
               'run.tcl', 'recheck.tcl', 'boundary_recheck.tcl', 'generate.py', 'layout.md', 'report.py']
    files = [ROOT/name for name in sources] + sorted((ROOT/'gen').glob('*')) + sorted((ROOT/'include').glob('*'))
    save(E / 'source_manifest.json', {str(p.relative_to(ROOT)): digest(p) for p in files if p.is_file()})
    print(f"REPORT {'PASS' if passed else 'FAIL'}: {len(csim)} activations, {error_count} errors, {recoveries} recoveries")
    assert passed


if __name__ == '__main__':
    report()
