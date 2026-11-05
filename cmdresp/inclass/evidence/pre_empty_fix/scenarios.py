"""Scenario intent and independent expected results, never a protocol parser."""
from dataclasses import dataclass, field
import numpy as np
from oracle import evaluate_bits
from scale_offset import (Command as C, Error as E, UNKNOWN_ID, MAGIC, header,
                          frame, sample_words, response, bits, from_bits)


@dataclass
class Case:
    name: str
    covers: list[str]
    words: list = field(default_factory=list)
    out: list = field(default_factory=list)
    status: dict = field(default_factory=lambda: {"halted": 0, "error": 0, "tx_id": 0})
    consumed: int = 0
    coeff: tuple = (0.0, 0.0)
    actions: list = field(default_factory=list)

    def config(self, tx, a=2.0, b=1.0):
        self.words += frame(header(C.CONFIG, tx, a=a, b=b).serialize(word_bw=32))
        self.out += response(C.CONFIG, tx)
        self.coeff = (a, b)
        self.consumed = len(self.words)
        self.actions.append({"kind": "CONFIG", "tx_id": tx, "a_bits": bits(a), "b_bits": bits(b)})
        return self

    def data(self, tx, samples, declared=None, last=True, error=E.NONE, accepted=None):
        xs = np.asarray(samples, dtype=np.float32)
        n = len(xs) if declared is None else declared
        self.words += frame(header(C.DATA, tx, nsamp=n).serialize(word_bw=32))
        header_end = len(self.words)
        self.words += frame(sample_words(xs), last)
        header_error = error in (E.BAD_PARAM, E.NOT_CONFIGURED)
        keep = (0 if header_error else len(xs)) if accepted is None else accepted
        if not header_error:
            self.out += response(C.DATA, tx)
            a, b = map(bits, self.coeff)
            ys = [from_bits(evaluate_bits(a, b, bits(x))[1]) for x in xs[:keep]]
            self.out += frame(sample_words(ys))
        self.consumed = header_end if header_error else len(self.words)
        if error:
            self.status = {"halted": 1, "error": int(error), "tx_id": tx}
        self.actions.append({"kind": "DATA", "tx_id": tx, "declared": n,
                             "samples_bits": [bits(x) for x in xs], "last": last,
                             "expected_error": int(error), "accepted": keep,
                             "header_end": header_end})
        return self

    def end(self, tx=900):
        self.words += frame(header(C.END, tx).serialize(word_bw=32))
        self.consumed = len(self.words)
        self.actions.append({"kind": "END", "tx_id": tx})
        return self

    def rejected(self, h, error, read_count=6, tx=None, early=None, missing=False):
        raw = frame(h.serialize(word_bw=32))
        if early is not None:
            raw = raw[:early]
            raw[-1][1] = 1
        if missing:
            raw[-1][1] = 0
        before = len(self.words)
        self.words += raw
        self.consumed = before + read_count
        self.status = {"halted": 1, "error": int(error),
                       "tx_id": int(h.tx_id) if tx is None else tx}
        self.actions.append({"kind": "REJECT", "opcode": int(h.opcode),
                             "tx_id": int(h.tx_id), "expected_error": int(error),
                             "read_count": read_count, "early": early, "missing": missing})
        return self

    def tail(self):
        # Deliberately queued commands; expected state is unchanged.
        self.words += frame(header(C.CONFIG, 0xAABBCCDD, a=7, b=8).serialize(word_bw=32))
        self.words += frame(header(C.DATA, 0x11223344, nsamp=2).serialize(word_bw=32))
        self.words += frame(sample_words([9, 10]))
        self.words += frame(header(C.END, 0x76543210).serialize(word_bw=32))
        return self

    def expected(self):
        return {"words": self.out, "status": self.status, "consumed": self.consumed,
                "unread": self.words[self.consumed:]}


