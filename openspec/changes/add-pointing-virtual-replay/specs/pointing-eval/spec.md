# Spec Delta

## ADDED Requirements

### Requirement: Virtual replay of the production pointing pipeline
The harness SHALL provide a virtual replay mode for pointing cases in which
the production pointing pipeline runs end-to-end: an observation phase under
the production observation instruction (the one that requests a pointing
box), a model pick over the observation's candidates or abstention, and the
production's deterministic resolution, unmodified. In replay mode the case
verdict SHALL be the end-to-end outcome: pass if and only if the pipeline
resolves to the gold target; a resolution to a different candidate SHALL be a
fail; a pipeline clarification SHALL be reported as unjudged with its reason
and SHALL NOT be a pass. A replay case whose observation phase fails to parse
SHALL be reported as parse-failed without a pointing verdict. Standard
(non-replay) deployed mode SHALL be unchanged and SHALL keep the final-choice
semantics of this capability.

#### Scenario: Pipeline resolves to the correct target
- **WHEN** a replay case's observation parses, the model makes a pick, and the deterministic resolution is `resolved` with the gold target id
- **THEN** the case scores `pass: true` and the per-candidate resolution scores are persisted with the case artifacts

#### Scenario: Pipeline resolves to the wrong target
- **WHEN** the deterministic resolution is `resolved` with a candidate id different from the gold target
- **THEN** the case scores `pass: false` with a high-confidence-wrong marker

#### Scenario: Pipeline clarifies instead of resolving
- **WHEN** the deterministic resolution is a clarification (`no_candidate`, `ambiguous`, or `unusable_frames`)
- **THEN** the case is reported unjudged with the clarification reason, is not counted as a pass, and the reason is aggregated at run level

#### Scenario: Observation phase failed in replay
- **WHEN** a replay case's observation phase produced no parsed observation
- **THEN** no pick and no resolution run, and the case is reported as parse-failed, not as a pointing verdict

### Requirement: Per-case virtual geometry with provenance and review
Each replay pointing case SHALL carry frozen virtual geometry: candidate
anchor pixels, candidate positions derived from the production camera model,
and a gold target region for box scoring. The geometry SHALL be recorded in a
frozen sidecar with provenance (authoring method, camera parameters, image
hash, review status). A human-reviewable artifact showing the anchors and
gold regions on the case images SHALL be generated, and selection results
SHALL be marked pending review until a human confirms it. Source dataset
images SHALL NOT be modified by geometry authoring.

#### Scenario: Geometry frozen with provenance
- **WHEN** virtual geometry is authored for a pointing case
- **THEN** the sidecar records its anchors, inverted positions, gold region, camera parameters, image hash, authoring method, and review status

#### Scenario: Review artifact before selection use
- **WHEN** replay results are to be used for model/variant selection
- **THEN** the generated review artifact exists and the results are marked pending geometry review until a human confirms it

#### Scenario: Source data stays read-only
- **WHEN** virtual geometry is authored for cases from a licensed benchmark
- **THEN** the benchmark's images and files are unmodified and the geometry lives only in the eval sidecar

### Requirement: Replay decomposition metrics
A replay run SHALL report: end-to-end resolved accuracy (the primary
selection metric), pointing-box IoU against the gold target region (where a
box was produced), gesture detection rate, pick-agreement rate (model pick
equals the geometry leader), and clarification rate broken down by reason.
Final-choice accuracy, abstention, and freeform top-1 SHALL continue to be
reported as secondary metrics alongside them.

#### Scenario: Run report carries the decomposition
- **WHEN** a replay run completes
- **THEN** its score records resolved accuracy, mean box IoU (where boxes exist), detection rate, agreement rate, and clarification counts per reason, in addition to the secondary final-choice and perception columns

#### Scenario: Missing box is explicit
- **WHEN** a model's observation contains no pointing box
- **THEN** the case's box IoU is recorded as absent (not zero) and the case still goes through the deterministic resolution with neutral geometry

### Requirement: Model and variant selection under the replay metric
Model/variant selection for pointing SHALL be made on the primary resolved
accuracy over a selection set, and SHALL be confirmed on a held-out set that
was not used for selection, per the held-out manifest discipline of this
capability.

#### Scenario: Grid on the selection set
- **WHEN** a pointing model/variant selection campaign is run
- **THEN** every (model, variant) pair is evaluated on the selection set under the replay mode and ranked by resolved accuracy

#### Scenario: Confirmation on the held-out set
- **WHEN** top pairs are selected from the selection set
- **THEN** they are re-evaluated on the held-out set, whose image ids are disjoint from every previously frozen manifest, before a selection is declared
