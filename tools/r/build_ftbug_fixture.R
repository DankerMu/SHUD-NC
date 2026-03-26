#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE, scipen = 999)

suppressPackageStartupMessages({
  library(sf)
  library(sp)
  library(terra)
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

yaml_quote <- function(x) {
  paste0("\"", gsub("\"", "\\\\\"", x), "\"")
}

polyline_length <- function(coords) {
  deltas <- coords[-1, , drop = FALSE] - coords[-nrow(coords), , drop = FALSE]
  sum(sqrt(rowSums(deltas ^ 2)))
}

make_reach_coords <- function(start_xy, end_xy, n_vertices, jitter) {
  assert_true(n_vertices >= 40 && n_vertices <= 80, "Each reach must have 40-80 vertices.")

  t <- seq(0, 1, length.out = n_vertices)
  coords <- cbind(
    x = start_xy[1] + (end_xy[1] - start_xy[1]) * t,
    y = start_xy[2] + (end_xy[2] - start_xy[2]) * t
  )

  if (n_vertices > 2 && jitter > 0) {
    direction <- end_xy - start_xy
    perp <- c(-direction[2], direction[1])
    perp <- perp / sqrt(sum(perp ^ 2))
    idx <- 2:(n_vertices - 1)
    taper <- sin(pi * t[idx])
    offset <- stats::runif(length(idx), min = -jitter, max = jitter) * taper
    coords[idx, 1] <- coords[idx, 1] + offset * perp[1]
    coords[idx, 2] <- coords[idx, 2] + offset * perp[2]
  }

  coords
}

categorize_slope <- function(slope) {
  if (slope < 0.001) {
    "gentle"
  } else if (slope >= 0.009) {
    "steep"
  } else {
    "medium"
  }
}

build_type_table <- function(n_types) {
  data.frame(
    Index = seq_len(n_types),
    Depth = 5 + 0.5 * seq_len(n_types),
    BankSlope = 0,
    Width = 2 * seq_len(n_types),
    Sinuosity = 1,
    Manning = 0.04,
    Cwr = 0.6,
    KsatH = 0.1,
    BedThick = 0.1,
    check.names = FALSE
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
          fmt_num(as.numeric(row["From.x"]), 0),
          fmt_num(as.numeric(row["From.y"]), 0),
          fmt_num(as.numeric(row["From.z"]), 6),
          fmt_num(as.numeric(row["To.x"]), 0),
          fmt_num(as.numeric(row["To.y"]), 0),
          fmt_num(as.numeric(row["To.z"]), 6)
        ),
        collapse = " "
      )
    })
  )

  writeLines(lines, con = path, useBytes = TRUE)
}

write_manifest <- function(path, manifest) {
  lines <- c(
    paste0("seed: ", manifest$seed),
    paste0("generator: ", yaml_quote(manifest$generator)),
    paste0("output_dir: ", yaml_quote(manifest$output_dir)),
    "crs:",
    paste0("  epsg: ", manifest$crs$epsg),
    paste0("  name: ", yaml_quote(manifest$crs$name)),
    "dem:",
    paste0("  file: ", yaml_quote(manifest$dem$file)),
    paste0("  formula: ", yaml_quote(manifest$dem$formula)),
    paste0("  resolution_m: ", manifest$dem$resolution_m),
    "  extent:",
    paste0("    xmin: ", manifest$dem$extent$xmin),
    paste0("    xmax: ", manifest$dem$extent$xmax),
    paste0("    ymin: ", manifest$dem$extent$ymin),
    paste0("    ymax: ", manifest$dem$extent$ymax),
    "network:",
    paste0("  reach_count: ", manifest$network$reach_count),
    paste0("  outlet_down_code: ", manifest$network$outlet_down_code),
    "  topology:",
    unlist(lapply(manifest$network$topology, function(x) {
      c(
        paste0("    - index: ", x$Index),
        paste0("      reach: ", yaml_quote(x$Reach)),
        paste0("      type: ", x$Type),
        paste0("      down: ", x$Down)
      )
    })),
    "reaches:",
    unlist(lapply(manifest$reaches, function(x) {
      c(
        paste0("  - index: ", x$Index),
        paste0("    reach: ", yaml_quote(x$Reach)),
        paste0("    type: ", x$Type),
        paste0("    down: ", x$Down),
        paste0("    vertices: ", x$Vertices),
        paste0("    length_m: ", fmt_num(x$Length, 6)),
        paste0("    slope: ", fmt_num(x$Slope, 10)),
        paste0("    slope_class: ", yaml_quote(x$SlopeClass))
      )
    })),
    "files:",
    paste0("  river_shp: ", yaml_quote(manifest$files$river_shp)),
    paste0("  basin_shp: ", yaml_quote(manifest$files$basin_shp)),
    paste0("  truth_down_csv: ", yaml_quote(manifest$files$truth_down_csv)),
    paste0("  truth_type_csv: ", yaml_quote(manifest$files$truth_type_csv)),
    paste0("  truth_nodes_csv: ", yaml_quote(manifest$files$truth_nodes_csv)),
    paste0("  truth_sp_riv: ", yaml_quote(manifest$files$truth_sp_riv))
  )

  writeLines(lines, con = path, useBytes = TRUE)
}

