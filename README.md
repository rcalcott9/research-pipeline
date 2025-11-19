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

---

## Testing Your Setup

Run these commands to verify everything works. First, make sure you have:
1. Activated your Python virtual environment: `source .venv/bin/activate`
2. Edited `tooling/config.yaml` with your actual paths

### Complete Test Workflow

```bash
# ============================================================================
# Test 1: Project Initialization
# ============================================================================
python tooling/ingest.py init-project --name test-project

# Verify structure was created
ls -la ~/Projects/test-project
# Should show: data/raw, data/clean, catalog, R, *.Rproj, README.md

# ============================================================================
# Test 2: File Ingestion with Manual Add
# ============================================================================
# Create two dummy CSV files
echo -e "name,age,city\nAlice,30,NYC\nBob,25,LA" > /tmp/test_data_1.csv
echo -e "id,value\n1,100\n2,200" > /tmp/test_data_2.csv

# Ingest first file
python tooling/ingest.py add /tmp/test_data_1.csv --project test-project --subdir data/raw

# Expected output:
#   Stabilizing: test_data_1.csv [OK]
#   Computing SHA256... <hash>...
#   Moving to: test-project/data/raw/2025-XX-XXTXXXXXX_test_data_1.csv
#   ✅ Ingested successfully

# Verify the file was moved and renamed
ls -la ~/Projects/test-project/data/raw/
# Should show a timestamped file: 2025-XX-XXTXXXXXX_test_data_1.csv

# Check manifest was created and populated
cat ~/Projects/test-project/catalog/manifest.csv
# Should show header + 1 data row with sha256, timestamp, etc.

# ============================================================================
# Test 3: Duplicate Detection
# ============================================================================
# Create an identical copy of the first file
echo -e "name,age,city\nAlice,30,NYC\nBob,25,LA" > /tmp/test_data_1_copy.csv

# Try to ingest it
python tooling/ingest.py add /tmp/test_data_1_copy.csv --project test-project --subdir data/raw

# Expected output:
#   Stabilizing: test_data_1_copy.csv [OK]
#   Computing SHA256... <same hash>...
#   ⚠️  Duplicate detected (SHA256 match)
#   Existing: ~/Projects/test-project/data/raw/2025-XX-XXTXXXXXX_test_data_1.csv
#   Skipping ingest, recording alias in manifest

# Check manifest - should have 2 rows now (original + duplicate)
cat ~/Projects/test-project/catalog/manifest.csv | tail -2

# The duplicate row should have action=duplicate_skipped

# ============================================================================
# Test 4: Routing with Patterns
# ============================================================================
# Create files matching different patterns from config.yaml
echo -e "survey,response\n1,5\n2,3" > /tmp/surveyA_wave1.csv
echo -e "acs_year,value\n2020,100" > /tmp/acs_2020.csv

# First, create the projects that routing expects (from config.yaml)
python tooling/ingest.py init-project --name moral-learning
python tooling/ingest.py init-project --name census-inequality

# Test routing
python tooling/ingest.py route /tmp/surveyA_wave1.csv /tmp/acs_2020.csv

# Expected output:
#   File: surveyA_wave1.csv
#   Routed to: moral-learning/data/raw
#   ...
#   File: acs_2020.csv
#   Routed to: census-inequality/data/raw
#   ...
#   Summary: 2 ingested, 0 duplicates, 0 not routed

# Verify files were routed to correct projects
ls ~/Projects/moral-learning/data/raw/
ls ~/Projects/census-inequality/data/raw/

# ============================================================================
# Test 5: Status Command
# ============================================================================
# View manifest for test-project
python tooling/ingest.py status --project test-project --limit 10

# Expected output: table showing recent ingestions with columns:
#   ts, stage, original_name, action, size_bytes, sha256

# ============================================================================
# Test 6: Collision Handling (Same Timestamp)
# ============================================================================
# Rapidly ingest multiple different files
# (They may get the same timestamp and trigger collision handling)
echo "a" > /tmp/file_a.txt
echo "b" > /tmp/file_b.txt
echo "c" > /tmp/file_c.txt

python tooling/ingest.py add /tmp/file_a.txt /tmp/file_b.txt /tmp/file_c.txt \
  --project test-project --subdir data/raw

# Check for collision suffixes (-a, -b, etc.) if timestamps match
ls ~/Projects/test-project/data/raw/

# ============================================================================
# Test 7: Pre-commit Hook (Data Protection)
# ============================================================================
# Make sure you're in the research-pipeline repo directory
cd ~/research-pipeline  # or wherever you cloned it

# Try to commit a data file (should fail)
touch test_block_me.csv
git add test_block_me.csv
git commit -m "test"

# Expected output:
#   ⛔ COMMIT BLOCKED: Data files detected
#   The following files are blocked:
#     ❌ test_block_me.csv

# Clean up
git reset HEAD test_block_me.csv
rm test_block_me.csv

# ============================================================================
# Test 8: Cleanup (Optional)
# ============================================================================
# Remove test projects if desired
# rm -rf ~/Projects/test-project
# rm -rf ~/Projects/moral-learning
# rm -rf ~/Projects/census-inequality
```

