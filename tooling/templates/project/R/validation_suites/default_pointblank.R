# =============================================================================
# Default Pointblank Validation Suite
# =============================================================================
# This validation suite defines basic data quality checks that should apply
# to most datasets. Customize this file or create new suites for specific
# validation needs.
#
# Usage:
#   This file is sourced by validate_clean() and should return a pointblank
#   agent object configured with validation rules.
#
# Learn more: https://rich-iannone.github.io/pointblank/
# =============================================================================

if (!requireNamespace("pointblank", quietly = TRUE)) {
  stop("pointblank package required. Install with: install.packages('pointblank')")
}

library(pointblank)

# Create a pointblank agent
agent <- create_agent(
  label = "Default Data Quality Checks",
  actions = action_levels(
    warn_at = 0.05,   # Warn if >5% of rows fail
    stop_at = 0.10    # Stop if >10% of rows fail
  )
)

# -----------------------------------------------------------------------------
# Basic structural checks
# -----------------------------------------------------------------------------

agent <- agent %>%
  # Must have at least one row
  rows_distinct(
    columns = NULL,
    threshold = 1,
    label = "Dataset is not empty"
  ) %>%

  # Must have at least one column
  col_exists(
    columns = vars(everything()),
    label = "Dataset has columns"
  )

# -----------------------------------------------------------------------------
# Column-level checks
# -----------------------------------------------------------------------------

agent <- agent %>%
  # No columns should be entirely missing
  col_vals_not_null(
    columns = vars(everything()),
    threshold = 0.95,  # Allow up to 5% missing per column
    label = "Columns are not entirely missing"
  )

# -----------------------------------------------------------------------------
# Domain-specific checks (CUSTOMIZE THESE!)
# -----------------------------------------------------------------------------
# Add your own validation rules below. Examples:

# Example: Check that a specific column exists
# agent <- agent %>%
#   col_exists(
#     columns = vars(participant_id),
#     label = "participant_id column exists"
#   )

# Example: Check that IDs are unique
# agent <- agent %>%
#   col_is_unique(
#     columns = vars(participant_id),
#     label = "Participant IDs are unique"
#   )

# Example: Check that a numeric column is in valid range
# agent <- agent %>%
#   col_vals_between(
#     columns = vars(age),
#     left = 18,
#     right = 100,
#     label = "Age is between 18 and 100"
#   )

# Example: Check that a column has no missing values
# agent <- agent %>%
#   col_vals_not_null(
#     columns = vars(response),
#     label = "Response column has no NAs"
#   )

# Example: Check that a categorical variable has expected values
# agent <- agent %>%
#   col_vals_in_set(
#     columns = vars(condition),
#     set = c("control", "treatment"),
#     label = "Condition is control or treatment"
#   )

# Example: Check date formats
# agent <- agent %>%
#   col_vals_regex(
#     columns = vars(date),
#     regex = "^\\d{4}-\\d{2}-\\d{2}$",
#     label = "Date is in YYYY-MM-DD format"
#   )

# Example: Check that counts match expected totals
# agent <- agent %>%
#   rows_distinct(
#     columns = vars(participant_id, trial),
#     label = "No duplicate participant-trial combinations"
#   )

# -----------------------------------------------------------------------------
# Return the agent
# -----------------------------------------------------------------------------
# The validate_clean() function will interrogate this agent with your data

agent
