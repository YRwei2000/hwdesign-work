"""Scenario intent and expected behavior, independent of the protocol parser."""
from dataclasses import dataclass, field
import numpy as np
from oracle import reference
from pool import Command as C, Error as E, UNKNOWN_ID, header, frame, encode_samples, encode_response

@dataclass
class Case:
    name: str
    purpose: str
    words: list = field(default_factory=list)
    out: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    consumed: int = 0
    status: dict = field(default_factory=lambda: dict(halted=0, error=0, tx_id=0))
    def compute(self, tx, matrix, k, error=0, received=None, last=True):
        a = np.asarray(matrix, np.float32)
        h,w = a.shape
        start, out_start = len(self.words), len(self.out)
        self.words += frame(header(tx,h,w,k).serialize(word_bw=32))
        values = a.ravel() if received is None else a.ravel()[:received]
        self.words += frame(encode_samples(values), last)
        self.out += encode_response(tx,h//k,w//k)
        if not error:
            self.out += frame(encode_samples(reference(a,k)))
        else:
            self.status = dict(halted=1, error=int(error), tx_id=tx)
        self.consumed = len(self.words)
        self.actions.append(dict(kind="COMPUTE",tx_id=tx,h=h,w=w,k=k,
                                 input_start=start,header_end=start+6,received=len(values),
                                 output_start=out_start,error=int(error),
                                 result_count=0 if error else (h//k)*(w//k)))
        return self
    def reject(self, tx, h=4,w=4,k=2,op=C.COMPUTE,error=E.HEADER,
               magic=None, early=None, missing=False, count=6, unknown=False):
        args = {} if magic is None else dict(magic=magic)
        raw = frame(header(tx,h,w,k,op=op,**args).serialize(word_bw=32))
        if early is not None:
            raw = raw[:early]
            raw[-1][1] = 1
        if missing:
            raw[-1][1] = 0
        start = len(self.words)
        self.words += raw
        self.consumed = start+count
        self.status = dict(halted=1,error=int(error),tx_id=UNKNOWN_ID if unknown else tx)
        self.actions.append(dict(kind="REJECT", tx_id=tx,h=h,w=w,k=k,opcode=int(op),
                                 error=int(error),input_start=start,read_count=count))
        # Queued malformed payload: must not be consumed on any header rejection.
        self.words += frame(encode_samples([7,8]),last=False)
        return self
    def end(self,tx=0x12345678,tail=False):
        start = len(self.words)
        # END parameters are ignored by the delegated protocol, exercise nonzero values.
        self.words += frame(header(tx,65,0,0,op=C.END).serialize(word_bw=32))
        self.consumed = len(self.words)
        self.actions.append(dict(kind="END",tx_id=tx,input_start=start))
        if tail:
            self.tail()
        return self
    def tail(self):
        self.words += frame(header(0xAABBCCDD,1,1,1).serialize(word_bw=32))
        self.words += frame(encode_samples([-17]))
        self.words += frame(header(0xDEADBEEF,op=C.END).serialize(word_bw=32))
        return self
    def expected(self):
        return dict(words=self.out,status=self.status,consumed=self.consumed,
                    unread=self.words[self.consumed:])

def scenarios():
    rng = np.random.default_rng(20261104)
    a = np.arange(1,17,dtype=np.float32).reshape(4,4)
    zeros = np.array([0x80000000,0,0,0x80000000,0,0x80000000,0x80000000,0],np.uint32).view(np.float32).reshape(2,4)
    normal = [
        Case("T01_worked","Hand example 4x4 1..16 K2").compute(101,a,2).end(),
        Case("T02_negative_ties_zero","Negative maxima, equal values and both zero signs").compute(201,-a,2)
            .compute(202,np.full((4,4),-3,np.float32),2).compute(203,zeros,2)
            .compute(204,zeros[::-1].copy(),1).end(),
        Case("T03_parameter_changes","Rectangular matrices and changing all parameters").compute(301,a,2)
            .compute(302,np.arange(-12,12,dtype=np.float32).reshape(4,6),2)
            .compute(303,np.arange(64,dtype=np.float32).reshape(8,8),4)
            .compute(304,np.array([[-0.0]],np.float32),1).end(tail=True),
        Case("T04_bounds","Minimum/maximum H W, K1 and K8").compute(401,np.ones((1,64),np.float32),1)
            .compute(402,-np.ones((64,1),np.float32),1)
            .compute(403,rng.standard_normal((64,64)).astype(np.float32),1)
            .compute(404,rng.standard_normal((64,64)).astype(np.float32),8).end(),
        Case("T05_end_first","END before COMPUTE and trailing command unread").end(tail=True),
        Case("T06_normal_boundary","Normal binary32 extrema and zero bit identity").compute(601,
            np.array([0x00800000,0x80800000,0x7F7FFFFF,0xFF7FFFFF,0,0x80000000,0x3f800000,0xbf800000],np.uint32)
                .view(np.float32).reshape(2,4),1).end(),
        Case("T07_performance","64x64 K2 no extra pauses/backpressure").compute(701,
            rng.standard_normal((64,64)).astype(np.float32),2).end(),
    ]
    random_case = Case("T08_random","Deterministic independent random legal shapes")
    for i,(h,w,k) in enumerate([(3,6,3),(16,24,8),(12,18,6),(7,7,7),(10,20,5),(8,16,4),(1,1,1),(32,64,2)]):
        random_case.compute(801+i,rng.standard_normal((h,w)).astype(np.float32),k)
    normal.append(random_case.end())
    errors = []
    tx = 1000
    def reject(name,purpose,**kw):
        nonlocal tx
        tx += 7
        errors.append(Case(name,purpose).reject(tx,**kw).tail())
    reject("E01_magic","Bad identifier before tx_id",magic=0,count=1,unknown=True)
    for n in range(1,6):
        reject(f"E02_header_short_{n}",f"Early header TLAST on word {n}",early=n,count=n,unknown=n<2)
    reject("E03_header_missing","Final header word received without TLAST",missing=True)
    reject("E04_unknown_opcode","Unknown opcode with otherwise valid header",op=0xFE,error=E.COMMAND)
    params=[("h_zero",0,4,2,E.H_RANGE),("h_large",65,4,2,E.H_RANGE),
            ("w_zero",4,0,2,E.W_RANGE),("w_large",4,65,2,E.W_RANGE),
            ("k_zero",4,4,0,E.K_RANGE),("k_large",16,16,9,E.K_RANGE),
            ("window_h",1,4,2,E.WINDOW),("window_w",4,1,2,E.WINDOW),
            ("div_h",3,4,2,E.DIVISIBILITY),("div_w",4,3,2,E.DIVISIBILITY)]
    for name,h,w,k,e in params:
        reject("E05_"+name,"Isolated parameter violation "+name,h=h,w=w,k=k,error=e)
    reject("E06_format_before_opcode","Missing header TLAST + unknown opcode + invalid parameters",
            op=99,h=0,w=0,k=0,missing=True)
    reject("E06_opcode_before_parameters","Unknown opcode + invalid parameters",op=99,h=0,w=0,k=0,error=E.COMMAND)
    for name,h,w,k,e in [("h_before_w_k",0,0,0,E.H_RANGE),("w_before_k",4,0,0,E.W_RANGE),
                          ("k_before_window",1,1,9,E.K_RANGE),("window_before_div",3,1,2,E.WINDOW)]:
        reject("E06_"+name,"Parameter precedence "+name,h=h,w=w,k=k,error=e)
    for name,n,last,e,shape in [("first",1,True,E.EARLY_TLAST,(4,4)),
                               ("later",7,True,E.EARLY_TLAST,(4,4)),
                               ("missing",None,False,E.MISSING_TLAST,(4,4)),
                               ("one_missing",1,False,E.MISSING_TLAST,(1,1))]:
        tx += 7
        errors.append(Case("E07_payload_"+name,"All cached results discarded on payload error")
                      .compute(tx,np.arange(1,1+shape[0]*shape[1],dtype=np.float32).reshape(shape),
                               1 if shape==(1,1) else 2,error=e,received=n,last=last).tail())
    tx += 7
    errors.append(Case("E08_prior_success","Keep prior success, discard failed matrix results")
                  .compute(tx,a,2).compute(tx+1,a,2,error=E.EARLY_TLAST,received=9).tail())
    result = list(normal)
    for i,case in enumerate(errors):
        result += [case, Case("R_"+case.name,"Fresh-stream recovery after "+case.name)
                   .compute(5000+i*3,a,2).end()]
    return result
