# Lab 5 - CI/CD with GitHub Actions

## Implementation Context

This lab continues the same `mlops-lab-1` project from Labs 1-4.

The project now uses:

```text
Git / GitHub
-> source code and workflow versioning

DVC
-> Food-11 dataset versioning

MLflow Tracking
-> training runs, parameters and metrics

MLflow Model Registry
-> registered model versions and aliases

Docker
-> inference image

Docker Compose
-> local multi-service orchestration

GitHub Actions
-> continuous integration and image publishing
```

The CI pipeline deliberately does not require the full Food-11 dataset or a live MLflow server.

Unit tests use small local fixtures and a fake model, while the Docker smoke test starts the API with:

```text
SKIP_MODEL=1
```

This keeps CI lightweight and independent from the local MLflow server and DVC dataset.

---

## Question 1

### Why is it a bad idea for a unit test to load the real model from the MLflow server?

A unit test should be fast, deterministic, and isolated.

Loading the real model from MLflow would introduce external dependencies that are not directly related to the application logic being tested.

The test could fail even when the code itself is correct because:

1. the MLflow server is stopped or unreachable;
2. the network connection times out;
3. the `champion` alias is missing or points to another version;
4. the model artifacts cannot be downloaded;
5. loading the real model consumes significantly more time and resources.

For this reason, the API tests use:

```text
SKIP_MODEL=1
```

and inject a fake model.

This isolates the API logic from MLflow, DVC, the network, and expensive model loading.

---

## Question 2

### What does `test_predict_returns_valid_json` prove, and what does it not prove?

The test proves that the API can:

- receive an uploaded image;
- decode and preprocess the image;
- call an object exposing the expected `predict()` interface;
- convert the prediction into a Food-11 category;
- return an HTTP 200 response;
- return valid JSON;
- return a confidence value between 0 and 1.

However, the test does not prove:

- that the real trained ResNet18 model is accurate;
- that the MLflow server is reachable;
- that the `champion` alias is correctly configured;
- that model artifacts can be downloaded;
- that the full Docker Compose environment works;
- that the real production inference model produces correct classifications.

The purpose of this test is therefore to verify the API plumbing independently from the real ML model infrastructure.

---

## Question 3

### Which check catches the copied image, and why is a train/test duplicate dangerous?

The copied image is detected by the cross-split duplicate-content check in:

```text
validate_data.py
```

The validator calculates a content hash for every image and verifies that identical image content does not appear in different dataset splits.

During the implementation of this lab, the validator actually detected real duplicate images between the existing processed splits.

The preprocessing pipeline was therefore modified to calculate image hashes and skip duplicate images when constructing the processed dataset.

After regenerating the dataset, the validator produced:

```text
PASS - Exactly 11 class folders
PASS - Images are valid RGB 128x128
PASS - Minimum images per class
PASS - No duplicate images across splits
PASS - Training/validation class distribution

DATA CONTRACT: PASS
```

To verify that the duplicate detector really worked, an image from the training split was manually copied into the evaluation split.

The validator correctly failed the duplicate check.

After deleting the copied image, the validator returned:

```text
DATA CONTRACT: PASS
```

A duplicate image between training and evaluation is dangerous because it creates data leakage.

The model may be evaluated using an image that it already saw during training. This can artificially increase the reported evaluation accuracy and give the impression that the model generalizes better than it actually does.

A corrupted image is often easier to notice because it may produce an explicit loading error or crash.

A duplicate is potentially more dangerous because the complete pipeline may continue to run successfully while silently producing misleading model performance results.

---

## Question 4

### Where can `validate_data.py` run if the GitHub runner cannot access the DVC dataset?

Two appropriate locations are:

1. locally or on the data-preparation machine before the processed dataset is versioned and pushed using DVC;
2. on a training or data-processing machine that has access to the DVC remote, such as a self-hosted GitHub Actions runner.

The normal GitHub-hosted CI runner should not assume that it can access a local DVC remote.

Therefore, lightweight unit tests can run directly in GitHub Actions, while full dataset validation can run in an environment where the actual DVC-managed data is available.

---

## Question 5

### What does `needs: test` do?

The following configuration:

```yaml
needs: test
```

makes the `smoke` job depend on the successful completion of the `test` job.

Therefore:

