# Spec Delta

## Purpose

Defines the evaluation contract for pointing (deixis) cases in the VLM eval
harness: how a final target choice is produced, scored, and reported — so a
"pass" always means the model picked the right exhibit, never merely that the
right exhibit was on its shortlist.

## ADDED Requirements

### Requirement: Decision phase for pointing cases
For every pointing case (gold type `target_box`) evaluated in deployed mode,
the harness SHALL run a decision phase after the observation phase, in which
the model must select exactly one candidate id from the candidates in its own
observation, or abstain. The decision output SHALL be persisted alongside the
case artifacts and recorded in the case metadata. The decision phase SHALL
also run for no-target pointing cases. The decision phase SHALL NOT run when
the observation phase did not produce a parsed observation.

#### Scenario: Model makes a final pick
- **WHEN** a pointing case's observation phase parses successfully and lists candidate ids
- **THEN** the decision phase asks the model to pick exactly one of those ids or abstain, and the decision is persisted with the case artifacts

#### Scenario: Decision phase on no-target cases
- **WHEN** a pointing case has no gold target (nobody is pointing)
- **THEN** the decision phase runs and the model must abstain to avoid a false positive

#### Scenario: Observation phase failed
- **WHEN** the observation phase produced no parsed observation
- **THEN** no decision phase runs and the case is reported as parse-failed, not as a pointing verdict

### Requirement: Final choice determines pass
For pointing cases, the case verdict (`pass`) SHALL be determined by the
model's final choice: pass if and only if the decided candidate id equals the
gold target id. Candidate recall SHALL NOT determine `pass`.

#### Scenario: Correct final pick
- **WHEN** the model's decision is the gold target id
- **THEN** the case scores `pass: true` with a recorded top-1 correctness of true

#### Scenario: Wrong final pick
- **WHEN** the model's decision is a candidate id different from the gold target
- **THEN** the case scores `pass: false` with a recorded top-1 correctness of false

#### Scenario: Recall alone never passes
- **WHEN** the gold target is among the observation's candidates but the model abstains or picks a different id
- **THEN** the case does not score `pass: true` on the basis of recall

### Requirement: Abstention is visible, not a pass
When a model abstains in the decision phase on a case that has a gold target,
the case SHALL be reported as unjudged with an abstention marker and SHALL
receive abstention credit in the run-level metrics. An abstention SHALL NOT
count as a pass.

#### Scenario: Model abstains on a target case
- **WHEN** the decision is "no target" on a case whose gold is a target id
- **THEN** the case is reported unjudged with an abstention marker, abstention credit is recorded at run level, and the case is not counted as a pass

### Requirement: No-target false positives
For no-target pointing cases, a decision that names a candidate id SHALL be
scored as a false positive (fail), and an abstention SHALL be scored as
correct with abstention credit.

#### Scenario: Model invents a target
- **WHEN** the decision names a candidate id on a no-target case
- **THEN** the case scores `pass: false` with a false-positive marker

#### Scenario: Model correctly refuses
- **WHEN** the decision abstains on a no-target case
- **THEN** the case scores correctly with abstention credit and no false positive

### Requirement: Legacy runs without a decision are unjudged
Pointing case results produced without a decision artifact SHALL be scored as
unjudged with a `decision_missing` marker. They SHALL NOT receive a pass via
candidate recall.

#### Scenario: Old run re-scored
- **WHEN** a pointing case result directory has no decision artifact
- **THEN** its score reports unjudged with `decision_missing: true` and no pass

### Requirement: Perception metrics stay, but do not gate
Candidate recall, evidence accuracy, and pointing-box IoU SHALL continue to
be computed and reported for pointing cases as perception metrics. They SHALL
NOT gate the case verdict.

#### Scenario: Perception columns alongside final choice
- **WHEN** a pointing case is scored
- **THEN** the score records candidate recall, evidence accuracy, and (where applicable) box IoU in addition to the final-choice verdict

### Requirement: Held-out manifest discipline
New pointing manifests SHALL exclude every image id already used in any
previously frozen manifest, SHALL be frozen at build time, and SHALL record
provenance (source, license, selection rule) for every case. Variant
comparison SHALL be confirmable on a held-out manifest that was not used for
variant selection.

#### Scenario: Held-out set is disjoint
- **WHEN** a new pointing manifest is built with exclusion enabled
- **THEN** no image id in it appears in any previously frozen manifest

#### Scenario: Provenance recorded
- **WHEN** a pointing manifest is built
- **THEN** each case records its source, license, and selection rule
