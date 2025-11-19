# Research Data Pipeline

**Privacy-first data management tooling for research projects**

This repository contains a tool I've built to manage and store data. Feel free to clone or to use it as inspo. 


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