def scenarios():
    normal = [
        Case("T01_T02_reconfigure", ["T01", "T02"]).config(101).data(102, [1, 2, 3])
            .config(103, 3, -1).data(104, [1, 2]).end(),
        Case("T03_reuse", ["T03"]).config(201).data(202, [1]).data(203, [2, 3])
            .data(204, [-1, 0]).end(),
        Case("T04_prior_success", ["T04"]).config(301, 13, 17).data(302, [1]).end(),
    ]
    errors = [
        Case("T04_no_carry", ["T04"]).data(303, [1], error=E.NOT_CONFIGURED).tail(),
        Case("E01_no_config", ["E01"]).data(401, [1, 2], error=E.NOT_CONFIGURED).tail(),
        Case("E02_zero", ["E02"]).config(410).data(411, [], error=E.BAD_PARAM).tail(),
        Case("E03_early", ["E03"]).config(420).data(421, [1, 2, 3], declared=5,
                                                   error=E.EARLY_TLAST, accepted=2).tail(),
        Case("E03_long_prefix", ["E03"]).config(425).data(426, list(range(1, 17)), declared=32,
                                                   error=E.EARLY_TLAST, accepted=15).tail(),
        Case("E04_missing", ["E04"]).config(430).data(431, [1, 2, 3], last=False,
                                                   error=E.MISSING_TLAST, accepted=2).tail(),
        Case("E05_opcode", ["E05"]).rejected(header(0xF0, 440), E.BAD_COMMAND).tail(),
        Case("E06_magic_unknown_id", ["E06"]).rejected(header(C.DATA, 451, 1, magic=0),
                                    E.BAD_HEADER, read_count=1, tx=UNKNOWN_ID).tail(),
        Case("E06_early_unknown_id", ["E06"]).rejected(header(C.DATA, 452, 1),
                                    E.BAD_HEADER, read_count=1, tx=UNKNOWN_ID, early=1).tail(),
        Case("E06_early_known_id", ["E06"]).rejected(header(C.DATA, 453, 1),
                                    E.BAD_HEADER, read_count=2, early=2).tail(),
        Case("E06_missing", ["E06"]).rejected(header(C.DATA, 454, 1),
                                    E.BAD_HEADER, missing=True).tail(),
        Case("E07_config_param", ["E07"]).config(460).rejected(
                                    header(C.CONFIG, 461, nsamp=1, a=3, b=-1), E.BAD_PARAM).tail(),
        Case("E08_header_before_opcode", ["E08"]).rejected(header(0xF0, 470, nsamp=1),
                                    E.BAD_HEADER, missing=True).tail(),
        Case("E08_opcode_before_param", ["E08"]).rejected(header(0xF0, 471, nsamp=0),
                                    E.BAD_COMMAND).tail(),
        Case("E08_param_before_config", ["E08"]).data(472, [], error=E.BAD_PARAM).tail(),
        Case("E08_param_before_payload", ["E08"]).config(473).data(474, [1], declared=0,
                                    last=False, error=E.BAD_PARAM).tail(),
        Case("E08_config_before_payload", ["E08"]).data(475, [1], declared=1,
                                    last=False, error=E.NOT_CONFIGURED).tail(),
        Case("E09_first_early", ["E09"]).config(480).data(481, [1], declared=3,
                                    error=E.EARLY_TLAST, accepted=0).tail(),
        Case("E09_first_missing", ["E09"]).config(482).data(483, [1], last=False,
                                    error=E.MISSING_TLAST, accepted=0).tail(),
        Case("E10_one_early", ["E10"]).config(490).data(491, [1, 2], declared=3,
                                    error=E.EARLY_TLAST, accepted=1).tail(),
        Case("E10_one_missing", ["E10"]).config(492).data(493, [1, 2], last=False,
                                    error=E.MISSING_TLAST, accepted=1).tail(),
        Case("E_extra_end_param", ["E08"]).rejected(header(C.END, 499, nsamp=1), E.BAD_PARAM).tail(),
    ]
    # Add prior successful DATA to an error scenario: earlier results must survive.
    errors.append(Case("E_prior_success", ["E03"]).config(510).data(511, [1, 2, 3])
                  .data(512, [4, 5], declared=4, error=E.EARLY_TLAST, accepted=1).tail())
    t = Case("T05_rounding", ["T05"])
    t.config(601, from_bits(0x3F800001), -1).data(602, [from_bits(0x3F7FFFFE)])
    t.config(603, 1, from_bits(0x33800000)).data(604, [1, from_bits(0x3F800001)])
    t.config(605, 1.5, 0).data(606, [from_bits(0x3F800001)]).end()
    normal += [t, Case("T06_end_tail", ["T06"]).config(610).end().tail(),
               Case("T07_empty", ["T07"]).end().tail()]
    t = Case("T08_zero_boundaries", ["T08"])
    t.config(620, from_bits(0x80000000), from_bits(0x80000000)).data(621, [1])
    t.config(622, 1, 0).data(623, [from_bits(0x80000000), from_bits(0x00800000),
                                 from_bits(0x80800000), from_bits(0x7F7FFFFF), from_bits(0xFF7FFFFF)])
    normal.append(t.end())
    rng = np.random.default_rng(20261104)
    t = Case("T_random", ["T05"])
    for i in range(5):
        t.config(700+2*i, np.float32(rng.uniform(-4, 4)), np.float32(rng.uniform(-4, 4)))
        t.data(701+2*i, rng.uniform(-16, 16, 256).astype(np.float32))
    normal.append(t.end())
    # T04's error must immediately follow its successful previous activation.
    result = normal[:3]
    for err in errors:
        result.append(err)
        result.append(Case("R_" + err.name, ["RECOVERY", *err.covers]).config(0x12340001)
                      .data(0x12340002, [1, 2, 3]).end())
    result += normal[3:]
    return result
