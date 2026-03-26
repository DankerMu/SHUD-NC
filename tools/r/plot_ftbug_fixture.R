#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE, scipen = 999)

suppressPackageStartupMessages({
  library(sf)
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

open_png <- function(path, width_in = 8, height_in = 6, res = 150) {
  os_name <- tolower(Sys.info()[["sysname"]])

  if (grepl("darwin", os_name)) {
    try_quartz <- try(
      quartz(
        file = path,
        type = "png",
        width = width_in,
        height = height_in,
        dpi = res
      ),
      silent = TRUE
    )
    if (!inherits(try_quartz, "try-error")) {
      return(invisible(TRUE))
    }
  }

  ok <- try(
    png(
      filename = path,
      width = width_in,
      height = height_in,
      units = "in",
      res = res,
      type = "cairo"
    ),
    silent = TRUE
  )
  if (!inherits(ok, "try-error")) {
    return(invisible(TRUE))
  }

  png(
    filename = path,
    width = width_in,
    height = height_in,
    units = "in",
    res = res
  )
  invisible(TRUE)
}

pad_range <- function(x, frac = 0.08) {
  xr <- range(x, finite = TRUE)
  span <- diff(xr)
  if (!is.finite(span) || span <= 0) {
    pad <- max(1, abs(xr[1]) * frac)
    return(c(xr[1] - pad, xr[2] + pad))
  }
  c(xr[1] - span * frac, xr[2] + span * frac)
}

read_manifest_value <- function(path, key) {
  lines <- readLines(path, warn = FALSE)
  hit <- grep(paste0("^  ", key, ": "), lines, value = TRUE)
  if (length(hit) < 1) {
    return(NA_character_)
  }
  sub(paste0("^  ", key, ": \"?(.*?)\"?$"), "\\1", hit[1])
}

line_coords <- function(geom) {
  sf::st_coordinates(geom)[, 1:2, drop = FALSE]
}

line_point_at <- function(coords, frac) {
  if (nrow(coords) < 2) {
    return(as.numeric(coords[1, ]))
  }

  seg_len <- sqrt(rowSums((coords[-1, , drop = FALSE] - coords[-nrow(coords), , drop = FALSE])^2))
  cum_len <- c(0, cumsum(seg_len))
  total_len <- cum_len[length(cum_len)]
  if (total_len <= 0) {
    return(as.numeric(coords[1, ]))
  }

  target <- max(0, min(1, frac)) * total_len
  idx <- max(which(cum_len <= target))
  idx <- min(idx, nrow(coords) - 1)
  local_len <- seg_len[idx]

  if (!is.finite(local_len) || local_len <= 0) {
    return(as.numeric(coords[idx, ]))
  }

  alpha <- (target - cum_len[idx]) / local_len
  as.numeric(coords[idx, ] + alpha * (coords[idx + 1, ] - coords[idx, ]))
}

junction_points <- function(truth_nodes) {
  endpoint_df <- rbind(
    data.frame(
      x = truth_nodes[["From.x"]],
      y = truth_nodes[["From.y"]],
      stringsAsFactors = FALSE
    ),
    data.frame(
      x = truth_nodes[["To.x"]],
      y = truth_nodes[["To.y"]],
      stringsAsFactors = FALSE
    )
  )
  key <- paste(endpoint_df$x, endpoint_df$y)
  hits <- duplicated(key) | duplicated(key, fromLast = TRUE)
  unique(endpoint_df[hits, , drop = FALSE])
}

compute_slope_class <- function(slope) {
  if (slope < 0.001) {
    "gentle"
  } else if (slope >= 0.009) {
    "steep"
  } else {
    "medium"
  }
}

raw_and_simplified_vertices <- function(river_sf) {
  raw_total <- sum(river_sf$NVert)
  bbox <- sf::st_bbox(river_sf)
  tol <- unname((bbox["xmax"] - bbox["xmin"]) * 0.01)

  old_s2 <- sf::sf_use_s2()
  on.exit(suppressMessages(sf::sf_use_s2(old_s2)), add = TRUE)
  suppressMessages(sf::sf_use_s2(FALSE))

  simp <- sf::st_simplify(river_sf, preserveTopology = FALSE, dTolerance = tol)
  simp_xy <- sf::st_coordinates(simp)[, 1:2, drop = FALSE]
  simp_unique <- unique(data.frame(round(simp_xy[, 1], 6), round(simp_xy[, 2], 6)))
  list(raw = raw_total, simplified = nrow(simp_unique), tolerance = tol)
}

draw_reach_arrows <- function(coords_list, col = "black", lwd = 1.2, length = 0.08) {
  for (coords in coords_list) {
    p0 <- line_point_at(coords, 0.43)
    p1 <- line_point_at(coords, 0.60)
    graphics::arrows(
      x0 = p0[1], y0 = p0[2],
      x1 = p1[1], y1 = p1[2],
      length = length, lwd = lwd, col = col
    )
  }
}

script_dir <- get_script_dir()
repo_root <- normalizePath(file.path(script_dir, "..", ".."), winslash = "/", mustWork = TRUE)
fixture_dir <- file.path(repo_root, "testdata", "ftbug")

manifest_path <- file.path(fixture_dir, "manifest.yaml")
truth_nodes_path <- file.path(fixture_dir, "truth_nodes.csv")
river_path <- file.path(fixture_dir, "river.shp")
dem_path <- file.path(fixture_dir, "dem.tif")

assert_true(file.exists(manifest_path), paste("Missing input file:", manifest_path))
assert_true(file.exists(truth_nodes_path), paste("Missing input file:", truth_nodes_path))
assert_true(file.exists(river_path), paste("Missing input file:", river_path))
assert_true(file.exists(dem_path), paste("Missing input file:", dem_path))

truth_nodes <- utils::read.csv(truth_nodes_path, check.names = FALSE)
river_sf <- sf::st_read(river_path, quiet = TRUE)
dem <- terra::rast(dem_path)

river_sf <- river_sf[order(river_sf$Index), ]
truth_nodes <- truth_nodes[order(truth_nodes$Index), ]
river_df <- sf::st_drop_geometry(river_sf)
coords_list <- lapply(sf::st_geometry(river_sf), line_coords)

from_xy <- as.matrix(truth_nodes[, c("From.x", "From.y")])
to_xy <- as.matrix(truth_nodes[, c("To.x", "To.y")])
mid_xy <- t(vapply(coords_list, function(x) line_point_at(x, 0.50), numeric(2)))
junction_xy <- junction_points(truth_nodes)
vertex_counts <- vapply(coords_list, nrow, integer(1))
vertex_stats <- raw_and_simplified_vertices(river_sf)

assert_true(all(vertex_counts == river_df$NVert), "Vertex counts in shapefile do not match geometry.")

type_cols <- c("1" = "#2C7BB6", "2" = "#1A9641", "3" = "#D7191C")
slope_cols <- c("steep" = "#D73027", "medium" = "#FC8D59", "gentle" = "#1A9850")
dem_cols <- grDevices::hcl.colors(80, "Terrain 2", rev = TRUE)
vertex_pal <- grDevices::colorRampPalette(c("#2C7BB6", "#ABD9E9", "#FDAE61", "#D7191C"))
slope_class <- vapply(river_df$Slope, compute_slope_class, character(1))

bbox <- sf::st_bbox(river_sf)
xlim <- pad_range(c(bbox["xmin"], bbox["xmax"]), frac = 0.12)
ylim <- pad_range(c(bbox["ymin"], bbox["ymax"]), frac = 0.10)

dem_formula <- read_manifest_value(manifest_path, "formula")
if (!is.character(dem_formula) || !nzchar(dem_formula) || is.na(dem_formula)) {
  dem_formula <- "z = 2500 - 0.0006 * (x - 500000) + 0.01 * (y - 4200000)"
}

fig1_path <- file.path(fixture_dir, "fig1_network_overview.png")
fig2_path <- file.path(fixture_dir, "fig2_dem_with_rivers.png")
fig3_path <- file.path(fixture_dir, "fig3_slope_profile.png")
fig4_path <- file.path(fixture_dir, "fig4_vertex_density.png")

plot_network_frame <- function(main) {
  graphics::plot(
    x = NA, y = NA, type = "n",
    xlim = xlim, ylim = ylim, asp = 1,
    xlab = "Easting (m)", ylab = "Northing (m)",
    xaxt = "n", yaxt = "n", main = main
  )
  graphics::axis(1)
  graphics::axis(2, las = 1)
  graphics::box()
}

open_png(fig1_path)
graphics::par(mar = c(4.2, 4.6, 3.2, 1.2), mgp = c(2.6, 0.8, 0), bty = "l")
plot_network_frame("Synthetic 6-Reach River Network")

for (i in seq_len(nrow(river_df))) {
  graphics::lines(coords_list[[i]], col = type_cols[as.character(river_df$Type[i])], lwd = 4, lend = "round")
}
draw_reach_arrows(coords_list, col = "#2B2B2B", lwd = 1.3, length = 0.09)
graphics::points(from_xy[, 1], from_xy[, 2], pch = 16, cex = 1.1, col = "#1F1F1F")
graphics::points(to_xy[, 1], to_xy[, 2], pch = 17, cex = 1.2, col = "#1F1F1F")
graphics::points(junction_xy$x, junction_xy$y, pch = 21, bg = "#FEE08B", col = "#3A3A3A", cex = 1.8, lwd = 1.1)
graphics::text(mid_xy[, 1], mid_xy[, 2], labels = river_df$Reach, font = 2, cex = 0.92, pos = 3, offset = 0.5)

graphics::legend(
  "bottomleft",
  legend = c("Type 1", "Type 2", "Type 3"),
  col = type_cols[c("1", "2", "3")],
  lwd = 4, bty = "n", title = "River Type"
)
graphics::legend(
  "topright",
  legend = c("From endpoint", "To endpoint", "Junction"),
  pch = c(16, 17, 21),
  pt.bg = c(NA, NA, "#FEE08B"),
  col = "#1F1F1F",
  pt.cex = c(1.0, 1.0, 1.4),
  bty = "n"
)
graphics::legend(
  "bottom",
  inset = 0.02,
  legend = c("R1,R2 -> R3 -> R5 -> R6(outlet)", "R4 -> R5"),
  title = "Topology",
  bg = grDevices::adjustcolor("white", alpha.f = 0.88),
  box.lty = 1,
  cex = 0.82
)
grDevices::dev.off()

open_png(fig2_path)
graphics::par(mar = c(4.2, 4.6, 4.2, 5.4), mgp = c(2.6, 0.8, 0), bty = "l")
terra::plot(
  dem,
  col = dem_cols,
  axes = TRUE,
  legend = TRUE,
  main = "DEM Surface with River Network",
  plg = list(title = "Elevation (m)")
)
graphics::title(sub = dem_formula, cex.sub = 0.82, line = 1.0)
graphics::plot(sf::st_geometry(river_sf), add = TRUE, col = "black", lwd = 2.4)
draw_reach_arrows(coords_list, col = "#202020", lwd = 1.2, length = 0.08)
graphics::points(from_xy[, 1], from_xy[, 2], pch = 21, bg = "#2C7BB6", col = "white", cex = 1.1, lwd = 0.8)
graphics::points(to_xy[, 1], to_xy[, 2], pch = 24, bg = "#D7191C", col = "white", cex = 1.15, lwd = 0.8)

from_pos <- c(3, 3, 4, 2, 3, 4)
to_pos <- c(2, 4, 4, 2, 4, 4)
for (i in seq_len(nrow(truth_nodes))) {
  graphics::text(
    truth_nodes[["From.x"]][i],
    truth_nodes[["From.y"]][i],
    labels = sprintf("%.2f", truth_nodes[["From.z"]][i]),
    pos = from_pos[i],
    offset = 0.45,
    cex = 0.72,
    col = "#08306B",
    font = 2
  )
  graphics::text(
    truth_nodes[["To.x"]][i],
    truth_nodes[["To.y"]][i],
    labels = sprintf("%.2f", truth_nodes[["To.z"]][i]),
    pos = to_pos[i],
    offset = 0.45,
    cex = 0.72,
    col = "#7F0000",
    font = 2
  )
}
graphics::legend(
  "bottomleft",
  legend = c("River centerline", "From z", "To z"),
  lwd = c(2.4, NA, NA),
  col = c("black", "#08306B", "#7F0000"),
  pch = c(NA, 21, 24),
  pt.bg = c(NA, "#2C7BB6", "#D7191C"),
  pt.cex = c(NA, 1.0, 1.0),
  bty = "n"
)
grDevices::dev.off()

min_riv_slope <- 4e-4
slope_ylim <- c(3e-4, max(river_df$Slope) * 1.9)
slope_ticks <- c(4e-4, 1e-3, 2e-3, 5e-3, 1e-2)
x_centers <- seq_len(nrow(river_df))
bar_half_width <- 0.34

open_png(fig3_path)
graphics::par(mar = c(4.2, 4.8, 3.2, 1.2), mgp = c(2.6, 0.8, 0), bty = "l", xpd = NA)
graphics::plot(
  x = NA, y = NA, type = "n",
  xlim = c(0.4, nrow(river_df) + 0.6),
  ylim = slope_ylim,
  log = "y",
  xaxt = "n", yaxt = "n",
  xlab = "Reach", ylab = "Slope (m/m, log scale)",
  main = "River Bed Slopes by Reach"
)
graphics::axis(1, at = x_centers, labels = river_df$Reach)
graphics::axis(2, at = slope_ticks, labels = c("4e-4", "1e-3", "2e-3", "5e-3", "1e-2"), las = 1)
graphics::abline(h = slope_ticks, col = "#E5E5E5", lty = 3)
for (i in seq_len(nrow(river_df))) {
  graphics::rect(
    xleft = x_centers[i] - bar_half_width,
    ybottom = slope_ylim[1],
    xright = x_centers[i] + bar_half_width,
    ytop = river_df$Slope[i],
    col = slope_cols[slope_class[i]],
    border = "white",
    lwd = 0.8
  )
}
graphics::abline(h = min_riv_slope, col = "#4D4D4D", lty = 2, lwd = 1.6)
graphics::text(
  x = x_centers,
  y = river_df$Slope * 1.18,
  labels = formatC(river_df$Slope, format = "e", digits = 2),
  cex = 0.77,
  font = 2
)
graphics::text(
  x = nrow(river_df) + 0.45,
  y = min_riv_slope,
  labels = "MINRIVSLOPE = 4e-4",
  pos = 3,
  offset = 0.35,
  cex = 0.77,
  col = "#4D4D4D"
)
graphics::legend(
  "topleft",
  legend = c("Steep", "Medium", "Gentle"),
  fill = slope_cols[c("steep", "medium", "gentle")],
  border = NA,
  bty = "n"
)
graphics::box()
grDevices::dev.off()

title_fig4 <- sprintf(
  "Vertex Density (N=%d total, simplify -> M~%d)",
  vertex_stats$raw,
  vertex_stats$simplified
)

open_png(fig4_path)
graphics::par(mar = c(4.2, 4.6, 3.2, 1.2), mgp = c(2.6, 0.8, 0), bty = "l")
plot_network_frame(title_fig4)
for (i in seq_len(nrow(river_df))) {
  coords <- coords_list[[i]]
  graphics::lines(coords, col = grDevices::adjustcolor("#6E6E6E", alpha.f = 0.7), lwd = 1.5)
  vcols <- vertex_pal(nrow(coords))
  graphics::points(coords[, 1], coords[, 2], pch = 16, cex = 0.55, col = vcols)
  graphics::text(
    mid_xy[i, 1],
    mid_xy[i, 2],
    labels = sprintf("%s: %d verts", river_df$Reach[i], river_df$NVert[i]),
    pos = 3,
    offset = 0.55,
    cex = 0.76,
    font = 2
  )
}
graphics::points(junction_xy$x, junction_xy$y, pch = 21, bg = "#FFF7BC", col = "#525252", cex = 1.3, lwd = 0.9)
graphics::legend(
  "topright",
  legend = c("Original polyline", "Raw vertices", "Junction"),
  lwd = c(1.5, NA, NA),
  col = c("#6E6E6E", "#2C7BB6", "#525252"),
  pch = c(NA, 16, 21),
  pt.bg = c(NA, NA, "#FFF7BC"),
  pt.cex = c(NA, 0.8, 1.2),
  bty = "n"
)
graphics::legend(
  "bottomleft",
  legend = c(
    sprintf("Simplify tolerance: %.1f m", vertex_stats$tolerance),
    sprintf("Raw vertices: %d", vertex_stats$raw),
    sprintf("Unique simplified nodes: %d", vertex_stats$simplified)
  ),
  bg = grDevices::adjustcolor("white", alpha.f = 0.9),
  box.lty = 1,
  cex = 0.80
)
grDevices::dev.off()

generated <- c(fig1_path, fig2_path, fig3_path, fig4_path)
info <- file.info(generated)

cat("Generated figures in:", normalizePath(fixture_dir, winslash = "/", mustWork = TRUE), "\n")
for (i in seq_along(generated)) {
  cat(
    sprintf(
      " - %s (%.1f KB)\n",
      basename(generated[i]),
      info$size[i] / 1024
    )
  )
}
