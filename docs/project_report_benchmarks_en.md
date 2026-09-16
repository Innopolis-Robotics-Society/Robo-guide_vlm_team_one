<!-- AGENT_EDIT_POLICY: USER_REQUEST_ONLY
Agents may modify this file only upon an explicit user request to update
the report. Do not update it automatically when code or results change.
-->

# VLM orchestration for a museum guide robot

This report describes the vision-language-model (VLM) subsystem implemented in
this repository and the benchmark evidence available for it. It is written for
a reader who is not familiar with the project.

Two kinds of evidence are kept separate throughout the report:

- **Repository evidence** means behavior, configuration, manifests, or metrics
  that can be inspected directly in the current checkout.
- **Historical benchmark results** means numerical measurements copied from the
  report supplied on 2026-09-16. The corresponding run outputs are not present
  in the current checkout, so those numbers cannot presently be recalculated or
  independently verified from the repository alone.

## 1. Problem statement

### 1.1 Task

The existing guide robot uses a language model to interpret a visitor's
utterance and choose an action, such as answering a question, starting a tour,
or pausing. Text alone is not sufficient for requests that depend on the
visitor's surroundings. For example, the robot cannot resolve “What is that?”
without seeing the visitor's gesture and the nearby exhibits.

This project adds optional visual context to the existing dialogue agent. At
the start of a dialogue turn, the agent can combine:

- the visitor's utterance;
- recent camera frames;
- the current mission state;
- the tools permitted in that state; and
- a restricted list of exhibit identifiers from the semantic map.

The model proposes an action using a four-field JSON object:
`tool`, `args`, `confidence`, and `abstain`. Host-side code then checks the
proposal before any tool is called. It rejects malformed output, tools that are
not allowed in the current mission state, invalid arguments, unknown semantic-
map identifiers, low-confidence actions, and explicit abstentions. A rejected
action is converted into a safe clarification response rather than being sent
to the robot's control layer. The checked-in [tool catalog](../guide_robot_llm/guide_robot_llm/tools/schema.py) and [action validator](../guide_robot_llm/guide_robot_llm/tools/validate.py) define this
boundary.

The VLM is therefore an advisory decision component. It does not replace
emergency stopping, collision monitoring, navigation, or the mission-state
machine.

### 1.2 Implemented visual tasks

The repository contains two visual tools and two additional offline evaluation
tracks:

| Track | Intended behavior | What the repository evaluates |
|---|---|---|
| Pointing | Resolve which known exhibit a visitor is indicating, or ask for clarification | Gesture evidence, candidate selection, bounding-box overlap when available, target selection, and abstention |
| Scene description | Answer a question about what is visible without inventing facts | Scene observations are recorded, but the scorer does not judge their factual grounding |
| Audience | Estimate the number of visible people and, where labelled, the engaged audience | Mean absolute error, exact accuracy, within-one accuracy, and engaged-count metrics |
| Tool policy | Select a permitted robot tool with the correct arguments, or abstain | Exact match of tool and arguments plus abstention behavior |

The audience track is an offline perception task; the live tool catalog does
not contain an audience-control tool. Visual obstacle detection is not an
implemented VLM task in the current tool catalog and is outside this report.

### 1.3 Data

The [unified evaluation schema](../guide_robot_llm/guide_robot_llm/eval/schema.py) defines four tracks: `pointing`, `audience`,
`scene`, and `tool`. Each case records its source, media reference6,
prompt, candidate identifiers, expected output, provenance, and analysis
slices. The loader rejects cases that do not satisfy this schema.

The checked-in aggregate manifests have the following composition:

| Manifest | Pointing | Audience | Tool | Scene | Total |
|---|---:|---:|---:|---:|---:|
| `bench_47.jsonl` | 15 | 25 | 7 | 0 | 47 |
| `bench_50.jsonl` | 15 | 25 | 7 | 3 | 50 |
| `pv_matrix_57.jsonl` | 15 | 32 | 7 | 3 | 57 |

