#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE, scipen = 999)

suppressPackageStartupMessages({
  library(devtools)
  library(pkgload)
  library(sp)
  library(raster)
  library(rgdal)
  library(jsonlite)
})

get_script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) < 1) {
    return(normalizePath(getwd(), winslash = "/", mustWork = TRUE))
  }
  script_path <- sub("^--file=", "", file_arg[1])
  dirname(normalizePath(script_path, winslash = "/", mustWork = TRUE))
}

assert_true <- function(ok, msg) {
  if (!isTRUE(ok)) {
    stop(msg, call. = FALSE)
  }
}

fmt_num <- function(x, digits = 6) {
  formatC(x, format = "f", digits = digits, drop0trailing = TRUE)
}

fmt_xy <- function(x) {
  if (isTRUE(all.equal(x, round(x), tolerance = 1e-9))) {
    return(fmt_num(x, 0))
  }
  fmt_num(x, 6)
}

read_numeric_csv <- function(path) {
  df <- utils::read.csv(path, check.names = FALSE)
  for (nm in names(df)) {
    df[[nm]] <- as.numeric(df[[nm]])
  }
  df
}

read_sp_riv <- function(path) {
  lines <- readLines(path, warn = FALSE)
  cursor <- 1L

  read_block <- function() {
    dims <- as.integer(strsplit(trimws(lines[[cursor]]), "\\s+")[[1]])
    assert_true(length(dims) == 2L, paste("Invalid block header in", path, "at line", cursor))
    nr <- dims[[1]]
    header <- lines[[cursor + 1L]]
    block_lines <- c(header, lines[(cursor + 2L):(cursor + nr + 1L)])
    df <- utils::read.table(
      text = paste(block_lines, collapse = "\n"),
      header = TRUE,
      check.names = FALSE,
      stringsAsFactors = FALSE
    )
    for (nm in names(df)) {
      df[[nm]] <- as.numeric(df[[nm]])
    }
    cursor <<- cursor + nr + 2L
    df
  }

  river <- read_block()
  rivertype <- read_block()
  point <- read_block()

  list(
    river = river,
    rivertype = rivertype,
    point = point
  )
}

write_sp_riv <- function(path, river_block, type_block, point_block) {
  lines <- c(
    paste(nrow(river_block), ncol(river_block)),
    paste(colnames(river_block), collapse = " "),
    apply(river_block, 1, function(row) {
      paste(
        c(
          fmt_num(as.numeric(row["Index"]), 0),
          fmt_num(as.numeric(row["Down"]), 0),
          fmt_num(as.numeric(row["Type"]), 0),
          fmt_num(as.numeric(row["Slope"]), 10),
          fmt_num(as.numeric(row["Length"]), 6),
          fmt_num(as.numeric(row["BC"]), 0)
        ),
        collapse = " "
      )
    }),
    paste(nrow(type_block), ncol(type_block)),
    paste(colnames(type_block), collapse = " "),
    apply(type_block, 1, function(row) {
      paste(
        c(
          fmt_num(as.numeric(row["Index"]), 0),
          fmt_num(as.numeric(row["Depth"]), 1),
          fmt_num(as.numeric(row["BankSlope"]), 0),
          fmt_num(as.numeric(row["Width"]), 0),
          fmt_num(as.numeric(row["Sinuosity"]), 1),
          fmt_num(as.numeric(row["Manning"]), 2),
          fmt_num(as.numeric(row["Cwr"]), 1),
          fmt_num(as.numeric(row["KsatH"]), 1),
          fmt_num(as.numeric(row["BedThick"]), 1)
        ),
        collapse = " "
      )
    }),
    paste(nrow(point_block), ncol(point_block)),
    paste(colnames(point_block), collapse = " "),
    apply(point_block, 1, function(row) {
      paste(
        c(
          fmt_xy(as.numeric(row["From.x"])),
          fmt_xy(as.numeric(row["From.y"])),
          fmt_num(as.numeric(row["From.z"]), 6),
          fmt_xy(as.numeric(row["To.x"])),
          fmt_xy(as.numeric(row["To.y"])),
          fmt_num(as.numeric(row["To.z"]), 6)
        ),
        collapse = " "
      )
    })
  )

  writeLines(lines, con = path, useBytes = TRUE)
}

