# R Data Pipeline Examples

This document shows typical workflows for working with the research data pipeline in R.

## Prerequisites

Make sure you have the required packages installed:

```r
install.packages(c("here", "fs", "readr", "pointblank", "digest", "dplyr"))

# Optional packages for specific file formats:
install.packages(c("haven", "readxl", "arrow"))
```

---

## Setup

### 1. Open your project in RStudio

Double-click the `.Rproj` file for your project.

### 2. Initialize renv (first time only)

```r
# Initialize reproducible environment
renv::init()

# Install required packages
install.packages(c("here", "fs", "readr", "pointblank", "digest", "dplyr"))

# Snapshot your package versions
renv::snapshot()
```

### 3. Load helper functions

```r
source("R/data_helpers.R")
```

You should see:
```
Data pipeline helpers loaded successfully!
Available functions:
  - raw_dir(), clean_dir(), manifest_path()
  - load_raw_latest(pattern)
  - save_clean(df, base, notes)
  - validate_clean(df, suite)
  - list_raw(pattern), list_clean(pattern)
  - read_manifest()
```

---

## Basic Workflow

### Example 1: Load, clean, and save (using project subfolders)

```r
library(dplyr)
source("R/data_helpers.R")

# Load the most recent file from a project subfolder
df_raw <- load_raw_latest("SML.*\\.csv$", subdir = "Moral_Learning")
# Loading: SML_criminal_2025-11-19T142241.csv
# Loaded 500 rows, 15 columns

# Or from MoreBench folder
df_morebench <- load_raw_latest("morebench.*\\.csv$", subdir = "MoreBench")

# Or from traditional data/raw folder
df_other <- load_raw_latest("survey.*\\.csv$", subdir = "data/raw")

# Inspect the data
str(df_raw)
summary(df_raw)

# Clean the data
df_clean <- df_raw %>%
  filter(!is.na(participant_id)) %>%
  filter(age >= 18, age <= 100) %>%
  mutate(
    condition = tolower(condition),
    response = as.numeric(response)
  ) %>%
  select(-contains("metadata"))

# Save the cleaned data back to the same project folder
save_clean(
  df_clean,
  base = "SML_criminal_clean.csv",
  subdir = "Moral_Learning",
  notes = "Removed NAs, filtered age 18-100, cleaned condition variable",
  derived_from = ""  # Optionally add SHA256 of raw file from manifest
)
# Saving to: SML_criminal_clean_2025-11-19T143022.csv
# Saved 487 rows, 12 columns
# Updated manifest: /path/to/catalog/manifest.csv

# Or save to the traditional data/clean folder
save_clean(
  df_clean,
  base = "analysis_clean.csv",
  subdir = "data/clean",
  notes = "Final cleaned dataset"
)
```

### Example 2: Validate cleaned data

```r
# Run validation suite on cleaned data
validate_clean(df_clean)

# The validation report will show:
# - Any structural issues (missing columns, all-NA columns, etc.)
# - Any custom validation rules you've defined
# - Pass/fail status for each check

# Validation report saved automatically to data/clean/validation_*.rds
```

### Example 3: Load specific file types

```r
# CSV (default)
df <- load_raw_latest("data.*\\.csv$")

# Stata files
df <- load_raw_latest("study.*\\.dta$")

# SPSS files
df <- load_raw_latest("survey.*\\.sav$")

# Excel files
df <- load_raw_latest("experiment.*\\.xlsx$")

# RDS files
df <- load_raw_latest("analysis.*\\.rds$")

# Custom reader with options
df <- load_raw_latest(
  "survey.*\\.csv$",
  reader = readr::read_csv,
  col_types = cols(
    participant_id = col_character(),
    age = col_integer(),
    response = col_double()
  )
)
```

---

## Advanced Examples

### Example 4: Work with multiple files across folders

```r
# List all files in a specific project folder
morebench_files <- list_files("MoreBench")
print(morebench_files)

# List files matching a pattern in Moral_Learning
sml_files <- list_files("Moral_Learning", pattern = "SML")
print(sml_files)

# List all raw files in traditional data/raw folder
raw_files <- list_raw(subdir = "data/raw")
print(raw_files)

# Load and combine multiple SML files
library(purrr)
all_sml <- sml_files %>%
  map_dfr(~{
    df <- readr::read_csv(.x, show_col_types = FALSE)
    df$source_file <- basename(.x)
    df
  })

# Clean and save back to Moral_Learning folder
df_clean <- all_sml %>%
  filter(!is.na(participant_id)) %>%
  # ... more cleaning ...

save_clean(df_clean, "SML_combined_clean.csv",
          subdir = "Moral_Learning",
          notes = "Combined 3 SML studies, removed NAs")
```

### Example 5: Use manifest for provenance

```r
# Read the manifest
manifest <- read_manifest()

# Find the SHA256 of a specific raw file
raw_sha <- manifest %>%
  filter(stage == "raw", grepl("survey_data", original_name)) %>%
  pull(sha256) %>%
  first()

# Use it when saving cleaned data
save_clean(
  df_clean,
  "survey_clean.csv",
  notes = "Cleaning pipeline v2.0",
  derived_from = raw_sha  # Links clean file to raw file
)

# View cleaning history
manifest %>%
  filter(stage == "clean") %>%
  select(ts, original_name, notes, derived_from, code_commit) %>%
  print()
```

