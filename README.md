# Research Data Pipeline

**Privacy-first data management tooling for research projects**

This repository contains a tool I've built to manage and store data. Feel free to fork or to use it as inspo. 


## Features

- Automated file ingestion from Downloads with regex-based routing
- SHA256 deduplication to avoid redundant storage
- Timestamped, normalized filenames (`YYYY-MM-DDTHHMMS_slug.ext`)
- Provenance tracking via per-project manifest files
- RStudio project scaffolding with `renv` for reproducibility
- Pre-commit hooks that block accidental data commits
- R helper functions using `{here}` for path management
- Data validation with `{pointblank}` (optional)


## Privacy & Security

### What's in this repo?
- Python CLI tools
- Configuration templates
- R helper functions
- Project scaffolding templates
- Documentation

### Protection mechanisms

1. **`.gitignore`**: Blocks all data file extensions and `data/` directories
2. **Pre-commit hook**: Actively prevents data files from being staged
3. **Template structure**: Projects live outside this repo in `projects_base`


## Prerequisites

- Python 3.10+
- R 4.0+ and RStudio (recommended)
- Git
- macOS (Linux/Windows notes included as comments)


## Setup

### 1. Clone this repository

```bash
git clone <your-repo-url>
cd research-pipeline
```

### 2. Install the pre-commit hook

This prevents accidental data commits:

```bash
git config core.hooksPath tooling/hooks
```

**Test it** (should block the commit):
```bash
# This should fail:
touch test.csv
git add test.csv
git commit -m "test"
# You should see a red error message blocking the commit
git reset HEAD test.csv
rm test.csv
```

### 3. Set up Python environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install pyyaml pandas python-dateutil
```

**Note**: You'll need to activate the virtual environment (`source .venv/bin/activate`) each time you open a new terminal session.

### 4. Configure your paths

Edit `tooling/config.yaml`:

```yaml
downloads_dir: "/Users/YOUR_USERNAME/Downloads"
projects_base: "/Users/YOUR_USERNAME/Projects"
```

**Important**: Replace `REPLACE_ME` with your actual username/paths.

### 5. (Optional) Install R packages

These are only needed when you start working with data in R:

```r
install.packages(c("here", "readr", "fs", "pointblank", "renv"))
```

## Usage

### Creating a new project

The `init-project` command scaffolds a new RStudio-ready project:

```bash
# Activate Python venv first
source .venv/bin/activate

# Create a new project
python tooling/ingest.py init-project --name moral-learning
```

This creates:
```
~/Projects/moral-learning/
  ├─ moral-learning.Rproj
  ├─ data/
  │   ├─ raw/
  │   └─ clean/
  ├─ catalog/
  ├─ R/
  │   ├─ data_helpers.R
  │   └─ validation_suites/
  │       └─ default_pointblank.R
  └─ renv/
```

**Next steps** for the new project:
1. Open `moral-learning.Rproj` in RStudio
2. Run `renv::init()` to initialize the reproducible environment
3. Install required packages: `install.packages(c("here", "readr", "fs", "pointblank"))`
4. Run `renv::snapshot()` to save your package versions

### Ingesting data files

The pipeline can automatically route files based on patterns in `config.yaml`.

**Option 1: Automatic routing from Downloads**

```bash
# Route all matching files from your Downloads folder
python tooling/ingest.py route --from-downloads
```

Files are matched against regex patterns in `config.yaml` and moved to the appropriate project.

**Option 2: Manual routing**

```bash
# Add specific files to a project
python tooling/ingest.py add ~/Downloads/survey_data.csv --project moral-learning --subdir data/raw

