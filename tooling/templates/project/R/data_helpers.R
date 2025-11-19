# =============================================================================
# Data Pipeline Helpers for R
# =============================================================================
# Helper functions for loading raw data, saving cleaned data, and maintaining
# provenance in the manifest.
#
# Required packages: here, fs, readr
# Optional packages: pointblank (for validation), haven (for Stata/SPSS files)
#
# Usage:
#   source("R/data_helpers.R")
#   df <- load_raw_latest("survey.*\\.csv$")
#   df_clean <- ... # your cleaning code
#   save_clean(df_clean, "survey_clean.csv", notes = "Removed NAs")
# =============================================================================

# -----------------------------------------------------------------------------
# Package checks
# -----------------------------------------------------------------------------

#' Check if required packages are installed
#' @param pkg Package name
#' @param install_msg Custom install message
check_package <- function(pkg, install_msg = NULL) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    if (is.null(install_msg)) {
      install_msg <- sprintf('install.packages("%s")', pkg)
    }
    stop(sprintf("Package '%s' is required but not installed.\nRun: %s",
                 pkg, install_msg),
         call. = FALSE)
  }
}

# Check required packages on load
check_package("here")
check_package("fs")
check_package("readr")

# Load packages
suppressPackageStartupMessages({
  library(here)
  library(fs)
  library(readr)
})

# -----------------------------------------------------------------------------
# Path helpers
# -----------------------------------------------------------------------------

#' Get path to a data directory
#' @param subdir Subdirectory path (e.g., "data/raw", "MoreBench", "Moral_Learning")
#' @return Absolute path to directory
data_dir <- function(subdir = "data/raw") {
  path <- here::here(subdir)
  if (!fs::dir_exists(path)) {
    warning("Data directory does not exist: ", path,
            "\nAvailable directories: ",
            paste(fs::dir_ls(here::here(), type = "directory"), collapse = ", "))
  }
  return(path)
}

#' Get path to raw data directory
#' @param subdir Subdirectory within project (default: "data/raw")
#' @return Absolute path to data directory
raw_dir <- function(subdir = "data/raw") {
  data_dir(subdir)
}

#' Get path to clean data directory
#' @return Absolute path to data/clean
clean_dir <- function() {
  path <- here::here("data", "clean")
  if (!fs::dir_exists(path)) {
    fs::dir_create(path, recurse = TRUE)
    message("Created clean data directory: ", path)
  }
  return(path)
}

#' Get path to manifest CSV
#' @return Absolute path to catalog/manifest.csv
manifest_path <- function() {
  path <- here::here("catalog", "manifest.csv")
  if (!fs::file_exists(path)) {
    warning("Manifest does not exist: ", path)
  }
  return(path)
}

# -----------------------------------------------------------------------------
# Loading raw data
# -----------------------------------------------------------------------------

#' Load the most recent raw data file matching a pattern
#'
#' Searches a data directory for files matching a regex pattern and
#' loads the most recently modified file.
#'
#' @param pattern Regex pattern to match filenames (e.g., "survey.*\\\\.csv$")
#' @param subdir Subdirectory to search (default: "data/raw", or use "MoreBench", "Moral_Learning", etc.)
#' @param reader Function to read the file (default: readr::read_csv)
#' @param ... Additional arguments passed to the reader function
#' @return Data frame
#' @examples
#' df <- load_raw_latest("survey.*\\.csv$")
#' df <- load_raw_latest("SML.*\\.csv$", subdir = "Moral_Learning")
#' df <- load_raw_latest("morebench.*\\.csv$", subdir = "MoreBench")
load_raw_latest <- function(pattern = ".*\\.csv$", subdir = "data/raw",
                            reader = NULL, ...) {
  raw_path <- data_dir(subdir)

  # Find matching files
  all_files <- fs::dir_ls(raw_path, regexp = pattern, type = "file")

  if (length(all_files) == 0) {
    stop("No files found matching pattern: ", pattern,
         "\nIn directory: ", raw_path,
         call. = FALSE)
  }

  # Get modification times and sort
  file_info <- fs::file_info(all_files)
  file_info <- file_info[order(file_info$modification_time, decreasing = TRUE), ]

  latest_file <- rownames(file_info)[1]

  message("Loading: ", fs::path_file(latest_file))
  message("Modified: ", file_info$modification_time[1])

  # Auto-detect reader if not provided
  if (is.null(reader)) {
    ext <- tolower(fs::path_ext(latest_file))

    reader <- switch(ext,
      "csv" = readr::read_csv,
      "tsv" = readr::read_tsv,
      "rds" = readRDS,
      "rda" = function(f, ...) {
        env <- new.env()
        load(f, envir = env)
        # Return first object in .RData file
        get(ls(env)[1], envir = env)
      },
      "dta" = function(f, ...) {
        check_package("haven")
        haven::read_dta(f, ...)
      },
      "sav" = function(f, ...) {
        check_package("haven")
        haven::read_sav(f, ...)
      },
      "xlsx" = function(f, ...) {
        check_package("readxl")
        readxl::read_excel(f, ...)
      },
      "parquet" = function(f, ...) {
        check_package("arrow")
        arrow::read_parquet(f, ...)
      },
      # Default to read_csv
      readr::read_csv
    )
  }

  # Load the file
  tryCatch({
    df <- reader(latest_file, ...)
    message("Loaded ", nrow(df), " rows, ", ncol(df), " columns")
    return(df)
  }, error = function(e) {
    stop("Error loading file: ", latest_file, "\n", e$message, call. = FALSE)
  })
}

