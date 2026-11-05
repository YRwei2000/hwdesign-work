# Float32 2-D max pooling, prompt v2

Implementation and measured results are in [results.md](results.md). The
confirmed [prompt](prompt.md) is unchanged. [layout.md](layout.md) is the host
contract, including protocol choices delegated to the implementation agent.

Use `/home/yw9286/waveflow-venv/bin/python` and existing Vitis 2026.1. No package
upgrade is needed. School license access is required by Vitis/Vivado; the
restricted execution sandbox may block it. Keep existing license configuration
and use the normal execution approval mechanism if the recorded license error
recurs. Never print license values or credentials.

The corrected implementation uses `gen_off/`, `off_proj/` and
`evidence/fix_v2/`; the initial implementation and its failed interface evidence
remain separately retained. For a separately authorized fresh correction run
with its own retained evidence directory, the stages are:

```bash
/home/yw9286/waveflow-venv/bin/python build.py fix-synth
/home/yw9286/waveflow-venv/bin/python build.py fix-cosim
/home/yw9286/waveflow-venv/bin/python build.py fix-protocol
```

The completed run is guarded against implicit reruns. Capture each stage's
stdout/stderr to separate logs. `generate_fix.py` configures Waveflow's emitter
before generation to add only explicit register_mode=off on both ports; it does
not edit generated files or the installed package. The ordinary Tcl-only attempt
was ineffective and remains in `evidence/fix_v2/tcl_attempt/`.

`fix-synth` reruns C simulation and synthesizes the isolated project. `fix-cosim`
uses Vitis `cosim_design -setup`, then its generated precheck/RTL/postcheck
runtime with Waveflow's VCD capture configured BEFORE execution; all original
66 activations run. `fix-protocol` exports complete serialized fixtures and runs
the independent AXI host against the same synthesized RTL, covering all 66 plus
three backpressure/error/recovery activations. Each new simulation records VCD
directly, rather than requiring a later replay.

The independently validated arithmetic/model/intent sources are unchanged, so
their original gate is reused. A new boundary prompted a new C simulation.
The original model/scenario creation scripts remain available for an authorized
clean rebuild, but do not regenerate unchanged fixtures just to inspect evidence.
Never hand-edit `gen/`, `gen_off/` or `include/`.

To inspect retained evidence without running Vitis or any simulation:

```bash
/home/yw9286/waveflow-venv/bin/python build.py evidence
```

This audits hashes, retained verdicts and document links without invoking any
simulation, model gate or synthesis. Final evidence is under `evidence/fix_v2/`.
Original raw vectors/WDB remain under `evidence/cosim_raw/`, with original
synthesis reports under `evidence/synthesis/`. `results_initial.md` preserves
the historical report. Per-scenario inputs, intent, expected output, model and
each stage's output/status/unread snapshots remain in `data/`; corrected C and
standard RTL results use `csim_fix` and `cosim_fix` directories.

The first co-simulation was followed by exactly one user-authorized same-snapshot
replay for VCD extraction with Waveflow's official helper. [The authorization,
snapshot and vector checks](evidence/replay_authorization.json) distinguish these
executions. That replay was not repeated. `capture_vcd.py` has an attempt guard.
`finalize_replay.py` records the offline correction of a snapshot comparison that
initially included the mutable simulator log. Kernel/RTL/snapshot code was unchanged.

`analyze.py` and `analyze_protocol.py` analyze actual waveforms, never predict
timing. The former establishes performance from the corrected standard co-sim;
the latter uses activation identity, external AXI handshakes, AXI-Lite readbacks
and observed resets to check the independent full-input test. The original
failed offline WDB-reader investigation remains retained and is not an accepted
timing oracle. The accepted waveforms come from XSIM itself.

The first independent protocol trial exposed an observation-window off-by-one
in the harness. Its source/log/VCD are preserved under
`evidence/fix_v2/protocol_observation_trial/`. Only the harness wait was corrected
and that affected test rerun; neither DUT, synthesis nor standard co-simulation
was repeated for this correction. The strict checker was retained.

Vitis projects, binaries and uncited work logs are ignored; all cited evidence
is retained separately. No commit or push is part of this implementation run.
