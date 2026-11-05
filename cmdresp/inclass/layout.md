# Scale-and-offset interface and implementation decisions

`prompt.md` is unchanged. This document records the representation choices delegated
to the implementation. The input/output data width is 32 bits; one DATA or result
word is one IEEE binary32 bit pattern. The generated AXI stream type carries
TDATA, TLAST, TKEEP and TSTRB; send full words (TKEEP=TSTRB=0xf). The kernel uses
TDATA/TLAST; partial-byte transfers are not a supported host encoding. Generated
writers set full TKEEP/TSTRB. No synthesis or pin-level validation is claimed.

## Commands and responses

Every command has the same six-word header, serialized by `CmdHdr`. Word indices
below are zero-based. TLAST must be 0 on words 0–4 and 1 on word 5. The magic is
checked as soon as word 0 is received. Framing is checked on each word; no extra
word is read to identify a malformed header's transaction.

| Word | Field | Encoding / rule |
| --- | --- | --- |
| 0 | magic | uint32, `0x53434f46` |
| 1 | tx_id | uint32, echoed without modification |
| 2 | opcode | uint32: CONFIG=1, DATA=2, END=3; all other values are illegal |
| 3 | nsamp | uint32: DATA 1..0xffffffff; CONFIG and END must use 0 |
| 4 | a | float32 coefficient for CONFIG; ignored on DATA/END |
| 5 | b | float32 coefficient for CONFIG; ignored on DATA/END |

CONFIG coefficients are in the header, with no separate coefficient burst. There
are no padding fields or unused bits in the header. No numeric-domain checking is
added: unsupported float encodings/intermediate results remain outside scope.
An invalid CONFIG is, for example, an otherwise well-formed CONFIG with nonzero
nsamp. This provides an applicable parameter check independent of float validity.
Unused coefficient fields in DATA/END are ignored and sent as +0 by the fixtures.
All uint32 transaction IDs are legal, including repeated IDs. The kernel does not
track uniqueness; test IDs identify commands within a scenario.

Each accepted CONFIG and each header-valid DATA produces a two-word `RespHdr`:
word 0 is the opcode, word 1 is the echoed tx_id. TLAST is 0 then 1. DATA emits
this complete header before any payload read. A successful DATA's subsequent
result burst contains nsamp words; END has no response. No footer is defined.

Examples obtained from actual Waveflow serialization, not hand packing, are saved
in [serialized_layout.json](evidence/serialized_layout.json) and
[response_layout.json](evidence/response_layout.json). CONFIG(2,1), tx=0x12345678,
serializes as `53434f46 12345678 00000001 00000000 40000000 3f800000`.

## Validation and status

Validation is format, opcode, applicable parameters, configuration availability,
then payload TLAST. For unknown opcodes no command-specific parameter meaning is
assigned. For CONFIG/END, configuration availability is not checked. Status is
cleared at every activation: halted=0, error=0, tx_id=0. On error halted=1.

| Error register | Name | Meaning |
| --- | --- | --- |
| 0 | NONE | Normal activation/completion |
| 1 | BAD_HEADER | Wrong magic, early header TLAST, or missing header TLAST on word 5 |
| 2 | BAD_COMMAND | Unknown opcode after a valid header |
| 3 | BAD_PARAM | DATA nsamp=0, or CONFIG/END nsamp nonzero |
| 4 | NOT_CONFIGURED | Positive-length DATA before CONFIG |
| 5 | EARLY_TLAST | Payload TLAST on sample k<nsamp |
| 6 | MISSING_TLAST | Received payload sample nsamp without TLAST |

The status tx_id is determinable once header word 1 has been received; otherwise
the fixed fallback is `0xffffffff`. A valid transaction can also use that value;
this sentinel is not a uniqueness reservation. Bad magic on word 0 therefore
uses the fallback even if later words are queued. No extra read is permitted to
obtain an ID. A header rejected by any applicable check produces no response.

AXI-Lite contains only ap_start/ap_done and the status outputs (halted:1 bit,
error:8 bits, tx_id:32 bits). The generated top is
[gen/scale_offset.cpp](gen/scale_offset.cpp). Coefficients are local activation
state and never AXI-Lite ports. Physical register offsets are not presented as
hardware-verified addresses; this classroom deliverable stops before synthesis.

## Error output and waiting

The C++ body keeps one result pending. After checking the next input sample, it
can either release the previous result normally or flush it with TLAST on error.
The error-triggering sample is never evaluated/emitted. A payload error at sample
k yields exactly k-1 results following the complete response header. If k=1,
there is no result burst and no fake closing word. Buffered valid results are
always included, and already-emitted results are not duplicated. The host
discards the failed command's complete batch and resets the stream path.

Reads block without timeout. Header/payload starvation without an observable
framing violation is outside error detection. The offline Python model raises
`WouldBlock` if a finite fixture lacks necessary input; this is a test-harness
condition, not a hardware error/status response. No such fixture is a required
terminating C simulation case. Fresh streams and poisoned status are used for
each activation, including the immediate recovery after every error case.

## Files and arithmetic

Python uses separate NumPy float32 multiply and add. The independent oracle uses
exact rational/integer arithmetic, with explicit ties-to-even rounding and
signed-zero rules. C++ uses two volatile float intermediates, FE_TONEAREST in the
testbench, `-ffp-contract=off`, and `-fno-fast-math`. No performance optimization
is attempted. Tests include literals that distinguish FMA and both tie directions.
Normal inputs whose rounded product is signed zero or the smallest normal remain
supported; dedicated vectors cover these lower-boundary cases. A rounded nonzero
subnormal intermediate or result remains outside scope.

Fixtures use Waveflow burst bundles: `words.bin` stores each 32-bit wire word in
a little-endian uint64 slot (upper 32 bits zero); `bounds.bin` contains cumulative
uint64 burst end indices; `tlast.bin` contains one byte per stored burst. Actual
TLAST flags, not artificial fixture boundaries, govern kernel framing. JSON
evidence represents each received/emitted word as `[uint32_value, tlast_0_or_1]`.
An empty protocol burst is omitted entirely: the Waveflow empty-array serializer
returns a zero placeholder, so callers must not serialize empty DATA/result arrays.

Per scenario, `intent.json` records intended commands and expected error sites;
`expected.json` and `model.json` contain results, status, consumed count, and unread
words. `csim/` contains captured binary words, status, operation trace, and
`observed.json`; `unread/` captures the old input stream after return solely as
evidence. Those stream objects are then destroyed and never reused for recovery.