```text
test succeeds
-> smoke can run
```

but:

```text
test fails
-> smoke is skipped
```

Without `needs: test`, the two jobs could run independently.

This could waste CI resources by building and testing the Docker image even when the source-code tests have already failed.

Using `needs` therefore creates a clear pipeline order:

```text
test
  |
  v
smoke
  |
  v
push
```

---

## Question 6

### How long did the CI runs take?

The first successful GitHub Actions workflow showed approximately:

```text
test: 23 seconds
smoke: 1 minute 43 seconds
```

The displayed job durations therefore represented approximately:

```text
2 minutes 6 seconds
```

of job execution.

A second workflow was then triggered using:

```bash
git commit --allow-empty -m "ci"
git push
```

The second workflow showed:

```text
Total duration: 2 minutes 20 seconds
test: 23 seconds
smoke: 1 minute 53 seconds
```

The second run was therefore not faster overall.

Although the workflow uses the `setup-uv` cache, CI execution time is also affected by factors such as:

- GitHub-hosted runner startup;
- network performance;
- dependency restoration;
- Docker image building;
- Docker layer availability;
- GitHub infrastructure variability.

Therefore, no clear improvement in total runtime was observed during these two runs.

The cache can still reduce repeated dependency downloads, but in these executions the variation in the Docker smoke job and runner environment was large enough to hide any overall time improvement.

---

## Question 7

### Why tag the Docker image with the commit SHA instead of only `latest`?

The Git commit SHA uniquely identifies the exact source-code revision that produced a Docker image.

For example:

```text
ghcr.io/<repository>:<commit-sha>
```

points to a specific code revision.

In contrast:

```text
latest
```

is a mutable tag.

For example:

```text
Monday:
Machine A pulls latest

Tuesday:
A new image replaces latest

Wednesday:
Machine B pulls latest
```

Both machines appear to run:

```text
latest
```

but they may actually be running different application versions.

Using the commit SHA makes the image:

- traceable;
- reproducible;
- auditable;
- easier to roll back;
- directly linked to the source code that produced it.

---

## Question 8

### Why declare GitHub token permissions explicitly?

The image-publishing job uses:

```yaml
permissions:
  contents: read
  packages: write
```

The job needs:

```text
contents: read
```

to access repository content.

It needs:

```text
packages: write
```

to publish the Docker image to GitHub Container Registry.

Explicitly declaring only the permissions that are needed follows the principle of least privilege.

If a workflow step or third-party action were compromised, giving the GitHub token unnecessary permissions could allow it to modify additional repository resources.

Restricting the permissions reduces the possible impact of a compromised workflow.

---

## Question 9

### What happens with a failing protected pull request?

A dedicated branch was created:

```text
lab5-break-test
```

The `category_from_filename()` function was intentionally modified from the correct behavior to:

```python
return "WRONG"
```

The branch was pushed and a pull request targeting:

```text
main
```

was created.

GitHub Actions produced the expected result:

```text
test   -> failed
smoke  -> skipped
push   -> skipped
```

The `test` job failed because the unit test expected the correct Food-11 category but received:

```text
WRONG
```

The `smoke` job was skipped because it depends on:

```yaml
needs: test
```

The `push` job was also skipped because it is intended only for the `main` branch after successful previous jobs.

The protected `main` ruleset required the CI checks to succeed, so the pull request did not satisfy the required merge conditions while the test was failing.

The code was then corrected back to:

```python
return CATEGORIES[label]
```

The fix was committed and pushed to the same branch.

GitHub Actions automatically reran the workflow.

After the fix:

```text
test   -> passed
smoke  -> passed
```

The pull request then satisfied the required CI conditions and could be merged.

This demonstrates how branch protection converts testing from an informal development convention into an automatically enforced repository policy.

---

## Question 10

### What did the quality gate decide?

The existing registered model was:

```text
Model name: food11
Champion version: 2
Champion test_accuracy: 0.759124
```

The test split contained:

```text
n = 1096 images
```

The promotion rule was:

```text
candidate_accuracy >= champion_accuracy + 2 * se
```

where:

```text
se = sqrt(p * (1 - p) / n)
```

and:

```text
p = champion test accuracy
n = number of images in the test split
```

Using:

```text
p = 0.759124
n = 1096
```

