# Spec Delta

## Purpose

Keep the project report, the README, and the submitted archive mutually consistent: inventory claims match the files actually shipped, every reported number is derivable from run artifacts, and every referenced file is present.

## ADDED Requirements

### Requirement: Archive inventory claims match the submitted files

The report and README SHALL state which run artifacts and configuration files the submission contains, and every such claim SHALL be true for the submitted archive.

#### Scenario: Inventory audit

- **WHEN** the report lists the contents of the submission
- **THEN** every listed item is present in the archive and no absent item is claimed to be present

### Requirement: Numeric tables are derivable from run artifacts

Every reported numeric value SHALL be computable from committed run artifacts (e.g. `score.json`) with the rounding convention documented in the report.

#### Scenario: Recomputing a table cell

- **WHEN** a reviewer recomputes a table value from the cited run artifact
- **THEN** the value matches the report within the documented rounding

### Requirement: Referenced files are included

Every file referenced by the report or README SHALL be present in the submission.

#### Scenario: Reference resolution

- **WHEN** the README or report links to a document
- **THEN** that document is present in the submitted archive
