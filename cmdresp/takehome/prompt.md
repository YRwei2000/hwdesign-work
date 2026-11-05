# Float32 2-D Max Pooling

Current stage: specification only. Do not implement, run simulations, or commit
Git changes until separately authorized. The instructions below govern that
future implementation.

Build a Vitis HLS kernel in this folder following the Waveflow stream_inband
example (https://sdrangan.github.io/waveflow/docs/examples/stream_inband/) and
the command-response pattern.

Read the example and its build documentation through Waveflow MCP first; the
course command-response rules take precedence where they differ. This prompt
uses the official [template](https://github.com/sdrangan/hwdesign/blob/main/labs/cmdresp/partial/prompt.md),
[take-home requirements](https://sdrangan.github.io/hwdesign/docs/labs/cmdresp/takehome.html),
and [pattern](https://sdrangan.github.io/hwdesign/docs/labs/cmdresp/pattern.html).

## Operation

Pool an `H × W` float32 matrix using square `K × K` windows, stride `K`, no
overlap and no padding. Require `1 <= H,W <= 64`, `1 <= K <= 8`, `K <= H,W`,
and both dimensions divisible by `K`. The output is `(H/K) × (W/K)`.
Input and output matrices travel in row-major order.

Within each window, initialize the maximum from its first element and visit
elements in row-major order. Replace it only on a strictly greater comparison;
ties retain the first element, including its original binary32 bits. Inputs
and outputs support finite normal float32 and positive/negative zero. NaNs,
infinities and subnormals are outside scope; detection is not required.
Each COMPUTE is independent; no computation state persists between matrices.

## Requirements

- Both AXI4-Streams are 32 bits; each matrix/result data word contains exactly
  one float32. All parameters and data travel on the input stream. AXI-Lite
  carries only activation control and status.
- Use the stream_inband FPGA and clock configuration: `xc7z020clg484-1`, 10 ns,
  as verified in its `run.tcl`. The synthesis estimated clock period must be
  **less than 10 ns**; a clock-uncertainty-margin warning alone is not a failure.
- For `H=W=64, K=2`, with no extra host input pauses and no output backpressure,
  target **at most 8192 cycles** from the first matrix input transfer to the
  last, inclusive: `last_input_cycle - first_input_cycle + 1`. Transfers mean
  `TVALID && TREADY`; headers are excluded from this interval.
- Also report total latency from the first matrix input transfer through the
  last result transfer, inclusive, and measured throughput with its units and
  interval. Obtain cycles, latency and throughput from RTL co-simulation;
  obtain estimated clock, II and resources from synthesis.
- Report a missed target as FAIL. Do not repeatedly optimize to force a pass,
  and do not create a Python timing model.

## Commands and parameters

- **COMPUTE:** a header burst carries `tx_id, H, W, K`, followed by a burst of
  exactly `H*W` samples. Check all applicable header and parameter conditions
  before reading matrix data. After acceptance, send the complete response
  header, echoing `tx_id` and giving `H/K, W/K`, with TLAST on its last word,
  **before the first matrix payload read**. Compute and buffer results; only
  after the entire matrix and its TLAST pass validation, send all results as
  one burst, with TLAST only on its final word.
- **END:** terminate the activation normally, send no response and process no
  subsequent command in that activation.

Each header is its own TLAST-terminated burst. The implementation agent may
choose and document opcodes, header/response layouts, packing, error codes,
file formats and unused-field conventions, consistently across all artifacts.
Use Waveflow schemas/serializers following the reference. These choices must
not change the confirmed operation or error behavior.

## Errors

Errors go in AXI-Lite status registers (halted, error code, tx_id). On an
error the kernel closes any output burst it started with TLAST and returns
without reading more input. Nothing persists between activations: the status
registers are cleared at the start of each one.

Validation order is **header format → command legality → parameter legality →
COMPUTE payload TLAST**. Perform only checks applicable to the current command
and report the first error. For COMPUTE, check parameters strictly in this order:
**H range → W range → K range → K <= H and K <= W → both H and W divisible
by K**. Execute each check only after its predecessors pass; do not use invalid
dimensions in size calculations, indexing or division/modulo operations.

- Validate header length, required identifiers and TLAST according to the
  chosen, documented format, including early TLAST and a received final header
  word without TLAST. Stop reading as soon as a format violation is detectable;
  do not complete the header or read extra words to obtain `tx_id`. Record the
  actual ID when determinable from already received words; otherwise use one
  fixed fallback value chosen and documented by the implementation agent.
  Header errors produce no response for the rejected command.
- Unknown commands, header errors and invalid COMPUTE parameters stop the
  activation: set error status, send no response for that command and read
  none of its matrix payload. Invalid parameters include every violation of
  the ranges, window-size and divisibility constraints above.
- Payload TLAST must be clear before element `H*W` and set on that element.
  Early TLAST, or a received final element with TLAST clear, causes immediate
  input stoppage and error status with the command's `tx_id`. Do not read
  another word to search for TLAST or drain queued commands.
- On either payload error, discard **all** cached results for that matrix and
  retain only its already-completed response header. No result burst has
  started, so there is none to close: never send a dummy sample or an empty
  burst placeholder. Preserve earlier successful commands' output.
- The host inspects status and resets the stream path after an error. Each
  error test must have its own successful recovery activation using entirely
  new input and output streams.

Do not implement an input timeout. Blocking while input is temporarily
unavailable is allowed. A host that permanently stops sending and leaves a
header or payload incomplete is outside required error detection. Missing
TLAST means the prescribed final word **was received** with TLAST clear,
not that a word has failed to arrive.

## Verification

Deliver a bit-exact Python model, HLS kernel, testbench and reproducible scripts.
Validate Python independently before C simulation: hand-check a 4×4 matrix
filled row-major with `1..16`, `K=2`, giving `[[6,8],[14,16]]`, and compare
against NumPy `A.reshape(H//K, K, W//K, K).max(axis=(1,3))`.
For ties, independently select the first row-major element equal to the
reference maximum and check its raw bits; NumPy max alone is not the signed-zero
tie oracle. Include hand-checked windows with both zero signs in both orders.

Cover negative inputs, equal maxima, signed zeros, `K=1`, `H/W=1` and `64`,
`K=8`, valid rectangular shapes, changes of H/W/K within one activation, END,
unknown commands, each invalid-parameter condition, and malformed headers.
Test early payload TLAST at the first and a later
element, and missing TLAST on a received final element, including a 1×1 input.
Check errors after earlier successful commands and fresh recovery after every
error subcase. Include the 64×64, K=2 performance scenario.

Include the following error-policy acceptance cases, each with its own
fresh-stream recovery activation:

- Malformed headers covering length, required identifiers, early TLAST and
  missing TLAST on a received final header word. Include cases with a known
  `tx_id` and cases where it is unavailable; verify the actual ID or fixed
  fallback, no response and no reads beyond the detection point.
- Simultaneous violations proving header format precedes opcode legality,
  opcode legality precedes parameters, and invalid parameters prevent payload
  reads even when a bad-TLAST payload is queued. Exercise every COMPUTE
  parameter stage and precedence between stages where simultaneous violations
  are possible, including invalid H/W with K=0; verify later unsafe calculations
  are not executed. All earlier checks must pass in tests isolating a later one.
- Queue distinguishable trailing input to verify immediate input stoppage.
  Recovery must process a valid matrix and END with clean status and correct
  output; never reuse the failed activation's streams or share a recovery
  between error subcases.

Malformed-header and payload tests must supply enough input to make their
violation detectable. Do not treat an empty-stream exception as a protocol
error or require permanently incomplete input tests to terminate. Inspect
blocking-read logic to verify that no input timeout is implemented.

Compare raw binary32 bits without tolerance, response IDs and dimensions,
result counts/order, TLAST, status and the exact input stopping position.
Retain operation-order evidence that the response header finishes before any
matrix read and that no result is transferred before complete input validation.

Compare the model, C simulation and co-simulation bit for bit. Run
co-simulation once: one testbench run that walks through every scenario in
order, calling the kernel once per activation with fresh streams, including
each error activation and the fresh activation after it.

This scope applies to the first co-simulation run too; do not substitute the
reference's timing-only run. Report any tool limitation instead of silently
omitting scenarios.

## results.md

Write results.md with these sections:

- Interface: the command and response layouts, how values pack into words,
  the status registers and the error codes.
- Design: the loop structure, where state is kept, and how the throughput
  target is reached.
- Targets: each target above with the required value, the measured value,
  PASS/FAIL and the file it came from (co-simulation for timing; synthesis
  for clock, II and resources). Always report the latency and throughput
  from co-simulation and the estimated clock and resources from synthesis,
  writing "no target" where this prompt sets none.
- Verification: the model's check against the hand-computed examples and the
  reference; then one row per scenario saying whether the model, C simulation
  and co-simulation agree, and for each error scenario the status it set and
  whether the fresh activation after it passed. Name the source file of each.
- Assumptions: every place this prompt was silent or ambiguous and what you
  chose, apart from interface details already given under Interface.
- Open Items: questions you could not settle, and anything that failed or was
  not done, or "None".
- Run History: one row per run, with the prompt version, what was built or
  changed, and what passed, so that a later run can continue from here.

Every number and PASS/FAIL in Targets and Verification names the file it came
from (a log, a comparison output or a synthesis report), and that file stays in
this folder to be committed: a reviewer opens them to check results.md.

Retain implementation/source files, reproduction scripts and all cited raw
evidence; exclude Vitis project directories and bulky uncited logs from future
commits. Do not claim unrun checks passed; list failures and unfinished work.
Creating results.md and running these checks belong to implementation, not
this specification-only stage.

## Revision History

| Version | Change | Why |
| --- | --- | --- |
| v1 | First version | User-confirmed design requirements. |
| v2 | Define error precedence, header validation and input waiting; add error and recovery coverage. | User confirmed validation order, immediate stopping with known/fallback tx_id, and blocking input without timeout. |
