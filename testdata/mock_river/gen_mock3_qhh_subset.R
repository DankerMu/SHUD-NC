#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(sf)
  library(terra)
  library(sp)
  library(raster)
})

stm_path <- file.path("runs", "qhh", "baseline", "DataPre", "pcs", "stm.shp")
dem_path <- file.path("runs", "qhh", "baseline", "DataPre", "pcs", "dem.tif")
out_path <- file.path("testdata", "mock_river", "mock3_qhh_subset.rds")

if (!file.exists(stm_path)) {
  stop("Missing stm.shp: ", stm_path)
}
if (!file.exists(dem_path)) {
  stop("Missing dem.tif: ", dem_path)
}

message("Reading stm: ", stm_path)
stm <- sf::st_read(stm_path, quiet = TRUE)

message("Reading DEM (lazy): ", dem_path)
dem <- terra::rast(dem_path)

crs_stm <- sf::st_crs(stm)
if (is.na(crs_stm)) {
  message("stm.shp CRS is NA; setting EPSG:32647 (UTM 47N).")
  sf::st_crs(stm) <- 32647
} else if (is.na(crs_stm$epsg)) {
  message("stm.shp CRS EPSG is NA; setting EPSG:32647 (UTM 47N).")
  sf::st_crs(stm) <- 32647
}

if (sf::st_is_longlat(stm)) {
  stop("stm.shp CRS appears to be geographic (lon/lat); expected PCS UTM (meters).")
}

stm$..len_m <- as.numeric(sf::st_length(stm))
seed_idx <- which.max(stm$..len_m)

min_n <- 15L
max_n <- 20L
target_n <- 18L

expand_connected <- function(stm_sf, seed, buffer_m, target_n, min_n, max_n, max_iter = 80L) {
  selected <- seed
  stop_n <- max(min_n, min(max_n, target_n))

  for (iter in seq_len(max_iter)) {
    if (length(selected) >= stop_n) break

    endpoints <- sf::st_cast(
      sf::st_boundary(sf::st_geometry(stm_sf[selected, ])),
      "POINT"
    )
    endpoints_buf <- sf::st_buffer(endpoints, dist = buffer_m)

    hits <- lengths(sf::st_intersects(stm_sf, endpoints_buf)) > 0
    cand <- setdiff(which(hits), selected)
    if (length(cand) == 0) break

    cand <- cand[order(stm_sf$..len_m[cand], decreasing = TRUE)]
    space <- stop_n - length(selected)
    if (space <= 0) break

    add <- cand[seq_len(min(length(cand), space))]
    selected <- unique(c(selected, add))
  }

  selected
}

select_by_bbox <- function(stm_sf, seed, target_n, min_n, max_n) {
  seed_geom <- sf::st_geometry(stm_sf[seed, ])
  base_bbox <- sf::st_bbox(seed_geom)
  bbox_poly <- function(bbox) sf::st_as_sfc(bbox)

  deltas <- c(200, 300, 500, 800, 1200, 1800, 2500, 3500, 5000, 8000)
  counts <- integer(length(deltas))
  picks <- vector("list", length(deltas))

  for (i in seq_along(deltas)) {
    d <- deltas[i]
    bb <- base_bbox
    bb[c("xmin", "ymin")] <- bb[c("xmin", "ymin")] - d
    bb[c("xmax", "ymax")] <- bb[c("xmax", "ymax")] + d
    hit <- lengths(sf::st_intersects(stm_sf, bbox_poly(bb))) > 0
    idx <- which(hit)
    counts[i] <- length(idx)
    picks[[i]] <- idx
  }

  ok <- which(counts >= min_n & counts <= max_n)
  if (length(ok) > 0) {
    i <- ok[which.min(abs(counts[ok] - target_n))]
    return(picks[[i]])
  }

  i <- which.min(abs(counts - target_n))
  idx <- picks[[i]]
  if (length(idx) > max_n) {
    idx <- idx[order(stm_sf$..len_m[idx], decreasing = TRUE)][seq_len(max_n)]
  }
  idx
}

message("Selecting subset from ", nrow(stm), " segments...")
buffer_candidates <- c(5, 10, 25, 50)

selected_idx <- integer()
for (buffer_m in buffer_candidates) {
  message("  trying connected expansion with buffer=", buffer_m, "m ...")
  idx <- expand_connected(stm, seed_idx, buffer_m, target_n, min_n, max_n)
  message("    got ", length(idx), " segments")
  if (length(idx) >= min_n) {
    selected_idx <- idx
    break
  }
}

if (length(selected_idx) < min_n) {
  warning("Connected expansion did not reach ", min_n, " segments; falling back to bbox selection.")
  selected_idx <- select_by_bbox(stm, seed_idx, target_n, min_n, max_n)
  message("  bbox selection got ", length(selected_idx), " segments")
}

if (length(selected_idx) > max_n) {
  selected_idx <- selected_idx[seq_len(max_n)]
}

stm_sub <- stm[selected_idx, ]
stm_sub$..len_m <- NULL

if (nrow(stm_sub) < min_n || nrow(stm_sub) > max_n) {
  warning("Final subset has ", nrow(stm_sub), " segments (expected ", min_n, "-", max_n, ").")
}

bbox <- sf::st_bbox(stm_sub)
expand_m <- 500
bbox_exp <- bbox
bbox_exp[c("xmin", "ymin")] <- bbox_exp[c("xmin", "ymin")] - expand_m
bbox_exp[c("xmax", "ymax")] <- bbox_exp[c("xmax", "ymax")] + expand_m

ext_sub <- terra::ext(
  as.numeric(bbox_exp["xmin"]),
  as.numeric(bbox_exp["xmax"]),
  as.numeric(bbox_exp["ymin"]),
  as.numeric(bbox_exp["ymax"])
)

message("Cropping DEM to subset bbox + ", expand_m, "m ...")
dem_sub <- terra::crop(dem, ext_sub, snap = "out")
if (terra::nlyr(dem_sub) != 1) {
  dem_sub <- dem_sub[[1]]
}

sl_sp <- as(sf::st_geometry(stm_sub), "Spatial")
sl <- as(sl_sp, "SpatialLines")

dem_rl <- raster::raster(dem_sub)
if (!raster::inMemory(dem_rl)) {
  dem_rl <- raster::readAll(dem_rl)
}

out <- list(
  sl = sl,
  dem = dem_rl,
  desc = "QHH subset ~15-20 segments",
  n_segments = nrow(stm_sub)
)

dir.create(dirname(out_path), recursive = TRUE, showWarnings = FALSE)
saveRDS(out, out_path)

coords <- sf::st_coordinates(stm_sub)
total_vertices <- nrow(coords)

cat("Saved:", normalizePath(out_path, winslash = "/", mustWork = FALSE), "\n")
cat("Summary\n")
cat("  n_segments    :", out$n_segments, "\n")
cat("  total_vertices:", total_vertices, "\n")
cat("  bbox          :", "\n")
print(bbox)
