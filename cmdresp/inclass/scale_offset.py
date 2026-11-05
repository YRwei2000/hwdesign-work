"""Waveflow wire schemas, binary32 arithmetic, and a pure activation model.

Schema serialization is the only wire encoder. Unknown opcodes deliberately use
an integer field so malformed input remains representable without manual packing.
"""
from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar

import numpy as np
from waveflow.hw.arrayutils import read_array, write_array
from waveflow.hw.dataschema import DataList, FloatField, IntField
from waveflow.hw.hw_hostactivated import HostActivated
from waveflow.hw.hw_module import HwParam
from waveflow.hw.interface import StreamIFMaster, StreamIFSlave
from waveflow.hw.regmap import Bit, RegAccess, RegField, VitisRegMap, VitisRegMapMMIFSlave

U32 = IntField.specialize(bitwidth=32, signed=False)
U8 = IntField.specialize(bitwidth=8, signed=False)
Float32 = FloatField.specialize(bitwidth=32, include_dir="include")
MAGIC = 0x53434F46
UNKNOWN_ID = 0xFFFFFFFF
HEADER_WORDS = 6


class Command(IntEnum):
    CONFIG = 1
    DATA = 2
    END = 3


class Error(IntEnum):
    NONE = 0
    BAD_HEADER = 1
    BAD_COMMAND = 2
    BAD_PARAM = 3
    NOT_CONFIGURED = 4
    EARLY_TLAST = 5
    MISSING_TLAST = 6


class CmdHdr(DataList):
    elements = {
        "magic": {"schema": U32},
        "tx_id": {"schema": U32},
        "opcode": {"schema": U32},
        "nsamp": {"schema": U32},
        "a": {"schema": Float32},
        "b": {"schema": Float32},
    }


class RespHdr(DataList):
    elements = {"opcode": {"schema": U32}, "tx_id": {"schema": U32}}


def header(opcode, tx_id, nsamp=0, a=0.0, b=0.0, magic=MAGIC):
    h = CmdHdr()
    h.magic, h.tx_id, h.opcode, h.nsamp = magic, tx_id, int(opcode), nsamp
    h.a, h.b = np.float32(a), np.float32(b)
    return h


def frame(words, last=True):
    return [[int(w), int(last and i == len(words)-1)] for i, w in enumerate(words)]


def sample_words(values):
    return write_array(np.asarray(values, dtype=np.float32), elem_type=Float32, word_bw=32)


def response(opcode, tx_id):
    h = RespHdr()
    h.opcode, h.tx_id = int(opcode), tx_id
    return frame(h.serialize(word_bw=32))


def bits(value):
    return int(np.asarray(value, dtype=np.float32).view(np.uint32))


def from_bits(value):
    return np.asarray(value, dtype=np.uint32).view(np.float32)[()]


def evaluate(a, b, x):
    """Two separate numpy binary32 operations, never a fused expression."""
    product = np.multiply(np.float32(a), np.float32(x), dtype=np.float32)
    result = np.add(product, np.float32(b), dtype=np.float32)
    return product, result


class WouldBlock(Exception):
    """Offline model cannot finish; this is not a hardware error code."""


def stream_model(words):
    out, pos = [], 0
    configured, a, b = False, np.float32(0), np.float32(0)
    status = {"halted": 0, "error": 0, "tx_id": 0}

    def finish(err=Error.NONE, tx=0):
        if err:
            status.update(halted=1, error=int(err), tx_id=int(tx))
        return {"words": out, "status": status, "consumed": pos,
                "unread": words[pos:]}

    def take():
        nonlocal pos
        if pos == len(words):
            raise WouldBlock("Input not available; hardware waits without timeout")
        w = words[pos]
        pos += 1
        return w

    while True:
        raw = [0] * HEADER_WORDS
        tx = UNKNOWN_ID
        for j in range(HEADER_WORDS):
            raw[j], last = take()
            h = CmdHdr().deserialize(raw, word_bw=32)
            if j >= 1:
                tx = int(h.tx_id)
            if (j == 0 and h.magic != MAGIC) or bool(last) != (j == HEADER_WORDS-1):
                return finish(Error.BAD_HEADER, tx)
        op, n = int(h.opcode), int(h.nsamp)
        if op not in tuple(Command):
            return finish(Error.BAD_COMMAND, tx)
        if (op == Command.DATA and n == 0) or (op != Command.DATA and n != 0):
            return finish(Error.BAD_PARAM, tx)
        if op == Command.END:
            return finish()
        if op == Command.CONFIG:
            a, b, configured = np.float32(h.a), np.float32(h.b), True
            out.extend(response(op, tx))
            continue
        if not configured:
            return finish(Error.NOT_CONFIGURED, tx)
        out.extend(response(op, tx))
        # Batch prefix in the pure model; C++ uses one-result holdback instead.
        accepted = []
        for j in range(n):
            raw_sample, last = take()
            final = j == n-1
            if bool(last) != final:
                # No zero-length burst: the framework serializes an empty
                # array to a placeholder word, which this protocol forbids.
                if accepted:
                    out.extend(frame(sample_words(accepted)))
                return finish(Error.EARLY_TLAST if last else Error.MISSING_TLAST, tx)
            x = read_array([raw_sample], elem_type=Float32, word_bw=32, shape=1).val[0]
            accepted.append(evaluate(a, b, x)[1])
        out.extend(frame(sample_words(accepted)))


@dataclass
class ScaleOffset(HostActivated):
    cpp_kernel_name: ClassVar[str] = "scale_offset"
    cpp_namespace: ClassVar[str] = "scale_offset_impl"
    cpp_body: ClassVar[str] = "body"
    in_bw: HwParam[int] = 32
    out_bw: HwParam[int] = 32

    def __post_init__(self):
        super().__post_init__()
        self.s_in = StreamIFSlave(name=f"{self.name}_in", sim=self.sim, bitwidth=self.in_bw)
        self.m_out = StreamIFMaster(name=f"{self.name}_out", sim=self.sim, bitwidth=self.out_bw)
        self.regmap = VitisRegMap({
            "halted": RegField(Bit, RegAccess.R),
            "error": RegField(U8, RegAccess.R),
            "tx_id": RegField(U32, RegAccess.R),
        }, bitwidth=32)
        self.s_lite = VitisRegMapMMIFSlave(name=f"{self.name}_lite", sim=self.sim,
                                          bitwidth=32, regmap=self.regmap, on_start=self.on_start)
        for endpoint in (self.s_in, self.m_out, self.s_lite):
            self.add_endpoint(endpoint)

    def body(self):
        # This project validates the pure model and Vitis C simulation. No timing
        # model is claimed; avoid a misleading runnable empty pysim body.
        raise NotImplementedError("Use stream_model; timed pysim is outside this classroom build")
        yield
