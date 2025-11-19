# Research Data Pipeline

A tool for managing research data with automatic file routing, deduplication, and provenance tracking. This repo contains tooling only—no actual data files.

## Setup

```bash
git clone https://github.com/rcalcott9/research-pipeline.git
cd research-pipeline
git config core.hooksPath tooling/hooks

python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml pandas python-dateutil
```

Edit `tooling/config.yaml` with your paths and routing patterns.

## Usage

Create a project:
```bash
python tooling/ingest.py init-project --name my-project
```

Route files automatically:
```bash
python tooling/ingest.py route --from-downloads
```

Or add files manually:
```bash
python tooling/ingest.py add ~/Downloads/data.csv --project my-project --subdir data/raw
```

In R:

```r
source("R/data_helpers.R")
df <- load_raw_latest(".*\\.csv$", subdir = "my-project")
# clean your data
save_clean(df_clean, "analysis.csv", subdir = "my-project", notes = "cleaned")
```

## How it works

Files are renamed to `name_TIMESTAMP.ext`, matched against regex patterns in `config.yaml`, and routed to the specified folder. A manifest tracks SHA256 hashes for deduplication and provenance. The pre-commit hook prevents accidental data commits.

See `R/examples.md` for detailed R usage.
