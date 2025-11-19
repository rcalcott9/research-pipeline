# Research Data Pipeline

**Privacy-first data management tooling for research projects**

This repository contains **tooling and templates only**—no research data is stored here. All actual data files remain in local project directories outside this repo, protecting privacy and keeping the public codebase clean.

---

## 🎯 Features

- **Automated file ingestion** from Downloads with regex-based routing
- **SHA256 deduplication** to avoid redundant storage
- **Timestamped, normalized filenames** (`YYYY-MM-DDTHHMMS_slug.ext`)
- **Provenance tracking** via per-project manifest files
- **RStudio project scaffolding** with `renv` for reproducibility
- **Pre-commit hooks** that block accidental data commits
- **R helper functions** using `{here}` for path management
- **Data validation** with `{pointblank}` (optional)

---

## 🔒 Privacy & Security

### What's in this repo?
- ✅ Python CLI tools
- ✅ Configuration templates
- ✅ R helper functions
- ✅ Project scaffolding templates
- ✅ Documentation

### What's NOT in this repo?
- ❌ Research data files (`.csv`, `.xlsx`, `.sav`, `.dta`, etc.)
- ❌ Manifest files
- ❌ Any files in `data/` directories

### Protection mechanisms

1. **`.gitignore`**: Blocks all data file extensions and `data/` directories
2. **Pre-commit hook**: Actively prevents data files from being staged
3. **Template structure**: Projects live outside this repo in `projects_base`

---

## 📋 Prerequisites

- **Python 3.10+**
- **R 4.0+** and RStudio (recommended)
- **Git**
- **macOS** (Linux/Windows notes included as comments)

---

## 🚀 Setup

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

---

## 📚 Usage

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
# Load helper functions
source("R/data_helpers.R")

# Load the most recent raw CSV file
df_raw <- load_raw_latest("survey.*\\.csv$")

# Clean your data
df_clean <- df_raw %>%
  filter(!is.na(participant_id)) %>%
  mutate(response_coded = recode_responses(response))

# Save cleaned data with provenance tracking
clean_path <- save_clean(
  df_clean,
  base = "survey_clean.csv",
  notes = "Removed NAs, recoded responses",
  derived_sha = "abc123..."  # SHA256 from manifest if available
)

# Validate the cleaned data
validate_clean(df_clean, suite = "default")
```

**Helper functions** (in `R/data_helpers.R`):
- `raw_dir()` → path to `data/raw/` using `{here}`
- `clean_dir()` → path to `data/clean/`
- `manifest_path()` → path to `catalog/manifest.csv`
- `load_raw_latest(pattern)` → reads newest matching file
- `save_clean(df, base, notes, derived_sha)` → saves with timestamp, updates manifest
- `validate_clean(df, suite)` → runs `{pointblank}` validation suite

---

## 📊 Manifest Structure

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

## 🔧 Configuration Reference

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

## 🧪 Testing Your Setup

Run these commands to verify everything works:

### 1. Test project initialization

```bash
python tooling/ingest.py init-project --name test-project
ls -la ~/Projects/test-project  # Should show directory structure
```

### 2. Test file ingestion

```bash
# Create a dummy CSV
echo "a,b,c\n1,2,3" > /tmp/test_data.csv

# Ingest it
python tooling/ingest.py add /tmp/test_data.csv --project test-project --subdir data/raw

# Check manifest
cat ~/Projects/test-project/catalog/manifest.csv
```

### 3. Test duplicate detection

```bash
# Try ingesting the same file again
python tooling/ingest.py add /tmp/test_data.csv --project test-project --subdir data/raw

# Should see: "Duplicate file skipped (SHA256 already exists)"
```

### 4. Test pre-commit hook

```bash
# Try to commit a CSV (should fail)
touch test.csv
git add test.csv
git commit -m "test"  # Should block with red error message

# Clean up
git reset HEAD test.csv
rm test.csv
```

---

## 🗂️ Repository Structure

```
research-pipeline/
├─ README.md                              # This file
├─ .gitignore                             # Data protection rules
├─ tooling/
│   ├─ ingest.py                          # Python CLI (to be implemented)
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
│               └─ .gitkeep               # R helper functions (to be implemented)
├─ R/
│   └─ examples.md                        # R usage examples (to be written)
└─ examples/
    └─ _project_template/                 # Example project structure
```

---

## ❓ FAQ

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

## 🛠️ Next Steps

**Step 2** will implement:
- Python CLI (`ingest.py`) with subcommands: `route`, `add`, `status`, `init-project`
- File stabilization, SHA256 hashing, deduplication logic
- Manifest creation and updates

**Step 3** will implement:
- R helper functions (`data_helpers.R`)
- `{pointblank}` validation suite template
- R usage examples

---

## 📝 License

MIT (or your preferred license)

---

## 🤝 Contributing

This is a personal tooling repo. If you'd like to adapt it for your own use:

1. Fork this repo
2. Edit `tooling/config.yaml` with your paths and routing rules
3. Extend the templates and helpers as needed

If you find bugs or have suggestions, open an issue!

---

## 🔗 Resources

- [Python `argparse` docs](https://docs.python.org/3/library/argparse.html)
- [R `{here}` package](https://here.r-lib.org/)
- [R `{renv}` package](https://rstudio.github.io/renv/)
- [R `{pointblank}` package](https://rich-iannone.github.io/pointblank/)
- [Git hooks documentation](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks)

---

**Built with privacy and reproducibility in mind** 🔒📊