seed <- 42L
set.seed(seed)

script_dir <- get_script_dir()
repo_root <- normalizePath(file.path(script_dir, "..", ".."), winslash = "/", mustWork = TRUE)
out_dir <- file.path(repo_root, "testdata", "ftbug")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

crs_epsg <- 32648
crs_obj <- sf::st_crs(crs_epsg)
crs_name <- if (!is.null(crs_obj$Name) && nzchar(crs_obj$Name)) crs_obj$Name else crs_obj$input

dem_fun <- function(x, y) {
  2500 - 0.0006 * (x - 500000) + 0.01 * (y - 4200000)
}
dem_formula <- "z = 2500 - 0.0006 * (x - 500000) + 0.01 * (y - 4200000)"

nodes <- list(
  r1_from = c(500150, 4201450),
  r2_from = c(500750, 4201450),
  j13 = c(500450, 4200550),
  r4_from = c(500250, 4200250),
  j35 = c(500950, 4200050),
  j56 = c(501850, 4200050),
  outlet = c(501950, 4198350)
)

reach_defs <- data.frame(
  Index = 1:6,
  Reach = paste0("R", 1:6),
  Type = c(1, 1, 2, 1, 3, 3),
  Down = c(3, 3, 5, 5, 6, -3),
  Start = c("r1_from", "r2_from", "j13", "r4_from", "j35", "j56"),
  End = c("j13", "j13", "j35", "j35", "j56", "outlet"),
  Vertices = c(61, 57, 67, 49, 73, 55),
  Jitter = c(11, 11, 9, 8, 4, 8),
  stringsAsFactors = FALSE
)

coords_list <- lapply(seq_len(nrow(reach_defs)), function(i) {
  make_reach_coords(
    start_xy = nodes[[reach_defs$Start[i]]],
    end_xy = nodes[[reach_defs$End[i]]],
    n_vertices = reach_defs$Vertices[i],
    jitter = reach_defs$Jitter[i]
  )
})
names(coords_list) <- reach_defs$Reach

first_last <- do.call(rbind, lapply(coords_list, function(coords) {
  c(coords[1, 1], coords[1, 2], coords[nrow(coords), 1], coords[nrow(coords), 2])
}))
colnames(first_last) <- c("From.x", "From.y", "To.x", "To.y")

assert_true(all(first_last[1, 3:4] == first_last[3, 1:2]), "R1 endpoint must match R3 start.")
assert_true(all(first_last[2, 3:4] == first_last[3, 1:2]), "R2 endpoint must match R3 start.")
assert_true(all(first_last[3, 3:4] == first_last[5, 1:2]), "R3 endpoint must match R5 start.")
assert_true(all(first_last[4, 3:4] == first_last[5, 1:2]), "R4 endpoint must match R5 start.")
assert_true(all(first_last[5, 3:4] == first_last[6, 1:2]), "R5 endpoint must match R6 start.")

