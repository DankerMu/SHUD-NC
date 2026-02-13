#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(sf)
  library(terra)
  library(sp)
  library(raster)
})

set.seed(123)

make_segment_coords <- function(start_xy, end_xy, n_vertices) {
  t <- seq(0, 1, length.out = n_vertices)
  x <- start_xy[1] + (end_xy[1] - start_xy[1]) * t
  y <- start_xy[2] + (end_xy[2] - start_xy[2]) * t

  if (n_vertices > 2) {
    idx <- 2:(n_vertices - 1)
    x[idx] <- x[idx] + runif(length(idx), min = -3, max = 3)
    y[idx] <- y[idx] + runif(length(idx), min = -3, max = 3)
  }

  cbind(x = x, y = y)
}

segments <- data.frame(
  seg = paste0("Seg", 1:7),
  name = c("L1a", "L1b", "R1a", "R1b", "L2", "R2", "Main"),
  n_vertices = c(10, 10, 10, 10, 8, 8, 12),
  stringsAsFactors = FALSE
)

starts <- list(
  c(0, 200),
  c(50, 200),
  c(100, 200),
  c(150, 200),
  c(25, 150),
  c(75, 150),
  c(50, 100)
)

ends <- list(
  c(25, 150),
  c(25, 150),
  c(75, 150),
  c(75, 150),
  c(50, 100),
  c(50, 100),
  c(50, 0)
)

geom <- vector("list", nrow(segments))
for (i in seq_len(nrow(segments))) {
  coords <- make_segment_coords(starts[[i]], ends[[i]], segments$n_vertices[i])
  geom[[i]] <- sf::st_linestring(coords)
}

sl_sf <- sf::st_sf(
  segments,
  geometry = sf::st_sfc(geom, crs = sf::st_crs(NA))
)

dem <- terra::rast(
  nrows = 20,
  ncols = 20,
  ext = terra::ext(-10, 160, -10, 210)
)
xy <- terra::xyFromCell(dem, 1:terra::ncell(dem))
terra::values(dem) <- xy[, 2]

sl_sp <- as(sf::st_geometry(sl_sf), "Spatial")
dem_rl <- raster::raster(dem)

out <- list(
  sl = sl_sp,
  dem = dem_rl,
  desc = "Tree 7 segments 2-level confluence"
)

out_path <- file.path("testdata", "mock_river", "mock2_tree.rds")
dir.create(dirname(out_path), recursive = TRUE, showWarnings = FALSE)
saveRDS(out, out_path)

cat("Saved:", normalizePath(out_path, winslash = "/", mustWork = FALSE), "\n\n")
cat("SpatialLines summary:\n")
print(summary(out$sl))
cat("\nDEM summary:\n")
print(summary(out$dem))
