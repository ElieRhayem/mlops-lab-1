# Lab 1 - Git/DVC and Data Preparation

## Adopted DVC Storage Solution

For this lab, I used the recommended **local DVC remote** solution instead of DagsHub because of the size of the Food-11 dataset.

The Git repository and the DVC storage are separate.

- GitHub stores the source code, project configuration, `.gitignore`, and DVC pointer files such as `data.dvc`.
- The actual Food-11 data is versioned using DVC.
- The DVC remote is a local folder located outside the Git repository.
- No DagsHub credentials were required.

This allowed me to use `dvc push`, `dvc pull`, and `dvc checkout` while avoiding the need to upload the complete dataset to DagsHub.

## Question 1

### What files were created by `uv init` and what are they used for?

`uv init` initialized the Python project.

The important generated files include `pyproject.toml`, which contains project metadata, the required Python version, and project dependencies. A `.python-version` file can be used to specify the Python version associated with the project. A README file provides project documentation, while the generated Python source files provide the initial source-code structure.

After adding Pillow using `uv add pillow`, Pillow was registered as a project dependency and `uv.lock` recorded the resolved dependency versions to improve reproducibility.

## Question 2

### What files were created by DVC and what are they used for?

Running `dvc init` initialized DVC inside the same repository as Git.

The `.dvc` directory contains DVC configuration and internal project information. `.dvc/config` stores project-level DVC configuration such as the configured remote.

`.dvc/.gitignore` prevents DVC internal cache and temporary information from accidentally being tracked by Git.

`.dvcignore` can be used to specify files that DVC itself should ignore.

The configuration files required to reproduce the repository setup should be tracked by Git, while DVC cache and temporary files should not be pushed to GitHub.

## Question 3

### Where are credentials stored, what alternatives to `--global` exist, and should credentials be pushed to GitHub?

For my implementation this question does not directly apply because I used a local DVC remote and therefore did not require authentication credentials.

In the DagsHub example, using `--global` stores the configuration outside the project in DVC's global user configuration.

DVC also supports repository/project configuration and local configuration. Local configuration can be used for sensitive or machine-specific information.

Credentials, passwords, access tokens, and other secrets should never be committed or pushed to GitHub.

## Question 4

### What happened to `.gitignore` after `dvc add data`?

After running `dvc add data`, DVC added the `data` directory to `.gitignore`.

This prevents Git from tracking the actual Food-11 images.

The large dataset is therefore managed by DVC instead of Git, while Git only tracks the lightweight `data.dvc` pointer file.

## Question 5

### What does `data.dvc` contain?

`data.dvc` is a DVC metadata/pointer file.

It contains information describing the DVC-tracked `data` directory, including its path and a checksum/hash representing the corresponding version of the data.

It does not contain the actual images.

Git versions the `data.dvc` file, while DVC versions the actual dataset.

## Question 6

### What is visible on GitHub and in the DVC remote?

The GitHub repository contains the project source code, configuration files, `.gitignore`, and `data.dvc`.

The actual Food-11 image files are not stored in GitHub because the `data` directory is ignored by Git.

`data.dvc` serves as the pointer that identifies the corresponding version of the data.

Because I used the recommended local-remote solution instead of DagsHub, the actual DVC data is stored in the configured local DVC remote. The remote uses DVC's cache/storage representation rather than being a normal copy of the original directory structure.

## Question 7

### What happens after cloning the Git repository into a new directory?

After cloning the GitHub repository into a completely new directory, the Git-tracked source files and `data.dvc` are available, but the actual `data` directory is not initially restored.

The command required to retrieve the DVC-tracked dataset is:

```bash
dvc pull
```

DVC reads the pointer/configuration and restores the required data from the configured DVC remote.

## Data Preparation

The Food-11 raw dataset was stored under:

```text
data/food11_raw/training
data/food11_raw/evaluation
data/food11_raw/validation
```

A Python script was created at:

```text
src/food11/data.py
```

The script converts the raw Food-11 dataset into two additional datasets:

```text
data/food11_processed
data/food11_processed_mini
```

For `food11_processed`, each image is resized to 128 × 128 pixels and reorganized into a directory corresponding to its food category.

For example:

```text
data/food11_processed/training/Bread/
data/food11_processed/training/Dairy product/
data/food11_processed/training/Dessert/
```

The category is determined from the numerical prefix of the original Food-11 filename.

`food11_processed_mini` follows the same structure but contains at most 100 images for each category in each dataset split. It provides a smaller dataset for development and testing.

Pillow was added as a project dependency using:

```bash
uv add pillow
```

The preprocessing script was executed using:

```bash
uv run python ./src/food11/data.py
```

After preprocessing, the updated complete `data` directory was tracked again using DVC.

## Question 8

### What happens after checking out the old Git and DVC version?

I first identified the commits that modified `data.dvc` using:

```bash
git log --oneline -- data.dvc
```

I then checked out the commit corresponding to the version before the processed datasets were generated:

```bash
git checkout <old-commit-hash>
dvc checkout
```

After `dvc checkout`, `food11_processed` and `food11_processed_mini` were no longer present because the `data.dvc` pointer from that Git commit represents the earlier version of the dataset containing only the raw data.

I then returned to the latest version using:

```bash
git checkout main
dvc checkout
```

The processed and mini datasets were restored.

This demonstrates how Git and DVC work together: Git versions the code and DVC metadata/pointers, while DVC versions and restores the actual data corresponding to each Git revision.