### Acceptance Criteria

After running the above tests, you should verify:

- **Project structure**: Directories `data/raw`, `data/clean`, `catalog/`, `R/` exist
- **File renaming**: Files have timestamped names (`YYYY-MM-DDTHHMMSS_slug.ext`)
- **Manifest creation**: `catalog/manifest.csv` exists with proper header
- **Manifest population**: Each ingestion adds a row with stage, sha256, timestamp, etc.
- **Deduplication**: Identical files are detected by SHA256 and skipped
- **Duplicate tracking**: Duplicate entries have `action=duplicate_skipped`
- **Routing**: Files are correctly routed based on regex patterns in config
- **Status display**: `status` command shows recent manifest entries
- **Pre-commit protection**: Attempting to commit `.csv` or other data files is blocked

### Troubleshooting

**Error: "REPLACE_ME in config.yaml"**
- Edit `tooling/config.yaml` and set your actual paths for `downloads_dir` and `projects_base`

**Error: "pyyaml not installed"**
- Activate venv: `source .venv/bin/activate`
- Install dependencies: `pip install pyyaml pandas python-dateutil`

**Error: "Project already exists"**
- Either use a different project name or remove the existing directory

**Pre-commit hook not blocking**
- Verify hook is installed: `git config core.hooksPath`
- Should show: `tooling/hooks`
- If not, run: `git config core.hooksPath tooling/hooks`

---

## Repository Structure

```
research-pipeline/
├─ README.md                              # This file
├─ .gitignore                             # Data protection rules
├─ tooling/
│   ├─ ingest.py                          # Python CLI ✅ IMPLEMENTED
│   ├─ config.yaml                        # User configuration
│   ├─ hooks/
│   │   └─ pre-commit                     # Git hook to block data commits
│   └─ templates/
│       └─ project/                       # Project scaffold template
│           ├─ _project.Rproj             # RStudio project file
│           ├─ data/
│           │   ├─ raw/.gitkeep
│           │   └─ clean/.gitkeep
│           ├─ catalog/.gitkeep
│           └─ R/
│               └─ .gitkeep               # R helper functions (Step 3)
├─ R/
│   └─ examples.md                        # R usage examples (Step 3)
└─ examples/
    └─ _project_template/                 # Example project structure
```

---

## FAQ

### Why isn't this a Python package?

For simplicity. You can call the CLI directly without `pip install -e .` or publishing to PyPI. If you prefer a package structure, you can easily refactor.

### Can I version control my manifests?

**For this tooling repo**: No—manifests live in project directories, not here.

**For individual projects**: Maybe. If your project has its own git repo, you *could* commit the manifest (it doesn't contain sensitive data, just metadata). But data files should still be ignored.

### What if two files download at the exact same second?

The ingest script appends `-a`, `-b`, etc. to avoid timestamp collisions.

### Can I change the timestamp format?

Yes! Edit `naming.timestamp_format` in `config.yaml`. Use Python's `strftime` codes. Avoid colons (`:`) as they're problematic on some filesystems.

### What about Stata/SPSS/SAS files?

The R helpers use `readr::read_csv()` by default. For other formats:
- **Stata (`.dta`)**: `haven::read_dta()`
- **SPSS (`.sav`)**: `haven::read_sav()`
- **Excel (`.xlsx`)**: `readxl::read_excel()`
- **Parquet**: `arrow::read_parquet()`

You can extend `load_raw_latest()` to detect file extensions and use the appropriate reader.

### Can I disable the pre-commit hook temporarily?

Yes, with `git commit --no-verify`, but **you shouldn't**. If you need to commit a small example dataset for documentation, consider:
1. Creating a `fixtures/` directory explicitly allowed in `.gitignore`
2. Using tiny synthetic data (not real research data)

---

## Implementation Status

**Step 1 - Core Tooling Repo** (Complete)
- Repository structure and `.gitignore`
- Pre-commit hook for data protection
- Configuration templates
- Project scaffolding templates

**Step 2 - Python Ingestion CLI** (Complete)
- `ingest.py` with subcommands: `route`, `add`, `status`, `init-project`
- File stabilization and SHA256 hashing
- Deduplication logic
- Manifest creation and updates
- Comprehensive test workflow in README

**Step 3 - R Helper Functions** (Complete)
- `R/data_helpers.R` with full implementation
- `{pointblank}` validation suite template
- R usage examples and documentation (`R/examples.md`)
- Support for flexible project folder structure

---

## License

MIT (or your preferred license)

---

## Contributing

This is a personal tooling repo. If you'd like to adapt it for your own use:

1. Fork this repo
2. Edit `tooling/config.yaml` with your paths and routing rules
3. Extend the templates and helpers as needed

If you find bugs or have suggestions, open an issue!

---

## Resources

- [Python `argparse` docs](https://docs.python.org/3/library/argparse.html)
- [R `{here}` package](https://here.r-lib.org/)
- [R `{renv}` package](https://rstudio.github.io/renv/)
- [R `{pointblank}` package](https://rich-iannone.github.io/pointblank/)
- [Git hooks documentation](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks)