### Example 6: Custom validation suite

Create a new file: `R/validation_suites/strict_pointblank.R`

```r
library(pointblank)

agent <- create_agent(
  label = "Strict Validation for Survey Data",
  actions = action_levels(warn_at = 0.01, stop_at = 0.05)
)

agent <- agent %>%
  # Participant ID must exist and be unique
  col_exists(vars(participant_id)) %>%
  col_is_unique(vars(participant_id)) %>%

  # Age must be reasonable
  col_vals_between(vars(age), 18, 100) %>%
  col_vals_not_null(vars(age)) %>%

  # Condition must be valid
  col_vals_in_set(vars(condition), set = c("control", "treatment")) %>%

  # Response must be in Likert scale
  col_vals_between(vars(response), 1, 7) %>%

  # No duplicate participant-trial pairs
  rows_distinct(vars(participant_id, trial))

agent
```

Then use it:

```r
validate_clean(df_clean, suite = "strict")
```

### Example 7: Save in different formats

```r
# Save as CSV (default)
save_clean(df_clean, "analysis.csv", notes = "Final cleaned dataset")

# Save as RDS (preserves R data types exactly)
save_clean(df_clean, "analysis.rds", notes = "Final cleaned dataset")

# Save as Parquet (efficient for large datasets)
save_clean(df_clean, "analysis.parquet", notes = "Final cleaned dataset")
```

### Example 8: Automated cleaning script

Create `R/cleaning_pipeline.R`:

```r
#!/usr/bin/env Rscript

library(dplyr)
source("R/data_helpers.R")

message("Starting automated cleaning pipeline...")

# Load raw data
df_raw <- load_raw_latest("SML_criminal.*\\.csv$")

# Clean
df_clean <- df_raw %>%
  # Remove test participants
  filter(!grepl("^TEST", participant_id)) %>%

  # Filter valid age range
  filter(age >= 18, age <= 100) %>%

  # Recode variables
  mutate(
    condition = factor(condition, levels = c("control", "treatment")),
    response = as.numeric(response)
  ) %>%

  # Remove unnecessary columns
  select(-starts_with("metadata_")) %>%

  # Remove rows with missing critical data
  filter(!is.na(participant_id), !is.na(response))

# Validate
agent <- validate_clean(df_clean)

# Check if validation passed
if (all(agent$validation_set$all_passed)) {
  message("Validation PASSED")

  # Get SHA256 of raw file from manifest
  manifest <- read_manifest()
  raw_sha <- manifest %>%
    filter(stage == "raw") %>%
    slice_max(ts, n = 1) %>%
    pull(sha256)

  # Save
  save_clean(
    df_clean,
    "SML_criminal_clean.csv",
    notes = "Automated pipeline: removed test participants, filtered age, recoded variables",
    derived_from = raw_sha
  )

  message("Pipeline completed successfully!")
} else {
  stop("Validation FAILED - clean data NOT saved")
}
```

Run it from terminal:

```bash
Rscript R/cleaning_pipeline.R
```

---

## Tips & Best Practices

### 1. Always work in RStudio projects

Open the `.Rproj` file to ensure `here::here()` works correctly.

### 2. Use renv for reproducibility

```r
renv::init()       # First time
renv::snapshot()   # After installing packages
renv::restore()    # On new machine or after clone
```

### 3. Document your cleaning steps

Use detailed `notes` parameter in `save_clean()` to document what you did:

```r
save_clean(
  df_clean,
  "dataset_clean.csv",
  notes = "v1.0: Removed NAs in age/response, filtered age 18-100, recoded condition to lowercase, excluded practice trials"
)
```

### 4. Check the manifest regularly

```r
manifest <- read_manifest()
View(manifest)

# See recent activity
manifest %>%
  arrange(desc(ts)) %>%
  head(10)
```

### 5. Use validation suites

Create custom validation suites for each dataset type to catch issues early.

### 6. Version your analysis code

If your project is a git repo, the `code_commit` field in the manifest will automatically record which version of your code created each clean file.

---

## Troubleshooting

### Package not found

```r
# Check if package is installed
"here" %in% installed.packages()[,"Package"]

# Install missing packages
install.packages("here")
```

### Cannot find files

```r
# Check your working directory
here::here()  # Should be project root

# List raw files
list_raw()

# Check if raw data directory exists
raw_dir()
fs::dir_ls(raw_dir())
```

### Validation fails

```r
# Run validation and inspect results
agent <- validate_clean(df_clean)

# View detailed results
agent$validation_set

# Get summary
pointblank::get_agent_report(agent)
```

### Manifest issues

```r
# Check if manifest exists
manifest_path()
fs::file_exists(manifest_path())

# Read manifest
manifest <- read_manifest()

# If corrupted, you can recreate header:
# WARNING: This will erase existing manifest!
# readr::write_csv(
#   data.frame(project = character(), stage = character(), ...),
#   manifest_path()
# )
```

---

## Additional Resources

- [here package](https://here.r-lib.org/)
- [fs package](https://fs.r-lib.org/)
- [readr package](https://readr.tidyverse.org/)
- [pointblank package](https://rich-iannone.github.io/pointblank/)
- [renv package](https://rstudio.github.io/renv/)