# Add multiple files
python tooling/ingest.py add ~/Downloads/*.csv --project census-inequality --subdir data/raw
```

**What happens during ingest:**
1. File size stabilizes (waits for downloads to complete)
2. SHA256 checksum computed
3. Duplicate detection (skips if already ingested)
4. File renamed: `2025-01-15T143022_survey_data.csv`
5. Moved to project's `data/raw/` directory
6. Row added to `catalog/manifest.csv` with provenance

### Checking ingestion status

```bash
# View recent ingestions for a project
python tooling/ingest.py status --project moral-learning --limit 20
```

### Working with data in R

Once files are ingested, open the project in RStudio:

```r
library(dplyr)
source("R/data_helpers.R")

# Load the most recent file from a project subfolder
df_raw <- load_raw_latest("SML.*\\.csv$", subdir = "Moral_Learning")
# Or: df_raw <- load_raw_latest("morebench.*\\.csv$", subdir = "MoreBench")
# Or: df_raw <- load_raw_latest("MC.*\\.csv$", subdir = "Reflective_Equilibrium")

# Clean your data
df_clean <- df_raw %>%
  filter(!is.na(participant_id)) %>%
  mutate(response_coded = recode_responses(response))

# Save cleaned data back to the same project folder
save_clean(
  df_clean,
  base = "SML_criminal_clean.csv",
  subdir = "Moral_Learning",
  notes = "Removed NAs, recoded responses",
  derived_from = ""  # Optionally add SHA256 from manifest
)

# Validate the cleaned data
validate_clean(df_clean, suite = "default")
```

**Helper functions** (in `R/data_helpers.R`):
- `data_dir(subdir)` → path to any subdirectory using `{here}`
- `raw_dir(subdir)` → path to data directory (default: `data/raw`)
- `clean_dir()` → path to `data/clean/`
- `manifest_path()` → path to `catalog/manifest.csv`
- `load_raw_latest(pattern, subdir)` → reads newest matching file from subfolder
- `save_clean(df, base, subdir, notes, derived_from)` → saves with timestamp, updates manifest
- `validate_clean(df, suite)` → runs `{pointblank}` validation suite
- `list_files(subdir, pattern)` → list all files in a subfolder
- `read_manifest()` → read the full provenance manifest

**See full examples:** `R/examples.md`

---

## Manifest Structure

Each project has a `catalog/manifest.csv` that tracks all data files:

| Column | Description |
|--------|-------------|
| `project` | Project name |
| `stage` | `raw` or `clean` |
| `path` | Absolute path to file |
| `ts` | Timestamp of ingestion |
| `original_name` | Original filename |
| `size_bytes` | File size |
| `sha256` | SHA256 checksum |
| `source` | Where file came from (e.g., "Downloads") |
| `notes` | User-provided notes |
| `action` | `ingested`, `duplicate_skipped`, etc. |
| `derived_from` | SHA256 of parent file (for clean stage) |
| `code_commit` | Git commit hash of cleaning code |

**Example row** (raw file):
```csv
moral-learning,raw,/Users/me/Projects/moral-learning/data/raw/2025-01-15T143022_survey.csv,2025-01-15T14:30:22,survey_data.csv,524288,a1b2c3...,Downloads,"Initial survey wave",ingested,,,
```

**Example row** (clean file):
```csv
moral-learning,clean,/Users/me/Projects/moral-learning/data/clean/2025-01-15T150000_survey_clean.csv,2025-01-15T15:00:00,survey_clean.csv,489012,d4e5f6...,R/cleaning.R,"Removed NAs, recoded",saved,a1b2c3...,9a8b7c6
```

---

## Configuration Reference

### Routing patterns (`tooling/config.yaml`)

Patterns use Python regex syntax (case-insensitive by default):

```yaml
routing:
  - pattern: "^acs_.*\\.(csv|zip)$"      # Starts with "acs_", ends .csv or .zip
    project: "census-inequality"
    subdir: "data/raw"

  - pattern: "^survey[_-].*\\.csv$"      # Starts with "survey_" or "survey-"
    project: "survey-data"
    subdir: "data/raw"

  - pattern: ".*"                         # Catch-all (must be last!)
    project: "misc-datasets"
    subdir: "data/raw"
```

**Tips**:
- Patterns are tested in order; first match wins
- Use `\\` to escape special regex characters in YAML
- Always include a catch-all `.*` pattern last
- Test patterns at [regex101.com](https://regex101.com/) (use Python flavor)

### Naming conventions

Configured in `config.yaml`:

```yaml
naming:
  timestamp_format: "%Y-%m-%dT%H%M%S"  # ISO 8601-like (filesystem-safe)
  slug_maxlen: 60                       # Max length for filename slug
  lower_ext: true                       # Convert extensions to lowercase
  preserve_basename: true               # Keep original name in slug
```

**Example transformation**:
```
Before: Survey Data (Wave 1) FINAL_v3.CSV
After:  2025-01-15T143022_survey_data_wave_1_final_v3.csv
```