normalize_river_result <- function(pr) {
  list(
    river = data.frame(
      pr@river[, c("Index", "Down", "Type", "Slope", "Length", "BC"), drop = FALSE],
      check.names = FALSE
    ),
    rivertype = data.frame(
      pr@rivertype[, c("Index", "Depth", "BankSlope", "Width", "Sinuosity", "Manning", "Cwr", "KsatH", "BedThick"), drop = FALSE],
      check.names = FALSE
    ),
    point = data.frame(
      pr@point[, c("From.x", "From.y", "From.z", "To.x", "To.y", "To.z"), drop = FALSE],
      check.names = FALSE
    )
  )
}

with_loaded_rshud <- function(pkg_path, code) {
  load_all(pkg_path, quiet = TRUE, export_all = FALSE, helpers = FALSE)
  on.exit({
    if (isNamespaceLoaded("rSHUD")) {
      unload("rSHUD")
    }
  }, add = TRUE)
  force(code)
}

generate_from_package <- function(pkg_path, sl, dem, truth_type, truth_down) {
  with_loaded_rshud(pkg_path, {
    set.seed(42)
    pr <- shud.river(sl, dem, rivord = truth_type, rivdown = truth_down)
    normalize_river_result(pr)
  })
}

exact_matrix_equal <- function(x, y) {
  identical(unname(as.matrix(x)), unname(as.matrix(y)))
}

compare_numeric_vector <- function(ref, other, abs_tol = 0) {
  abs_diff <- abs(other - ref)
  rel_diff <- abs_diff / pmax(abs(ref), 1e-12)
  list(
    reference = as.numeric(ref),
    other = as.numeric(other),
    abs_diff = as.numeric(abs_diff),
    rel_diff = as.numeric(rel_diff),
    max_abs_diff = as.numeric(max(abs_diff)),
    max_rel_diff = as.numeric(max(rel_diff)),
    rows_abs_gt_tol = which(abs_diff > abs_tol),
    rows_rel_gt_20pct = which(rel_diff > 0.2)
  )
}

compare_point_block <- function(ref, other) {
  stopifnot(identical(colnames(ref), colnames(other)))
  diffs <- other - ref
  col_metrics <- lapply(names(ref), function(nm) {
    vals <- abs(diffs[[nm]])
    list(
      max_abs_diff = as.numeric(max(vals)),
      rows_abs_nonzero = which(vals > 0)
    )
  })
  names(col_metrics) <- names(ref)

  row_max <- apply(abs(as.matrix(diffs)), 1, max)
  list(
    max_abs_diff = as.numeric(max(abs(as.matrix(diffs)))),
    row_max_abs_diff = as.numeric(row_max),
    rows_with_any_diff = which(row_max > 0),
    columns = col_metrics
  )
}

make_summary_rows <- function(...) {
  items <- list(...)
  do.call(rbind, lapply(items, function(x) {
    data.frame(
      Check = x$Check,
      Pass = if (isTRUE(x$Pass)) "PASS" else "FAIL",
      Metric = x$Metric,
      Value = x$Value,
      stringsAsFactors = FALSE,
      check.names = FALSE
    )
  }))
}

script_dir <- get_script_dir()
repo_root <- normalizePath(file.path(script_dir, "..", ".."), winslash = "/", mustWork = TRUE)

fixture_dir <- file.path(repo_root, "testdata", "ftbug")
output_dir <- file.path(repo_root, "runs", "ftbug", "preprocess")
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

river_shp <- file.path(fixture_dir, "river.shp")
dem_tif <- file.path(fixture_dir, "dem.tif")
truth_down_csv <- file.path(fixture_dir, "truth_down.csv")
truth_type_csv <- file.path(fixture_dir, "truth_type.csv")
truth_sp_riv <- file.path(fixture_dir, "truth.sp.riv")

fixed_pkg_path <- normalizePath(file.path(repo_root, "rSHUD"), winslash = "/", mustWork = TRUE)
old_pkg_path <- normalizePath(file.path(repo_root, "runs", "_cmp", "rSHUD-old"), winslash = "/", mustWork = TRUE)

river_layer <- tools::file_path_sans_ext(basename(river_shp))
river_spdf <- rgdal::readOGR(dsn = dirname(river_shp), layer = river_layer, verbose = FALSE)
sl <- methods::as(river_spdf, "SpatialLines")
dem <- raster::raster(dem_tif)
truth_down_df <- read_numeric_csv(truth_down_csv)
truth_type_df <- read_numeric_csv(truth_type_csv)
truth_down <- truth_down_df$Down
truth_type <- truth_type_df$Type
truth <- read_sp_riv(truth_sp_riv)

