# In-class scale-and-offset results

**Overall: PASS.** All 55 activations agree bit for bit between the
independently checked Python model, scenario intent, and Vitis C simulation.
This includes 23 error activations and 23 separate fresh-stream recoveries.
The arithmetic gate contains 4112 vectors, including 16 fixed worked
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
| T01_T02_reconfigure | T01, T02 | PASS | 13 output words; consumed 35; error 0; tx 0 | [expected](data/T01_T02_reconfigure/expected.json), [model](data/T01_T02_reconfigure/model.json), [C output](data/T01_T02_reconfigure/csim/observed.json), [trace](data/T01_T02_reconfigure/csim/trace.jsonl) |
| T03_reuse | T03 | PASS | 13 output words; consumed 35; error 0; tx 0 | [expected](data/T03_reuse/expected.json), [model](data/T03_reuse/model.json), [C output](data/T03_reuse/csim/observed.json), [trace](data/T03_reuse/csim/trace.jsonl) |
| T04_prior_success | T04 | PASS | 5 output words; consumed 19; error 0; tx 0 | [expected](data/T04_prior_success/expected.json), [model](data/T04_prior_success/model.json), [C output](data/T04_prior_success/csim/observed.json), [trace](data/T04_prior_success/csim/trace.jsonl) |
| T04_no_carry | T04 | PASS | 0 output words; consumed 6; error 4; tx 303 | [expected](data/T04_no_carry/expected.json), [model](data/T04_no_carry/model.json), [C output](data/T04_no_carry/csim/observed.json), [trace](data/T04_no_carry/csim/trace.jsonl) |
| R_T04_no_carry | RECOVERY, T04 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_T04_no_carry/expected.json), [model](data/R_T04_no_carry/model.json), [C output](data/R_T04_no_carry/csim/observed.json), [trace](data/R_T04_no_carry/csim/trace.jsonl) |
| E01_no_config | E01 | PASS | 0 output words; consumed 6; error 4; tx 401 | [expected](data/E01_no_config/expected.json), [model](data/E01_no_config/model.json), [C output](data/E01_no_config/csim/observed.json), [trace](data/E01_no_config/csim/trace.jsonl) |
| R_E01_no_config | RECOVERY, E01 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E01_no_config/expected.json), [model](data/R_E01_no_config/model.json), [C output](data/R_E01_no_config/csim/observed.json), [trace](data/R_E01_no_config/csim/trace.jsonl) |
| E02_zero | E02 | PASS | 2 output words; consumed 12; error 3; tx 411 | [expected](data/E02_zero/expected.json), [model](data/E02_zero/model.json), [C output](data/E02_zero/csim/observed.json), [trace](data/E02_zero/csim/trace.jsonl) |
| R_E02_zero | RECOVERY, E02 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E02_zero/expected.json), [model](data/R_E02_zero/model.json), [C output](data/R_E02_zero/csim/observed.json), [trace](data/R_E02_zero/csim/trace.jsonl) |
| E03_early | E03 | PASS | 6 output words; consumed 15; error 5; tx 421 | [expected](data/E03_early/expected.json), [model](data/E03_early/model.json), [C output](data/E03_early/csim/observed.json), [trace](data/E03_early/csim/trace.jsonl) |
| R_E03_early | RECOVERY, E03 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E03_early/expected.json), [model](data/R_E03_early/model.json), [C output](data/R_E03_early/csim/observed.json), [trace](data/R_E03_early/csim/trace.jsonl) |
| E03_long_prefix | E03 | PASS | 19 output words; consumed 28; error 5; tx 426 | [expected](data/E03_long_prefix/expected.json), [model](data/E03_long_prefix/model.json), [C output](data/E03_long_prefix/csim/observed.json), [trace](data/E03_long_prefix/csim/trace.jsonl) |
| R_E03_long_prefix | RECOVERY, E03 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E03_long_prefix/expected.json), [model](data/R_E03_long_prefix/model.json), [C output](data/R_E03_long_prefix/csim/observed.json), [trace](data/R_E03_long_prefix/csim/trace.jsonl) |
| E04_missing | E04 | PASS | 6 output words; consumed 15; error 6; tx 431 | [expected](data/E04_missing/expected.json), [model](data/E04_missing/model.json), [C output](data/E04_missing/csim/observed.json), [trace](data/E04_missing/csim/trace.jsonl) |
| R_E04_missing | RECOVERY, E04 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E04_missing/expected.json), [model](data/R_E04_missing/model.json), [C output](data/R_E04_missing/csim/observed.json), [trace](data/R_E04_missing/csim/trace.jsonl) |
| E05_opcode | E05 | PASS | 0 output words; consumed 6; error 2; tx 440 | [expected](data/E05_opcode/expected.json), [model](data/E05_opcode/model.json), [C output](data/E05_opcode/csim/observed.json), [trace](data/E05_opcode/csim/trace.jsonl) |
| R_E05_opcode | RECOVERY, E05 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E05_opcode/expected.json), [model](data/R_E05_opcode/model.json), [C output](data/R_E05_opcode/csim/observed.json), [trace](data/R_E05_opcode/csim/trace.jsonl) |
| E06_magic_unknown_id | E06 | PASS | 0 output words; consumed 1; error 1; tx 4294967295 | [expected](data/E06_magic_unknown_id/expected.json), [model](data/E06_magic_unknown_id/model.json), [C output](data/E06_magic_unknown_id/csim/observed.json), [trace](data/E06_magic_unknown_id/csim/trace.jsonl) |
| R_E06_magic_unknown_id | RECOVERY, E06 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E06_magic_unknown_id/expected.json), [model](data/R_E06_magic_unknown_id/model.json), [C output](data/R_E06_magic_unknown_id/csim/observed.json), [trace](data/R_E06_magic_unknown_id/csim/trace.jsonl) |
| E06_early_unknown_id | E06 | PASS | 0 output words; consumed 1; error 1; tx 4294967295 | [expected](data/E06_early_unknown_id/expected.json), [model](data/E06_early_unknown_id/model.json), [C output](data/E06_early_unknown_id/csim/observed.json), [trace](data/E06_early_unknown_id/csim/trace.jsonl) |
| R_E06_early_unknown_id | RECOVERY, E06 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E06_early_unknown_id/expected.json), [model](data/R_E06_early_unknown_id/model.json), [C output](data/R_E06_early_unknown_id/csim/observed.json), [trace](data/R_E06_early_unknown_id/csim/trace.jsonl) |
| E06_early_known_id | E06 | PASS | 0 output words; consumed 2; error 1; tx 453 | [expected](data/E06_early_known_id/expected.json), [model](data/E06_early_known_id/model.json), [C output](data/E06_early_known_id/csim/observed.json), [trace](data/E06_early_known_id/csim/trace.jsonl) |
| R_E06_early_known_id | RECOVERY, E06 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E06_early_known_id/expected.json), [model](data/R_E06_early_known_id/model.json), [C output](data/R_E06_early_known_id/csim/observed.json), [trace](data/R_E06_early_known_id/csim/trace.jsonl) |
| E06_missing | E06 | PASS | 0 output words; consumed 6; error 1; tx 454 | [expected](data/E06_missing/expected.json), [model](data/E06_missing/model.json), [C output](data/E06_missing/csim/observed.json), [trace](data/E06_missing/csim/trace.jsonl) |
| R_E06_missing | RECOVERY, E06 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E06_missing/expected.json), [model](data/R_E06_missing/model.json), [C output](data/R_E06_missing/csim/observed.json), [trace](data/R_E06_missing/csim/trace.jsonl) |
| E07_config_param | E07 | PASS | 2 output words; consumed 12; error 3; tx 461 | [expected](data/E07_config_param/expected.json), [model](data/E07_config_param/model.json), [C output](data/E07_config_param/csim/observed.json), [trace](data/E07_config_param/csim/trace.jsonl) |
| R_E07_config_param | RECOVERY, E07 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E07_config_param/expected.json), [model](data/R_E07_config_param/model.json), [C output](data/R_E07_config_param/csim/observed.json), [trace](data/R_E07_config_param/csim/trace.jsonl) |
| E08_header_before_opcode | E08 | PASS | 0 output words; consumed 6; error 1; tx 470 | [expected](data/E08_header_before_opcode/expected.json), [model](data/E08_header_before_opcode/model.json), [C output](data/E08_header_before_opcode/csim/observed.json), [trace](data/E08_header_before_opcode/csim/trace.jsonl) |
| R_E08_header_before_opcode | RECOVERY, E08 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E08_header_before_opcode/expected.json), [model](data/R_E08_header_before_opcode/model.json), [C output](data/R_E08_header_before_opcode/csim/observed.json), [trace](data/R_E08_header_before_opcode/csim/trace.jsonl) |
| E08_opcode_before_param | E08 | PASS | 0 output words; consumed 6; error 2; tx 471 | [expected](data/E08_opcode_before_param/expected.json), [model](data/E08_opcode_before_param/model.json), [C output](data/E08_opcode_before_param/csim/observed.json), [trace](data/E08_opcode_before_param/csim/trace.jsonl) |
| R_E08_opcode_before_param | RECOVERY, E08 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E08_opcode_before_param/expected.json), [model](data/R_E08_opcode_before_param/model.json), [C output](data/R_E08_opcode_before_param/csim/observed.json), [trace](data/R_E08_opcode_before_param/csim/trace.jsonl) |
| E08_param_before_config | E08 | PASS | 0 output words; consumed 6; error 3; tx 472 | [expected](data/E08_param_before_config/expected.json), [model](data/E08_param_before_config/model.json), [C output](data/E08_param_before_config/csim/observed.json), [trace](data/E08_param_before_config/csim/trace.jsonl) |
| R_E08_param_before_config | RECOVERY, E08 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E08_param_before_config/expected.json), [model](data/R_E08_param_before_config/model.json), [C output](data/R_E08_param_before_config/csim/observed.json), [trace](data/R_E08_param_before_config/csim/trace.jsonl) |
| E08_param_before_payload | E08 | PASS | 2 output words; consumed 12; error 3; tx 474 | [expected](data/E08_param_before_payload/expected.json), [model](data/E08_param_before_payload/model.json), [C output](data/E08_param_before_payload/csim/observed.json), [trace](data/E08_param_before_payload/csim/trace.jsonl) |
| R_E08_param_before_payload | RECOVERY, E08 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E08_param_before_payload/expected.json), [model](data/R_E08_param_before_payload/model.json), [C output](data/R_E08_param_before_payload/csim/observed.json), [trace](data/R_E08_param_before_payload/csim/trace.jsonl) |
| E08_config_before_payload | E08 | PASS | 0 output words; consumed 6; error 4; tx 475 | [expected](data/E08_config_before_payload/expected.json), [model](data/E08_config_before_payload/model.json), [C output](data/E08_config_before_payload/csim/observed.json), [trace](data/E08_config_before_payload/csim/trace.jsonl) |
| R_E08_config_before_payload | RECOVERY, E08 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E08_config_before_payload/expected.json), [model](data/R_E08_config_before_payload/model.json), [C output](data/R_E08_config_before_payload/csim/observed.json), [trace](data/R_E08_config_before_payload/csim/trace.jsonl) |
| E09_first_early | E09 | PASS | 4 output words; consumed 13; error 5; tx 481 | [expected](data/E09_first_early/expected.json), [model](data/E09_first_early/model.json), [C output](data/E09_first_early/csim/observed.json), [trace](data/E09_first_early/csim/trace.jsonl) |
| R_E09_first_early | RECOVERY, E09 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E09_first_early/expected.json), [model](data/R_E09_first_early/model.json), [C output](data/R_E09_first_early/csim/observed.json), [trace](data/R_E09_first_early/csim/trace.jsonl) |
| E09_first_missing | E09 | PASS | 4 output words; consumed 13; error 6; tx 483 | [expected](data/E09_first_missing/expected.json), [model](data/E09_first_missing/model.json), [C output](data/E09_first_missing/csim/observed.json), [trace](data/E09_first_missing/csim/trace.jsonl) |
| R_E09_first_missing | RECOVERY, E09 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E09_first_missing/expected.json), [model](data/R_E09_first_missing/model.json), [C output](data/R_E09_first_missing/csim/observed.json), [trace](data/R_E09_first_missing/csim/trace.jsonl) |
| E10_one_early | E10 | PASS | 5 output words; consumed 14; error 5; tx 491 | [expected](data/E10_one_early/expected.json), [model](data/E10_one_early/model.json), [C output](data/E10_one_early/csim/observed.json), [trace](data/E10_one_early/csim/trace.jsonl) |
| R_E10_one_early | RECOVERY, E10 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E10_one_early/expected.json), [model](data/R_E10_one_early/model.json), [C output](data/R_E10_one_early/csim/observed.json), [trace](data/R_E10_one_early/csim/trace.jsonl) |
| E10_one_missing | E10 | PASS | 5 output words; consumed 14; error 6; tx 493 | [expected](data/E10_one_missing/expected.json), [model](data/E10_one_missing/model.json), [C output](data/E10_one_missing/csim/observed.json), [trace](data/E10_one_missing/csim/trace.jsonl) |
| R_E10_one_missing | RECOVERY, E10 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E10_one_missing/expected.json), [model](data/R_E10_one_missing/model.json), [C output](data/R_E10_one_missing/csim/observed.json), [trace](data/R_E10_one_missing/csim/trace.jsonl) |
| E_extra_end_param | E08 | PASS | 0 output words; consumed 6; error 3; tx 499 | [expected](data/E_extra_end_param/expected.json), [model](data/E_extra_end_param/model.json), [C output](data/E_extra_end_param/csim/observed.json), [trace](data/E_extra_end_param/csim/trace.jsonl) |
| R_E_extra_end_param | RECOVERY, E08 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E_extra_end_param/expected.json), [model](data/R_E_extra_end_param/model.json), [C output](data/R_E_extra_end_param/csim/observed.json), [trace](data/R_E_extra_end_param/csim/trace.jsonl) |
| E_prior_success | E03 | PASS | 10 output words; consumed 23; error 5; tx 512 | [expected](data/E_prior_success/expected.json), [model](data/E_prior_success/model.json), [C output](data/E_prior_success/csim/observed.json), [trace](data/E_prior_success/csim/trace.jsonl) |
| R_E_prior_success | RECOVERY, E03 | PASS | 7 output words; consumed 21; error 0; tx 0 | [expected](data/R_E_prior_success/expected.json), [model](data/R_E_prior_success/model.json), [C output](data/R_E_prior_success/csim/observed.json), [trace](data/R_E_prior_success/csim/trace.jsonl) |
| T05_rounding | T05 | PASS | 16 output words; consumed 46; error 0; tx 0 | [expected](data/T05_rounding/expected.json), [model](data/T05_rounding/model.json), [C output](data/T05_rounding/csim/observed.json), [trace](data/T05_rounding/csim/trace.jsonl) |
| T06_end_tail | T06 | PASS | 2 output words; consumed 12; error 0; tx 0 | [expected](data/T06_end_tail/expected.json), [model](data/T06_end_tail/model.json), [C output](data/T06_end_tail/csim/observed.json), [trace](data/T06_end_tail/csim/trace.jsonl) |
| T07_empty | T07 | PASS | 0 output words; consumed 6; error 0; tx 0 | [expected](data/T07_empty/expected.json), [model](data/T07_empty/model.json), [C output](data/T07_empty/csim/observed.json), [trace](data/T07_empty/csim/trace.jsonl) |
| T08_zero_boundaries | T08 | PASS | 14 output words; consumed 36; error 0; tx 0 | [expected](data/T08_zero_boundaries/expected.json), [model](data/T08_zero_boundaries/model.json), [C output](data/T08_zero_boundaries/csim/observed.json), [trace](data/T08_zero_boundaries/csim/trace.jsonl) |
| T08_round_to_zero_and_normal | T08 | PASS | 11 output words; consumed 33; error 0; tx 0 | [expected](data/T08_round_to_zero_and_normal/expected.json), [model](data/T08_round_to_zero_and_normal/model.json), [C output](data/T08_round_to_zero_and_normal/csim/observed.json), [trace](data/T08_round_to_zero_and_normal/csim/trace.jsonl) |
| T_random | T05 | PASS | 1300 output words; consumed 1346; error 0; tx 0 | [expected](data/T_random/expected.json), [model](data/T_random/model.json), [C output](data/T_random/csim/observed.json), [trace](data/T_random/csim/trace.jsonl) |

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
