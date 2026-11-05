# In-Class Project Specification: Float32 Scale and Offset

## Scope and authority

This document specifies a future implementation in `cmdresp/inclass/`. The current task is specification only: update this file, without implementing the accelerator, running any simulation, or committing Git changes. The implementation instructions below apply only when implementation is separately requested.

Build a host-activated command-response accelerator that computes `y = a*x + b` for each input sample. Deliver a bit-exact Python model, a Vitis HLS kernel, a C++ testbench, reproducible verification artifacts, and `results.md`. Independently validate the Python model first; then verify C simulation against it bit for bit. Stop when the required C simulation checks pass. Do not run synthesis or RTL co-simulation, or claim hardware timing/resource verification. Do not commit or push Git changes unless separately requested.

Read the `stream_inband` example through Waveflow MCP, including its model, kernel body, scenarios, testbench, and relevant documentation before implementation. Follow the course command-response pattern wherever it differs from the reference. The explicit requirements in this document govern this project; do not import incompatible example defaults.

References consulted for this specification:

- [Course command-response pattern](https://sdrangan.github.io/hwdesign/docs/labs/cmdresp/pattern), read through the course material tool: `docs/labs/cmdresp/pattern.md`.
- [Course in-class assignment](https://sdrangan.github.io/hwdesign/docs/labs/cmdresp/inclass), read through the course material tool: `docs/labs/cmdresp/inclass.md`.
- [Waveflow stream_inband example](https://sdrangan.github.io/waveflow/docs/examples/stream_inband/), read through Waveflow MCP, including `index.md`, `decisions.md`, `01_python_golden_model.md`, and `poly_body_impl.tpp`; also consult `waveflow_get_process(frame="stream_inband")` for implementation mechanics.

The course material was served as ECE-GY 6463, Fall 2026, package `2026-10-15.34eccd5`, code version `c98e568e0e7c`. Its historical description of the example may differ from the current Waveflow example. Apply the course's actual rules rather than relying on that historical description.

Key adaptations: use a separate CONFIG command and retain its coefficients across DATA commands within one activation; reject zero-length DATA; stop verification at C simulation. The reference's per-DATA coefficients, legal zero-length DATA, and full synthesis/co-simulation flow do not override these requirements.

## Confirmed computation and state

- `a`, `b`, each `x`, and each `y` are float32 values. Preserve their binary32 representations in stimulus and result artifacts.
- Rounding is IEEE 754 round-to-nearest, ties-to-even. For each sample, compute a multiplication, round its result to float32, then perform the addition and round again to float32:
  1. `product = round_to_float32(a * x)`
  2. `y = round_to_float32(product + b)`
- Fused multiply-add is prohibited. Do not compute the full expression in a wider type and round only once. In the future implementation, use explicit intermediate precision and compiler settings that prevent contraction; separate source statements alone are not sufficient evidence. Record the effective settings and a test that distinguishes the required result from FMA.
- Each activation starts with no valid configuration and cleared status. Coefficients from an earlier activation must never authorize DATA in a new activation.
- Each valid CONFIG immediately replaces both `a` and `b`. Every subsequent DATA command uses those coefficients until another valid CONFIG arrives or the activation ends. CONFIG cannot change results of earlier commands.
- DATA has no arithmetic state across samples or commands beyond the current configuration. Multiple DATA commands may use the same configuration.
- The supported domain consists of finite normal binary32 values and positive/negative zero, for all coefficients, input samples, the rounded multiplication intermediate, and the rounded final result. NaNs, infinities, subnormals, and computations producing such intermediate or final results are outside the supported domain. Detection and behavior for those cases are not required. Do not add numeric-domain errors or promise behavior for them. Preserve IEEE 754 signed-zero semantics within the supported domain.

## Interfaces and command behavior

Use a **32-bit AXI4-Stream input and a 32-bit AXI4-Stream output**. The input carries all CONFIG, DATA, and END commands and their content; the output carries responses and results. Each DATA payload word carries exactly one complete float32 sample, and each result word carries exactly one complete float32 result. AXI-Lite is exclusively for activation control and status, including `ap_start`, `ap_done`, and the logical status fields `halted`, `error`, and the offending `tx_id`. Do not put coefficients or other computation inputs in AXI-Lite registers.

The host starts an activation; the kernel processes commands in input order until END or an error causes it to return. A command header forms its own burst, followed by a data burst when the command carries data, as in the course pattern. Document how CONFIG carries its two coefficients within that framing.

| Command | Required logical content | Confirmed behavior |
| --- | --- | --- |
| CONFIG | Command identity, transaction identity, float32 `a` and `b` | Replace the current coefficients after receiving a valid CONFIG; emit one acknowledgement response header echoing its `tx_id`. |
| DATA | Command identity, `tx_id`, declared `nsamp`, followed by samples | Require a valid configuration and `nsamp > 0`; compute one result per sample for a successful command. |
| END | Command identity and documented header fields | End the activation normally without a response, including when no CONFIG has been received; no later command is processed in that activation. |

After all applicable DATA header checks pass (format, command legality, parameter legality, and configuration availability), emit the **complete response-header burst**, echoing that DATA's `tx_id` and ending with TLAST, **before reading the first payload word**. If any applicable header check fails, emit no response for that command and read none of its payload. Unknown commands, malformed headers, and invalid CONFIG likewise produce no response for the rejected command.

After that DATA response header, emit eligible results in input order as a separate result-data burst. Successful DATA produces exactly `nsamp` results with TLAST on the final result. A payload error retains the complete response header and produces exactly the valid prefix specified below. A valid CONFIG produces a header-only acknowledgement burst terminated with TLAST, with no result-data burst. Each valid CONFIG, including a replacement CONFIG, gets its own acknowledgement. END produces no output.

Normal completion must report a non-error status. The initial/normal value of the status transaction field is a documented representation choice; on error it must identify the failing command when its ID is determinable, otherwise use the documented fixed fallback value. A response header emitted before sample processing does not prove that the entire DATA succeeded: the host must also inspect completion status.

For DATA payload framing, TLAST must be absent on sample words 1 through `nsamp - 1` and present on sample word `nsamp`. There are no multi-sample words, partial sample lanes, or DATA payload padding samples.

Do not implement an input timeout. When input is temporarily unavailable, blocking while waiting for the next word is allowed. A host that permanently stops sending and leaves a header or payload incomplete is outside the required error-detection scope. Missing payload TLAST means that the declared final sample word **has been received** and its TLAST is clear; it never means that a word has not yet arrived. Detectable malformed framing, such as an early header TLAST, remains an error under the documented header format.

## Required errors and termination

Provide documented error codes that identify these conditions. Numeric code assignments are implementation choices.

Validation order is fixed: **header format → command legality → command-parameter legality → configuration availability → DATA payload TLAST**. Perform only checks applicable to the current command, and report the first error found in this order. In particular, zero-length DATA before CONFIG reports the parameter error, not the missing-configuration error. A malformed header takes precedence over an unknown opcode or bad parameters; an unknown opcode takes precedence over parameter checks. CONFIG and END do not require a prior configuration. Header-format validation includes the structural/framing rules of the chosen interface; do not copy the reference's policy of ignoring header TLAST.

| Error condition | Required detection point |
| --- | --- |
| Malformed header | As soon as a violation of the documented header format is detectable. Do not continue reading after detection just to obtain a transaction ID. |
| Unknown/illegal command | After header-format validation, before interpreting command-specific parameters. |
| Invalid CONFIG or other illegal command parameters | After header-format and command-legality checks, before configuration-availability or sample checks. CONFIG must pass all applicable checks before being accepted or acknowledged. |
| DATA before the first valid CONFIG of an activation | When the DATA header establishes that DATA is being requested without configuration. |
| DATA with `nsamp = 0` | When the DATA header is validated. |
| DATA payload TLAST early | On reading a payload word marked TLAST before the declared final sample word. |
| DATA payload TLAST missing | On reading the declared final sample word without TLAST; do not read an extra word to look for it. |

On any error:

1. Set error status, including `halted = 1`, the first applicable error code, and the offending command's `tx_id` when determinable. Otherwise use one fixed fallback value selected by the implementation agent and documented in the interface specification. Do not perform extra reads to recover an unavailable ID.
2. Stop reading input at the detection point. In particular, do not read a rejected DATA's payload after detecting its header error, drain to TLAST, read ahead past the offending sample, or consume queued commands.
3. For a payload error, finish and emit the results of **all earlier samples already read and checked successfully**, including any pending computation or buffered results. Preserve previously emitted results without duplicating them, and exclude the offending sample. Close the nonempty result burst with TLAST on its final valid result. If there are no eligible samples, do not start a result burst.
4. Ensure every output burst that was started is closed, then return immediately. Do not attempt to modify a word already transferred; arrange buffering or emission so the final valid result can carry TLAST. Completing pending valid output is required and does not authorize any further input reads.
5. Do not emit a success footer for a failed command or attempt kernel-side recovery. Immediate return means return after the required valid-prefix output and burst closure; it is not a zero-cycle or backpressure-independent timing guarantee.

Precisely, if a payload TLAST error is detected at the **1-based sample index `k`**, the failed DATA's output is its already-completed response header followed by exactly the results for samples `1..k-1`, in order. For `k > 1`, emit those `k-1` results as one burst, with TLAST only on the final result. All buffered valid results must be included, even if the result burst had not started at detection. For `k = 1`, retain only the completed response header: there is no result-data burst to close. Never emit a dummy sample, empty-burst placeholder, or the offending sample's result. This differs from the reference kernel, which emits the result associated with the offending input before reporting the error.

The host must discard the entire result batch belonging to the failed command. Do not require rollback or discard earlier successful commands or CONFIG acknowledgements. A one-sample DATA missing TLAST and an early TLAST on the first sample both have `k = 1`: the failed DATA contributes exactly one complete response-header burst and zero result words. A command rejected by its header checks contributes no response at all. These cases are distinct from preserving output belonging to earlier commands.

After an error the stream contents are undefined for reuse. Recovery is the host's responsibility: inspect status, reset the stream path, and start again. In tests, model that reset with entirely new input and output stream objects for every recovery activation; do not reuse or drain the failed activation's streams to simulate recovery. Configuration must be sent again.

## Delegated representation choices

The implementation agent may choose command encodings, header-field widths, header and response layouts, header-field packing and padding conventions, filenames, and artifact formats. Both stream widths are fixed at 32 bits, with one float32 per DATA payload/result word; those choices are no longer delegated. Choose a single coherent contract and document it before comparing implementations. These choices must not change the confirmed arithmetic, configuration lifetime, command ordering, or error rules.

Document at least: opcode and error-code tables; supported sample-count and transaction-ID ranges; each command and response layout; word and byte ordering; TLAST placement; coefficient encoding; status encoding including the fixed unavailable-ID value; and how exact float32 bits are stored in files. Define header validity, command-specific parameter constraints, invalid CONFIG encodings, and when a transaction ID is determinable under the chosen layout. Distinguish malformed wire encodings from unsupported floating-point cases: out-of-domain floats are not required invalid-CONFIG tests. If header structure and command parameters have distinct violations, classify them explicitly so the required precedence is reproducible.

Use Waveflow schemas or array serialization utilities for headers and sample bursts, in both Python and C++; do not hand-pack an alternative protocol. Keep generated boundaries and serializers generated. If the framework cannot express a required behavior, report the concrete limitation instead of silently changing the requirement or editing generated code.

## Verification order and evidence

1. Record the delegated protocol choices and report any newly discovered material ambiguity before implementing dependent behavior. Define scenario intent and expected status/framing independently of the protocol parser or kernel.
2. Independently check the pure Python arithmetic model using hand-computed cases and independently derived binary32 bit patterns. Verify its activation/configuration state, framing, errors, and input-consumption behavior against scenario intent. Do not generate all expected answers by calling the same model under test.
3. Demonstrate that the checker rejects at least a changed result bit and a missing output TLAST. Preserve the rejection evidence.
4. Only after the Python checks pass, run the Vitis HLS C++ testbench in C simulation. Preload each scenario's input, call the kernel, and capture output and status. Use the independently validated Python results and scenario expectations as the reference.
5. Compare every float32 result by its raw 32-bit representation, with no tolerance. Also compare response IDs, result counts, ordering, burst boundaries, TLAST flags, error codes, and status. Observe input consumption to prove the kernel stops reading on an error and on END. Use operation-order evidence to verify that the full DATA response header is written before the first payload read; final output files alone cannot establish that ordering.
6. Stop once all required C simulation checks pass. Do not invoke a reference build target that also launches synthesis, RTL co-simulation, or timing calibration. C simulation does not establish RTL timing, throughput, or resource use.

For error tests, queue identifiable trailing commands behind the failing command. Record the expected and observed unread input or read count before disposing of the old streams. This is a testbench observation after return, not permission for the kernel to drain input. A leftover-input warning is not automatically a failure if the recorded unread input matches the required stopping point.

Do not run permanently incomplete input as a required error test or reinterpret a C simulation empty-stream assertion as a protocol error. The no-timeout requirement can be checked by inspecting the kernel's blocking-read/control logic. A test-harness watchdog, if used to catch test failures, is not a kernel timeout or an accepted error response. Temporary input-delay tests, if the chosen harness supports them, must resume input and expect normal continuation; no RTL timing test is required.

## Required test scenarios

Assign stable scenario IDs and distinct, nontrivial transaction IDs so echoing and error attribution are observable. Each row below must have evidence; report error and recovery activations separately.

| ID | Stimulus / purpose | Required checks |
| --- | --- | --- |
| T01 | CONFIG(2, 1), DATA([1, 2, 3]) | CONFIG acknowledgement echoes its ID and ends with TLAST; DATA results `[3, 5, 7]`, exact float32 bits, response ID, count, and TLAST. This is the first segment of T02's activation. |
| T02 | In that same activation, CONFIG(3, -1), DATA([1, 2]), END | Replacement CONFIG acknowledgement echoes its own ID; results `[2, 5]`; replacement takes effect immediately; normal termination with no END response. T01 and T02 must not be split into separate activations. |
| T03 | CONFIG(2, 1), DATA([1]), DATA([2, 3]), DATA([-1, 0]), END | Results `[3]`, `[5, 7]`, `[-1, 1]`; one configuration reused across three commands with independently echoed IDs. |
| E01 | DATA with a positive count before any CONFIG | Configuration error, failing ID, no response for this command, and no payload or subsequent command read. |
| E02 | Valid CONFIG, then DATA with `nsamp = 0` | Zero-length error, failing ID, no DATA response and no subsequent input consumed; prior CONFIG acknowledgement remains. Use valid configuration to isolate this error. |
| E03 | CONFIG(2, 1), DATA declaring 5 samples but receiving `[1, 2, 3]` with TLAST on sample 3 | Early-TLAST error at `k = 3`, correct ID, complete DATA response header, then exactly `[3, 5]` with TLAST on `5`; no result `7`, no trailing reads. Verify that all pending valid-prefix results are emitted. Also include a longer-prefix case exercising closure after result emission has begun under the chosen buffering scheme. |
| E04 | CONFIG(2, 1), DATA declaring 3 samples, receiving `[1, 2, 3]` with TLAST clear on all three | Missing-TLAST error at `k = 3`, correct ID, complete DATA response header, then exactly `[3, 5]` with TLAST on `5`; no result `7` and no extra read. Do not substitute an empty/truncated stream for this case. |
| R01-R04 | Immediately after each corresponding E01-E04 activation, create fresh streams; run CONFIG(2, 1), DATA([1, 2, 3]), END | Successful `[3, 5, 7]`, correct response ID/framing, cleared error status, and normal return. Every error requires its own recovery test. |
| T04 | Finish a successful configured activation; start another activation whose first command is positive-length DATA | DATA-before-CONFIG error despite prior success, proving configuration does not survive activation boundaries. Follow this additional error with its own fresh-stream recovery test. |
| T05 | Float32 step-rounding cases | Check independently derived intermediate product bits and final result bits; include a case that fails under FMA or a single final rounding, plus an addition-rounding case. |
| T06 | Valid CONFIG, END, with a distinguishable command queued afterward | CONFIG acknowledgement only; normal completion with no END response; the command after END remains unread. |
| T07 | END as the first command of a fresh activation, with a distinguishable trailing command | Normal completion, cleared error status, no output, and trailing input unread; no CONFIG is required. |
| T08 | Supported signed-zero and finite-normal boundary cases | Independently verify exact product and result bits, including `a = -0, x = 1, b = -0` giving `-0`, and `a = 1, x = -0, b = +0` giving `+0`; include the smallest/largest finite normal values with arithmetic that stays in the supported domain. No unsupported-domain detection is required. |
| E05 | Well-formed header with an unknown opcode | Illegal-command error, correct determinable ID, no response for the rejected command, immediate stop with trailing input unread; no interpretation as END. |
| E06 | Malformed headers under the chosen layout | Separate cases with a determinable ID and an unavailable ID; check the header-format error and the actual ID or fixed fallback respectively, no response for the rejected command, and no reads after detection. Cover early and missing header TLAST where applicable to the documented format, using received words that make the violation observable, not permanent input starvation. |
| E07 | Invalid CONFIG under documented command-parameter rules, with valid header structure and legal opcode | Parameter error and correct ID; no CONFIG acknowledgement, no subsequent DATA processed. Use in-domain coefficient values to isolate protocol validity from unsupported arithmetic. |
| E08 | Multiple simultaneous violations | Separate cases proving header format precedes opcode legality, opcode legality precedes parameters, and zero-length DATA before CONFIG reports the parameter error. Also preload bad-TLAST payloads behind parameter-invalid and unconfigured positive-length DATA, and prove those payloads are not read. Only applicable checks participate. |
| E09 | Valid CONFIG, then early TLAST on sample 1 of a longer DATA; separately, valid CONFIG then `nsamp = 1` with a received word missing TLAST | Correct framing error and ID; for each failed DATA, exactly its complete TLAST-terminated response header and zero result words/bursts. No dummy result, no second header, no open burst, and no extra reads. Prior CONFIG acknowledgement remains. |
| E10 | Two separate activations, each starting with CONFIG(2, 1): DATA declaring 3 samples and receiving `[1, 2]` with early TLAST on sample 2; DATA declaring 2 samples and receiving `[1, 2]` without TLAST | In each case exactly one valid result `3`, carrying TLAST, follows the complete DATA response header. Result `5` is excluded. Verify any held-back first result is emitted, not dropped; no more input is read. |
| T09 | Observe DATA header-validation, output-write, and payload-read order for success and payload-error scenarios | Complete response header including its TLAST precedes the first payload read. Header-rejection scenarios produce neither a response for the rejected command nor payload reads. Record an operation trace or equivalent verification evidence without introducing synthesis or RTL co-simulation. |
| T10 | Review input-wait/error logic and the received-last-word tests E04/E09 | Confirm blocking reads without input timeout or empty-input error; missing-TLAST errors depend on a received final word with TLAST clear. Record source-review evidence. Permanently incomplete header/payload streams are excluded, not expected to return an error. |
| R05+ | A separate fresh-stream recovery activation after every E05-E10 subcase and every other added error subcase | CONFIG(2, 1), DATA([1, 2, 3]), END produces its CONFIG acknowledgement and `[3, 5, 7]`, exact DATA response/framing, clean status, and no END response. Never share one recovery activation across several error cases. |

Required T05 expectations under the confirmed round-to-nearest, ties-to-even mode:

- `a = 1 + 2^-23` (`0x3f800001`), `x = 1 - 2^-23` (`0x3f7ffffe`), `b = -1` (`0xbf800000`).
- The exact product is `1 - 2^-46`; its float32 rounded value is `1` (`0x3f800000`). The separate addition produces `+0` (`0x00000000`), whereas FMA produces `-2^-46` (`0xa8800000`).
- An addition-rounding tie is `a = 1`, `x = 1`, `b = 2^-24` (`0x33800000`): the result is `1` (`0x3f800000`). Also test the opposite tie direction: `a = 1`, `x = 1 + 2^-23`, `b = 2^-24` gives `1 + 2^-22` (`0x3f800002`), selecting the even significand rather than always rounding down.

These are mathematical expectations, not executed test results. Independently verify them during model validation, and add tests for every additional semantic decision that is adopted. Every additional error scenario must also have a fresh-stream recovery test. Keep mandatory arithmetic vectors inside the supported domain, including their intermediate and final results.

## Implementation deliverables and results.md

The future implementation must include:

- A pure bit-exact Python arithmetic model and a protocol/activation model.
- Waveflow schemas and a documented wire format, with example serialized layouts.
- A Vitis HLS kernel with explicit non-fused arithmetic and the specified command loop, state, and error handling.
- A C++ testbench, scenario fixtures, independent expected values, and exact comparison tools.
- Reproducible commands and tool/compiler versions, including evidence that model validation preceded C simulation and that the build stops there.
- `cmdresp/inclass/results.md`, linked to retained validation artifacts.

In `results.md`, list every scenario, including each error and each recovery activation, with PASS/FAIL and evidence paths. Include expected versus observed outputs/status, the check command or log, and machine-readable bit/framing evidence where relevant. A missing or blocked required test is FAIL with a clear explanation that it was not run; never present it as a measured pass. Do not create this report during the specification-only task.

Also list every omission or ambiguity encountered, the decision adopted and its basis or confirmation, and all unfinished work or tool limitations. Separate verified facts from assumptions. Explicitly state that synthesis and RTL co-simulation were not run and are outside this classroom scope.

## Specification status and consistency

No material semantic ambiguity remains identified within the supported scope. Previously open questions about buffered output, DATA response timing, sample packing, and input timeout are resolved above. Representation choices remain delegated only within the fixed 32-bit stream and behavioral contract, and must be documented in the interface specification and `results.md`.

The error rules distinguish three cases consistently:

- Header rejection: no response for that command and no payload read.
- Payload error at sample 1: preserve the complete response header; emit no result-data burst and no fake closing sample.
- Payload error at sample `k > 1`: emit all and only the `k-1` valid-prefix results, including buffered results, close their burst with TLAST, and return without further input reads.

Stopping input immediately and completing pending valid output are separate obligations. A buffer/emission design must make both achievable; it must not rely on modifying a word already sent. No input timeout is required, and permanent input starvation is outside error detection. If implementation exposes a new material ambiguity or a framework limitation, report it instead of changing these confirmed behaviors.