`bench_47` combines 15 EgoPoint cases, 25 AGHRI cases, and seven synthetic
`bench_47` combines 15 [EgoPoint-Bench](https://guyyyug.github.io/EgoPoint-Bench/)
cases, 25 [AGHRI](https://doi.org/10.24385/lincoln.32982638) cases, and seven synthetic
tool-policy cases. `bench_50` adds three synthetic scene cases. The
`pv_matrix_57` manifest adds seven audience cases to `bench_50`.

These datasets do not reproduce the complete physical-robot situation. In
particular, the offline pointing cases do not exercise the live combination of
camera calibration, robot pose, semantic-map coordinates, and the visitor's
gesture.

### 1.4 Evaluation metrics

The checked-in [scorer](../guide_robot_llm/guide_robot_llm/eval/scoring.py)
implements the following principal metrics:

| Area | Metrics implemented by the scorer | Interpretation |
|---|---|---|
| Pointing perception | Gesture-evidence accuracy, target-in-candidates, top-2 recall, mean box IoU | Whether the visual observation contains useful pointing evidence |
| Pointing policy | Top-1 target accuracy; no-target false-positive rate and abstention credit | Whether the system selects the correct target or safely declines |
| Audience | Count MAE, exact accuracy, within-one accuracy, engaged-count MAE and exact accuracy | Error in the estimated audience size |
| Tool policy | Exact match of `{tool, args}`; no-target behavior | Whether the requested robot capability is selected correctly |
| Reliability | Pass, fail, unjudged, parse/backend failures, attempts | Whether the pipeline produces a usable response |
| Performance | Per-call and end-to-end timing recorded by the runner | Inference cost for the tested execution strategy |

The repository does not define a pass threshold for deployment readiness.
Time-to-first-token, peak RAM, and peak VRAM are not produced by the unified
scorer and should not be presented as measured benchmark outcomes.

## 2. Baselines

The experiment varies two independent factors: the model and the prompt. These
must not be collapsed into a single meaning of “baseline.”

### 2.1 Model candidates

The checked-in [small-model
matrix](../guide_robot_llm/scripts/matrix_pv16.json) names four candidates:

| Model ID | Experimental role |
|---|---|
| `gemma4-e2b` | The Gemma model that was deployed on the robot originally  |
| `gemma4-e4b` | Larger candidate from the same model family |
| `qwen3.5-4b` | Similar-size cross-family comparison |
| `qwen3.5-9b` | Higher-capacity comparison |

The matrix configuration does not contain the weights themselves. It points to
four environment profiles under `llm_server/config/models/`.

### 2.2 Prompt baselines

Each skill has six prompt configurations:

- `D0`, `P0`, and `A0` are minimal experimental baselines for scene,
  pointing, and audience tasks respectively.
- `D_base`, `P_base`, and `A_base` are snapshots of the built-in production
  instructions.

## 3. Proposed model

### 3.1 Contribution

No model weights are trained or fine-tuned in this project, since fine-tunning and training would require both time and resources that we don't posses. “Proposed model” in this report means the proposed **VLM orchestration system** around pretrained models. Its contribution is the controlled path from camera observations to a validated robot action.

The live sequence is:

1. When vision is enabled, the dialogue agent subscribes to compressed camera
   frames and freezes a small recent set at the start of the visitor's turn.
2. It builds a visual context containing frame metadata and at most five
   candidate exhibits from the semantic map near the current tour stop.
3. A multimodal model either proposes an action directly or first produces a
   structured visual observation.
4. A grammar constrains the generated JSON shape, and deterministic host code
   parses and validates the result.
5. For pointing, host code can compare the proposed target with the robot pose,
   configured camera geometry, candidate coordinates, visible identifiers, and
   gesture evidence.
6. Only an accepted action is sent to the relevant tool. The dialogue agent
   then generates the visitor-facing reply.

The default frame-buffer configuration keeps up to three frames from a
two-second lookback window, rejects stale or invalid JPEG data, limits the long
edge to 1280 pixels, and caps the total payload at 2.5 MB.

### 3.2 Visual strategies

The code implements two strategies:

- `direct_action`: camera frames and candidate identifiers go directly to the
  action-selection call. This needs fewer model calls.
- `observe_then_decide`: the first call produces a structured observation with
  a people count, visible exhibit identifiers, pointing evidence, an optional
  pointing box, and short scene facts. A later call uses that observation to
  select the action.

The second strategy gives the host explicit visual evidence to validate.
This matters for pointing: the live host-side resolver obtains visible
identifiers and gesture evidence from the parsed observation. Under
`direct_action`, that parsed observation is absent, so the full pointing
resolver cannot confirm the model's choice and safely abstains.

### 3.3 Default configuration and current limitations

The checked-in [default configuration](../guide_robot_llm/config/llm.yaml) is conservative:

- `vision.enabled` is `false`;
- both configured model endpoints are marked as non-multimodal;
- `vision.prompt_strategy` is `direct_action`; and
- `vision.answer_phase_images` is `false`.

Visual operation therefore requires an explicit deployment configuration. The
camera launch starts the raw V4L2 source, while the dialogue agent subscribes to
`/camera/image_raw/compressed`; the deployment must ensure that a compressed
transport is actually available.

The `describe_scene` tool itself returns prepared visual context rather than a
natural-language description. A visitor-facing description consequently
depends on the answer phase receiving adequate visual evidence. With the
checked-in default `vision.answer_phase_images=false`, this path is not a
complete scene-description implementation.

## 4. Model improvements

The project improves behavior through prompt design and inference organization,
not through weight updates. The prompt manifest contains 18 variants: six for
each of the three visual skills. Their machine-readable definitions are in the
[prompt-variant manifest](../guide_robot_llm/guide_robot_llm/eval/prompt_variants.json).

| Family | Baseline | Skill-specific instruction | Two-pass reasoning | Iterative loop or self-check | Few-shot | Production reference |
|---|---|---|---|---|---|---|
| Scene | `D0` | `D1` observational rules | `D2` | `D3` confidence-labelled self-check | `D4` | `D_base` |
| Pointing | `P0` | `P1` combines gesture, gaze, language, and geometry | `P2` | `P3` observe-match-clarify loop | `P4` | `P_base` |
| Audience | `A0` | `A1` counting criteria | `A2` | `A3` iterative counting loop | `A4` | `A_base` |

The variants use three execution modes:

- `single`: one inference pass;
- `cot_2pass`: a reasoning pass followed by a final-answer pass; and
- `loop`: repeated calls within fixed call and frame budgets.

Because the modes use different numbers of model calls, a quality comparison
must also report latency, call count, parse failures, and unjudged cases.

The few-shot variants use deterministic synthetic scenes that are kept out of
the evaluation manifests. 

## 5. Results

### 5.1 Audience-count results

The supplied report describes 32 audience cases. “Production” means `A_base`;
“selected variant” is the best result chosen from the tested variants for that
model. MAE is calculated only over outputs with an extractable count.

| Model | Production prompt | Selected variant |
|---|---|---|
| Gemma 4 E2B | MAE 0.76 (`n=21`), exact 12/32 (38%) | `A2`: MAE 0.43 (`n=28`), exact 21/32 (66%) |
| Gemma 4 E4B | MAE 0.70 (`n=10`), exact 6/32 (19%) | `A2`: MAE 0.22 (`n=32`), exact 28/32 (88%) |
| Qwen3.5-4B | MAE 0.50 (`n=32`), exact 21/32 (66%) | `A0`: MAE 0.44 (`n=32`), exact 23/32 (72%) |
| Qwen3.5-9B | MAE 0.27 (`n=15`), exact 12/32 (38%) | `A2`: MAE 0.16 (`n=32`), exact 29/32 (91%) |

The production-prompt coverage varies from 10 to 32 judged cases. Comparing
MAE without this denominator would be misleading: a model may obtain a small
error after leaving difficult cases unjudged. On these reported runs, `A2`
both increased coverage and reduced error for three models, while Qwen3.5-4B
performed best with the minimal `A0` prompt.

### 5.2 Pointing results

The supplied report describes 15 pointing cases:

| Model | Production prompt | Selected variant |
|---|---:|---:|
| Gemma 4 E2B | 20% | `P3`: 15/15 (100%) |
| Gemma 4 E4B | 33% | `P3`: 15/15 (100%) |
| Qwen3.5-4B | 33% | `P0`: 15/15 (100%) |
| Qwen3.5-9B | 33% | `P4`: 14/15 (93%); one case unjudged |

These figures show a large prompt effect on this small sample, but they do not
show that the selected prompt will generalize. The best variant was selected
from results on the reported cases, no held-out confirmation is included, and
the set contains too little no-target evidence to evaluate safe abstention
reliably. The offline score also does not validate the complete live pointing
pipeline with robot pose and camera geometry.

### 5.4 Reliability and latency

| Model | One decision call, p50 | Full pass, p50 / p95 |
|---|---:|---:|
| Qwen3.5-4B | 0.34 s | 1.0 / 1.2 s |
| Qwen3.5-9B | 0.41 s | 1.4 / 1.5 s |
| Gemma 4 E2B | 0.43 s | 0.7 / 0.8 s |
| Gemma 4 E4B | 0.54 s | 1.0 / 1.2 s |

These measurements compare different execution costs: a “full pass” may
include observation, multiple reasoning calls, and repair. They were collected
on a workstation, with a single reported repetition and no cold-versus-warm
split. They are not measurements of latency on the robot.

### 5.5 What the results support

Subject to the provenance limitations above, the historical measurements
support three narrow observations:

1. Prompt choice had a large effect on the 15 pointing cases.
2. Two-pass audience prompting (`A2`) improved both output coverage and count
   error for three of the four reported models.
3. Additional calls improved some quality results but introduced latency and,
   for the Qwen models, more parse failures in some pointing variants.

They do not establish scene-description quality, robust abstention, physical-
robot readiness, or a universally best model. There are only three scene cases
and the scorer does not judge them. The supplied report identifies only one
no-target pointing case, which is insufficient for a meaningful false-positive
estimate.

## 6. Reproducibility

Reproduction has two separate targets: the offline benchmark and the live ROS 2
system. The offline benchmark should be reproduced first because it isolates
model and prompt behavior from camera, localization, speech, and navigation.

### 6.1 Offline benchmark

The code declares Python dependencies on Requests and Pillow; the ROS package
also depends on ROS 2 Humble interfaces and the project message package. From a
built workspace, the benchmark runner can be invoked from
`guide_robot_llm/`.

1. Restore the external media referenced by the selected manifest. Every file
   must be placed under the relative path stored in `media.path` and must match
   the stored SHA-256.
2. Restore or create the model profiles referenced by
   `scripts/matrix_pv16.json`. Record the exact weight and projector hashes,
   quantization, context size, image settings, random seed, and server build.
3. Replace the machine-specific `llama_server_bin` path in the matrix config.
   The checked-in value points to
   `/home/sinorin/llama.cpp/build-cuda/bin/llama-server` and is not portable.
4. Rebuild `bench_50` if its source manifests changed:

   ```bash
   cd guide_robot_llm
   python3 scripts/make_bench50.py
   ```

5. For one model and one prompt variant, prepare a backend JSON file containing
   `base_url`, `model_name`, `multimodal_enabled`, `max_images`, and timeouts,
   then run:

   ```bash
   python3 -m guide_robot_llm.eval.runner \
     --manifest eval_manifests/pv_matrix_57.jsonl \
     --out eval_runs/reproduction-P0 \
     --data-root . \
     --backend-config backend.json \
     --prompt-variant P0

   python3 -m guide_robot_llm.eval.scoring \
     --run-dir eval_runs/reproduction-P0 \
     --data-root .
   ```

6. After making the matrix configuration portable, run the complete campaign:

   ```bash
   python3 scripts/run_matrix.py \
     --config scripts/matrix_pv16.json \
     --campaign-dir eval_runs/reproduction-matrix
   ```

Each successful variant run should preserve `run_config.json`,
`run_manifest.json`, `results.jsonl`, `score.json`, `summary.csv`, and
`report.md`. A campaign should additionally preserve its state, logs, and
summary matrix. Those artifacts, plus model hashes and hardware information,
are required to substantiate numerical claims in this report.

### 6.2 Live robot validation

Offline success does not demonstrate the deployed system. A live validation
must additionally record:

- the commit under test and the complete ROS parameter files;
- the camera device and calibration;
- how `/camera/image_raw/compressed` is produced;
- the semantic map and tour state;
- robot pose and transform availability;
- the multimodal endpoint configuration;
- whether `direct_action` or `observe_then_decide` is used;
- model calls, validation decisions, tool executions, and end-to-end latency;
  and
- expected and observed behavior for ambiguous, stale, and no-target cases.

We couldn't validate anything on real hardware, due to the tight deadline and the fact that robot is already transfered to another team.

## 7. Conclusion

The repository implements an optional multimodal extension to the guide
robot's dialogue agent. It can buffer camera frames, restrict the VLM to known
semantic-map candidates, request structured visual observations, validate
proposed actions, and abstain before unsafe or unsupported tool calls. The main
engineering contribution is this orchestration and validation layer, not a
newly trained model.

The supplied historical benchmark suggests that prompt design strongly affects
pointing and audience-counting performance. On the reported cases, several
small models reached high pointing accuracy, while Qwen3.5-9B and Gemma 4 E4B
gave the lowest selected-variant audience-count errors. These findings remain
preliminary, as the samples are small, the best variants were selected on the reported cases,
scene descriptions are not judged, abstention coverage is inadequate, and
latency was measured on a workstation rather than the robot.

The next defensible milestone is a frozen, reproducible benchmark with restored
media, complete model profiles, preserved per-case outputs, and a held-out test
set. That should be followed by an end-to-end robot trial using calibrated
camera geometry and explicit multimodal deployment settings. Until both steps
are complete, the project demonstrates a credible VLM integration architecture
and promising diagnostic results, but not production readiness.