lengths <- vapply(coords_list, polyline_length, numeric(1))
from_z <- dem_fun(first_last[, "From.x"], first_last[, "From.y"])
to_z <- dem_fun(first_last[, "To.x"], first_last[, "To.y"])
slopes <- (from_z - to_z) / lengths
slope_class <- vapply(slopes, categorize_slope, character(1))

assert_true(any(slope_class == "steep"), "Fixture must include at least one steep reach.")
assert_true(any(slope_class == "medium"), "Fixture must include at least one medium reach.")
assert_true(any(slope_class == "gentle"), "Fixture must include at least one gentle reach.")
assert_true(any(abs(slopes - 0.0006) < 0.0002), "Fixture must include a gentle reach near 0.0006.")
assert_true(all(slopes > 0), "All reaches must have positive downstream slope.")

river_sfc <- sf::st_sfc(lapply(coords_list, sf::st_linestring), crs = crs_epsg)
river_sf <- sf::st_sf(
  Index = reach_defs$Index,
  Reach = reach_defs$Reach,
  Type = reach_defs$Type,
  Down = reach_defs$Down,
  NVert = reach_defs$Vertices,
  Slope = slopes,
  Len_m = lengths,
  geometry = river_sfc
)
river_sp <- methods::as(river_sf, "Spatial")
assert_true(inherits(river_sp, "SpatialLinesDataFrame"), "River object must be SpatialLinesDataFrame.")

bbox <- sf::st_bbox(river_sf)
basin_buffer <- 250
basin_bbox <- bbox
basin_bbox["xmin"] <- basin_bbox["xmin"] - basin_buffer
basin_bbox["xmax"] <- basin_bbox["xmax"] + basin_buffer
basin_bbox["ymin"] <- basin_bbox["ymin"] - basin_buffer
basin_bbox["ymax"] <- basin_bbox["ymax"] + basin_buffer
basin_sf <- sf::st_sf(
  Name = "ftbug_basin",
  Buffer_m = basin_buffer,
  geometry = sf::st_as_sfc(basin_bbox)
)

dem_res <- 100
dem_padding <- 300
dem_xmin <- floor((bbox["xmin"] - dem_padding) / dem_res) * dem_res
dem_xmax <- ceiling((bbox["xmax"] + dem_padding) / dem_res) * dem_res
dem_ymin <- floor((bbox["ymin"] - dem_padding) / dem_res) * dem_res
dem_ymax <- ceiling((bbox["ymax"] + dem_padding) / dem_res) * dem_res

dem <- terra::rast(
  xmin = dem_xmin,
  xmax = dem_xmax,
  ymin = dem_ymin,
  ymax = dem_ymax,
  resolution = dem_res,
  crs = crs_obj$wkt
)
dem_xy <- terra::xyFromCell(dem, 1:terra::ncell(dem))
terra::values(dem) <- dem_fun(dem_xy[, 1], dem_xy[, 2])

on_cell_center <- function(x, minv, res) {
  abs((((x - minv) - res / 2) %% res)) < 1e-9
}

assert_true(
  all(on_cell_center(c(first_last[, "From.x"], first_last[, "To.x"]), dem_xmin, dem_res)),
  "All river endpoint x-coordinates must land on DEM cell centers."
)
assert_true(
  all(on_cell_center(c(first_last[, "From.y"], first_last[, "To.y"]), dem_ymin, dem_res)),
  "All river endpoint y-coordinates must land on DEM cell centers."
)

truth_down <- reach_defs[, c("Index", "Down")]
truth_type <- reach_defs[, c("Index", "Type")]
truth_nodes <- data.frame(
  Index = reach_defs$Index,
  `From.x` = first_last[, "From.x"],
  `From.y` = first_last[, "From.y"],
  `From.z` = from_z,
  `To.x` = first_last[, "To.x"],
  `To.y` = first_last[, "To.y"],
  `To.z` = to_z,
  check.names = FALSE
)

