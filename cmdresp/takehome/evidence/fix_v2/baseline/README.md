# Float32 2-D max pooling, prompt v2

Implementation and measured results are in [results.md](results.md). The
confirmed [prompt](prompt.md) is unchanged. [layout.md](layout.md) is the host
contract, including protocol choices delegated to the implementation agent.

Use `/home/yw9286/waveflow-venv/bin/python` and existing Vitis 2026.1. No package
upgrade is needed. School license access is required by Vitis/Vivado; the
restricted execution sandbox may block it. Keep existing license configuration
and use the normal execution approval mechanism if the recorded license error
recurs. Never print license values or credentials.

For an authorized fresh implementation run, run these stages in order from
this folder (capture stdout/stderr to separate retained logs):

```bash
/home/yw9286/waveflow-venv/bin/python build.py model
/home/yw9286/waveflow-venv/bin/python build.py generate
/home/yw9286/waveflow-venv/bin/python build.py csim
/home/yw9286/waveflow-venv/bin/python build.py synth
/home/yw9286/waveflow-venv/bin/python build.py cosim
```

The first model gate uses hand literals plus the independent NumPy oracle,
checks activation/framing intent, exports fixtures and freezes model sources.
`generate.py` uses Waveflow BuildDag/DataSchemaStep/HlsCodegenStep with
`BuildConfig(vitis_version="2026.1")`. Never edit `gen/` or `include/`.
The Tcl stages select exactly one operation. Co-simulation invokes every line
of `data/scenarios.txt` without filtering, including every error immediately
followed by its distinct recovery. `build.py` refuses an implicit repeated
co-simulation once its comparison exists. Preserve prior evidence across any
separately authorized revision.

To inspect retained evidence without running Vitis or any simulation:

```bash
/home/yw9286/waveflow-venv/bin/python build.py evidence
```

This only repeats file comparisons, trace/source review and report generation;
it does not rerun the Python arithmetic gate or any hardware stage. Raw RTL
vectors, the original WDB, timing report and generated simulation trace setup
are retained under `evidence/cosim_raw/`. Synthesis reports are retained under
`evidence/synthesis/`. Per-scenario input, intent, expected output, model and
each C/RTL stage's output/status/unread snapshots remain in `data/`.

The first co-simulation was followed by exactly one user-authorized same-snapshot
replay for VCD extraction with Waveflow's official helper. [The authorization,
snapshot and vector checks](evidence/replay_authorization.json) distinguish these
executions; no further replay is permitted. `capture_vcd.py` has an attempt guard.
`finalize_replay.py` records the offline correction of a snapshot comparison that
initially included the mutable simulator log. Kernel/RTL/snapshot code was unchanged.

`analyze.py` only analyzes the retained VCD; it never predicts timing or launches
a simulator. It can read `evidence/ports.vcd.gz` directly. The failed offline WDB
reader investigation is retained with logs and MIT source and is not an accepted
timing oracle. The accepted waveform comes from XSIM itself. There is no Python
timing model or performance-optimization loop. The measured external AXI ordering
failure and input-harness limitation are explicit Open Items in results.md.

Vitis projects, binaries and uncited work logs are ignored; all cited evidence
is retained separately. No commit or push is part of this implementation run.
