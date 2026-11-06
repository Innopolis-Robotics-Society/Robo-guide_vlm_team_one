# Spec Delta

## Purpose

Ensure the inference environment and inputs of an evaluation campaign are fully pinned by the submitted artifacts, so a third party can recreate the environment and verify the reported results without access to the original machine.

## ADDED Requirements

### Requirement: Model weight provenance is pinned

For every model weight and projector file used by a recorded evaluation run, the submission SHALL record the file's source (URL or repository), quantization, and SHA-256 of the exact file used.

#### Scenario: Verifying a weight file against a recorded run

- **WHEN** a reviewer wants to verify a weight file used in a recorded run
- **THEN** the provenance record supplies a SHA-256 the file can be matched against, plus the source location for obtaining an identical file

#### Scenario: Every profile-referenced file has a provenance entry

- **WHEN** a model profile references a weight or projector file
- **THEN** the provenance record contains an entry for that file

### Requirement: Inference server build is pinned

The inference server binary used by a campaign SHALL be identified in the submission by an immutable source identifier (source commit), not only by a local path.

#### Scenario: Identifying the server build from the submission

- **WHEN** a reviewer reproduces a recorded run
- **THEN** the exact server build can be identified from the submission alone, without probing any local machine

### Requirement: Sampling parameters are fixed and recorded

A campaign SHALL start the inference server with a fixed sampling seed and temperature, and both values SHALL be recorded in the per-run configuration.

#### Scenario: Re-running a campaign case

- **WHEN** a campaign case is re-run against the same pinned inputs
- **THEN** the sampling seed and temperature used are recorded in the per-run configuration file
