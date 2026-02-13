#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(sf)
  library(terra)
  library(sp)
  library(raster)
})

set.seed(42)

make_segment_coords <- function(start_xy, end_xy, n_vertices = 7, jitter = 2) {
  t <- seq(0, 1, length.out = n_vertices)
  x <- start_xy[1] + (end_xy[1] - start_xy[1]) * t
  y <- start_xy[2] + (end_xy[2] - start_xy[2]) * t

  if (n_vertices > 2) {
    idx <- 2:(n_vertices - 1)
    x[idx] <- x[idx] + runif(length(idx), min = -jitter, max = jitter)
    y[idx] <- y[idx] + runif(length(idx), min = -jitter, max = jitter)
  }

  cbind(x = x, y = y)
}

segments <- data.frame(
  seg = c("Seg1", "Seg2", "Seg3"),
  role = c("trib1", "trib2", "main"),
  stringsAsFactors = FALSE
)

starts <- list(
  c(0, 100),
  c(100, 100),
  c(50, 50)
)

ends <- list(
  c(50, 50),
  c(50, 50),
  c(50, 0)
)

geom <- vector("list", nrow(segments))
for (i in seq_len(nrow(segments))) {
  coords <- make_segment_coords(starts[[i]], ends[[i]], n_vertices = 7, jitter = 2)
  geom[[i]] <- sf::st_linestring(coords)
}

sl_sf <- sf::st_sf(
  segments,
  geometry = sf::st_sfc(geom, crs = sf::st_crs(NA))
)

dem <- terra::rast(
  nrows = 10,
  ncols = 10,
  ext = terra::ext(-5, 105, -5, 105)
)
xy <- terra::xyFromCell(dem, 1:terra::ncell(dem))
terra::values(dem) <- xy[, 2]

sl_sp <- as(sf::st_geometry(sl_sf), "Spatial")
dem_rl <- raster::raster(dem)

out <- list(
  sl = sl_sp,
  dem = dem_rl,
  desc = "Y-shape 3 segments"
)

args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", args, value = TRUE)
script_path <- if (length(file_arg) > 0) sub("^--file=", "", file_arg[1]) else NA_character_
out_dir <- if (!is.na(script_path)) dirname(normalizePath(script_path)) else file.path("testdata", "mock_river")
out_path <- file.path(out_dir, "mock1_y_shape.rds")
dir.create(dirname(out_path), recursive = TRUE, showWarnings = FALSE)
saveRDS(out, out_path)

coords <- sf::st_coordinates(sl_sf)
coords_xy <- data.frame(x = coords[, "X"], y = coords[, "Y"])

cat("Segments:", nrow(sl_sf), "\n")
cat("Total vertices:", nrow(coords_xy), "\n")
cat("Unique vertices:", nrow(unique(coords_xy)), "\n")