assert_true(length(sl) == nrow(truth$river), "River reach count does not match truth.sp.riv.")
assert_true(length(truth_down) == nrow(truth$river), "truth_down.csv row count does not match truth.sp.riv.")
assert_true(length(truth_type) == nrow(truth$river), "truth_type.csv row count does not match truth.sp.riv.")

cat("Generating fixed.sp.riv from", fixed_pkg_path, "\n")
fixed_obj <- generate_from_package(fixed_pkg_path, sl, dem, truth_type, truth_down)
fixed_path <- file.path(output_dir, "fixed.sp.riv")
write_sp_riv(fixed_path, fixed_obj$river, fixed_obj$rivertype, fixed_obj$point)

cat("Generating old.sp.riv from", old_pkg_path, "\n")
old_obj <- generate_from_package(old_pkg_path, sl, dem, truth_type, truth_down)
old_path <- file.path(output_dir, "old.sp.riv")
write_sp_riv(old_path, old_obj$river, old_obj$rivertype, old_obj$point)

slope_only_obj <- fixed_obj
slope_only_obj$river$Slope <- old_obj$river$Slope
slope_only_path <- file.path(output_dir, "slope-only.sp.riv")
write_sp_riv(slope_only_path, slope_only_obj$river, slope_only_obj$rivertype, slope_only_obj$point)

point_only_obj <- fixed_obj
point_only_obj$point <- old_obj$point
point_only_path <- file.path(output_dir, "point-only.sp.riv")
write_sp_riv(point_only_path, point_only_obj$river, point_only_obj$rivertype, point_only_obj$point)

fixed_out <- read_sp_riv(fixed_path)
old_out <- read_sp_riv(old_path)
slope_only_out <- read_sp_riv(slope_only_path)
point_only_out <- read_sp_riv(point_only_path)

truth_vs_fixed_slope <- compare_numeric_vector(truth$river$Slope, fixed_out$river$Slope)
truth_vs_old_slope <- compare_numeric_vector(truth$river$Slope, old_out$river$Slope)
fixed_vs_old_slope <- compare_numeric_vector(fixed_out$river$Slope, old_out$river$Slope)

truth_vs_fixed_point <- compare_point_block(truth$point, fixed_out$point)
truth_vs_old_point <- compare_point_block(truth$point, old_out$point)
fixed_vs_old_point <- compare_point_block(fixed_out$point, old_out$point)

locked_fields_equal <- exact_matrix_equal(
  fixed_out$river[, c("Down", "Type", "Length"), drop = FALSE],
  old_out$river[, c("Down", "Type", "Length"), drop = FALSE]
)

slope_only_exact_non_slope <- exact_matrix_equal(
  fixed_out$river[, setdiff(colnames(fixed_out$river), "Slope"), drop = FALSE],
  slope_only_out$river[, setdiff(colnames(slope_only_out$river), "Slope"), drop = FALSE]
) &&
  exact_matrix_equal(fixed_out$rivertype, slope_only_out$rivertype) &&
  exact_matrix_equal(fixed_out$point, slope_only_out$point)

slope_only_slope_matches_old <- exact_matrix_equal(
  slope_only_out$river[, "Slope", drop = FALSE],
  old_out$river[, "Slope", drop = FALSE]
)

point_only_exact_blocks_1_2 <- exact_matrix_equal(fixed_out$river, point_only_out$river) &&
  exact_matrix_equal(fixed_out$rivertype, point_only_out$rivertype)

point_only_point_matches_old <- exact_matrix_equal(point_only_out$point, old_out$point)

fixed_slope_abs_tol <- 1e-6
fixed_slope_matches_truth <- truth_vs_fixed_slope$max_abs_diff <= fixed_slope_abs_tol
old_slope_has_major_diff <- length(truth_vs_old_slope$rows_rel_gt_20pct) >= 1L
slope_only_only_changes_slope <- slope_only_exact_non_slope && slope_only_slope_matches_old &&
  !exact_matrix_equal(fixed_out$river[, "Slope", drop = FALSE], slope_only_out$river[, "Slope", drop = FALSE])
point_only_only_changes_point <- point_only_exact_blocks_1_2 && point_only_point_matches_old &&
  !exact_matrix_equal(fixed_out$point, point_only_out$point)

