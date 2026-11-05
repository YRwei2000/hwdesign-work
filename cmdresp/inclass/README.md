# Scale-and-offset classroom implementation

The authoritative behavior is [prompt.md](prompt.md). The user explicitly authorized
implementation after its specification-only phase. The specification is unchanged.
See [layout.md](layout.md) for the wire contract and [results.md](results.md) for
measured results, known limitations, and per-scenario evidence.

## Files

- `scale_offset.py`: Waveflow schemas, binary32 function, pure protocol model,
  and body-only HostActivated interface declaration.
- `oracle.py`: independent integer/rational RNE binary32 arithmetic reference.
- `scenarios.py`: scenario intent, stimulus and expected response/status/read count.
- `verify.py`: independent model gate, checker rejection tests, exact C comparison.
- `scale_offset_body_impl.tpp`: hand-written kernel body with one-result holdback.
- `scale_offset_tb.cpp`, `trace.hpp`: fresh-stream C++ testbench and C-only observations.
- `generate.py`: Waveflow code generation; `gen/` and `include/` are generated.
- `run.tcl`: C simulation only, with no synthesis/RTL stage.
- `data/`, `evidence/`: retained fixtures, captured results, checks and logs.

## Check retained results without rebuilding

From `/home/yw9286/hwdesign-work/cmdresp/inclass/`:

```bash
/home/yw9286/waveflow-venv/bin/python verify.py csim
/home/yw9286/waveflow-venv/bin/python report.py
```

This checks existing outputs and generates the report. It does not run C simulation.
The checker rejects a changed model-source hash until its model gate is validated.

## Full reproduction when needed

```bash
/home/yw9286/waveflow-venv/bin/python verify.py model
/home/yw9286/waveflow-venv/bin/python generate.py
/eda/xilinx/2026.1/Vitis/bin/vitis-run --mode hls --tcl run.tcl
/home/yw9286/waveflow-venv/bin/python verify.py csim
/home/yw9286/waveflow-venv/bin/python report.py
```

Run each command only if the preceding command succeeds. Save command output when
creating new evidence; do not replace a previous successful run's logs with a failed
attempt. Use the existing school license environment, in a context permitted to
access its license service. Do not put license values or credentials into project
files. No package installation or environment upgrade is needed.

The measured run used Python 3.12.14, Vitis/HLS 2026.1, and Vitis clang-16. The Tcl
sets the stream_inband reference target `xc7z020clg484-1` and a 10 ns clock only as
build configuration. These are not measured performance results. `run.tcl` creates
the one-level `csim_proj` project and runs `csim_design`; it defines no synthesis
or co-simulation target. `generate.py` sets `vitis_version="2026.1"`, avoiding legacy
support-file compatibility assumptions. Generated files must not be hand-edited.

`recheck.tcl` documents the limited resume used during this session: it opens the
existing project and runs only the two changed fixtures and their immediately
following recoveries in `data/recheck/scenarios.txt` (four activations total).
The linked case directories receive their new outputs. Do not use it as a substitute
for the full verification suite after changing the kernel. The final checker always
compares every case in the complete suite.

`boundary_recheck.tcl` similarly records the single additional numeric-boundary
activation. It reuses the compiled kernel and leaves the original 54 cases intact.

The initial model/fixture empty-array bug and its correction are documented in
`results.md` and archived under `evidence/pre_empty_fix/`. Those archived outputs are
historical failures, not the accepted golden results. Arithmetic evidence was
retained after proving the arithmetic function and oracle unchanged. A later oracle
boundary correction required full arithmetic revalidation; the previous results
are archived in `evidence/pre_boundary_oracle_fix/`. The historical
`verify.py model --reuse-arithmetic` mode is guarded and now refuses to reuse the
earlier oracle's evidence because that oracle hash has changed. Use `verify.py model`
for current full model validation.

The scaffold smoke test in `evidence/scaffold_py_sim.log` is reference-only. This
accelerator provides a pure protocol model; its HostActivated timed pysim body
deliberately raises an error instead of pretending to provide a calibrated model.
