#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE)

suppressPackageStartupMessages({
  library(sf)
  library(sp)
  library(raster)
  library(jsonlite)
})

get_script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) < 1) {
    return(normalizePath(getwd()))
  }
  script_path <- sub("^--file=", "", file_arg[1])
  dirname(normalizePath(script_path))
}

fmt_num <- function(x, digits = 6) {
  if (length(x) != 1 || is.na(x) || !is.finite(x)) {
    return("NA")
  }
  formatC(x, format = "fg", digits = digits)
}

num_stats <- function(x) {
  x <- as.numeric(x)
  n_total <- length(x)
  n_na <- sum(is.na(x))
  x_ok <- x[!is.na(x)]
  if (length(x_ok) < 1) {
    return(list(n = n_total, n_na = n_na))
  }
  list(
    n = n_total,
    n_na = n_na,
    min = min(x_ok),
    p05 = unname(stats::quantile(x_ok, 0.05)),
    median = stats::median(x_ok),
    mean = mean(x_ok),
    p95 = unname(stats::quantile(x_ok, 0.95)),
    max = max(x_ok),
    sd = stats::sd(x_ok)
  )
}

stats_one_line <- function(st) {
  if (is.null(st$min)) {
    return(paste0("n=", st$n, ", n_na=", st$n_na))
  }
  paste0(
    "n=", st$n,
    ", n_na=", st$n_na,
    ", min=", fmt_num(st$min),
    ", p05=", fmt_num(st$p05),
    ", median=", fmt_num(st$median),
    ", mean=", fmt_num(st$mean),
    ", p95=", fmt_num(st$p95),
    ", max=", fmt_num(st$max),
    ", sd=", fmt_num(st$sd)
  )
}

# ----------------------------------------------------------------------
# Helper functions extracted from old rSHUD workspace (no rgeos/rgdal).
# Do NOT source whole files; only keep minimal functions needed.
# Sources (for reference):
# - /Users/danker/Desktop/Hydro-SHUD/rSHUD/R/Func_Misc.R
# - /Users/danker/Desktop/Hydro-SHUD/rSHUD/R/GIS_RiverProcess.R
# ----------------------------------------------------------------------

rowMatch <- function(x, m) {
  n <- length(x)
  nc <- ncol(m)
  if (n != nc) {
    return(FALSE)
  }
  y <- m * 1
  for (i in seq_len(nc)) {
    y[, i] <- (m[, i] - x[i])
  }
  apply(y, 1, FUN = function(x) {
    all(x == 0)
  })
}

extractCoords <- function(x, unique = TRUE, aslist = FALSE) {
  spl <- methods::as(x, "SpatialLines")
  spp <- methods::as(spl, "SpatialPoints")
  pts <- sp::coordinates(spp)
  if (unique) {
    return(unique(pts))
  }
  pts
}

xy2ID <- function(xy, coord) {
  if (!(is.matrix(xy) || is.data.frame(xy))) {
    xy <- matrix(xy, ncol = 2)
  }
  ng <- nrow(xy)
  id <- rep(0, ng)
  for (i in seq_len(ng)) {
    dd <- which(rowMatch(xy[i, ], coord))
    if (length(dd) > 0) {
      id[i] <- dd
    }
  }
  id
}

NodeIDList <- function(sp, coord = extractCoords(sp, unique = TRUE)) {
  pt.list <- unlist(sp::coordinates(sp), recursive = FALSE)
  lapply(pt.list, function(x) {
    xy2ID(x, coord = coord)
  })
}

FromToNode <- function(sp, coord = extractCoords(sp, unique = TRUE), simplify = TRUE) {
  if (simplify) {
    ext <- raster::extent(sp)
    tol <- (ext[2] - ext[1]) * 0.01
    old_s2 <- sf::sf_use_s2()
    on.exit(suppressMessages(sf::sf_use_s2(old_s2)), add = TRUE)
    suppressMessages(sf::sf_use_s2(FALSE))
    sp.sf <- sf::st_as_sf(sp)
    sp.sf <- sf::st_simplify(sp.sf, preserveTopology = FALSE, dTolerance = tol)
    sp <- methods::as(sp.sf, "Spatial")
  }
  id.list <- NodeIDList(sp, coord = coord)
  frto <- cbind(
    unlist(lapply(id.list, function(x) x[1])),
    unlist(lapply(id.list, function(x) x[length(x)]))
  )
  frto <- cbind(seq_len(length(sp)), frto)
  colnames(frto) <- c("ID", "FrNode", "ToNode")
  rbind(frto)
}

simplify_sp_lines <- function(sp) {
  ext <- raster::extent(sp)
  tol <- (ext[2] - ext[1]) * 0.01
  old_s2 <- sf::sf_use_s2()
  on.exit(suppressMessages(sf::sf_use_s2(old_s2)), add = TRUE)
  suppressMessages(sf::sf_use_s2(FALSE))
  sp.sf <- sf::st_as_sf(sp)
  sp.sf <- sf::st_simplify(sp.sf, preserveTopology = FALSE, dTolerance = tol)
  methods::as(sp.sf, "Spatial")
}

segment_first_vertices <- function(sp) {
  sp <- methods::as(sp, "SpatialLines")
  pt.list <- unlist(sp::coordinates(sp), recursive = FALSE)
  if (length(pt.list) != length(sp)) {
    stop("Unexpected SpatialLines structure: multiple Line parts per segment.")
  }
  ret <- do.call(rbind, lapply(pt.list, function(x) {
    x[1, 1:2, drop = FALSE]
  }))
  colnames(ret) <- c("X", "Y")
  ret
}

assert_true <- function(ok, msg) {
  if (!isTRUE(ok)) {
    stop(msg, call. = FALSE)
  }
}

