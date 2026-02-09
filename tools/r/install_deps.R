#!/usr/bin/env Rscript

options(warn = 1)

parse_args <- function(args) {
  out <- list(
    lib = NULL,
    rshud = NULL,
    skip_rshud = FALSE,
    skip_lwgeom = FALSE,
    help = FALSE
  )

  i <- 1
  while (i <= length(args)) {
    a <- args[[i]]
    if (a %in% c("-h", "--help")) {
      out$help <- TRUE
      i <- i + 1
      next
    }
    if (a == "--skip-rshud") {
      out$skip_rshud <- TRUE
      i <- i + 1
      next
    }
    if (a == "--skip-lwgeom") {
      out$skip_lwgeom <- TRUE
      i <- i + 1
      next
    }
    if (a %in% c("--lib", "--rshud")) {
      if (i == length(args)) {
        stop(paste0("Missing value for ", a))
      }
      val <- args[[i + 1]]
      if (a == "--lib") out$lib <- val
      if (a == "--rshud") out$rshud <- val
      i <- i + 2
      next
    }
    stop(paste0("Unknown argument: ", a))
  }
  out
}

script_path <- function() {
  cmd <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", cmd, value = TRUE)
  if (length(file_arg) == 0) return(NULL)
  normalizePath(sub("^--file=", "", file_arg[[1]]), winslash = "/", mustWork = FALSE)
}

die <- function(..., status = 1) {
  message(...)
  quit(status = status, save = "no")
}

info <- function(...) {
  cat(..., "\n", sep = "")
}

args <- parse_args(commandArgs(trailingOnly = TRUE))
if (isTRUE(args$help)) {
  info("Usage: Rscript tools/r/install_deps.R [--lib <path>] [--rshud <path>] [--skip-rshud] [--skip-lwgeom]")
  info("")
  info("Installs required R packages into a project-local library (default: <repo>/.Rlib).")
  info("Also installs local rSHUD from the git submodule by default.")
  quit(status = 0, save = "no")
}

sp <- script_path()
script_dir <- if (is.null(sp)) getwd() else dirname(sp)
repo_root <- normalizePath(file.path(script_dir, "..", ".."), winslash = "/", mustWork = FALSE)

lib_dir <- if (!is.null(args$lib)) args$lib else file.path(repo_root, ".Rlib")
if (!grepl("^/", lib_dir) && !grepl("^[A-Za-z]:", lib_dir)) {
  lib_dir <- file.path(repo_root, lib_dir)
}
lib_dir <- normalizePath(lib_dir, winslash = "/", mustWork = FALSE)

dir.create(lib_dir, recursive = TRUE, showWarnings = FALSE)
.libPaths(c(lib_dir, .libPaths()))

cran_repo <- Sys.getenv("SHUDNC_CRAN_REPO")
if (nchar(cran_repo) == 0) cran_repo <- "https://cloud.r-project.org"
options(repos = c(CRAN = cran_repo))

info("[install_deps] repo_root: ", repo_root)
info("[install_deps] lib_dir:   ", lib_dir)
info("[install_deps] CRAN:      ", getOption("repos")[["CRAN"]])
info("")

cran_pkgs <- c("sf", "terra", "ncdf4", "units")
if (!isTRUE(args$skip_lwgeom)) cran_pkgs <- c(cran_pkgs, "lwgeom")

missing <- character(0)
for (pkg in cran_pkgs) {
  if (requireNamespace(pkg, quietly = TRUE)) {
    info("[install_deps] OK: ", pkg)
    next
  }
  info("[install_deps] Installing: ", pkg)
  tryCatch(
    utils::install.packages(pkg, lib = lib_dir, dependencies = c("Depends", "Imports", "LinkingTo")),
    error = function(e) die("[install_deps] Failed to install ", pkg, ": ", conditionMessage(e))
  )
  if (!requireNamespace(pkg, quietly = TRUE)) {
    missing <- c(missing, pkg)
  }
}

if (!isTRUE(args$skip_rshud)) {
  rshud_path <- if (!is.null(args$rshud)) args$rshud else file.path(repo_root, "rSHUD")
  if (!grepl("^/", rshud_path) && !grepl("^[A-Za-z]:", rshud_path)) {
    rshud_path <- file.path(repo_root, rshud_path)
  }
  rshud_path <- normalizePath(rshud_path, winslash = "/", mustWork = FALSE)

  if (!dir.exists(rshud_path)) {
    die(
      "[install_deps] rSHUD path not found: ", rshud_path, "\n",
      "[install_deps] Did you init submodules?\n",
      "  git submodule update --init --recursive\n",
      "[install_deps] Or re-run with --skip-rshud."
    )
  }

  if (requireNamespace("rSHUD", quietly = TRUE)) {
    info("[install_deps] OK: rSHUD (already installed)")
  } else {
    info("[install_deps] Installing local rSHUD: ", rshud_path)
    r_bin <- file.path(R.home("bin"), "R")
    if (!file.exists(r_bin)) r_bin <- "R"

    cmd_args <- c(
      "CMD",
      "INSTALL",
      paste0("--library=", lib_dir),
      rshud_path
    )
    status <- system2(r_bin, args = cmd_args)
    if (!identical(status, 0L)) {
      die(
        "[install_deps] R CMD INSTALL rSHUD failed (exit code ", status, ").\n",
        "[install_deps] Note: current rSHUD may still depend on legacy GIS packages.\n",
        "[install_deps] If you are in the middle of the sf/terra migration, re-run with:\n",
        "  Rscript tools/r/install_deps.R --skip-rshud\n"
      )
    }
    if (!requireNamespace("rSHUD", quietly = TRUE)) {
      missing <- c(missing, "rSHUD")
    }
  }
}

if (length(missing) > 0) {
  die(
    "[install_deps] Some packages are still missing after install:\n  - ",
    paste(missing, collapse = "\n  - ")
  )
}

info("")
info("[install_deps] Done.")
quit(status = 0, save = "no")
