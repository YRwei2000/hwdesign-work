"""Waveflow schemas, untimed binary32 pooling and activation model."""
from dataclasses import dataclass
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
MAGIC, UNKNOWN_ID, HEADER_WORDS = 0x504F4F4C, 0xFFFFFFFF, 6

class Command(IntEnum):
    COMPUTE = 1
    END = 2

class Error(IntEnum):
    NONE = 0
    HEADER = 1
    COMMAND = 2
    H_RANGE = 3
    W_RANGE = 4
    K_RANGE = 5
    WINDOW = 6
    DIVISIBILITY = 7
    EARLY_TLAST = 8
    MISSING_TLAST = 9

class PoolCmd(DataList):
    elements = {key: {"schema": U32} for key in ("magic", "tx_id", "opcode", "h", "w", "k")}

class PoolResp(DataList):
    elements = {key: {"schema": U32} for key in ("tx_id", "out_h", "out_w")}

def header(tx, h=0, w=0, k=0, op=Command.COMPUTE, magic=MAGIC):
    obj = PoolCmd()
    obj.magic, obj.tx_id, obj.opcode = magic, tx, int(op)
    obj.h, obj.w, obj.k = h, w, k
    return obj

def frame(words, last=True):
    return [[int(x), int(last and i == len(words)-1)] for i, x in enumerate(words)]

def encode_samples(values):
    arr = np.asarray(values, dtype=np.float32).ravel()
    if not arr.size:
        return []  # Empty Waveflow arrays serialize a placeholder: never call that here.
    return write_array(arr, elem_type=Float32, word_bw=32)

def encode_response(tx, h, w):
    obj = PoolResp()
    obj.tx_id, obj.out_h, obj.out_w = tx, h, w
    return frame(obj.serialize(word_bw=32))

def evaluate(matrix, k):
    """Scalar, row-major strict-greater selection; assignments preserve raw bits."""
    a = np.asarray(matrix, dtype=np.float32)
    h, w = a.shape
    out = np.empty((h//k, w//k), dtype=np.float32)
    for r in range(h//k):
        for c in range(w//k):
            best = a[r*k, c*k]
            for dr in range(k):
                for dc in range(k):
                    candidate = a[r*k+dr, c*k+dc]
                    if candidate > best:
                        best = candidate
            out[r,c] = best
    return out

class WouldBlock(Exception):
    """An incomplete offline fixture; not a hardware status or timeout."""

def stream_model(words):
    pos, out, events = 0, [], []
    def take():
        nonlocal pos
        if pos >= len(words):
            raise WouldBlock("hardware waits for input without timeout")
        value = words[pos]
        pos += 1
        return value
    def finish(code=0, tx=0):
        return dict(words=out, status=dict(halted=int(bool(code)), error=int(code), tx_id=tx),
                    consumed=pos, unread=words[pos:], events=events)
    while True:
        raw, tx = [0]*HEADER_WORDS, UNKNOWN_ID
        for j in range(HEADER_WORDS):
            raw[j], last = take()
            cmd = PoolCmd().deserialize(raw, word_bw=32)
            if j >= 1:
                tx = int(cmd.tx_id)
            if (j == 0 and cmd.magic != MAGIC) or bool(last) != (j == HEADER_WORDS-1):
                return finish(Error.HEADER, tx)
        if cmd.opcode not in tuple(Command):
            return finish(Error.COMMAND, tx)
        if cmd.opcode == Command.END:
            return finish()
        h, w, k = int(cmd.h), int(cmd.w), int(cmd.k)
        if not 1 <= h <= 64:
            return finish(Error.H_RANGE, tx)
        if not 1 <= w <= 64:
            return finish(Error.W_RANGE, tx)
        if not 1 <= k <= 8:
            return finish(Error.K_RANGE, tx)
        if k > h or k > w:
            return finish(Error.WINDOW, tx)
        if h % k or w % k:
            return finish(Error.DIVISIBILITY, tx)
        out.extend(encode_response(tx, h//k, w//k))
        events.append(dict(kind="RESP_DONE", tx=tx, consumed=pos, output=len(out)))
        samples = []
        for i in range(h*w):
            value, last = take()
            events.append(dict(kind="PREAD", tx=tx, consumed=pos, output=len(out)))
            if bool(last) != (i == h*w-1):
                return finish(Error.EARLY_TLAST if last else Error.MISSING_TLAST, tx)
            samples.append(value)
        a = read_array(samples, elem_type=Float32, word_bw=32, shape=(h,w)).val
        out.extend(frame(encode_samples(evaluate(a, k))))

@dataclass
class PoolAccel(HostActivated):
    cpp_kernel_name: ClassVar[str] = "max_pool"
    cpp_namespace: ClassVar[str] = "pool_impl"
    cpp_body: ClassVar[str] = "body"
    in_bw: HwParam[int] = 32
    out_bw: HwParam[int] = 32
    def __post_init__(self):
        super().__post_init__()
        self.s_in = StreamIFSlave(name=f"{self.name}_in", sim=self.sim, bitwidth=self.in_bw)
        self.m_out = StreamIFMaster(name=f"{self.name}_out", sim=self.sim, bitwidth=self.out_bw)
        self.regmap = VitisRegMap({"halted": RegField(Bit, RegAccess.R),
                                  "error": RegField(U8, RegAccess.R),
                                  "tx_id": RegField(U32, RegAccess.R)}, bitwidth=32)
        self.s_lite = VitisRegMapMMIFSlave(name=f"{self.name}_lite", sim=self.sim,
                                          bitwidth=32, regmap=self.regmap, on_start=self.on_start)
        for endpoint in (self.s_in, self.m_out, self.s_lite):
            self.add_endpoint(endpoint)
    def body(self):
        raise NotImplementedError("Use untimed stream_model; no Python timing model is defined")
        yield
