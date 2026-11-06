# Spec Delta

## Purpose

Define which metrics may be reported as pointing capability, so that "pointing success" always measures the final pointing decision (or a validated end-to-end replay of it), and variant selection and headline evaluation remain on disjoint data.

## ADDED Requirements

### Requirement: Pointing success metrics measure the final decision

A metric labeled as pointing success, or used in the headline pointing results, SHALL be based on the model's final pointing choice or an end-to-end replay of it. Candidate-set inclusion SHALL be reportable only as a perception metric, explicitly labeled as such.

#### Scenario: Labeled results table

- **WHEN** the report presents pointing results
- **THEN** each column is labeled as a perception metric (candidate recall) or a policy metric (final choice / end-to-end replay)

#### Scenario: Candidate hit without final choice

- **WHEN** a case's candidate set contains the target exhibit but the model makes no final choice for it
- **THEN** the case does not count as pointing success

### Requirement: Variant selection and headline evaluation use disjoint sets

Prompt or model variants selected on a development set SHALL be evaluated on a disjoint set for any headline claim of their superiority.

#### Scenario: Selected variant claim

- **WHEN** the report claims a selected variant is best
- **THEN** the claim is supported by results on a set disjoint from the selection set

### Requirement: Abstention behavior is reported completely

Pointing results SHALL report abstention rates alongside accuracy. If the evaluation set contains true no-target cases, the safe-abstention rate on them SHALL be reported; if it contains none, the absence SHALL be disclosed as a limitation.

#### Scenario: No-target cases present

- **WHEN** the evaluation set contains true no-target cases
- **THEN** the abstention-correct rate on those cases is reported

#### Scenario: No-target cases absent

- **WHEN** the evaluation set contains no true no-target cases
- **THEN** the report discloses that the safe-abstention path is unmeasured
