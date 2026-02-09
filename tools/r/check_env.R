#!/usr/bin/env Rscript

options(warn = 1)

parse_args <- function(args) {
  out <- list(
    lib = NULL,
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
    if (a == "--lib") {
      if (i == length(args)) {
        stop("Missing value for --lib")
      }
      out$lib <- args[[i + 1]]
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

info <- function(...) {
  cat(..., "\n", sep = "")
}

die <- function(..., status = 1) {
  message(...)
  quit(status = status, save = "no")
}

check_pkg <- function(pkg) {
  err <- NULL
  ok <- tryCatch(
    {
      loadNamespace(pkg)
      TRUE
    },
    error = function(e) {
      err <<- conditionMessage(e)
      FALSE
    }
  )
  list(ok = ok, err = err)
}

args <- parse_args(commandArgs(trailingOnly = TRUE))
if (isTRUE(args$help)) {
  info("Usage: Rscript tools/r/check_env.R [--lib <path>] [--skip-rshud] [--skip-lwgeom]")
  info("")
  info("Checks required R packages and exits non-zero if missing.")
  quit(status = 0, save = "no")
}

sp <- script_path()
script_dir <- if (is.null(sp)) getwd() else dirname(sp)
repo_root <- normalizePath(file.path(script_dir, "..", ".."), winslash = "/", mustWork = FALSE)
default_lib_dir <- normalizePath(file.path(repo_root, ".Rlib"), winslash = "/", mustWork = FALSE)

if (!is.null(args$lib)) {
  lib_dir <- args$lib
  if (!grepl("^/", lib_dir) && !grepl("^[A-Za-z]:", lib_dir)) {
    lib_dir <- file.path(repo_root, lib_dir)
  }
  lib_dir <- normalizePath(lib_dir, winslash = "/", mustWork = FALSE)
  if (dir.exists(lib_dir) && !(lib_dir %in% .libPaths())) {
    .libPaths(c(lib_dir, .libPaths()))
  }
}

if (dir.exists(default_lib_dir) && !(default_lib_dir %in% .libPaths())) {
  .libPaths(c(default_lib_dir, .libPaths()))
}

required <- c("sf", "terra", "ncdf4", "units")
if (!isTRUE(args$skip_lwgeom)) required <- c(required, "lwgeom")
if (!isTRUE(args$skip_rshud)) required <- c(required, "rSHUD")

missing <- list()
for (pkg in required) {
  res <- check_pkg(pkg)
  if (isTRUE(res$ok)) next
  missing[[pkg]] <- res$err
}

if (length(missing) > 0) {
  info("[check_env] R: ", R.version.string)
  info("[check_env] .libPaths():")
  for (p in .libPaths()) info("  - ", p)
  info("")
  info("[check_env] Missing / broken packages:")
  for (pkg in names(missing)) {
    reason <- missing[[pkg]]
    if (is.null(reason) || !nzchar(reason)) {
      info("  - ", pkg)
    } else {
      info("  - ", pkg, ": ", reason)
    }
  }
  info("")
  info("[check_env] Fix:")
  install_cmd <- "Rscript tools/r/install_deps.R"
  check_cmd <- "Rscript tools/r/check_env.R"
  if (isTRUE(args$skip_rshud)) {
    install_cmd <- paste(install_cmd, "--skip-rshud")
    check_cmd <- paste(check_cmd, "--skip-rshud")
  }
  if (isTRUE(args$skip_lwgeom)) {
    install_cmd <- paste(install_cmd, "--skip-lwgeom")
    check_cmd <- paste(check_cmd, "--skip-lwgeom")
  }
  info("  ", install_cmd)
  info("  R_LIBS_USER=\"$PWD/.Rlib\" ", check_cmd)
  quit(status = 1, save = "no")
}

info("[check_env] OK")
info("[check_env] R: ", R.version.string)
info("[check_env] .libPaths():")
for (p in .libPaths()) info("  - ", p)
info("")
for (pkg in required) {
  ver <- as.character(utils::packageVersion(pkg))
  info("[check_env] ", pkg, ": ", ver)
}
quit(status = 0, save = "no")