# -----------------------------------------------------------------------------
# Saving cleaned data
# -----------------------------------------------------------------------------

#' Generate timestamped filename
#' @param base Base filename (e.g., "survey_clean.csv")
#' @return Timestamped filename (e.g., "survey_clean_2025-11-19T142241.csv")
generate_timestamped_name <- function(base) {
  # Split into name and extension
  ext <- fs::path_ext(base)
  name <- fs::path_ext_remove(base)

  # Generate timestamp (matches Python format)
  timestamp <- format(Sys.time(), "%Y-%m-%dT%H%M%S")

  # Combine: name_timestamp.ext
  timestamped <- paste0(name, "_", timestamp, ".", ext)

  return(timestamped)
}

#' Get current git commit hash (if in a git repo)
#' @return Short git hash or empty string
get_git_commit <- function() {
  tryCatch({
    hash <- system("git rev-parse --short HEAD 2>/dev/null",
                   intern = TRUE,
                   ignore.stderr = TRUE)
    if (length(hash) == 0 || hash == "") {
      return("")
    }
    return(hash)
  }, error = function(e) {
    return("")
  })
}

#' Compute SHA256 hash of a file
#' @param filepath Path to file
#' @return SHA256 hash as hex string
compute_sha256 <- function(filepath) {
  tryCatch({
    hash <- digest::digest(file = filepath, algo = "sha256")
    return(hash)
  }, error = function(e) {
    warning("Could not compute SHA256: ", e$message)
    return("")
  })
}

#' Save cleaned data with provenance tracking
#'
#' Saves a data frame with a timestamped filename and records
#' the operation in the manifest.
#'
#' @param df Data frame to save
#' @param base Base filename (e.g., "survey_clean.csv")
#' @param subdir Subdirectory to save to (default: "data/clean", or use project folders)
#' @param notes Description of cleaning operations performed
#' @param derived_from SHA256 hash of the raw file this was derived from (optional)
#' @param writer Function to write the file (default: readr::write_csv)
#' @param ... Additional arguments passed to the writer function
#' @return Path to saved file (invisibly)
#' @examples
#' save_clean(df_clean, "survey_clean.csv",
#'            notes = "Removed NAs, recoded variables")
#' save_clean(df_clean, "SML_clean.csv", subdir = "Moral_Learning")
save_clean <- function(df, base, subdir = "data/clean", notes = "",
                       derived_from = "", writer = NULL, ...) {

  # Ensure directory exists
  clean_path <- data_dir(subdir)
  if (!fs::dir_exists(clean_path)) {
    fs::dir_create(clean_path, recurse = TRUE)
    message("Created directory: ", clean_path)
  }

  # Generate timestamped filename
  timestamped_name <- generate_timestamped_name(base)
  output_path <- fs::path(clean_path, timestamped_name)

  # Auto-detect writer if not provided
  if (is.null(writer)) {
    ext <- tolower(fs::path_ext(base))

    writer <- switch(ext,
      "csv" = readr::write_csv,
      "tsv" = readr::write_tsv,
      "rds" = saveRDS,
      "rda" = function(x, file, ...) {
        save(x, file = file, ...)
      },
      "parquet" = function(x, file, ...) {
        check_package("arrow")
        arrow::write_parquet(x, file, ...)
      },
      # Default to CSV
      readr::write_csv
    )
  }

  # Write the file
  message("Saving to: ", timestamped_name)
  tryCatch({
    writer(df, output_path, ...)
    message("Saved ", nrow(df), " rows, ", ncol(df), " columns")
  }, error = function(e) {
    stop("Error writing file: ", output_path, "\n", e$message, call. = FALSE)
  })

  # Compute SHA256 of saved file
  sha256 <- ""
  if (requireNamespace("digest", quietly = TRUE)) {
    sha256 <- compute_sha256(output_path)
  } else {
    message("Install 'digest' package for SHA256 checksums: install.packages('digest')")
  }

  # Get git commit
  code_commit <- get_git_commit()

  # Append to manifest
  append_to_manifest(
    path = output_path,
    stage = "clean",
    original_name = base,
    notes = notes,
    derived_from = derived_from,
    code_commit = code_commit,
    sha256 = sha256
  )

  invisible(output_path)
}

