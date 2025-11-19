#!/usr/bin/env python3
"""
Research Data Pipeline - Ingestion CLI

Privacy-first data ingestion tool for research projects.
Never reads file contents except for computing checksums.
"""

import argparse
import csv
import hashlib
import os
import re
import shutil
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    print("Error: pyyaml not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("Error: pandas not installed. Run: pip install pandas", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# Configuration Management
# ============================================================================

def load_config(config_path: str = "tooling/config.yaml") -> Dict:
    """Load and validate configuration from YAML file."""
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Validate required fields
    if 'projects_base' not in config:
        print("Error: 'projects_base' not set in config.yaml", file=sys.stderr)
        sys.exit(1)

    if 'REPLACE_ME' in str(config.get('projects_base', '')):
        print("Error: Please edit config.yaml and replace REPLACE_ME with your actual paths", file=sys.stderr)
        sys.exit(1)

    # Expand user paths
    config['projects_base'] = os.path.expanduser(config['projects_base'])
    if 'downloads_dir' in config:
        config['downloads_dir'] = os.path.expanduser(config['downloads_dir'])

    return config


# ============================================================================
# File Operations
# ============================================================================

def stabilize_file(filepath: str, poll_interval: float = 0.5,
                   stable_count: int = 3, timeout: float = 30) -> bool:
    """
    Wait for file size to stabilize (useful for in-progress downloads).

    Returns True if stable, False if timeout reached.
    """
    if not os.path.exists(filepath):
        return False

    start_time = time.time()
    last_size = -1
    stable_checks = 0

    while time.time() - start_time < timeout:
        current_size = os.path.getsize(filepath)

        if current_size == last_size:
            stable_checks += 1
            if stable_checks >= stable_count:
                return True
        else:
            stable_checks = 0
            last_size = current_size

        time.sleep(poll_interval)

    # Timeout reached, but file exists - probably okay
    return True


def compute_sha256(filepath: str, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash of file contents."""
    sha256_hash = hashlib.sha256()

    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256_hash.update(chunk)

    return sha256_hash.hexdigest()


def slugify(text: str, max_len: int = 60) -> str:
    """
    Convert text to filesystem-safe slug.

    - ASCII fold unicode characters
    - Keep only alphanumeric, dots, hyphens, underscores
    - Replace whitespace with hyphens
    - Collapse multiple hyphens
    - Limit length
    """
    # Normalize unicode to ASCII
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')

    # Replace whitespace with hyphens
    text = re.sub(r'\s+', '-', text)

    # Keep only safe characters
    text = re.sub(r'[^A-Za-z0-9._-]', '', text)

    # Collapse multiple hyphens
    text = re.sub(r'-+', '-', text)

    # Strip leading/trailing hyphens
    text = text.strip('-')

    # Limit length
    if len(text) > max_len:
        text = text[:max_len].rstrip('-')

    return text


def generate_timestamped_filename(original_name: str, config: Dict) -> str:
    """
    Generate timestamped filename: slug_YYYY-MM-DDTHHMMSS.ext
    """
    # Get naming config
    naming = config.get('naming', {})
    timestamp_format = naming.get('timestamp_format', '%Y-%m-%dT%H%M%S')
    slug_maxlen = naming.get('slug_maxlen', 60)
    lower_ext = naming.get('lower_ext', True)

    # Split name and extension
    base, ext = os.path.splitext(original_name)

    if lower_ext and ext:
        ext = ext.lower()

    # Generate timestamp
    timestamp = datetime.now().strftime(timestamp_format)

    # Generate slug from base
    slug = slugify(base, max_len=slug_maxlen)

    if not slug:
        slug = "file"

    # Combine - timestamp at END
    new_name = f"{slug}_{timestamp}{ext}"

    return new_name


def handle_collision(target_path: str) -> str:
    """
    If target path exists, append -a, -b, etc. before extension.
    """
    if not os.path.exists(target_path):
        return target_path

    base, ext = os.path.splitext(target_path)
    suffix = ord('a')

    while True:
        new_path = f"{base}-{chr(suffix)}{ext}"
        if not os.path.exists(new_path):
            return new_path
        suffix += 1
        if suffix > ord('z'):
            # Fallback to numbers
            counter = 1
            while True:
                new_path = f"{base}-{counter}{ext}"
                if not os.path.exists(new_path):
                    return new_path
                counter += 1


# ============================================================================
# Manifest Management
# ============================================================================

def ensure_manifest(manifest_path: str) -> None:
    """Create manifest CSV with header if it doesn't exist."""
    if os.path.exists(manifest_path):
        return

    # Create parent directory if needed
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)

    # Create with header
    header = [
        'project', 'stage', 'path', 'ts', 'original_name',
        'size_bytes', 'sha256', 'source', 'notes', 'action',
        'derived_from', 'code_commit'
    ]

    with open(manifest_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)


def check_duplicate(manifest_path: str, sha256: str) -> Optional[str]:
    """
    Check if SHA256 already exists in manifest.
    Returns the path of the existing file if found, None otherwise.
    """
    if not os.path.exists(manifest_path):
        return None

    try:
        df = pd.read_csv(manifest_path)
        if 'sha256' not in df.columns:
            return None

        matches = df[df['sha256'] == sha256]
        if len(matches) > 0:
            return matches.iloc[0]['path']
    except Exception as e:
        print(f"Warning: Error reading manifest: {e}", file=sys.stderr)
        return None

    return None


def append_to_manifest(manifest_path: str, row: Dict) -> None:
    """Append a row to the manifest CSV."""
    ensure_manifest(manifest_path)

    # Ensure all required fields are present
    fields = [
        'project', 'stage', 'path', 'ts', 'original_name',
        'size_bytes', 'sha256', 'source', 'notes', 'action',
        'derived_from', 'code_commit'
    ]

    row_data = [row.get(field, '') for field in fields]

    with open(manifest_path, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(row_data)


# ============================================================================
# Project Management
# ============================================================================

def init_project(project_name: str, config: Dict) -> None:
    """
    Initialize a new research project from template.
    """
    projects_base = config['projects_base']
    project_path = os.path.join(projects_base, project_name)

    # Check if project already exists
    if os.path.exists(project_path):
        print(f"Error: Project '{project_name}' already exists at {project_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Creating project: {project_name}")
    print(f"Location: {project_path}")

    # Create directory structure
    dirs = [
        '',
        'data/raw',
        'data/clean',
        'catalog',
        'R',
        'R/validation_suites',
    ]

    for d in dirs:
        path = os.path.join(project_path, d)
        os.makedirs(path, exist_ok=True)
        print(f"  ✓ Created {d or '(root)'}/")

    # Copy template files
    template_dir = Path(__file__).parent / 'templates' / 'project'

    # Copy .Rproj file
    rproj_template = template_dir / '_project.Rproj'
    rproj_dest = os.path.join(project_path, f"{project_name}.Rproj")
    if rproj_template.exists():
        shutil.copy(rproj_template, rproj_dest)
        print(f"  ✓ Created {project_name}.Rproj")

    # Create .gitkeep files
    gitkeep_locations = [
        'data/raw/.gitkeep',
        'data/clean/.gitkeep',
        'catalog/.gitkeep',
        'R/.gitkeep',
    ]

    for loc in gitkeep_locations:
        gitkeep_path = os.path.join(project_path, loc)
        with open(gitkeep_path, 'w') as f:
            f.write("# Placeholder to preserve directory structure\n")

    # Create placeholder R files (will be implemented in Step 3)
    r_helpers = os.path.join(project_path, 'R', 'data_helpers.R')
    with open(r_helpers, 'w') as f:
        f.write("# Data helper functions\n")
        f.write("# To be implemented: load_raw_latest(), save_clean(), validate_clean()\n")
    print(f"  ✓ Created R/data_helpers.R (placeholder)")

    # Create README
    readme_path = os.path.join(project_path, 'README.md')
    with open(readme_path, 'w') as f:
        f.write(f"# {project_name}\n\n")
        f.write("Research project initialized with the data pipeline.\n\n")
        f.write("## Setup\n\n")
        f.write("1. Open `{}.Rproj` in RStudio\n".format(project_name))
        f.write("2. Run `renv::init()` to set up reproducible environment\n")
        f.write("3. Install required packages: `install.packages(c('here', 'readr', 'fs', 'pointblank'))`\n")
        f.write("4. Run `renv::snapshot()` to save package versions\n\n")
        f.write("## Directory Structure\n\n")
        f.write("- `data/raw/`: Raw data files (auto-populated by ingest pipeline)\n")
        f.write("- `data/clean/`: Cleaned data files\n")
        f.write("- `catalog/manifest.csv`: Data provenance tracking\n")
        f.write("- `R/`: Analysis scripts and helper functions\n")
    print(f"  ✓ Created README.md")

    print(f"\n✅ Project '{project_name}' created successfully!")
    print(f"\nNext steps:")
    print(f"  1. Open {rproj_dest} in RStudio")
    print(f"  2. Run renv::init() to set up reproducible environment")
    print(f"  3. Start ingesting data with: python tooling/ingest.py add <files> --project {project_name}")


# ============================================================================
# File Ingestion
# ============================================================================

def ingest_file(filepath: str, project: str, subdir: str, config: Dict,
                source: str = "manual", notes: str = "") -> bool:
    """
    Ingest a single file into a project.

    Returns True if successful, False if skipped (duplicate).
    """
    # Validate file exists
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        return False

    # Check if trying to ingest into tooling repo
    abs_filepath = os.path.abspath(filepath)
    tooling_repo = os.path.abspath(os.path.dirname(__file__))
    if abs_filepath.startswith(tooling_repo):
        print(f"Error: Cannot ingest files from within the tooling repo", file=sys.stderr)
        print(f"  File: {filepath}", file=sys.stderr)
        return False

    # Stabilize file
    print(f"Stabilizing: {os.path.basename(filepath)}", end='', flush=True)
    if not stabilize_file(filepath):
        print(" [TIMEOUT]")
        print(f"Warning: File may still be downloading, proceeding anyway", file=sys.stderr)
    else:
        print(" [OK]")

    # Compute hash
    print(f"Computing SHA256...", end='', flush=True)
    sha256 = compute_sha256(filepath)
    print(f" {sha256[:16]}...")

    # Get file info
    original_name = os.path.basename(filepath)
    size_bytes = os.path.getsize(filepath)

    # Build paths
    projects_base = config['projects_base']
    project_path = os.path.join(projects_base, project)
    manifest_path = os.path.join(project_path, 'catalog', 'manifest.csv')

    # Check for duplicate
    existing = check_duplicate(manifest_path, sha256)
    if existing:
        print(f"⚠️  Duplicate detected (SHA256 match)")
        print(f"   Existing: {existing}")
        print(f"   Skipping ingest, recording alias in manifest")

        # Record as duplicate
        row = {
            'project': project,
            'stage': 'raw',
            'path': abs_filepath,
            'ts': datetime.now().isoformat(),
            'original_name': original_name,
            'size_bytes': size_bytes,
            'sha256': sha256,
            'source': source,
            'notes': f"Duplicate of {existing}. {notes}".strip(),
            'action': 'duplicate_skipped',
            'derived_from': '',
            'code_commit': '',
        }
        append_to_manifest(manifest_path, row)
        return False

    # Generate new filename
    new_filename = generate_timestamped_filename(original_name, config)

    # Build destination path
    dest_dir = os.path.join(project_path, subdir)
    os.makedirs(dest_dir, exist_ok=True)

    dest_path = os.path.join(dest_dir, new_filename)

    # Handle collisions
    dest_path = handle_collision(dest_path)

    # Move file
    print(f"Moving to: {os.path.relpath(dest_path, projects_base)}")
    shutil.move(filepath, dest_path)

    # Record in manifest
    row = {
        'project': project,
        'stage': 'raw',
        'path': os.path.abspath(dest_path),
        'ts': datetime.now().isoformat(),
        'original_name': original_name,
        'size_bytes': size_bytes,
        'sha256': sha256,
        'source': source,
        'notes': notes,
        'action': 'ingested',
        'derived_from': '',
        'code_commit': '',
    }
    append_to_manifest(manifest_path, row)

    print(f"✅ Ingested successfully")
    return True


def route_file(filepath: str, config: Dict) -> Optional[Tuple[str, str]]:
    """
    Route a file based on regex patterns in config.

    Returns (project, subdir) tuple or None if no match.
    """
    routing_rules = config.get('routing', [])
    basename = os.path.basename(filepath)

    for rule in routing_rules:
        pattern = rule.get('pattern')
        project = rule.get('project')
        subdir = rule.get('subdir')

        if not all([pattern, project, subdir]):
            continue

        # Case-insensitive regex match
        if re.search(pattern, basename, re.IGNORECASE):
            return (project, subdir)

    return None


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_init_project(args, config):
    """Handle init-project subcommand."""
    init_project(args.name, config)


def cmd_add(args, config):
    """Handle add subcommand."""
    if not args.paths:
        print("Error: No files specified", file=sys.stderr)
        sys.exit(1)

    success_count = 0
    skip_count = 0

    for filepath in args.paths:
        # Expand globs
        from glob import glob
        files = glob(os.path.expanduser(filepath))

        if not files:
            print(f"Warning: No files match pattern: {filepath}", file=sys.stderr)
            continue

        for f in files:
            if os.path.isdir(f):
                print(f"Skipping directory: {f}", file=sys.stderr)
                continue

            print(f"\n{'='*60}")
            print(f"File: {f}")
            print(f"{'='*60}")

            result = ingest_file(
                f,
                args.project,
                args.subdir,
                config,
                source=args.source or "manual",
                notes=args.notes or ""
            )

            if result:
                success_count += 1
            else:
                skip_count += 1

    print(f"\n{'='*60}")
    print(f"Summary: {success_count} ingested, {skip_count} skipped")
    print(f"{'='*60}")


def cmd_route(args, config):
    """Handle route subcommand."""
    if args.from_downloads:
        downloads_dir = config.get('downloads_dir')
        if not downloads_dir:
            print("Error: downloads_dir not set in config.yaml", file=sys.stderr)
            sys.exit(1)

        if not os.path.exists(downloads_dir):
            print(f"Error: Downloads directory not found: {downloads_dir}", file=sys.stderr)
            sys.exit(1)

        # Get all files in downloads (non-recursive)
        files = [os.path.join(downloads_dir, f)
                for f in os.listdir(downloads_dir)
                if os.path.isfile(os.path.join(downloads_dir, f))]

        if not files:
            print("No files found in Downloads directory")
            return

        print(f"Found {len(files)} file(s) in {downloads_dir}\n")
    else:
        if not args.paths:
            print("Error: No files specified. Use --from-downloads or provide file paths", file=sys.stderr)
            sys.exit(1)

        # Expand globs
        from glob import glob
        files = []
        for pattern in args.paths:
            matched = glob(os.path.expanduser(pattern))
            files.extend([f for f in matched if os.path.isfile(f)])

        if not files:
            print("No files matched the specified patterns")
            return

    success_count = 0
    skip_count = 0
    no_route_count = 0

    for filepath in files:
        print(f"\n{'='*60}")
        print(f"File: {os.path.basename(filepath)}")
        print(f"{'='*60}")

        # Route file
        route = route_file(filepath, config)

        if not route:
            print(f"⚠️  No routing rule matched, skipping")
            no_route_count += 1
            continue

        project, subdir = route
        print(f"Routed to: {project}/{subdir}")

        result = ingest_file(
            filepath,
            project,
            subdir,
            config,
            source="Downloads" if args.from_downloads else "routed",
            notes=""
        )

        if result:
            success_count += 1
        else:
            skip_count += 1

    print(f"\n{'='*60}")
    print(f"Summary: {success_count} ingested, {skip_count} duplicates, {no_route_count} not routed")
    print(f"{'='*60}")


def cmd_status(args, config):
    """Handle status subcommand."""
    projects_base = config['projects_base']
    project_path = os.path.join(projects_base, args.project)
    manifest_path = os.path.join(project_path, 'catalog', 'manifest.csv')

    if not os.path.exists(manifest_path):
        print(f"No manifest found for project: {args.project}")
        print(f"Expected: {manifest_path}")
        return

    # Read manifest
    df = pd.read_csv(manifest_path)

    if len(df) == 0:
        print(f"Manifest is empty for project: {args.project}")
        return

    # Show last N rows
    limit = args.limit or 20
    recent = df.tail(limit)

    print(f"\n{'='*60}")
    print(f"Project: {args.project}")
    print(f"Manifest: {manifest_path}")
    print(f"Total entries: {len(df)}")
    print(f"Showing last {len(recent)} entries:")
    print(f"{'='*60}\n")

    # Format output
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 50)

    # Show key columns
    cols = ['ts', 'stage', 'original_name', 'action', 'size_bytes', 'sha256']
    display_cols = [c for c in cols if c in recent.columns]

    print(recent[display_cols].to_string(index=False))
    print(f"\n{'='*60}")


# ============================================================================
# Main CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Research Data Pipeline - Privacy-first data ingestion',
        epilog='For more info, see README.md'
    )

    parser.add_argument(
        '--config',
        default='tooling/config.yaml',
        help='Path to config file (default: tooling/config.yaml)'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # init-project
    parser_init = subparsers.add_parser(
        'init-project',
        help='Initialize a new research project from template'
    )
    parser_init.add_argument('--name', required=True, help='Project name')

    # add
    parser_add = subparsers.add_parser(
        'add',
        help='Add specific files to a project (bypass routing)'
    )
    parser_add.add_argument('paths', nargs='+', help='File paths or glob patterns')
    parser_add.add_argument('--project', required=True, help='Target project name')
    parser_add.add_argument('--subdir', default='data/raw', help='Subdirectory within project (default: data/raw)')
    parser_add.add_argument('--source', help='Source label for manifest (default: manual)')
    parser_add.add_argument('--notes', help='Notes to record in manifest')

    # route
    parser_route = subparsers.add_parser(
        'route',
        help='Route files automatically based on config.yaml patterns'
    )
    parser_route.add_argument('paths', nargs='*', help='File paths or glob patterns (optional)')
    parser_route.add_argument('--from-downloads', action='store_true',
                             help='Route all files from downloads_dir in config')

    # status
    parser_status = subparsers.add_parser(
        'status',
        help='Show recent manifest entries for a project'
    )
    parser_status.add_argument('--project', required=True, help='Project name')
    parser_status.add_argument('--limit', type=int, help='Number of entries to show (default: 20)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Load config
    config = load_config(args.config)

    # Dispatch to command handlers
    commands = {
        'init-project': cmd_init_project,
        'add': cmd_add,
        'route': cmd_route,
        'status': cmd_status,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args, config)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