acceptance <- list(
  fixed_slope_matches_truth_near_zero = list(
    pass = fixed_slope_matches_truth,
    tolerance = fixed_slope_abs_tol,
    max_abs_diff = truth_vs_fixed_slope$max_abs_diff
  ),
  old_slope_differs_from_truth = list(
    pass = old_slope_has_major_diff,
    threshold_rel_diff = 0.2,
    reaches_gt_20pct = truth_vs_old_slope$rows_rel_gt_20pct,
    max_rel_diff = truth_vs_old_slope$max_rel_diff
  ),
  fixed_old_locked_fields_identical = list(
    pass = locked_fields_equal
  ),
  slope_only_changes_only_block1_col4 = list(
    pass = slope_only_only_changes_slope
  ),
  point_only_changes_only_block3 = list(
    pass = point_only_only_changes_point
  )
)

compare_report <- list(
  generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
  seed = 42,
  inputs = list(
    fixture_dir = fixture_dir,
    fixed_pkg_path = fixed_pkg_path,
    old_pkg_path = old_pkg_path,
    truth_sp_riv = truth_sp_riv
  ),
  outputs = list(
    fixed = fixed_path,
    old = old_path,
    slope_only = slope_only_path,
    point_only = point_only_path
  ),
  comparisons = list(
    truth_vs_fixed = list(
      slope = truth_vs_fixed_slope,
      point_block = truth_vs_fixed_point
    ),
    truth_vs_old = list(
      slope = truth_vs_old_slope,
      point_block = truth_vs_old_point
    ),
    fixed_vs_old = list(
      locked_fields_identical = locked_fields_equal,
      down = list(
        identical = exact_matrix_equal(fixed_out$river[, "Down", drop = FALSE], old_out$river[, "Down", drop = FALSE])
      ),
      type = list(
        identical = exact_matrix_equal(fixed_out$river[, "Type", drop = FALSE], old_out$river[, "Type", drop = FALSE])
      ),
      length = list(
        identical = exact_matrix_equal(fixed_out$river[, "Length", drop = FALSE], old_out$river[, "Length", drop = FALSE])
      ),
      slope = fixed_vs_old_slope,
      point_block = fixed_vs_old_point
    ),
    slope_only_vs_fixed = list(
      only_block1_col4_differs = slope_only_only_changes_slope
    ),
    point_only_vs_fixed = list(
      only_block3_differs = point_only_only_changes_point
    )
  ),
  acceptance = acceptance
)

compare_path <- file.path(output_dir, "compare.json")
writeLines(
  jsonlite::toJSON(compare_report, auto_unbox = TRUE, pretty = TRUE, digits = NA),
  con = compare_path,
  useBytes = TRUE
)

summary_rows <- make_summary_rows(
  list(
    Check = "fixed slope ~= truth",
    Pass = fixed_slope_matches_truth,
    Metric = "max_abs_diff",
    Value = format(truth_vs_fixed_slope$max_abs_diff, scientific = TRUE, digits = 6)
  ),
  list(
    Check = "old slope != truth",
    Pass = old_slope_has_major_diff,
    Metric = "reaches_rel_diff_gt_20pct",
    Value = paste(truth_vs_old_slope$rows_rel_gt_20pct, collapse = ",")
  ),
  list(
    Check = "old/fixed Down-Type-Length identical",
    Pass = locked_fields_equal,
    Metric = "exact_match",
    Value = as.character(locked_fields_equal)
  ),
  list(
    Check = "slope-only only changes Block1 Col4",
    Pass = slope_only_only_changes_slope,
    Metric = "exact_structure_check",
    Value = as.character(slope_only_only_changes_slope)
  ),
  list(
    Check = "point-only only changes Block3",
    Pass = point_only_only_changes_point,
    Metric = "exact_structure_check",
    Value = as.character(point_only_only_changes_point)
  ),
  list(
    Check = "truth vs fixed point block",
    Pass = TRUE,
    Metric = "max_abs_diff",
    Value = format(truth_vs_fixed_point$max_abs_diff, scientific = TRUE, digits = 6)
  ),
  list(
    Check = "truth vs old point block",
    Pass = TRUE,
    Metric = "max_abs_diff",
    Value = format(truth_vs_old_point$max_abs_diff, scientific = TRUE, digits = 6)
  )
)

cat("\nSummary\n")
print(summary_rows, row.names = FALSE, right = FALSE)
cat("\nArtifacts written to", output_dir, "\n")
cat("compare.json:", compare_path, "\n")

overall_pass <- all(vapply(acceptance, function(x) isTRUE(x$pass), logical(1)))
if (!overall_pass) {
  quit(status = 1L)
}
