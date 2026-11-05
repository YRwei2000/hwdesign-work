# Host interface and representation decisions (prompt v2)

This describes the required protocol and chosen encodings. The current RTL has
an external response/payload ordering failure; see [results.md](results.md)
before using this as a validated host contract.

Both streams use 32-bit words with one float32 per matrix/result word. Headers
are Waveflow DataList schemas. This layout was obtained by serializing the
schemas; see [serialized examples](evidence/layout_examples.json).

| Input header word (zero-based) | Field | Encoding |
| --- | --- | --- |
| 0 | magic | `0x504f4f4c` |
| 1 | tx_id | uint32 |
| 2 | opcode | uint32: COMPUTE=1, END=2; all other values illegal |
| 3 | H | uint32 |
| 4 | W | uint32 |
| 5 | K | uint32 |

Every input header has exactly six words, TLAST only on word 5. The magic and
each received word's TLAST are checked immediately. Before word 1 has arrived,
tx_id is unavailable and the error status uses `0xffffffff`; afterward it uses
the received ID, including when that word has early TLAST. The fallback is also
a legal actual ID, so the host uses its command context to distinguish it. No
extra read is permitted. Length is implicit in the fixed schema; missing final
TLAST and early TLAST detect long/short bursts without an additional length field.

COMPUTE parameters are checked in prompt order. Its payload is exactly H*W
row-major float32 words, TLAST only on the last. Each accepted COMPUTE first
emits a three-word response header: `[tx_id, H/K, W/K]`, each uint32, TLAST only
on its last word. The separate result burst is row-major float32 with TLAST
only on its last result. It is emitted only after all input is validated and
all results are cached. A payload error retains the header and emits zero
results, without an empty-burst placeholder. END ignores H/W/K, emits nothing,
and returns normally even as the first command. It still validates header framing
and magic. No separate CONFIG, footer, timeout or kernel recovery is present.

| Status error | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Header format (magic or framing/length) |
| 2 | Unknown opcode |
| 3 | H outside 1..64 |
| 4 | W outside 1..64 |
| 5 | K outside 1..8 |
| 6 | K exceeds H or W |
| 7 | H or W not divisible by K |
| 8 | Early payload TLAST |
| 9 | Received final payload word without TLAST |

AXI-Lite holds only Vitis control and read-only status: halted (1 bit), error
(8 bits), tx_id (32 bits). All are cleared on activation; normal return keeps
them zero. On error halted=1, the first applicable code is recorded with the
actual/fallback ID. Register offsets come from generated control RTL and are
retained in [the control source](evidence/synthesis/max_pool_control_s_axi.v).
Host words use all byte lanes. Unsupported floating-point inputs are a host
precondition, not an extra parameter check.

Fixture/result files use Waveflow `write_bursts`/`read_bursts` and
`wf::play_stream`/`wf::record_stream`: words.bin holds uint64 little-endian
containers for 32-bit words; the framework metadata records burst lengths and
TLAST. JSON evidence stores exact uint32 sample words and 0/1 TLAST pairs,
with status and exact consumed/unread input. Schema/array serializers, rather
than manual field packing, encode headers and samples. Deliberately malformed
fixtures change framing or schema values explicitly.

No material semantic assumptions beyond the confirmed prompt were needed.
Buffering the full input before pooling is an implementation choice; memory
contents are local to a call and are never used to authorize another command.
The Waveflow reference's timing-model calibration and timing-only cosim selection
are superseded by the course prompt: this project has no Python timing model,
and its first cosim invokes every scenario.
