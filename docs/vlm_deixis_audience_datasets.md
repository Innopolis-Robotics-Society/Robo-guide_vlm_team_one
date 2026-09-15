# Datasets for Deixis and Audience Assessment in a Tour-Guide Robot

> Research survey, 2026-09-14 (license/access checks as of that date).
> **Status (decision 2026-09-15, recorded in Taiga issue #10):** the runnable scope
> is reduced to an external-only mini-benchmark of at most 50 curated cases —
> DP 20, EgoPoint-Bench real-world 10, YouRefIt 5, AGHRI 15. Robot-view
> end-to-end validation stays on the #9 pilot episodes replayed through the
> harness. The rest of this document is retained as the full survey and
> watchlist context.

## License verification (checked 2026-09-15)

Fresh verification against primary sources, executed for plan task T1 of
`vlm-bench-50` (harness for Taiga #10). Dates below are the verification date.

| Source | Verdict | Evidence (checked 2026-09-15) |
|---|---|---|
| **DP / Deepoint** | **GO** — modifiable, noncommercial | [data/README.md](https://github.com/kyotovision-public/deepoint/blob/main/data/README.md) states CC BY-NC 4.0; 7 zips (5 frame days `2023-01-{17,18,19,24,25}.zip` + `labels.zip` + `keypoints.zip`) with published md5sums; frames are squashfs (mount required); layout `frames_squashed/<date-venue>/take*/00..14` (15 camera views per take). |
| **EgoPoint-Bench** | **GO for unmodified private research use ONLY — NO-GO for adaptation/redistribution** | Hugging Face API: `license: None`, no README in the dataset repo, `gated: False` ([dataset](https://huggingface.co/datasets/GUYYYUG/EgoPoint), tree: `realdata_benchmark/`, `simdata_benchmark/`). GitHub [project is Apache-2.0](https://github.com/GUYYYUG/EgoPoint) ("This project is licensed…", code only). No declared license ⇒ HF default terms; no derivative or redistribution rights. Our use: download real-world images, run authors' QA protocol, no redistribution, no derivative set — within private research use. Re-verify before any publication of an adapted subset. |
| **YouRefIt** | **GO for unmodified protocol use — NO-GO for adaptation** | [License.pdf](https://yixchen.github.io/YouRefIt/file/License.pdf): non-commercial scientific research only; "The Datasets shall not be reproduced, modified, distributed and/or made available in any form to any third party without Licensor's prior written permission"; one archive copy allowed. [Request page](https://yixchen.github.io/YouRefIt/request.html): registration form, noncommercial research. |
| **AGHRI** | **GO** — modifiable, attribution required | [AGHRI-dataset-benchmark README](https://github.com/LCAS/AGHRI-dataset-benchmark): "The AGHRI dataset is distributed separately under CC BY 4.0… independent of the benchmark code licence" (Apache-2.0). [AGHRI-dataset-tools](https://github.com/LCAS/AGHRI-dataset-tools): ~70 GB released, 65 sequences (52/7/6 train/val/test), 10 participants, ZED RGB 672×376 + 3 fisheye 640×360, 138,741 camera frames, 154,002 2D human boxes. **Release re-check (2026-09-16, bench-40 run):** v2 release (2026-08-21) ships ten parts with a per-sequence summary CSV (`Number of Humans`, `Environment`, `Robot movements`); counts 4–5 occur only in parts 7/10, so parts 1–3 suffice for a 1–3-person slice (verified against the downloaded parts). |

Watchlist re-check (2026-09-15), all still release-pending — do not plan around them:

- **GestureTarget** — [TransGesture README](https://github.com/IrohXu/TransGesture) line 29: "Get GestureTarget-v1. Coming Soon."
- **EgoPoint-Ground** — [arXiv:2603.26646](https://arxiv.org/abs/2603.26646) abs page: "code will be made publicly available."
- **EgoPointVQA** — [EgoPointVQA repo](https://github.com/Yuuraa/EgoPointVQA): dataset badge has an empty link; release pending.

## Decision summary

The robot needs two different evaluations. **Deixis resolution** asks which of the exhibits available at the current stop a visitor indicates while saying, for example, «а что это такое?»; the scored answer is the exhibit's existing `content_id` or an explicit abstention. **Audience assessment** asks how many visitors are in the robot's interaction zone, whether each is attending to the robot or the exhibit, and whether `mission_control` should continue, wait, or seek clarification. The latter action is a policy decision over visual observations, not a property that most public vision datasets label.

No public dataset found supplies the full combination of a *third-person robot webcam*, synchronized Russian speech, a pointing visitor, multiple nearby named exhibits, a local exhibit catalogue, audience count, gaze, and a tour-control decision. This is an evidence gap, not a reason to discard external data. The most useful approach is to use external datasets for narrow component tests and build a small, held-out set from the actual robot camera for the end-to-end decisions.

**Recommended first downloads:** the **DP Dataset** for modifiable pointing examples and **AGHRI** for modifiable robot-view person detection/counting. **EgoPoint-Bench** is a hard test of implicit deictic questions, but rights for its separately hosted images need confirmation before adaptation. Use **EGO-CH-Gaze** for museum exhibit localization if its image rights are clarified. **YouRefIt** is the closest existing language-plus-gesture benchmark, but its license disallows dataset modification without written permission. **TOGURO** is exceptionally relevant to a museum robot, yet its underlying video cannot be publicly released; its paper and released model can inform the annotation rubric only.^1–7,12

### Fit and access matrix

"Adapt" below means making a private derivative evaluation set by selecting samples and adding or changing annotations. A public repository or code license does not by itself establish image rights.

| Dataset | Main role | View / labels that matter | Access and adaptation status | Principal gap for this robot |
|---|---|---|---|---|
| **DP Dataset (Deepoint)** | Pointing target and gesture timing | Indoor multiview JPEG sequences; marker/target ID, pointing interval, arm; 2D/3D keypoints | Downloadable; dataset **CC BY-NC 4.0**, which permits adaptation with attribution for noncommercial use.^1 | Marker targets and a multi-camera setup, not exhibit `content_id` or language; select a single camera to simulate the webcam. |
| **EgoPoint-Bench** | Implicit «this/that» reasoning and hard distractors | 11,729 image–question samples, including 1,162 real-world tests; simulated and real first-person pointing; QA and target information | Benchmark JSON/code and real/sim images are separately available. GitHub states Apache-2.0 for the *project*; the Hugging Face image repository has no explicit license visible on its page, so image adaptation rights need confirmation.^2 | Camera is the pointer's first-person view; the robot sees the pointer from outside. Object-name/QA output needs remapping to target ID. |
| **YouRefIt** | Closest reference test for gesture + language | 4,195 reference clips in 432 indoor scenes; a person refers to a target using speech and pointing | Registration and noncommercial research access. License explicitly prohibits modification without prior written permission.^3 | Cannot be adapted under standard terms; no exhibit catalogue or Russian speech. |
| **EGO-CH-Gaze** | Exhibit detection/instance ID in a museum | Museum visitor first-person RGB frames with artwork/detail boxes and gaze; 15 objects of interest | Frames and annotations have download links, but the project page does not state an image/dataset license. Verify terms before derivative use.^4 | Wearable visitor camera plus eye gaze, neither available from the robot webcam; no pointing. |
| **AGHRI** | Robot-view person count and occlusion | Robot RGB/fisheye frames with identity-consistent 2D human boxes; single- and multi-person sequences | About 70 GB in parts; dataset described as **CC BY 4.0** by the authors' benchmark repository; adaptation with attribution is supported.^5 | Outdoor agriculture, not a museum; "look at robot" appears in sequence/activity names rather than verified per-person gaze labels. |
| **Gaze4HRI** | "Looking at robot/camera" subtest | Robot-mounted RGB videos and 3D gaze ground truth; mutual-gaze, head–gaze conflict, lighting, camera-motion conditions | Project describes 52 subjects, 3,258 videos and a dataset format, but I could not verify a direct raw-video download or a dataset license on the linked page/repository. Treat acquisition and rights as **unconfirmed**.^6 | Lab, usually one subject, mocap ground truth; no audience counting or tour engagement label. |
| **UE-HRI** | Engagement-decrease and gaze-cue research test | Pepper-camera/multisensor ROS bags from spontaneous interactions | Registration; explicitly research-only and restrictive copying terms. Any adapted set or redistribution requires checking the terms/permission.^7 | Different robot and interaction; "engagement decrease" is broader than visible attention or the desired continue/wait action. |
| **COCO 2017** | Low-cost person-count baseline | General images with `person` instance boxes | Official detection data downloadable; image-level copyright/license varies and should be checked per image before republishing derivatives.^8 | Third-party scenes; gaze and interaction-zone status absent. |

Two additional sources have narrower value. **Shutter/PAR-D** is publicly downloadable under CC0 and includes scenarios with up to five people visible per frame, robot/person pose, and interaction/noninteraction labels; the released archives are *processed CSVs*, so they cannot directly test a webcam VLM, but they can test a downstream interaction policy with structured observations.^9 **CrowdHuman** supplies visible/full/head boxes and occlusion-heavy count tests, but its terms limit use to noncommercial research/education and prohibit image redistribution. Its crowded scenes are a useful stress test after the basic audience benchmark, not the first dataset to tune a museum camera.^10

Several appealing search hits should **not yet be put in the runnable dataset list**. **GestureTarget** reports more than 20,000 annotated deictic targets and a CC BY-NC 3.0 benchmark, but its authors' repository still says "GestureTarget-v1. Coming Soon." **EgoPoint-Ground** describes more than 15,000 hand–target samples but says the dataset and code *will* be made public. **EgoPointVQA** reports 4,000 synthetic and 400 real first-person pointing videos, while its repository still lists dataset release as pending. Recheck these projects later rather than planning an evaluation around unavailable files.^14–16 Finally, **PixMo-Points** uses human-placed *annotation points* for image regions; it does not show a visitor pointing with a hand and cannot evaluate gesture understanding.^17

## 1. What the evaluation should measure

### Deixis resolution

The input should contain a frame or short synchronized clip from the robot webcam, the visitor utterance/transcript, the current stop or zone, and only the candidate exhibits actually available there. The expected output is one of those candidates' `content_id` values, or `unknown` when the point is invisible, off-screen, outside the candidate set, or genuinely ambiguous. The local semantic map already distinguishes a location's `id` and `exhibit_id`; the exhibit content service takes `exhibit_id`, while search results use `content_id`. In current lab examples they coincide (such as `promobot_m13_artist` and `livox_mid70`), but the evaluation schema should store both names explicitly to avoid relying on that coincidence. This is a direct implication of the repository's `locations.yaml` and semantic-map interface.^11

The key failure mode is selecting an object that is prominent or close to the hand instead of the one indicated by the pointing direction. EgoPoint-Bench was designed around precisely this error, including implicit-pronoun questions and adversarial/void references.^2 The camera mismatch is important: first-person pointing benchmarks can test whether a VLM understands deictic language and pointed targets, but they cannot establish that it can infer the *visitor's* gesture from a robot-mounted camera. YouRefIt and DP supply third-person gestures and are therefore more representative for gesture geometry.^1,3

**Proposed scoring:** exact-match `content_id` accuracy on answerable cases; false-positive rate on no-target/ambiguous cases; top-2 recall if the system can provide ranked candidates; accuracy broken down by target size, number of visible exhibits, partial arm visibility, left/right hand, distance and occlusion. Log whether an incorrect answer was nevertheless in the local candidate set. An explicit abstention should be rewarded when no unique target is visually supported. Evaluate Russian transcripts («это», «вон то», «а этот?») separately from translated English prompts; these phrasings should be written for the collected robot-view cases rather than replacing the original text of a licensed benchmark.

### Audience assessment

Define **`visible_people`**, **`in_interaction_zone`**, **`attention_target`**, and **`mission_signal`** separately. `visible_people` is a count in the image. `in_interaction_zone` requires a calibrated distance/region rule for this robot, not just a `person` bounding box. `attention_target` can be `robot`, `exhibit`, `other`, or `unobservable`. Finally, `mission_signal` can be `continue`, `wait`, or `ask/uncertain`, based on a short temporal window and the tour state. A visitor staring at an exhibit while listening may be highly engaged, despite not looking at the robot. In the TOGURO museum annotation instructions, looking at either the robot/screen **or the exhibit** counted as high engagement; looking at a phone, turning away, or leaving the field of view contributed to lower scores.^12

This means "are they looking at the robot?" is a useful observable but a poor standalone definition of "continue the narration." One webcam frame is also insufficient when a person briefly blinks, turns toward a companion, or looks between exhibit and robot. Use short clips or repeated frames for the mission signal. The existing `PresenceTracker` in this repository retains `present` for a timeout after the last accepted evidence; a future vision signal should be evaluated alongside that temporal behavior, without interpreting a temporary absence of eye contact as visitor departure.^13

**Proposed scoring:** count mean absolute error plus exact-count accuracy for 0–5 people; per-person attention precision/recall (with an `unobservable` category); macro-F1 for `continue/wait/ask`; and an "unsafe wait/continue" confusion table. Report results separately for one versus several visitors, visitors near the edge of the field of view, camera motion, backlit faces, people looking at an exhibit behind/beside the robot, and passers-by. The interaction-zone rule and the mission decision should be annotated locally because none of the shortlisted external datasets encodes the same physical tour policy.

## 2. Dataset-specific assessment

### DP Dataset — first source for modifiable pointing examples

The Kyoto University Deepoint data page describes seven archives containing synchronized JPEG frames from 15 camera views, labels, and keypoints. Each pointing label identifies a marker/target, start and end frames, and pointing arm. The linked `data/README.md` states CC BY-NC 4.0 for the dataset.^1 Unlike gesture-class collections, this offers a target ID that can be converted into a pseudo-`content_id`. For an RGB-webcam test, choose only one camera view per take, hide depth/3D signals from the evaluated model, and keep sequence/participant separation between any tuning and held-out sets. Map each marker ID to a stable synthetic exhibit ID (for example `marker_19 → exhibit_19`) without altering the original ground truth.

The synthetic remapping measures target selection, not semantic identification of real artworks. Record that distinction in results. The 15-camera collection may produce near-duplicate views, so splitting by image would leak the same gesture into both training and test. The CC BY-NC terms make it suitable for noncommercial adapted research; a commercial deployment needs separate rights.

### EgoPoint-Bench — hard implicit-reference benchmark, with rights check

The authors' repository provides benchmark JSON and evaluation scripts, and directs readers to separate Hugging Face images. It reports 10,567 simulated and 1,162 real-world QA samples. Its deixis taxonomy goes from explicit mention of pointing, through locatives, to an implicit pronoun, and it includes misleading or void references.^2 These properties make it useful for testing whether the VLM abstains instead of inventing a target. Start with the real subset; use the simulation subset as a controlled stress test. If its annotations include a target box/name for a case, construct a candidate-ID table from the scene and score target selection before scoring free-form answers.

However, the hand is filmed from the pointer's own perspective. Treat improvements here as evidence of deictic reasoning, not proof of robot-camera performance. The GitHub Apache-2.0 statement applies to "this project"; the separate Hugging Face image store did not show a license on the page I could verify. Confirm image and underlying simulator-scene rights before modifying or redistributing an adapted copy.^2

### YouRefIt — best conceptual match, but modification blocked by its license

YouRefIt explicitly combines a person's language and pointing to select an object in a shared indoor environment. It contains 4,195 localized reference clips in 432 scenes and supports image and video benchmarks.^3 It is attractive for a VLM comparison because it preserves the coupling between gesture and utterance. Its standard download, however, requires registration, is limited to noncommercial research, and says the dataset must not be "modified" without prior written permission.^3 That is a material blocker for the requested adaptation. It can still be evaluated under the provided benchmark protocol if the team accepts those terms; ask the licensor before creating or publishing relabelled Russian `content_id` derivatives. Do not substitute the license of an unrelated GitHub implementation for the dataset license.

### EGO-CH-Gaze — museum exhibit localization, with viewpoint and rights gaps

This is the strongest museum-specific source located. The project page offers frame and annotation downloads from HoloLens recordings of seven visitors, with 15 objects or artwork details in one gallery and bounding-box annotations.^4 The task is "attended object detection": identify the artwork viewed by the camera wearer, using visual data and gaze. It can help determine whether a model can distinguish similar exhibits or details, especially when the guide's catalogue has fine-grained IDs. To use it for this robot, ignore wearer gaze at inference and evaluate plain RGB exhibit recognition or localization; mapping the 15 object labels to artificial content IDs is an evaluation transformation, not evidence of real robot-view deixis.

The site does not show a dataset license. Until terms are confirmed, download links establish availability but not permission to publish derivatives. A headset view also changes both target scale and the position of visitors; use it only as an auxiliary test, not the end-to-end test.

### AGHRI — best modifiable robot-view count source

The AGHRI release includes extracted robot RGB/fisheye frames, synchronized modalities, and identity-consistent 2D/3D human annotations in single- and multi-person scenarios. It is approximately 70 GB split across ten archives, with an index to choose specific sequences. The v2 release (2026-08-21) index is a per-sequence CSV with `Number of Humans`, `Environment` and `Robot movements` columns; verified 2026-09-16 against the downloaded parts 1–3 (counts 1–3 are spread over all parts, while 4–5-person sequences exist only in parts 7 and 10). Its authors' benchmark repository states that the **dataset** is CC BY 4.0, separately from the Apache-2.0 benchmark code.^5 For a simple webcam VLM, use the forward RGB or fisheye frames and 2D human boxes only. Count unique non-ignored people in the relevant camera frame; keep the sequence and identities available for checking double counts over time.

The collection is agricultural/outdoor, which is a substantial lighting and background shift from a museum. Sequence names include a `check` activity for checking/looking at the robot, but that is **not** a verified frame-level gaze or per-person "looking at robot" label. It can generate candidate clips for manual gaze annotation, not an automatic gaze ground truth.^5

### Gaze4HRI — direct gaze geometry if raw data is obtained

Gaze4HRI is unusually aligned with the "looking at the robot" subskill: a robot-mounted camera records 52 participants under varied lighting, camera viewpoints and head–gaze conflict, and a mutual-gaze condition asks participants to follow the moving robot camera. The project reports 3,258 videos and 620,933 frames; its raw-data schema includes RGB video, target positions and head/eye poses.^6 If the raw videos and use terms can be obtained, frames can be relabelled into "looking toward robot camera" versus "looking elsewhere" using the known gaze target and calibration. A simple head-orientation-only shortcut should be tested specifically on the head–gaze-conflict condition.

The web project and code repository I verified did not expose a direct raw-video download or dataset-specific license. It should therefore sit in a **conditional** queue; do not count it as an immediately runnable benchmark. Its controlled lab setup has too few group interactions to validate audience count or narration policy.

### UE-HRI and TOGURO — engagement evidence with strict access limits

UE-HRI records spontaneous interactions with a Pepper robot across camera, audio, depth, sonar and other ROS streams. Its official page allows registration for research use only; the conditions restrict reproduction and transmission.^7 For the camera-only VLM, select the RGB stream and derive an engagement-decrease endpoint, while keeping other sensor streams out of the model input. Check the agreement before creating or sharing a relabelled version.

TOGURO is closer to the actual application: an autonomous museum guide recorded visitor groups from a robot camera, and researchers scored perceived engagement continuously. Its public paper reports an annotated subset of about 5 h 50 min of unique video and explains an exhibit-aware rating rubric. But the article states that the generated datasets will **not** be made public because identifiable people could appear; only the model/software is released.^12 It is a strong precedent for the label definition, **not** an obtainable public image benchmark. The distinction matters more here than its excellent domain match.

## 3. Proposed adaptation and local benchmark

The local collection should be a small, deliberately varied *acceptance set* rather than a large training dump. A practical starting target is **roughly 200–300 deictic events and 150–250 audience clips**, each from the production webcam geometry; these are planning estimates, not sample-size guarantees. Keep complete session/visitor groups in one split to avoid leakage. Collect a consent/retention procedure suitable for identifiable visitors before recording, and ensure the benchmark copy has controlled access. Once the test cases have been fixed, do not tune prompts or thresholds on them.

For deixis, record 1–3 seconds around an utterance and gesture. Save the webcam frame sequence, transcript, stop/zone, visible exhibit IDs and boxes, pointed exhibit ID or `unknown`, and why an `unknown` label was assigned. Include: two or more nearby exhibits; a target between two objects; pointing across another person's body; only part of the hand visible; no gesture with «это»; gesture without a visible target; visitors pointing at something outside the current stop; and multiple speakers. Obtain two independent labels on ambiguous cases and adjudicate against the video. Capture the real relation between each image region, semantic-map `exhibit_id`, and returned `content_id`, rather than asking a VLM to invent a museum identifier.

For audience clips, record repeated frames over a short window. Give each visible person a track ID, bounding box, interaction-zone flag, and attention target (`robot`, `exhibit`, `other`, `unobservable`). Add a clip-level `mission_signal` with a documented policy: for example, `continue` when at least one participating visitor visibly attends to either robot or exhibit, `wait` when the audience has left or disengaged for a sustained interval, and `ask/uncertain` when evidence is insufficient or visitors disagree. This is a **proposed operational definition**, to be reviewed against actual tour behavior; it is not a label supplied by AGHRI or Gaze4HRI. Include empty scenes, passers-by, groups of different sizes, children/adults at different camera heights, exhibit viewing, companions talking, masks or occlusions, low light and backlighting.

An evaluation record can be compact:

```json
{
  "sample_id": "session_03_event_017",
  "task": "deixis",
  "camera_view": "robot_front_rgb",
  "utterance_ru": "А что это такое?",
  "stop_id": "lab_demo_stop_2",
  "candidate_content_ids": ["promobot_m13_artist", "livox_mid70"],
  "target_content_id": "promobot_m13_artist",
  "target_status": "visible_unique",
  "source": "local_robot_capture"
}
```

For audience assessment, replace the utterance/candidate fields with person tracks, attention labels and the mission signal. Preserve provenance and license alongside each external sample, since DP, AGHRI, YouRefIt and other collections cannot safely be mixed into a distributable set under one blanket license.

### Evaluation order

1. **Start with prompt-only VLM baselines** on original external splits. On DP, score target marker ID from one camera view. On EgoPoint-Bench, score the authors' QA protocol and then a separate target-selection subset where labels support it. On AGHRI, score person count from RGB only. This isolates basic failures before building new annotations.^1,2,5
2. **Run the held-out robot-view acceptance set** using a strict output contract: `content_id | unknown` for deixis; person count, attention vector and `continue | wait | ask` for audience. Provide the VLM only the candidate IDs and metadata the deployed system would actually know. Record both raw VLM output and validated parsed output.
3. **Slice errors by the physical situation**, especially nearby visually similar exhibits, uncertain pointing geometry, absence of speech/gesture alignment, gaze toward an exhibit, passers-by and temporary face occlusion. These slices decide whether another dataset is worth acquiring or whether targeted local recording is more valuable.
4. **Keep policy and perception scores separate.** A correct count with a wrong continue/wait action is a policy problem; a correct action produced from a wrong count is not evidence that counting works. Compare a simple detector/pose/gaze pipeline with the VLM under the same camera frames and latency budget before choosing the runtime architecture.

The dataset list changes over time. The access and license notes above were checked against the linked primary project, author repository or dataset terms on **14 September 2026**. Entries marked "unconfirmed" need fresh verification before ingestion or derivative publication.

## Sources

1. Kyoto University, **"DP Dataset,"** Deepoint project [dataset instructions and CC BY-NC 4.0 notice](https://github.com/kyotovision-public/deepoint/blob/main/data/README.md), accessed 14 September 2026. The source specifies archive layout, label fields and license.
2. Chentao Li et al., **"Do MLLMs Understand Pointing? Benchmarking and Enhancing Referential Reasoning in Egocentric Vision,"** 2026, [author repository](https://github.com/GUYYYUG/EgoPoint), [benchmark images](https://huggingface.co/datasets/GUYYYUG/EgoPoint). The repository reports sample counts and deixis levels and states the project license; the separately hosted image page did not show an explicit license in the version inspected.
3. Yixin Chen et al., **"YouRefIt: Embodied Reference Understanding with Language and Gesture,"** ICCV 2021, [project page](https://yixchen.github.io/YouRefIt/), [dataset request page](https://yixchen.github.io/YouRefIt/request.html), [dataset license](https://yixchen.github.io/YouRefIt/file/License.pdf).
4. Michele Mazzamuto et al., **"Learning to Detect Attended Objects in Cultural Sites with Gaze Signals and Weak Object Supervision,"** *ACM Transactions on Multimedia Computing, Communications, and Applications*, 2024, [EGO-CH-Gaze project and downloads](https://iplab.dmi.unict.it/legacy/EGO-CH-Gaze/).
5. University of Lincoln / LCAS, **"AGHRI Dataset Tools,"** [dataset structure, activity names and download](https://github.com/LCAS/AGHRI-dataset-tools); **"AGHRI Dataset Benchmark,"** [dataset CC BY 4.0 statement](https://github.com/LCAS/AGHRI-dataset-benchmark). Official dataset DOI: [10.24385/lincoln.32982638](https://doi.org/10.24385/lincoln.32982638).
6. Berk Sezer et al., **"Gaze4HRI: Zero-shot Benchmarking Gaze Estimation Neural-Networks for Human-Robot Interaction,"** FG 2026, [project and raw-data schema](https://gazeforhri.github.io/), [author code repository](https://github.com/GazeForHRI/Gaze4HRI).
7. Atef Ben-Youssef et al., **"UE-HRI: A New Dataset for the Study of User Engagement in Spontaneous Human-Robot Interactions,"** ICMI 2017, [official access page](https://adasp.telecom-paris.fr/resources/2017-05-18-ue-hri/), [terms](https://adasp.telecom-paris.fr/rc/datasets/ue-hri/Copyright.pdf).
8. COCO Consortium, **"COCO 2017 Object Detection,"** 2017, [official dataset page](https://cocodataset.org/dataset/detection-2017.htm), [main site/download entry](https://cocodataset.org/).
9. Sydney Thompson et al., **"Shutter Interaction Dataset,"** Yale Dataverse, 2025, v2 updated 2026, [dataset record and CC0 terms](https://dataverse.yale.edu/dataset.xhtml?persistentId=doi:10.60600/YU/KFFQPF), [feature description](https://shutter.interactive-machines.com/dataset/).
10. CrowdHuman authors, **"CrowdHuman Dataset,"** [official downloads, annotation format and terms](https://www.crowdhuman.org/download.html).
11. This repository, [semantic-map locations and exhibit IDs](../guide_robot_semantic_map/config/locations.yaml), [semantic-map service documentation](../guide_robot_semantic_map/README.md), inspected 14 September 2026.
12. Francesco Del Duchetto, Paul Baxter and Marc Hanheide, **"Are You Still With Me? Continuous Engagement Assessment From a Robot's Point of View,"** *Frontiers in Robotics and AI* 7:116, 2020, [full article including coding rubric and data-availability statement](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2020.00116/full); [released model/software](https://github.com/LCAS/engagement_detector).
13. This repository, [presence tracking implementation](../guide_robot_mission_control/guide_robot_mission_control/presence.py), inspected 14 September 2026.
14. Xu Cao et al., **"Toward Human Deictic Gesture Target Estimation,"** NeurIPS 2025, [paper](https://openreview.net/pdf?id=hio3T2OwHB), [author repository and dataset-release status](https://github.com/IrohXu/TransGesture).
15. Ling Li et al., **"Beyond Language: Grounding Referring Expressions with Hand Pointing in Egocentric Vision,"** 2026 preprint, [paper and release statement](https://arxiv.org/abs/2603.26646).
16. Yura Choi et al., **"Do You See What I Am Pointing At? Gesture-Based Egocentric Video Question Answering,"** CVPR 2026, [paper](https://openaccess.thecvf.com/content/CVPR2026/papers/Choi_Do_You_See_What_I_Am_Pointing_At_Gesture-Based_Egocentric_CVPR_2026_paper.pdf), [author repository/release status](https://github.com/Yuuraa/EgoPointVQA).
17. Allen Institute for AI, **"PixMo-Points,"** [dataset card and annotation description](https://huggingface.co/datasets/allenai/pixmo-points).