#' Append a row to the manifest CSV
#' @param path Absolute path to file
#' @param stage "raw" or "clean"
#' @param original_name Original filename
#' @param notes User notes
#' @param derived_from SHA256 of parent file
#' @param code_commit Git commit hash
#' @param sha256 SHA256 of this file
append_to_manifest <- function(path, stage, original_name, notes = "",
                               derived_from = "", code_commit = "", sha256 = "") {

  manifest_file <- manifest_path()

  # Get project name from here::here() path
  project_path <- here::here()
  project_name <- fs::path_file(project_path)

  # Get file size
  size_bytes <- fs::file_size(path)

  # Create manifest row
  new_row <- data.frame(
    project = project_name,
    stage = stage,
    path = path,
    ts = format(Sys.time(), "%Y-%m-%dT%H:%M:%OS3"),
    original_name = original_name,
    size_bytes = as.numeric(size_bytes),
    sha256 = sha256,
    source = "R",
    notes = notes,
    action = "saved",
    derived_from = derived_from,
    code_commit = code_commit,
    stringsAsFactors = FALSE
  )

  # Append to manifest
  if (fs::file_exists(manifest_file)) {
    # Read existing manifest
    manifest <- readr::read_csv(manifest_file, show_col_types = FALSE)

    # Append new row
    manifest <- rbind(manifest, new_row)

    # Write back
    readr::write_csv(manifest, manifest_file)
    message("Updated manifest: ", manifest_file)
  } else {
    # Create new manifest
    readr::write_csv(new_row, manifest_file)
    message("Created manifest: ", manifest_file)
  }
}

# -----------------------------------------------------------------------------
# Data validation
# -----------------------------------------------------------------------------

#' Validate cleaned data using pointblank suite
#'
#' Runs validation checks from a pointblank suite and saves a report.
#'
#' @param df Data frame to validate
#' @param suite Name of validation suite (default: "default")
#' @return pointblank agent object (invisibly)
#' @examples
#' validate_clean(df_clean)
#' validate_clean(df_clean, suite = "strict")
validate_clean <- function(df, suite = "default") {

  # Check for pointblank
  if (!requireNamespace("pointblank", quietly = TRUE)) {
    warning("Package 'pointblank' not installed. Skipping validation.\n",
            "Install with: install.packages('pointblank')")
    return(invisible(NULL))
  }

  # Load suite file
  suite_path <- here::here("R", "validation_suites",
                           paste0(suite, "_pointblank.R"))

  if (!fs::file_exists(suite_path)) {
    warning("Validation suite not found: ", suite_path)
    return(invisible(NULL))
  }

  message("Running validation suite: ", suite)

  # Source the suite (should return an agent)
  agent <- tryCatch({
    source(suite_path, local = TRUE)$value
  }, error = function(e) {
    stop("Error loading validation suite: ", e$message, call. = FALSE)
  })

  # Run validation on the data
  agent <- pointblank::interrogate(agent, df)

  # Print summary
  print(agent)

  # Save validation report
  report_path <- here::here("data", "clean",
                            paste0("validation_", suite, "_",
                                   format(Sys.time(), "%Y%m%d_%H%M%S"),
                                   ".rds"))

  saveRDS(agent, report_path)
  message("Validation report saved: ", fs::path_file(report_path))

  invisible(agent)
}

# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------

#' List all files in a directory
#' @param subdir Subdirectory to list (default: "data/raw")
#' @param pattern Optional regex pattern to filter files
#' @return Character vector of file paths
list_files <- function(subdir = "data/raw", pattern = NULL) {
  dir_path <- data_dir(subdir)

  if (is.null(pattern)) {
    files <- fs::dir_ls(dir_path, type = "file")
  } else {
    files <- fs::dir_ls(dir_path, regexp = pattern, type = "file")
  }

  # Remove .gitkeep and validation reports
  files <- files[!grepl("(\\.gitkeep$|^validation_)", basename(files))]

  return(files)
}

#' List all raw data files
#' @param pattern Optional regex pattern to filter files
#' @param subdir Subdirectory to search (default: "data/raw")
#' @return Character vector of file paths
list_raw <- function(pattern = NULL, subdir = "data/raw") {
  list_files(subdir, pattern)
}

#' List all cleaned data files
#' @param pattern Optional regex pattern to filter files
#' @param subdir Subdirectory to search (default: "data/clean")
#' @return Character vector of file paths
list_clean <- function(pattern = NULL, subdir = "data/clean") {
  list_files(subdir, pattern)
}

#' Read the manifest
#' @return Data frame of manifest entries
read_manifest <- function() {
  manifest_file <- manifest_path()

  if (!fs::file_exists(manifest_file)) {
    stop("Manifest does not exist: ", manifest_file, call. = FALSE)
  }

  readr::read_csv(manifest_file, show_col_types = FALSE)
}

# -----------------------------------------------------------------------------
# Startup message
# -----------------------------------------------------------------------------

message("Data pipeline helpers loaded successfully!")
message("Available functions:")
message("  - data_dir(subdir), raw_dir(subdir), clean_dir(), manifest_path()")
message("  - load_raw_latest(pattern, subdir)")
message("  - save_clean(df, base, subdir, notes)")
message("  - validate_clean(df, suite)")
message("  - list_files(subdir, pattern), list_raw(pattern, subdir)")
message("  - read_manifest()")
message("\nExamples:")
message('  df <- load_raw_latest("SML.*\\\\.csv$", subdir = "Moral_Learning")')
message('  save_clean(df_clean, "analysis.csv", subdir = "MoreBench")')
message("\nFor help: ?load_raw_latest")