run_one_case <- function(case_name, rds_path) {
  message("Case: ", case_name, " (", basename(rds_path), ")")
  dat <- readRDS(rds_path)
  sl <- dat$sl
  dem <- dat$dem

  # Validation 1: coord table row count differs after simplify
  xy_orig <- extractCoords(sl)
  sl_simp_sp <- simplify_sp_lines(sl)
  xy_simp <- extractCoords(sl_simp_sp)
  N_orig <- nrow(xy_orig)
  M_simp <- nrow(xy_simp)
  assert_true(N_orig != M_simp, paste0(
    "Validation1 failed: nrow(xy_orig) == nrow(xy_simp) == ", N_orig
  ))

  # Validation 2: reproduce mismatch (ft index from simplified coord used on original coord)
  ft_all <- FromToNode(sl, simplify = TRUE)[, 2:3, drop = FALSE]
  assert_true(all(ft_all[, 1] >= 1) && all(ft_all[, 1] <= M_simp), paste0(
    "Validation2 failed: ft FrNode index out of range for xy_simp (M_simp=", M_simp, ")"
  ))

  wrong_from <- xy_orig[ft_all[, 1], , drop = FALSE]
  right_from <- xy_simp[ft_all[, 1], , drop = FALSE]

  mismatch_component_rate <- sum(wrong_from != right_from) / nrow(ft_all)
  mismatch_row_rate <- sum(rowSums(wrong_from != right_from) > 0) / nrow(ft_all)
  assert_true(mismatch_component_rate > 0, "Validation2 failed: mismatch_component_rate == 0")

  z_wrong <- raster::extract(dem, wrong_from)
  z_right <- raster::extract(dem, right_from)
  dz_wrong_right <- z_wrong - z_right

  # Validation 3: fixed approach (explicit coord=xy_orig, simplify=FALSE)
  ft_fixed <- FromToNode(sl, coord = xy_orig, simplify = FALSE)[, 2:3, drop = FALSE]
  fixed_from <- xy_orig[ft_fixed[, 1], , drop = FALSE]
  true_from <- segment_first_vertices(sl)
  max_abs_diff <- suppressWarnings(max(abs(fixed_from - true_from)))
  fixed_endpoints_ok <- is.finite(max_abs_diff) && max_abs_diff < 1e-9
  assert_true(fixed_endpoints_ok, paste0(
    "Validation3 failed: fixed_from != segment first vertices (max_abs_diff=", fmt_num(max_abs_diff), ")"
  ))

  z_fixed <- raster::extract(dem, fixed_from)
  dz_fixed_right <- z_fixed - z_right

  # Print structured report block
  cat("\n==============================\n")
  cat("Mock river case: ", case_name, "\n", sep = "")
  cat("Input: ", basename(rds_path), "\n", sep = "")
  cat("Segments: ", length(sl), "\n", sep = "")
  cat("Validation1 (coord rows): N_orig=", N_orig, ", M_simp=", M_simp, "\n", sep = "")
  cat(
    "Validation2 (index mismatch): mismatch_component_rate=",
    fmt_num(mismatch_component_rate, digits = 6),
    ", mismatch_row_rate=",
    fmt_num(mismatch_row_rate, digits = 6),
    "\n",
    sep = ""
  )
  cat("Elevation diff (wrong-right): ", stats_one_line(num_stats(dz_wrong_right)), "\n", sep = "")
  cat(
    "Validation3 (fixed endpoints): max_abs_diff=",
    fmt_num(max_abs_diff, digits = 12),
    "\n",
    sep = ""
  )
  cat("Elevation diff (fixed-right): ", stats_one_line(num_stats(dz_fixed_right)), "\n", sep = "")
  cat("==============================\n")

  list(
    case = case_name,
    input = basename(rds_path),
    n_segments = length(sl),
    N_orig = N_orig,
    M_simp = M_simp,
    mismatch_component_rate = mismatch_component_rate,
    mismatch_row_rate = mismatch_row_rate,
    elev_diff_wrong_right = num_stats(dz_wrong_right),
    fixed_endpoints_ok = fixed_endpoints_ok,
    fixed_max_abs_diff = max_abs_diff,
    elev_diff_fixed_right = num_stats(dz_fixed_right)
  )
}

script_dir <- get_script_dir()
mock_dir <- script_dir

cases <- c(
  mock1_y_shape = file.path(mock_dir, "mock1_y_shape.rds"),
  mock2_tree = file.path(mock_dir, "mock2_tree.rds"),
  mock3_qhh_subset = file.path(mock_dir, "mock3_qhh_subset.rds")
)

results <- list()
had_error <- FALSE

for (nm in names(cases)) {
  rds_path <- cases[[nm]]
  if (!file.exists(rds_path)) {
    message("Skip: ", nm, " (missing file: ", rds_path, ")")
    had_error <- TRUE
    next
  }
  out <- tryCatch(
    run_one_case(nm, rds_path),
    error = function(e) {
      had_error <<- TRUE
      message("ERROR in ", nm, ": ", conditionMessage(e))
      list(case = nm, input = basename(rds_path), error = conditionMessage(e))
    }
  )
  results[[nm]] <- out
}

report <- list(
  run_info = list(
    time = format(Sys.time(), "%Y-%m-%d %H:%M:%S %z"),
    r_version = R.version.string,
    sf_use_s2 = sf::sf_use_s2()
  ),
  cases = results
)

report_path <- file.path(mock_dir, "mismatch_report.json")
jsonlite::write_json(report, report_path, pretty = TRUE, auto_unbox = TRUE, digits = 10)
message("Saved JSON report: ", report_path)

if (had_error) {
  quit(status = 1)
}
