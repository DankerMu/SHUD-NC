#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE, scipen = 999)

suppressPackageStartupMessages({
  library(sf)
  library(terra)
  library(RTriangle)
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

with_dir <- function(dir, code) {
  old <- getwd()
  on.exit(setwd(old), add = TRUE)
  setwd(dir)
  force(code)
}

assert_true <- function(ok, msg) {
  if (!isTRUE(ok)) {
    stop(msg, call. = FALSE)
  }
}

fmt_num <- function(x, digits = 6) {
  if (length(x) != 1L || is.na(x)) {
    stop("fmt_num expects one non-NA value.", call. = FALSE)
  }
  if (abs(x - round(x)) < 1e-9) {
    return(formatC(round(x), format = "f", digits = 0))
  }
  formatC(x, format = "f", digits = digits, drop0trailing = TRUE)
}

read_sp_riv <- function(path) {
  lines <- readLines(path, warn = FALSE)
  cursor <- 1L

  read_block <- function() {
    dims <- as.integer(strsplit(trimws(lines[[cursor]]), "\\s+")[[1]])
    assert_true(length(dims) >= 2L, paste("Invalid block header in", path, "at line", cursor))
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

  list(
    river = read_block(),
    rivertype = read_block(),
    point = read_block()
  )
}

extract_dem_values <- function(dem, coords) {
  vals <- terra::extract(dem, coords)
  vals[[ncol(vals)]]
}

signed_triangle_area <- function(points, tri_row) {
  p1 <- points[tri_row[1], , drop = FALSE]
  p2 <- points[tri_row[2], , drop = FALSE]
  p3 <- points[tri_row[3], , drop = FALSE]
  0.5 * ((p2[1, 1] - p1[1, 1]) * (p3[1, 2] - p1[1, 2]) - (p2[1, 2] - p1[1, 2]) * (p3[1, 1] - p1[1, 1]))
}

triangle_polygon <- function(points, tri_row) {
  coords <- points[tri_row, , drop = FALSE]
  sf::st_polygon(list(rbind(coords, coords[1, , drop = FALSE])))
}

line_geom_length <- function(geom, crs) {
  if (length(geom) == 0L) {
    return(0)
  }
  if (inherits(geom, "LINESTRING") || inherits(geom, "MULTILINESTRING")) {
    return(as.numeric(sf::st_length(sf::st_sfc(geom, crs = crs))))
  }
  if (inherits(geom, "GEOMETRYCOLLECTION")) {
    return(sum(vapply(geom, line_geom_length, numeric(1), crs = crs)))
  }
  0
}

build_mesh <- function(basin_sf, truth_sp_riv, dem) {
  basin_coords <- sf::st_coordinates(sf::st_geometry(basin_sf)[[1]])[, 1:2, drop = FALSE]
  basin_coords <- basin_coords[-nrow(basin_coords), , drop = FALSE]

  reach_from <- truth_sp_riv$point[, c("From.x", "From.y"), drop = FALSE]
  reach_to <- truth_sp_riv$point[, c("To.x", "To.y"), drop = FALSE]
  names(reach_from) <- c("x", "y")
  names(reach_to) <- c("x", "y")
  reach_points <- rbind(reach_from, reach_to)

  point_df <- as.data.frame(rbind(
    data.frame(x = basin_coords[, 1], y = basin_coords[, 2]),
    reach_points
  ))
  point_df <- point_df[!duplicated(point_df), , drop = FALSE]
  points <- as.matrix(point_df)

  boundary_n <- nrow(basin_coords)
  segments <- cbind(seq_len(boundary_n), c(seq.int(2, boundary_n), 1))

  tri_raw <- RTriangle::triangulate(RTriangle::pslg(P = points, S = segments), Q = TRUE)
  triangles <- tri_raw$T
  neighbors <- tri_raw$NB
  neighbors[neighbors < 0] <- 0L

  signed_area <- apply(triangles, 1, signed_triangle_area, points = tri_raw$P)
  flip_idx <- which(signed_area < 0)
  if (length(flip_idx) > 0L) {
    triangles[flip_idx, c(2, 3)] <- triangles[flip_idx, c(3, 2)]
    neighbors[flip_idx, c(2, 3)] <- neighbors[flip_idx, c(3, 2)]
  }

  node_z <- extract_dem_values(dem, tri_raw$P)
  assert_true(all(is.finite(node_z)), "Failed to sample DEM elevations at mesh nodes.")

  element_z <- vapply(seq_len(nrow(triangles)), function(i) {
    mean(node_z[triangles[i, ]])
  }, numeric(1))

  tri_sf <- sf::st_sf(
    ID = seq_len(nrow(triangles)),
    geometry = sf::st_sfc(
      lapply(seq_len(nrow(triangles)), function(i) triangle_polygon(tri_raw$P, triangles[i, ])),
      crs = sf::st_crs(basin_sf)
    )
  )

  centroid_inside <- sf::st_within(sf::st_centroid(sf::st_geometry(tri_sf)), basin_sf, sparse = FALSE)[, 1]
  assert_true(all(centroid_inside), "Generated triangles extend outside the basin polygon.")
  assert_true(nrow(triangles) >= 10 && nrow(triangles) <= 20,
              paste("Expected 10-20 triangles, got", nrow(triangles)))

  list(
    points = tri_raw$P,
    triangles = triangles,
    neighbors = neighbors,
    node_z = node_z,
    element_z = element_z,
    triangles_sf = tri_sf
  )
}

build_rivseg <- function(river_sf, triangles_sf) {
  crs_use <- sf::st_crs(river_sf)
  rows <- vector("list", length = nrow(river_sf) * nrow(triangles_sf))
  idx <- 1L

  for (i in seq_len(nrow(river_sf))) {
    hit_count <- 0L
    reach_geom <- sf::st_geometry(river_sf)[[i]]
    for (j in seq_len(nrow(triangles_sf))) {
      tri_geom <- sf::st_geometry(triangles_sf)[[j]]
      ints <- suppressWarnings(sf::st_intersection(
        sf::st_sfc(reach_geom, crs = crs_use),
        sf::st_sfc(tri_geom, crs = crs_use)
      ))
      if (length(ints) < 1L || sf::st_is_empty(ints)) {
        next
      }
      seg_len <- line_geom_length(ints[[1]], crs_use)
      if (!is.finite(seg_len) || seg_len <= 1e-6) {
        next
      }
      rows[[idx]] <- data.frame(
        INDEX = idx,
        iRiv = as.integer(river_sf$Index[i]),
        iEle = as.integer(triangles_sf$ID[j]),
        Length = seg_len,
        stringsAsFactors = FALSE
      )
      idx <- idx + 1L
      hit_count <- hit_count + 1L
    }
    assert_true(hit_count > 0L, paste("River reach", river_sf$Index[i], "does not intersect any mesh element."))
  }

  rivseg <- do.call(rbind, rows[seq_len(idx - 1L)])
  assert_true(nrow(rivseg) > 0L, "No river-element intersections were generated.")

  ref_len <- as.numeric(sf::st_length(river_sf))
  got_len <- stats::aggregate(Length ~ iRiv, rivseg, sum)
  got_len <- got_len[match(river_sf$Index, got_len$iRiv), "Length"]
  assert_true(all(abs(got_len - ref_len) < 1e-3),
              "River-segment lengths do not sum back to the original reach lengths.")

  rivseg
}

write_mesh_file <- function(path, mesh) {
  ele_rows <- vapply(seq_len(nrow(mesh$triangles)), function(i) {
    paste(
      c(
        i,
        mesh$triangles[i, 1],
        mesh$triangles[i, 2],
        mesh$triangles[i, 3],
        mesh$neighbors[i, 1],
        mesh$neighbors[i, 2],
        mesh$neighbors[i, 3],
        fmt_num(mesh$element_z[i], 6)
      ),
      collapse = "\t"
    )
  }, character(1))

  node_rows <- vapply(seq_len(nrow(mesh$points)), function(i) {
    paste(
      c(
        i,
        fmt_num(mesh$points[i, 1], 6),
        fmt_num(mesh$points[i, 2], 6),
        fmt_num(10.0, 1),
        fmt_num(mesh$node_z[i], 6)
      ),
      collapse = "\t"
    )
  }, character(1))

  lines <- c(
    paste(nrow(mesh$triangles), 8, sep = "\t"),
    "ID\tNode1\tNode2\tNode3\tNabr1\tNabr2\tNabr3\tZmax",
    ele_rows,
    paste(nrow(mesh$points), 5, sep = "\t"),
    "ID\tx\ty\tAqDepth\tZmax",
    node_rows
  )

  writeLines(lines, path, useBytes = TRUE)
}

write_att_file <- function(path, num_ele) {
  rows <- vapply(seq_len(num_ele), function(i) {
    paste(c(i, 1, 1, 1, 1, 1, 0, 0, 0), collapse = "\t")
  }, character(1))

  lines <- c(
    paste(num_ele, 9, sep = "\t"),
    "INDEX\tiSoil\tiGeol\tiLC\tiForc\tiMF\tiBC\tiSS\tiLake",
    rows
  )

  writeLines(lines, path, useBytes = TRUE)
}

write_table_file <- function(path, header, rows) {
  lines <- c(
    paste(nrow(rows), length(header), sep = "\t"),
    paste(header, collapse = "\t"),
    apply(rows, 1, function(row) paste(row, collapse = "\t"))
  )
  writeLines(lines, path, useBytes = TRUE)
}

build_time_axis_days <- function(total_days) {
  seq(0, total_days - 1 / 24, by = 1 / 24)
}

write_forcing_csv <- function(path, total_days, mode, start_date = 20200101L) {
  times_day <- build_time_axis_days(total_days)
  nrow_out <- length(times_day)
  end_date <- if (total_days == 10) 20200111L else 20200131L

  forcing <- data.frame(
    Time_Day = times_day,
    APCP = 0,
    TMP = 0,
    SPFH = 0,
    UGRD = 0,
    DSWRF = 0,
    check.names = FALSE
  )

  if (identical(mode, "coupled")) {
    forcing$TMP <- 15
    forcing$SPFH <- 0.6
    forcing$UGRD <- 2.0
    forcing$DSWRF <- 200
    pulse <- forcing$Time_Day >= 2.0 & forcing$Time_Day < 2.25
    forcing$APCP[pulse] <- 10
  }

  lines <- c(
    paste(nrow_out, 6, start_date, end_date),
    "Time_Day\tAPCP\tTMP\tSPFH\tUGRD\tDSWRF",
    apply(forcing, 1, function(row) {
      paste(
        c(
          fmt_num(as.numeric(row[["Time_Day"]]), 10),
          fmt_num(as.numeric(row[["APCP"]]), 6),
          fmt_num(as.numeric(row[["TMP"]]), 6),
          fmt_num(as.numeric(row[["SPFH"]]), 6),
          fmt_num(as.numeric(row[["UGRD"]]), 6),
          fmt_num(as.numeric(row[["DSWRF"]]), 6)
        ),
        collapse = "\t"
      )
    })
  )

  writeLines(lines, path, useBytes = TRUE)
}

write_tsd_constant <- function(path, value_name, total_days, value, start_date = 20200101L) {
  times_day <- build_time_axis_days(total_days)
  lines <- c(
    paste(length(times_day), 2, start_date),
    paste("Time_Day", value_name, sep = "\t"),
    vapply(times_day, function(ti) {
      paste(fmt_num(ti, 10), fmt_num(value, 6), sep = "\t")
    }, character(1))
  )
  writeLines(lines, path, useBytes = TRUE)
}

write_tsd_forc <- function(path, input_dir, station_row, start_date = 20200101L) {
  lines <- c(
    paste(1, start_date),
    normalizePath(input_dir, winslash = "/", mustWork = TRUE),
    "ID\tLon\tLat\tX\tY\tZ\tFilename",
    paste(
      c(
        1,
        fmt_num(station_row$Lon, 8),
        fmt_num(station_row$Lat, 8),
        fmt_num(station_row$X, 6),
        fmt_num(station_row$Y, 6),
        fmt_num(station_row$Z, 6),
        "forcing.csv"
      ),
      collapse = "\t"
    )
  )
  writeLines(lines, path, useBytes = TRUE)
}

write_calib_file <- function(path) {
  lines <- c(
    "GEOL_KSATH\t1",
    "GEOL_KSATV\t1",
    "GEOL_KMACSATH\t1",
    "GEOL_MACVF\t1",
    "GEOL_THETAS\t1",
    "GEOL_THETAR\t1",
    "GEOL_DMAC\t1",
    "SOIL_KINF\t1",
    "SOIL_KMACSATV\t1",
    "SOIL_DINF\t1",
    "SOIL_ALPHA\t1",
    "SOIL_BETA\t1",
    "SOIL_MACHF\t1",
    "LC_VEGFRAC\t1",
    "LC_ALBEDO\t1",
    "LC_ROUGH\t1",
    "LC_DROOT\t1",
    "LC_ISMAX\t1",
    "LC_IMPAF\t1",
    "LC_SOILDGD\t1",
    "TS_PRCP\t1",
    "TS_LAI\t1",
    "TS_SFCTMP+\t0",
    "ET_ETP\t1",
    "ET_IC\t1",
    "ET_TR\t1",
    "ET_SOIL\t1",
    "RIV_ROUGH\t1",
    "RIV_KH\t1",
    "RIV_SINU\t1",
    "RIV_CWR\t1",
    "RIV_BEDTHICK\t1",
    "RIV_BSLOPE+\t0",
    "RIV_DPTH+\t0",
    "RIV_WDTH+\t0",
    "IC_GW+\t0",
    "IC_RIV+\t0",
    "AQ_DEPTH+\t0"
  )
  writeLines(lines, path, useBytes = TRUE)
}

write_cfg_para <- function(path, init_mode, end_days) {
  lines <- c(
    "# START and END are in days in the current SHUD parser.",
    "VERBOSE\t0",
    "INIT_MODE\t",
    "ASCII_OUTPUT\t1",
    "BINARY_OUTPUT\t0",
    "FORCING_MODE\tCSV",
    "OUTPUT_MODE\tLEGACY",
    "RADIATION_INPUT_MODE\tSWDOWN",
    "SOLAR_LONLAT_MODE\tFORCING_FIRST",
    "SPINUPDAY\t0",
    "NUM_OPENMP\t1",
    "SCR_INTV\t60",
    "ABSTOL\t1e-6",
    "RELTOL\t1e-4",
    "INIT_SOLVER_STEP\t1",
    "MAX_SOLVER_STEP\t10",
    "LSM_STEP\t60",
    "START\t0",
    paste("END", end_days, sep = "\t"),
    "DT_YE_IC\t60",
    "DT_YE_SNOW\t60",
    "DT_YE_SURF\t60",
    "DT_YE_UNSAT\t60",
    "DT_YE_GW\t60",
    "DT_QE_PRCP\t60",
    "DT_QE_ET\t60",
    "DT_QE_INFIL\t60",
    "DT_QE_RECH\t60",
    "DT_QE_SUB\t60",
    "DT_QE_SURF\t60",
    "DT_QE_RSUB\t60",
    "DT_QE_RSURF\t60",
    "DT_YR_STAGE\t60",
    "DT_QR_DOWN\t60",
    "DT_QR_SURF\t60",
    "DT_QR_SUB\t60",
    "DT_QR_UP\t60",
    "TERRAIN_RADIATION\t0"
  )
  lines[3] <- paste("INIT_MODE", init_mode, sep = "\t")
  writeLines(lines, path, useBytes = TRUE)
}

write_cfg_ic <- function(path, num_ele, river_stage) {
  ele_rows <- vapply(seq_len(num_ele), function(i) {
    paste(c(i, fmt_num(0, 1), fmt_num(0, 1), fmt_num(0, 1), fmt_num(0, 1), fmt_num(5, 1)), collapse = "\t")
  }, character(1))

  riv_rows <- vapply(seq_along(river_stage), function(i) {
    paste(c(i, fmt_num(river_stage[[i]], 6)), collapse = "\t")
  }, character(1))

  lines <- c(
    paste(num_ele, 6, sep = "\t"),
    "Index\tCanopy\tSnow\tSurface\tUnsat\tGW",
    ele_rows,
    paste(length(river_stage), 2, sep = "\t"),
    "Index\tStage",
    riv_rows
  )

  writeLines(lines, path, useBytes = TRUE)
}

write_project_file <- function(path, input_dir, output_dir) {
  input_dir <- normalizePath(input_dir, winslash = "/", mustWork = TRUE)
  output_dir <- normalizePath(output_dir, winslash = "/", mustWork = FALSE)
  prefix <- file.path(input_dir, "ftbug")

  lines <- c(
    "PRJ\tftbug",
    paste("INPATH", input_dir, sep = "\t"),
    paste("OUTPATH", output_dir, sep = "\t"),
    paste("MESH", paste0(prefix, ".sp.mesh"), sep = "\t"),
    paste("ATT", paste0(prefix, ".sp.att"), sep = "\t"),
    paste("RIV", paste0(prefix, ".sp.riv"), sep = "\t"),
    paste("RIVSEG", paste0(prefix, ".sp.rivseg"), sep = "\t"),
    paste("CALIB", paste0(prefix, ".cfg.calib"), sep = "\t"),
    paste("PARA", paste0(prefix, ".cfg.para"), sep = "\t"),
    paste("INIT", paste0(prefix, ".cfg.ic"), sep = "\t"),
    paste("LC", paste0(prefix, ".para.lc"), sep = "\t"),
    paste("SOIL", paste0(prefix, ".para.soil"), sep = "\t"),
    paste("GEOL", paste0(prefix, ".para.geol"), sep = "\t"),
    paste("FORC", paste0(prefix, ".tsd.forc"), sep = "\t"),
    paste("LAI", paste0(prefix, ".tsd.lai"), sep = "\t"),
    paste("MF", paste0(prefix, ".tsd.mf"), sep = "\t")
  )

  writeLines(lines, path, useBytes = TRUE)
}

verify_route_only_case <- function(repo_root, project_file) {
  shud_dir <- file.path(repo_root, "SHUD")
  route_project <- normalizePath(project_file, winslash = "/", mustWork = TRUE)

  build_output <- with_dir(shud_dir, system2("make", "shud", stdout = TRUE, stderr = TRUE))
  build_status <- attr(build_output, "status")
  if (is.null(build_status)) {
    build_status <- 0L
  }
  if (length(build_output) > 0L) {
    cat(paste(utils::tail(build_output, 3), collapse = "\n"), "\n", sep = "")
  }
  assert_true(build_status == 0L, "SHUD build failed while verifying the ftbug route-only case.")

  run_output <- with_dir(shud_dir, system2("./shud", c("-p", route_project), stdout = TRUE, stderr = TRUE))
  run_status <- attr(run_output, "status")
  if (is.null(run_status)) {
    run_status <- 0L
  }
  if (length(run_output) > 0L) {
    cat(paste(run_output, collapse = "\n"), "\n", sep = "")
  }
  assert_true(run_status == 0L, "SHUD route-only verification run failed.")
}

args <- commandArgs(trailingOnly = TRUE)
skip_verify <- "--skip-verify" %in% args

script_dir <- get_script_dir()
repo_root <- normalizePath(file.path(script_dir, "..", ".."), winslash = "/", mustWork = TRUE)

fixture_dir <- file.path(repo_root, "testdata", "ftbug")
base_dir <- file.path(repo_root, "runs", "ftbug", "base")
route_input_dir <- file.path(base_dir, "route-only", "input", "ftbug")
route_output_dir <- file.path(base_dir, "route-only", "output", "ftbug.out")
coupled_input_dir <- file.path(base_dir, "coupled", "input", "ftbug")
coupled_output_dir <- file.path(base_dir, "coupled", "output", "ftbug.out")

unlink(file.path(base_dir, "route-only"), recursive = TRUE, force = TRUE)
unlink(file.path(base_dir, "coupled"), recursive = TRUE, force = TRUE)

dir.create(route_input_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(route_output_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(coupled_input_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(coupled_output_dir, recursive = TRUE, showWarnings = FALSE)

basin_sf <- sf::st_read(file.path(fixture_dir, "basin.shp"), quiet = TRUE)
river_sf <- sf::st_read(file.path(fixture_dir, "river.shp"), quiet = TRUE)
dem <- terra::rast(file.path(fixture_dir, "dem.tif"))
truth_sp_riv <- read_sp_riv(file.path(fixture_dir, "truth.sp.riv"))

mesh <- build_mesh(basin_sf, truth_sp_riv, dem)
rivseg <- build_rivseg(river_sf, mesh$triangles_sf)

station_centroid <- sf::st_centroid(sf::st_geometry(basin_sf))
station_xy <- sf::st_coordinates(station_centroid)
station_lonlat <- sf::st_coordinates(sf::st_transform(station_centroid, 4326))
station_z <- extract_dem_values(dem, station_xy)
station_row <- list(
  Lon = station_lonlat[1, 1],
  Lat = station_lonlat[1, 2],
  X = station_xy[1, 1],
  Y = station_xy[1, 2],
  Z = station_z[1]
)

write_mesh_file(file.path(route_input_dir, "ftbug.sp.mesh"), mesh)
write_att_file(file.path(route_input_dir, "ftbug.sp.att"), nrow(mesh$triangles))
copied_truth <- file.copy(file.path(fixture_dir, "truth.sp.riv"), file.path(route_input_dir, "ftbug.sp.riv"), overwrite = TRUE)
assert_true(isTRUE(copied_truth), "Failed to copy truth.sp.riv into the route-only input directory.")

rivseg_rows <- data.frame(
  INDEX = rivseg$INDEX,
  iRiv = rivseg$iRiv,
  iEle = rivseg$iEle,
  Length = vapply(rivseg$Length, fmt_num, character(1), digits = 6),
  stringsAsFactors = FALSE
)
write_table_file(file.path(route_input_dir, "ftbug.sp.rivseg"),
                 c("INDEX", "iRiv", "iEle", "Length"),
                 rivseg_rows)

soil_rows <- data.frame(
  INDEX = 1,
  KsatV = fmt_num(1.0, 6),
  ThetaS = fmt_num(0.45, 6),
  ThetaR = fmt_num(0.05, 6),
  InfD = fmt_num(1.0, 6),
  Alpha = fmt_num(1.0, 6),
  Beta = fmt_num(3.0, 6),
  hAreaF = fmt_num(0.1, 6),
  macKsatV = fmt_num(10.0, 6),
  stringsAsFactors = FALSE
)
write_table_file(file.path(route_input_dir, "ftbug.para.soil"),
                 c("INDEX", "KsatV", "ThetaS", "ThetaR", "InfD", "Alpha", "Beta", "hAreaF", "macKsatV"),
                 soil_rows)

geol_rows <- data.frame(
  INDEX = 1,
  KsatH = fmt_num(0.1, 6),
  KsatV = fmt_num(0.01, 6),
  ThetaS = fmt_num(0.35, 6),
  ThetaR = fmt_num(0.02, 6),
  vAreaF = fmt_num(0.1, 6),
  macKsatH = fmt_num(1.0, 6),
  Dmac = fmt_num(2.0, 6),
  stringsAsFactors = FALSE
)
write_table_file(file.path(route_input_dir, "ftbug.para.geol"),
                 c("INDEX", "KsatH", "KsatV", "ThetaS", "ThetaR", "vAreaF", "macKsatH", "Dmac"),
                 geol_rows)

lc_rows <- data.frame(
  INDEX = 1,
  ALBEDO = fmt_num(0.2, 6),
  VEGFRAC = fmt_num(0.5, 6),
  ROUGH = fmt_num(0.01, 6),
  RZD = fmt_num(1.0, 6),
  SOILDGRD = fmt_num(0.0, 6),
  IMPAF = fmt_num(0.0, 6),
  stringsAsFactors = FALSE
)
write_table_file(file.path(route_input_dir, "ftbug.para.lc"),
                 c("INDEX", "ALBEDO", "VEGFRAC", "ROUGH", "RZD", "SOILDGRD", "IMPAF"),
                 lc_rows)

write_tsd_forc(file.path(route_input_dir, "ftbug.tsd.forc"), route_input_dir, station_row)
write_forcing_csv(file.path(route_input_dir, "forcing.csv"), total_days = 10, mode = "route-only")
write_tsd_constant(file.path(route_input_dir, "ftbug.tsd.lai"), "LAI", total_days = 30, value = 2.0)
write_tsd_constant(file.path(route_input_dir, "ftbug.tsd.mf"), "MF", total_days = 30, value = 0.001)
write_calib_file(file.path(route_input_dir, "ftbug.cfg.calib"))
write_cfg_para(file.path(route_input_dir, "ftbug.cfg.para"), init_mode = 3, end_days = 10)
write_cfg_ic(
  file.path(route_input_dir, "ftbug.cfg.ic"),
  num_ele = nrow(mesh$triangles),
  river_stage = c("1" = 2.0, "2" = 2.0, "3" = 1.0, "4" = 2.0, "5" = 1.0, "6" = 0.5)
)

static_files <- c(
  "ftbug.sp.mesh",
  "ftbug.sp.att",
  "ftbug.sp.riv",
  "ftbug.sp.rivseg",
  "ftbug.para.soil",
  "ftbug.para.geol",
  "ftbug.para.lc",
  "ftbug.tsd.lai",
  "ftbug.tsd.mf",
  "ftbug.cfg.calib"
)
copied_static <- file.copy(file.path(route_input_dir, static_files), coupled_input_dir, overwrite = TRUE)
assert_true(all(copied_static), "Failed to copy one or more static input files into the coupled directory.")

write_tsd_forc(file.path(coupled_input_dir, "ftbug.tsd.forc"), coupled_input_dir, station_row)
write_forcing_csv(file.path(coupled_input_dir, "forcing.csv"), total_days = 30, mode = "coupled")
write_cfg_para(file.path(coupled_input_dir, "ftbug.cfg.para"), init_mode = 1, end_days = 30)

route_project_file <- file.path(base_dir, "route-only", "ftbug.SHUD")
coupled_project_file <- file.path(base_dir, "coupled", "ftbug.SHUD")
write_project_file(route_project_file, route_input_dir, route_output_dir)
write_project_file(coupled_project_file, coupled_input_dir, coupled_output_dir)

if (!skip_verify) {
  verify_route_only_case(repo_root, route_project_file)
}

cat("Generated ftbug SHUD base case.\n")
cat("Mesh elements:", nrow(mesh$triangles), "\n")
cat("Mesh nodes:", nrow(mesh$points), "\n")
cat("River segments:", nrow(rivseg), "\n")
cat("Route-only project:", normalizePath(route_project_file, winslash = "/", mustWork = TRUE), "\n")
cat("Coupled project:", normalizePath(coupled_project_file, winslash = "/", mustWork = TRUE), "\n")