truth_river <- data.frame(
  Index = reach_defs$Index,
  Down = reach_defs$Down,
  Type = reach_defs$Type,
  Slope = slopes,
  Length = lengths,
  BC = 0,
  check.names = FALSE
)
truth_rivertype <- build_type_table(3)

river_path <- file.path(out_dir, "river.shp")
basin_path <- file.path(out_dir, "basin.shp")
dem_path <- file.path(out_dir, "dem.tif")
truth_down_path <- file.path(out_dir, "truth_down.csv")
truth_type_path <- file.path(out_dir, "truth_type.csv")
truth_nodes_path <- file.path(out_dir, "truth_nodes.csv")
truth_riv_path <- file.path(out_dir, "truth.sp.riv")
manifest_path <- file.path(out_dir, "manifest.yaml")

unlink(Sys.glob(file.path(out_dir, "river.*")), force = TRUE)
unlink(Sys.glob(file.path(out_dir, "basin.*")), force = TRUE)
if (file.exists(dem_path)) {
  file.remove(dem_path)
}

sf::st_write(river_sf, river_path, delete_layer = TRUE, quiet = TRUE)
sf::st_write(basin_sf, basin_path, delete_layer = TRUE, quiet = TRUE)
terra::writeRaster(dem, dem_path, overwrite = TRUE)
utils::write.csv(truth_down, truth_down_path, row.names = FALSE)
utils::write.csv(truth_type, truth_type_path, row.names = FALSE)
utils::write.csv(truth_nodes, truth_nodes_path, row.names = FALSE)
write_sp_riv(truth_riv_path, truth_river, truth_rivertype, truth_nodes[, -1, drop = FALSE])

manifest <- list(
  seed = seed,
  generator = "tools/r/build_ftbug_fixture.R",
  output_dir = "testdata/ftbug",
  crs = list(
    epsg = crs_epsg,
    name = crs_name
  ),
  dem = list(
    file = "dem.tif",
    formula = dem_formula,
    resolution_m = dem_res,
    extent = list(
      xmin = unname(dem_xmin),
      xmax = unname(dem_xmax),
      ymin = unname(dem_ymin),
      ymax = unname(dem_ymax)
    )
  ),
  network = list(
    reach_count = nrow(reach_defs),
    outlet_down_code = -3,
    topology = lapply(seq_len(nrow(reach_defs)), function(i) {
      list(
        Index = reach_defs$Index[i],
        Reach = reach_defs$Reach[i],
        Type = reach_defs$Type[i],
        Down = reach_defs$Down[i]
      )
    })
  ),
  reaches = lapply(seq_len(nrow(reach_defs)), function(i) {
    list(
      Index = reach_defs$Index[i],
      Reach = reach_defs$Reach[i],
      Type = reach_defs$Type[i],
      Down = reach_defs$Down[i],
      Vertices = reach_defs$Vertices[i],
      Length = lengths[i],
      Slope = slopes[i],
      SlopeClass = slope_class[i]
    )
  }),
  files = list(
    river_shp = "river.shp",
    basin_shp = "basin.shp",
    truth_down_csv = "truth_down.csv",
    truth_type_csv = "truth_type.csv",
    truth_nodes_csv = "truth_nodes.csv",
    truth_sp_riv = "truth.sp.riv"
  )
)
write_manifest(manifest_path, manifest)

summary_df <- data.frame(
  Index = reach_defs$Index,
  Reach = reach_defs$Reach,
  Type = reach_defs$Type,
  Down = reach_defs$Down,
  Vertices = reach_defs$Vertices,
  Length_m = round(lengths, 3),
  Slope = signif(slopes, 6),
  Class = slope_class,
  check.names = FALSE
)

cat("Generated fixture in:", normalizePath(out_dir, winslash = "/", mustWork = TRUE), "\n\n")
print(summary_df, row.names = FALSE)