the promotion script calculated:

```text
Standard error = 0.012917
2 * SE = 0.025833
```

Therefore:

```text
Required candidate accuracy
= 0.759124 + 0.025833
= 0.784957
```

A candidate therefore had to achieve at least approximately:

```text
78.50%
```

test accuracy before replacing the current champion.

### Candidate 1

Candidate 1 was deliberately trained using a very small learning rate:

```text
epochs = 5
learning rate = 0.00001
batch size = 32
```

Training run:

```text
Run ID:
089992c2c3a646048465bb4881a038d9
```

It was registered as:

```text
Model version: 3
```

The promotion gate produced:

```text
Candidate version: 3
Champion version before gate: 2
Candidate accuracy: 0.566606
Champion accuracy: 0.759124
Test size: 1096
Standard error: 0.012917
2 * SE: 0.025833
Required candidate accuracy: 0.784957
Decision: assigned_challenger
```

Candidate 1 achieved approximately:

```text
56.66%
```

which was substantially below the required:

```text
78.50%
```

Therefore Candidate 1 was not promoted to champion.

Instead:

```text
challenger -> version 3
champion -> version 2
```

---

### Candidate 2

Candidate 2 was trained using:

```text
epochs = 5
learning rate = 0.001
batch size = 32
```

Training run:

```text
Run ID:
845eaa4bbf264c9883d8e8051302a4b1
```

It was registered as:

```text
Model version: 4
```

The promotion gate produced:

```text
Candidate version: 4
Champion version before gate: 2
Candidate accuracy: 0.572080
Champion accuracy: 0.759124
Test size: 1096
Standard error: 0.012917
2 * SE: 0.025833
Required candidate accuracy: 0.784957
Decision: assigned_challenger
```

Candidate 2 achieved approximately:

```text
57.21%
```

which was also below the required:

```text
78.50%
```

Therefore Candidate 2 was not promoted.

The `challenger` alias was moved to version 4 while the existing champion remained:

```text
champion -> version 2
challenger -> version 4
```

An MLflow alias points to one model version at a time, so assigning version 4 as the challenger replaced version 3 as the version referenced by the `challenger` alias.

### Quality Gate Summary

| Item               | Candidate 1 | Candidate 2 |
| ------------------ | ----------: | ----------: |
| Model version      |           3 |           4 |
| Candidate accuracy |    0.566606 |    0.572080 |
| Champion version   |           2 |           2 |
| Champion accuracy  |    0.759124 |    0.759124 |
| Test size          |        1096 |        1096 |
| Standard error     |    0.012917 |    0.012917 |
| 2 × SE             |    0.025833 |    0.025833 |
| Required accuracy  |    0.784957 |    0.784957 |
| Decision           |  Challenger |  Challenger |

The value:

```text
2 * SE = 0.025833
```

corresponds to approximately:

```text
2.5833 percentage points
```

The experiment demonstrates the purpose of the quality gate.

Both newly trained models were significantly weaker than the existing champion, and the automated promotion logic prevented either one from replacing it.

The existing version 2 therefore remained the production-quality champion.

---

## Question 11

### How could `promote.py` run automatically if MLflow is local?

There are two main approaches.

### Option 1 - Self-hosted GitHub Actions runner

A self-hosted GitHub Actions runner could be installed on a machine that has network access to the MLflow server.

The workflow could then execute:

```text
promote.py
```

directly against the internal MLflow tracking server.

This keeps MLflow private while still allowing automated promotion decisions.

### Option 2 - Host MLflow on accessible infrastructure

MLflow could be deployed on infrastructure that GitHub Actions can reach, such as:

- a cloud virtual machine;
- a managed server;
- an organization-controlled remote environment;
- DagsHub or another remote MLflow-compatible service.

Credentials and connection information could then be stored using GitHub Actions secrets.

This would allow a GitHub-hosted runner to communicate with MLflow securely.

For the current lab, MLflow remains local, so promotion is invoked manually from the development environment.

---

## Question 12

### End-to-end pipeline

The final pipeline can be represented as:

```text
Developer
   |
   | git push / pull request
   v
GitHub
   |
   | AUTOMATIC
   v
test job
   |
   | checkout repository
   | setup uv
   | restore dependency cache
   | uv sync
   | ruff
   | pytest
   v
smoke job
   |
   | docker build
   | start API with SKIP_MODEL=1
   | GET /health
   v
push job
(main branch only)
   |
   | authenticate with GHCR
   | build Docker image
   | push Docker image
   | image tag = Git commit SHA
   v
GitHub Container Registry
   |
   | exact CODE version
   | determined by SHA tag
   v
Running inference container
   |
   | application startup
   v
MLflow Model Registry
   |
   | MODEL_URI
   | models:/food11@champion
   v
Registered Food-11 model
```

The model promotion path is:

```text
Training
   |
   v
MLflow Tracking Run
   |
   | metrics + artifacts
   v
Register candidate model
   |
   v
MLflow Model Registry
   |
   | HUMAN invocation in current setup
   v
promote.py
   |
   | calculate:
   |
   | champion accuracy
   | candidate accuracy
   | test-set size
   | standard error
   | champion + 2 * SE
   |
   +-----------------------------------+
   |                                   |
   v                                   v
Candidate passes                 Candidate fails
quality gate                     quality gate
   |                                   |
   v                                   v
Set champion alias               Set challenger alias
to candidate                     to candidate
```

### Automatic steps

The following operations are automatic once the GitHub workflow is triggered:

- repository checkout;
- environment setup;
- dependency synchronization;
- Ruff linting;
- pytest unit tests;
- Docker image build for the smoke test;
- API health probe;
- Docker image publishing on `main`;
- tagging the image using the Git commit SHA.

Once `promote.py` is invoked, the promotion decision itself is also automatic.

It calculates the quality threshold and decides whether to assign:

```text
champion
```

or:

```text
challenger
```

without requiring a human to manually compare the metrics.

### Human-controlled steps in the current implementation

The following steps are still manually initiated:

- training a new model;
- registering the model candidate;
- running `promote.py`;
- deployment of the published Docker image.

Because the MLflow server is currently local, GitHub-hosted Actions cannot directly invoke the promotion script.

This could later be automated using a self-hosted runner or remotely accessible MLflow server.

### Code version

The application code version is identified by:

```text
Git commit SHA
```

and the published Docker image is tagged using that SHA.

### Model version

The model deployed by the inference application is selected independently using the MLflow alias:

```text
models:/food11@champion
```

This means the system separates:

```text
CODE VERSION
```

from:

```text
MODEL VERSION
```

which is an important MLOps principle.

---

# Final Validation

Before completing the lab, the local project was validated again.

Ruff:

```text
All checks passed!
```

Pytest:

```text
5 passed, 1 warning in 14.28s
```

The warning was a Starlette deprecation warning concerning the use of `httpx` with `starlette.testclient`.

It did not cause any test failure.

Data contract validation:

```text
PASS - Exactly 11 class folders
PASS - Images are valid RGB 128x128
PASS - Minimum images per class
PASS - No duplicate images across splits
PASS - Training/validation class distribution

DATA CONTRACT: PASS
```

Therefore the final local validation confirms that:

```text
linting      -> PASS
unit tests   -> PASS
data contract -> PASS
```

---

# Conclusion

Lab 5 adds a complete CI/CD and model-quality-control layer to the MLOps project.

The code-release workflow is:

```text
CODE RELEASE

git push / pull request
        |
        v
GitHub Actions
        |
        +-> Ruff
        |
        +-> pytest
        |
        +-> Docker smoke test
        |
        v
main branch
        |
        v
Docker image published to GHCR
        |
        v
Image tagged with exact Git commit SHA
```

The model-release workflow is:

```text
MODEL RELEASE

Training run
     |
     v
MLflow Tracking
     |
     v
Registered candidate
     |
     v
Statistical quality gate
     |
     +-> PASS -> champion
     |
     +-> FAIL -> challenger
```

The final architecture therefore separates two different lifecycle decisions:

```text
Code release
!=
Model promotion
```

GitHub Actions protects the software-delivery pipeline, while MLflow aliases and the statistical quality gate protect the model-delivery pipeline.

In the performed experiment, both new candidate models were weaker than the existing model version 2.

The quality gate correctly rejected both candidates as champion replacements, demonstrating that an automated MLOps pipeline can prevent a weaker model from replacing the currently approved model.
