#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE, scipen = 999)

suppressPackageStartupMessages({
  library(sf)
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

open_png <- function(path, width_in = 10, height_in = 7, res = 150) {
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

split_fields <- function(line) {
  line <- trimws(line)
  if (!nzchar(line)) {
    return(character(0))
  }
  strsplit(line, "[[:space:]]+")[[1]]
}

parse_dim_line <- function(line, label) {
  fields <- split_fields(line)
  assert_true(length(fields) == 2L, paste("Invalid", label, "dimension line:", line))
  dims <- suppressWarnings(as.integer(fields))
  assert_true(!anyNA(dims), paste("Non-integer", label, "dimension line:", line))
  dims
}

parse_numeric_block <- function(lines, pos, label) {
  assert_true(pos <= length(lines), paste("Unexpected end of file while reading", label))

  dims <- parse_dim_line(lines[pos], label)
  header_pos <- pos + 1L
  assert_true(header_pos <= length(lines), paste("Missing header for", label))

  cols <- split_fields(lines[header_pos])
  assert_true(length(cols) == dims[2], paste("Header width mismatch for", label))

  data_start <- header_pos + 1L
  data_end <- data_start + dims[1] - 1L
  assert_true(data_end <= length(lines), paste("Missing data rows for", label))

  rows <- lapply(lines[data_start:data_end], function(line) {
    fields <- split_fields(line)
    assert_true(length(fields) == dims[2], paste("Column count mismatch in", label, "row:", line))
    nums <- suppressWarnings(as.numeric(fields))
    assert_true(!anyNA(nums), paste("Non-numeric value in", label, "row:", line))
    nums
  })

  block <- as.data.frame(do.call(rbind, rows), check.names = FALSE)
  names(block) <- cols

  list(data = block, next_pos = data_end + 1L)
}

read_sp_mesh <- function(path) {
  lines <- readLines(path, warn = FALSE)
  parsed_elements <- parse_numeric_block(lines, 1L, ".sp.mesh element block")
  parsed_nodes <- parse_numeric_block(lines, parsed_elements$next_pos, ".sp.mesh node block")

  elements <- parsed_elements$data
  nodes <- parsed_nodes$data

  int_cols_ele <- c("ID", "Node1", "Node2", "Node3", "Nabr1", "Nabr2", "Nabr3")
  int_cols_node <- c("ID")
  elements[int_cols_ele] <- lapply(elements[int_cols_ele], function(x) as.integer(round(x)))
  nodes[int_cols_node] <- lapply(nodes[int_cols_node], function(x) as.integer(round(x)))

  assert_true(
    all(elements$Node1 %in% nodes$ID) &&
      all(elements$Node2 %in% nodes$ID) &&
      all(elements$Node3 %in% nodes$ID),
    "Mesh elements reference node IDs that are not present in the node block."
  )

  list(elements = elements, nodes = nodes)
}

read_rivseg <- function(path) {
  lines <- readLines(path, warn = FALSE)
  parsed <- parse_numeric_block(lines, 1L, ".sp.rivseg block")
  rivseg <- parsed$data
  rivseg[c("INDEX", "iRiv", "iEle")] <- lapply(
    rivseg[c("INDEX", "iRiv", "iEle")],
    function(x) as.integer(round(x))
  )
  rivseg
}

read_shud_series <- function(path, reach_names = NULL) {
  lines <- readLines(path, warn = FALSE)
  header_idx <- grep("^\\s*Time_min\\b", lines)
  assert_true(length(header_idx) >= 1L, paste("Missing Time_min header in", path))
  header_idx <- header_idx[1]

  header_fields <- split_fields(lines[header_idx])
  assert_true(length(header_fields) >= 2L, paste("Invalid Time_min header in", path))
  expected_width <- length(header_fields)

  rows <- vector("list", length(lines) - header_idx)
  kept <- 0L
  for (i in seq.int(header_idx + 1L, length(lines))) {
    fields <- split_fields(lines[i])
    if (length(fields) != expected_width) {
      next
    }
    nums <- suppressWarnings(as.numeric(fields))
    if (anyNA(nums)) {
      next
    }
    kept <- kept + 1L
    rows[[kept]] <- nums
  }

  assert_true(kept > 0L, paste("No numeric time-series rows found in", path))

  mat <- do.call(rbind, rows[seq_len(kept)])
  out <- data.frame(time_min = mat[, 1], mat[, -1, drop = FALSE], check.names = FALSE)

  if (!is.null(reach_names)) {
    assert_true(
      (ncol(out) - 1L) == length(reach_names),
      paste("Reach count does not match columns in", path)
    )
    names(out) <- c("time_min", reach_names)
  } else {
    names(out) <- c("time_min", paste0("V", seq_len(ncol(out) - 1L)))
  }

  out
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

line_coords <- function(geom) {
  sf::st_coordinates(geom)[, 1:2, drop = FALSE]
}

line_point_at <- function(coords, frac) {
  if (nrow(coords) < 2L) {
    return(as.numeric(coords[1, ]))
  }

  seg_len <- sqrt(rowSums((coords[-1, , drop = FALSE] - coords[-nrow(coords), , drop = FALSE])^2))
  cum_len <- c(0, cumsum(seg_len))
  total_len <- cum_len[length(cum_len)]
  if (!is.finite(total_len) || total_len <= 0) {
    return(as.numeric(coords[1, ]))
  }

  target <- max(0, min(1, frac)) * total_len
  idx <- max(which(cum_len <= target))
  idx <- min(idx, nrow(coords) - 1L)
  local_len <- seg_len[idx]
  if (!is.finite(local_len) || local_len <= 0) {
    return(as.numeric(coords[idx, ]))
  }

  alpha <- (target - cum_len[idx]) / local_len
  as.numeric(coords[idx, ] + alpha * (coords[idx + 1L, ] - coords[idx, ]))
}

build_mesh_geometry <- function(mesh) {
  node_row <- setNames(seq_len(nrow(mesh$nodes)), mesh$nodes$ID)
  polygons <- vector("list", nrow(mesh$elements))
  centroids <- matrix(NA_real_, nrow = nrow(mesh$elements), ncol = 2L)
  colnames(centroids) <- c("x", "y")

  for (i in seq_len(nrow(mesh$elements))) {
    node_ids <- as.integer(unlist(mesh$elements[i, c("Node1", "Node2", "Node3")], use.names = FALSE))
    node_idx <- unname(node_row[as.character(node_ids)])
    assert_true(!anyNA(node_idx), paste("Element", mesh$elements$ID[i], "references unknown nodes."))

    coords <- as.matrix(mesh$nodes[node_idx, c("x", "y")])
    polygons[[i]] <- rbind(coords, coords[1, , drop = FALSE])
    centroids[i, ] <- colMeans(coords)
  }

  list(polygons = polygons, centroids = centroids)
}

plot_map_frame <- function(xlim, ylim, main) {
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

draw_mesh <- function(polygons, fill_cols, border_col = "#555555", lwd = 1) {
  for (i in seq_along(polygons)) {
    graphics::polygon(
      polygons[[i]][, 1],
      polygons[[i]][, 2],
      col = fill_cols[i],
      border = border_col,
      lwd = lwd
    )
  }
}

draw_river_lines <- function(coords_list, cols, lwd = 3) {
  for (i in seq_along(coords_list)) {
    graphics::lines(coords_list[[i]][, 1], coords_list[[i]][, 2], col = cols[i], lwd = lwd)
  }
}

plot_timeseries <- function(df, reach_names, reach_cols, path, ylab, main) {
  time_days <- df$time_min / 1440
  ymat <- as.matrix(df[, reach_names, drop = FALSE])
  y_rng <- range(ymat, finite = TRUE)
  x_ticks <- pretty(time_days)
  y_ticks <- pretty(y_rng)

  open_png(path)
  graphics::par(mar = c(4.8, 5.0, 3.3, 1.2), mgp = c(2.8, 0.85, 0), bty = "l")

  graphics::plot(
    x = NA, y = NA, type = "n",
    xlim = range(time_days, finite = TRUE),
    ylim = y_rng,
    xlab = "Time (days)",
    ylab = ylab,
    xaxt = "n",
    yaxt = "n",
    main = main
  )
  graphics::abline(v = x_ticks, h = y_ticks, col = "#E6E6E6", lty = 3)
  graphics::axis(1, at = x_ticks)
  graphics::axis(2, at = y_ticks, las = 1)

  for (reach in reach_names) {
    graphics::lines(time_days, df[[reach]], col = reach_cols[reach], lwd = 2.4)
  }

  graphics::legend(
    "topright",
    legend = reach_names,
    col = reach_cols[reach_names],
    lwd = 2.4,
    bty = "n",
    title = "Reach"
  )

  graphics::box()
  grDevices::dev.off()
}

script_dir <- get_script_dir()
repo_root <- normalizePath(file.path(script_dir, "..", ".."), winslash = "/", mustWork = TRUE)

fixture_dir <- file.path(repo_root, "testdata", "ftbug")
mesh_path <- file.path(repo_root, "runs", "ftbug", "base", "route-only", "input", "ftbug", "ftbug.sp.mesh")
rivseg_path <- file.path(repo_root, "runs", "ftbug", "base", "route-only", "input", "ftbug", "ftbug.sp.rivseg")
river_path <- file.path(fixture_dir, "river.shp")
stage_path <- file.path(repo_root, "runs", "ftbug", "base", "route-only", "output", "ftbug.out", ".rivystage.csv")
qdown_path <- file.path(repo_root, "runs", "ftbug", "base", "route-only", "output", "ftbug.out", ".rivqdown.csv")

required_paths <- c(mesh_path, rivseg_path, river_path, stage_path, qdown_path)
for (path in required_paths) {
  assert_true(file.exists(path), paste("Missing input file:", path))
}

dir.create(fixture_dir, recursive = TRUE, showWarnings = FALSE)

mesh <- read_sp_mesh(mesh_path)
rivseg <- read_rivseg(rivseg_path)
river_sf <- sf::st_read(river_path, quiet = TRUE)
river_sf <- river_sf[order(river_sf$Index), ]
river_df <- sf::st_drop_geometry(river_sf)

assert_true(nrow(mesh$elements) == 16L, "Expected 16 mesh elements.")
assert_true(nrow(river_sf) == 6L, "Expected 6 river reaches.")
assert_true(nrow(rivseg) == 12L, "Expected 12 rivseg rows.")
assert_true(all(rivseg$iRiv %in% river_df$Index), "rivseg references river IDs not found in river.shp.")
assert_true(all(rivseg$iEle %in% mesh$elements$ID), "rivseg references element IDs not found in mesh.")

reach_names <- river_df$Reach
reach_by_index <- setNames(river_df$Reach, river_df$Index)
reach_cols <- c(R1 = "blue", R2 = "cyan", R3 = "green", R4 = "purple", R5 = "red", R6 = "orange")
type_cols <- c("1" = "blue", "2" = "green", "3" = "red")

stage_df <- read_shud_series(stage_path, reach_names = reach_names)
qdown_df <- read_shud_series(qdown_path, reach_names = reach_names)

mesh_geom <- build_mesh_geometry(mesh)
coords_list <- lapply(sf::st_geometry(river_sf), line_coords)
mid_xy <- t(vapply(coords_list, function(coords) line_point_at(coords, 0.5), numeric(2)))

xlim <- pad_range(c(mesh$nodes$x, mid_xy[, 1]), frac = 0.08)
ylim <- pad_range(c(mesh$nodes$y, mid_xy[, 2]), frac = 0.08)

river_element_ids <- sort(unique(rivseg$iEle))
river_fill_fig9 <- ifelse(mesh$elements$ID %in% river_element_ids, "#CFE8FF", "#E3E3E3")

first_reach_by_element <- tapply(rivseg$iRiv, rivseg$iEle, function(x) x[1])
fig12_fill <- rep("#D9D9D9", nrow(mesh$elements))
for (i in seq_len(nrow(mesh$elements))) {
  ele_id <- mesh$elements$ID[i]
  if (as.character(ele_id) %in% names(first_reach_by_element)) {
    reach_idx <- first_reach_by_element[[as.character(ele_id)]]
    reach_name <- reach_by_index[[as.character(reach_idx)]]
    fig12_fill[i] <- grDevices::adjustcolor(reach_cols[reach_name], alpha.f = 0.35)
  }
}

rivseg_split <- split(rivseg, rivseg$iEle)
element_annotations <- lapply(rivseg_split, function(df) {
  paste(sprintf("S%d:%s", df$INDEX, reach_by_index[as.character(df$iRiv)]), collapse = "\n")
})

fig9_path <- file.path(fixture_dir, "fig9_mesh_overview.png")
fig10_path <- file.path(fixture_dir, "fig10_route_only_stage.png")
fig11_path <- file.path(fixture_dir, "fig11_route_only_qdown.png")
fig12_path <- file.path(fixture_dir, "fig12_mesh_rivseg_detail.png")

open_png(fig9_path)
graphics::par(mar = c(4.8, 4.8, 3.5, 1.2), mgp = c(2.8, 0.85, 0), bty = "l", xpd = NA)
plot_map_frame(xlim, ylim, "SHUD Mesh with River Network (16 elements, 6 reaches)")
draw_mesh(mesh_geom$polygons, river_fill_fig9, border_col = "#4D4D4D", lwd = 1.1)
draw_river_lines(coords_list, type_cols[as.character(river_df$Type)], lwd = 3.1)
graphics::text(
  mesh_geom$centroids[, 1],
  mesh_geom$centroids[, 2],
  labels = mesh$elements$ID,
  cex = 0.82,
  font = 2,
  col = "#2F2F2F"
)
graphics::text(
  mid_xy[, 1],
  mid_xy[, 2],
  labels = reach_names,
  pos = 3,
  offset = 0.45,
  cex = 0.84,
  font = 2,
  col = type_cols[as.character(river_df$Type)]
)
graphics::legend(
  "bottomleft",
  legend = c("Element with river", "Element without river", "River Type 1", "River Type 2", "River Type 3"),
  pt.bg = c("#CFE8FF", "#E3E3E3", NA, NA, NA),
  pch = c(22, 22, NA, NA, NA),
  pt.cex = c(1.4, 1.4, NA, NA, NA),
  col = c("#4D4D4D", "#4D4D4D", "blue", "green", "red"),
  lwd = c(1, 1, 3, 3, 3),
  bty = "n"
)
grDevices::dev.off()

plot_timeseries(
  stage_df,
  reach_names,
  reach_cols,
  fig10_path,
  ylab = "Stage (m)",
  main = "Route-Only: River Stage (10 days)"
)

plot_timeseries(
  qdown_df,
  reach_names,
  reach_cols,
  fig11_path,
  ylab = "Qdown (m3/min)",
  main = "Route-Only: Downstream Discharge (10 days)"
)

open_png(fig12_path)
graphics::par(mar = c(4.8, 4.8, 3.5, 1.2), mgp = c(2.8, 0.85, 0), bty = "l", xpd = NA)
plot_map_frame(xlim, ylim, "Element-River Adjacency (12 segments)")
draw_mesh(mesh_geom$polygons, fig12_fill, border_col = "#4D4D4D", lwd = 1.1)
draw_river_lines(coords_list, reach_cols[reach_names], lwd = 3.1)

label_dy <- diff(ylim) * 0.012
anno_dy <- diff(ylim) * 0.018
for (i in seq_len(nrow(mesh$elements))) {
  ele_id <- mesh$elements$ID[i]
  cx <- mesh_geom$centroids[i, 1]
  cy <- mesh_geom$centroids[i, 2]
  graphics::text(cx, cy + label_dy, labels = paste0("E", ele_id), cex = 0.82, font = 2, col = "#222222")
  if (as.character(ele_id) %in% names(element_annotations)) {
    graphics::text(
      cx,
      cy - anno_dy,
      labels = element_annotations[[as.character(ele_id)]],
      cex = 0.62,
      col = "#333333"
    )
  }
}

graphics::legend(
  "bottomleft",
  legend = c(reach_names, "No river"),
  pt.bg = c(grDevices::adjustcolor(reach_cols[reach_names], alpha.f = 0.35), "#D9D9D9"),
  pch = rep(22, length(reach_names) + 1L),
  pt.cex = 1.4,
  col = rep("#4D4D4D", length(reach_names) + 1L),
  bty = "n",
  title = "Element fill"
)
grDevices::dev.off()

cat("Wrote figures:\n")
cat(" -", fig9_path, "\n")
cat(" -", fig10_path, "\n")
cat(" -", fig11_path, "\n")
cat(" -", fig12_path, "\n")
