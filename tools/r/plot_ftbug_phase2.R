#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE, scipen = 999)

suppressPackageStartupMessages({
  library(sf)
  library(jsonlite)
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

pad_range <- function(x, frac = 0.08) {
  xr <- range(x, finite = TRUE)
  span <- diff(xr)
  if (!is.finite(span) || span <= 0) {
    pad <- max(1, abs(xr[1]) * frac)
    return(c(xr[1] - pad, xr[2] + pad))
  }
  c(xr[1] - span * frac, xr[2] + span * frac)
}

fmt_sci <- function(x, digits = 2) {
  formatC(x, format = "e", digits = digits)
}

fmt_dec <- function(x, digits = 1) {
  formatC(x, format = "f", digits = digits)
}

num_vec <- function(x) {
  as.numeric(unlist(x, recursive = TRUE, use.names = FALSE))
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

parse_sp_block <- function(lines, pos) {
  assert_true(pos <= length(lines), "Unexpected end of .sp.riv file.")
  dims <- scan(text = lines[pos], what = integer(), quiet = TRUE)
  assert_true(length(dims) == 2, paste("Invalid block dimension line:", lines[pos]))

  nrow_block <- dims[1]
  ncol_block <- dims[2]
  header_pos <- pos + 1
  assert_true(header_pos <= length(lines), "Missing .sp.riv block header.")
  cols <- strsplit(trimws(lines[header_pos]), "[[:space:]]+")[[1]]
  assert_true(length(cols) == ncol_block, "Column count does not match .sp.riv header.")

  data_start <- header_pos + 1
  data_end <- data_start + nrow_block - 1
  assert_true(data_end <= length(lines), "Missing .sp.riv block rows.")

  block <- utils::read.table(
    text = paste(lines[data_start:data_end], collapse = "\n"),
    header = FALSE,
    check.names = FALSE,
    stringsAsFactors = FALSE
  )
  assert_true(ncol(block) == ncol_block, "Parsed .sp.riv block width does not match declared width.")
  names(block) <- cols
  block[] <- lapply(block, as.numeric)

  list(data = block, next_pos = data_end + 1)
}

read_sp_riv <- function(path) {
  lines <- readLines(path, warn = FALSE)
  pos <- 1
  blocks <- vector("list", 3)
  names(blocks) <- c("river", "type", "points")

  for (i in seq_along(blocks)) {
    parsed <- parse_sp_block(lines, pos)
    blocks[[i]] <- parsed$data
    pos <- parsed$next_pos
  }

  blocks
}

max_endpoint_xy_diff <- function(ref_pts, other_pts) {
  from_dist <- sqrt(
    (other_pts[["From.x"]] - ref_pts[["From.x"]])^2 +
      (other_pts[["From.y"]] - ref_pts[["From.y"]])^2
  )
  to_dist <- sqrt(
    (other_pts[["To.x"]] - ref_pts[["To.x"]])^2 +
      (other_pts[["To.y"]] - ref_pts[["To.y"]])^2
  )
  max(c(from_dist, to_dist))
}

from_endpoint_stats <- function(ref_pts, other_pts) {
  dx <- other_pts[["From.x"]] - ref_pts[["From.x"]]
  dy <- other_pts[["From.y"]] - ref_pts[["From.y"]]
  data.frame(
    dx = dx,
    dy = dy,
    dist_m = sqrt(dx^2 + dy^2),
    stringsAsFactors = FALSE
  )
}

match_index_order <- function(df, index_col = "Index") {
  df[order(df[[index_col]]), , drop = FALSE]
}

draw_bar_rect <- function(x_center, y_value, bar_width, floor_value, fill, border = "white", lwd = 0.8) {
  if (!is.finite(y_value) || y_value <= floor_value) {
    return(invisible(FALSE))
  }
  graphics::rect(
    xleft = x_center - bar_width / 2,
    ybottom = floor_value,
    xright = x_center + bar_width / 2,
    ytop = y_value,
    col = fill,
    border = border,
    lwd = lwd
  )
  invisible(TRUE)
}

panel_title <- function(label) {
  graphics::mtext(label, side = 3, line = 0.4, adj = 0, font = 2, cex = 1.0)
}

script_dir <- get_script_dir()
repo_root <- normalizePath(file.path(script_dir, "..", ".."), winslash = "/", mustWork = TRUE)

fixture_dir <- file.path(repo_root, "testdata", "ftbug")
preprocess_dir <- file.path(repo_root, "runs", "ftbug", "preprocess")

truth_sp_path <- file.path(fixture_dir, "truth.sp.riv")
truth_nodes_path <- file.path(fixture_dir, "truth_nodes.csv")
fixed_sp_path <- file.path(preprocess_dir, "fixed.sp.riv")
old_sp_path <- file.path(preprocess_dir, "old.sp.riv")
compare_path <- file.path(preprocess_dir, "compare.json")
river_path <- file.path(fixture_dir, "river.shp")

required_paths <- c(
  truth_sp_path,
  truth_nodes_path,
  fixed_sp_path,
  old_sp_path,
  compare_path,
  river_path
)
for (path in required_paths) {
  assert_true(file.exists(path), paste("Missing input file:", path))
}

truth_sp <- read_sp_riv(truth_sp_path)
fixed_sp <- read_sp_riv(fixed_sp_path)
old_sp <- read_sp_riv(old_sp_path)
compare_json <- jsonlite::fromJSON(compare_path, simplifyVector = FALSE)

truth_sp$river <- match_index_order(truth_sp$river, "Index")
fixed_sp$river <- fixed_sp$river[order(fixed_sp$river$Index), , drop = FALSE]
old_sp$river <- old_sp$river[order(old_sp$river$Index), , drop = FALSE]
truth_sp$type <- match_index_order(truth_sp$type, "Index")
fixed_sp$type <- fixed_sp$type[order(fixed_sp$type$Index), , drop = FALSE]
old_sp$type <- old_sp$type[order(old_sp$type$Index), , drop = FALSE]

ord_truth <- order(truth_sp$river$Index)
ord_fixed <- order(fixed_sp$river$Index)
ord_old <- order(old_sp$river$Index)
truth_sp$points <- truth_sp$points[ord_truth, , drop = FALSE]
fixed_sp$points <- fixed_sp$points[ord_fixed, , drop = FALSE]
old_sp$points <- old_sp$points[ord_old, , drop = FALSE]

truth_nodes <- utils::read.csv(truth_nodes_path, check.names = FALSE)
truth_nodes <- truth_nodes[order(truth_nodes$Index), , drop = FALSE]

river_sf <- sf::st_read(river_path, quiet = TRUE)
river_sf <- river_sf[order(river_sf$Index), ]
river_df <- sf::st_drop_geometry(river_sf)
coords_list <- lapply(sf::st_geometry(river_sf), line_coords)
mid_xy <- t(vapply(coords_list, function(x) line_point_at(x, 0.5), numeric(2)))

assert_true(
  identical(as.integer(truth_sp$river$Index), as.integer(river_df$Index)),
  "truth.sp.riv river block indices do not align with river.shp."
)
assert_true(
  identical(as.integer(fixed_sp$river$Index), as.integer(river_df$Index)),
  "fixed.sp.riv river block indices do not align with river.shp."
)
assert_true(
  identical(as.integer(old_sp$river$Index), as.integer(river_df$Index)),
  "old.sp.riv river block indices do not align with river.shp."
)
assert_true(
  identical(as.integer(truth_nodes$Index), as.integer(river_df$Index)),
  "truth_nodes.csv indices do not align with river.shp."
)

truth_point_diff <- max(abs(as.matrix(truth_nodes[, c("From.x", "From.y", "From.z", "To.x", "To.y", "To.z")]) -
  as.matrix(truth_sp$points)))
assert_true(truth_point_diff < 1e-9, "truth_nodes.csv and truth.sp.riv point block disagree.")

reach_names <- river_df$Reach
truth_slope <- truth_sp$river$Slope
fixed_slope <- fixed_sp$river$Slope
old_slope <- old_sp$river$Slope

min_riv_slope <- 4e-4
truth_col <- "#1A9850"
fixed_col <- "#2C7FB8"
old_col <- "#D7301F"
river_line_col <- "#8F8F8F"
reach_cols <- setNames(
  c("#1B9E77", "#D95F02", "#7570B3", "#E7298A", "#66A61E", "#E6AB02"),
  reach_names
)

bbox <- sf::st_bbox(river_sf)
xlim <- pad_range(c(bbox["xmin"], bbox["xmax"]), frac = 0.12)
ylim <- pad_range(c(bbox["ymin"], bbox["ymax"]), frac = 0.10)

compare_fixed <- compare_json$comparisons$truth_vs_fixed
compare_old <- compare_json$comparisons$truth_vs_old
acceptance <- compare_json$acceptance

fixed_slope_max_abs <- compare_fixed$slope$max_abs_diff
old_slope_max_abs <- compare_old$slope$max_abs_diff
fixed_slope_max_rel <- compare_fixed$slope$max_rel_diff
old_slope_max_rel <- compare_old$slope$max_rel_diff

fixed_xy_max <- max_endpoint_xy_diff(truth_sp$points, fixed_sp$points)
old_xy_max <- max_endpoint_xy_diff(truth_sp$points, old_sp$points)

old_from_stats <- from_endpoint_stats(truth_nodes, old_sp$points)
old_from_stats$Reach <- reach_names

old_zero_count <- sum(old_slope == 0)
old_negative_count <- sum(old_slope < 0)
old_wrong_positive_count <- sum(old_slope > 0 & abs(old_slope - truth_slope) > 1e-12)

fig5_path <- file.path(fixture_dir, "fig5_slope_comparison.png")
fig6_path <- file.path(fixture_dir, "fig6_point_mismatch.png")
fig7_path <- file.path(fixture_dir, "fig7_slope_scatter.png")
fig8_path <- file.path(fixture_dir, "fig8_phase2_summary.png")

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

open_png(fig5_path)
graphics::par(mar = c(5.0, 4.8, 3.2, 1.2), mgp = c(2.7, 0.8, 0), bty = "l", xpd = NA)

slope_floor <- 5e-5
slope_ylim <- c(slope_floor, max(c(abs(truth_slope), abs(fixed_slope), abs(old_slope), min_riv_slope)) * 2.0)
slope_ticks <- c(5e-5, 1e-4, 4e-4, 1e-3, 2e-3, 5e-3, 1e-2, 2e-2)
x_centers <- seq_along(reach_names)
bar_offsets <- c(-0.25, 0, 0.25)
bar_width <- 0.19

graphics::plot(
  x = NA, y = NA, type = "n",
  xlim = c(0.4, length(reach_names) + 0.6),
  ylim = slope_ylim,
  log = "y",
  xaxt = "n", yaxt = "n",
  xlab = "Reach", ylab = "Slope magnitude (m/m, log scale)",
  main = "Slope Comparison: Truth vs Fixed vs Old"
)
graphics::axis(1, at = x_centers, labels = reach_names)
graphics::axis(2, at = slope_ticks, labels = c("5e-5", "1e-4", "4e-4", "1e-3", "2e-3", "5e-3", "1e-2", "2e-2"), las = 1)
graphics::abline(h = slope_ticks, col = "#E7E7E7", lty = 3)
graphics::abline(h = min_riv_slope, col = "#4D4D4D", lty = 2, lwd = 1.5)

for (i in seq_along(reach_names)) {
  draw_bar_rect(x_centers[i] + bar_offsets[1], abs(truth_slope[i]), bar_width, slope_floor, truth_col)
  draw_bar_rect(x_centers[i] + bar_offsets[2], abs(fixed_slope[i]), bar_width, slope_floor, fixed_col)
  if (old_slope[i] != 0) {
    draw_bar_rect(x_centers[i] + bar_offsets[3], abs(old_slope[i]), bar_width, slope_floor, old_col)
  }
}

old_zero_idx <- which(old_slope == 0)
if (length(old_zero_idx) > 0) {
  graphics::points(
    x_centers[old_zero_idx] + bar_offsets[3],
    rep(slope_floor * 1.25, length(old_zero_idx)),
    pch = 4,
    cex = 1.15,
    lwd = 1.5,
    col = old_col
  )
}

old_neg_idx <- which(old_slope < 0)
if (length(old_neg_idx) > 0) {
  graphics::points(
    x_centers[old_neg_idx] + bar_offsets[3],
    abs(old_slope[old_neg_idx]) * 1.12,
    pch = 25,
    cex = 1.35,
    bg = old_col,
    col = old_col
  )
}

graphics::legend(
  "topleft",
  legend = c("Truth", "Fixed", "Old", "Old = 0", "Old < 0 (bar = |slope|)"),
  fill = c(truth_col, fixed_col, old_col, NA, NA),
  border = c(NA, NA, NA, NA, NA),
  pch = c(NA, NA, NA, 4, 25),
  pt.bg = c(NA, NA, NA, NA, old_col),
  col = c(NA, NA, NA, old_col, old_col),
  pt.cex = c(NA, NA, NA, 1.0, 1.1),
  bty = "n"
)
graphics::text(
  x = length(reach_names) + 0.55,
  y = min_riv_slope,
  labels = "MINRIVSLOPE = 4e-4",
  pos = 3,
  offset = 0.35,
  cex = 0.78,
  col = "#4D4D4D"
)
graphics::text(
  x = 3.45,
  y = slope_ylim[2] / 1.35,
  labels = "Old: 4 reaches=0, 1 negative, 1 wrong",
  cex = 0.88,
  font = 2,
  col = "#5A1D12"
)
graphics::box()
grDevices::dev.off()

open_png(fig6_path)
graphics::par(mar = c(4.3, 4.6, 3.4, 1.2), mgp = c(2.7, 0.8, 0), bty = "l", xpd = NA)
plot_network_frame("From/To Endpoint Mismatch: Truth vs Old")
graphics::plot(sf::st_geometry(river_sf), add = TRUE, col = river_line_col, lwd = 3.0)
graphics::text(mid_xy[, 1], mid_xy[, 2], labels = reach_names, cex = 0.78, font = 2, col = "#666666", pos = 3, offset = 0.45)

truth_from_xy <- as.matrix(truth_nodes[, c("From.x", "From.y")])
old_from_xy <- as.matrix(old_sp$points[, c("From.x", "From.y")])

truth_label_dx <- c(65, 45, 60, 60, 55, 65)
truth_label_dy <- c(90, 90, 50, 30, 35, 45)
old_label_x <- rep(unname(bbox["xmin"]) - 260, length(reach_names))
old_label_y <- c(4201600, 4201510, 4201420, 4201330, 4201240, 4201150)
dist_offset <- max(diff(xlim), diff(ylim)) * 0.018

for (i in seq_along(reach_names)) {
  tx <- truth_from_xy[i, 1]
  ty <- truth_from_xy[i, 2]
  ox <- old_from_xy[i, 1]
  oy <- old_from_xy[i, 2]
  dist_i <- old_from_stats$dist_m[i]

  graphics::points(tx, ty, pch = 21, bg = truth_col, col = "white", cex = 1.25, lwd = 1.0)
  graphics::points(ox, oy, pch = 4, col = old_col, cex = 1.4, lwd = 2.0)

  graphics::text(
    tx + truth_label_dx[i],
    ty + truth_label_dy[i],
    labels = paste0(reach_names[i], " T"),
    cex = 0.84,
    font = 2,
    col = truth_col
  )
  graphics::segments(
    x0 = tx + truth_label_dx[i] * 0.7,
    y0 = ty + truth_label_dy[i] * 0.7,
    x1 = tx,
    y1 = ty,
    col = grDevices::adjustcolor(truth_col, alpha.f = 0.55),
    lty = 3
  )

  graphics::text(
    old_label_x[i],
    old_label_y[i],
    labels = paste0(reach_names[i], " O"),
    cex = 0.80,
    font = 2,
    col = old_col,
    adj = c(0, 0.5)
  )
  graphics::segments(
    x0 = old_label_x[i] + 35,
    y0 = old_label_y[i],
    x1 = ox,
    y1 = oy,
    col = grDevices::adjustcolor(old_col, alpha.f = 0.55),
    lty = 3
  )

  if (dist_i > 1e-9) {
    graphics::arrows(
      x0 = tx,
      y0 = ty,
      x1 = ox,
      y1 = oy,
      length = 0.08,
      lwd = 1.35,
      col = grDevices::adjustcolor(old_col, alpha.f = 0.75)
    )

    midx <- (tx + ox) / 2
    midy <- (ty + oy) / 2
    dx <- ox - tx
    dy <- oy - ty
    seg_len <- sqrt(dx^2 + dy^2)
    perp <- c(-dy, dx) / seg_len
    graphics::text(
      midx + perp[1] * dist_offset,
      midy + perp[2] * dist_offset,
      labels = paste0(round(dist_i), " m"),
      cex = 0.76,
      font = 2,
      col = "#5C1A14"
    )
  } else {
    graphics::text(
      tx + 70,
      ty - 85,
      labels = "0 m",
      cex = 0.76,
      font = 2,
      col = "#5C1A14"
    )
  }
}

graphics::legend(
  "bottomleft",
  legend = c("River network", "Truth From endpoint", "Old From endpoint", "Truth -> Old displacement"),
  lwd = c(3.0, NA, NA, 1.35),
  col = c(river_line_col, truth_col, old_col, old_col),
  pch = c(NA, 21, 4, NA),
  pt.bg = c(NA, truth_col, NA, NA),
  pt.cex = c(NA, 1.0, 1.0, NA),
  bty = "n"
)
grDevices::dev.off()

plot_scatter_panel <- function(x, y, main, ylab, xlab, cols, labels, min_line, xlim_panel, ylim_panel) {
  axis_ticks_x <- pretty(xlim_panel, n = 5)
  axis_ticks_y <- pretty(ylim_panel, n = 6)

  graphics::plot(
    x, y,
    pch = 19,
    col = cols,
    xlim = xlim_panel,
    ylim = ylim_panel,
    xlab = xlab,
    ylab = ylab,
    main = main,
    xaxt = "n",
    yaxt = "n"
  )
  graphics::axis(1, at = axis_ticks_x, labels = formatC(axis_ticks_x, format = "f", digits = 3))
  graphics::axis(2, at = axis_ticks_y, labels = formatC(axis_ticks_y, format = "f", digits = 3), las = 1)
  graphics::abline(a = 0, b = 1, col = "black", lty = 2, lwd = 1.3)
  graphics::abline(h = 0, col = "#777777", lty = 3)
  graphics::abline(h = min_line, col = "#4D4D4D", lty = 2)
  graphics::grid(col = "#ECECEC", lty = 1)
  graphics::points(x, y, pch = 19, col = cols)
  graphics::text(x, y, labels = labels, pos = c(4, 2, 3, 4, 2, 4), offset = 0.5, cex = 0.82, font = 2, col = cols)
  graphics::box()
}

open_png(fig7_path)
graphics::par(mfrow = c(1, 2), mar = c(4.5, 4.8, 3.0, 1.2), oma = c(0, 0, 2.0, 0), mgp = c(2.7, 0.8, 0), bty = "l")

xlim_scatter <- c(0, max(truth_slope) * 1.12)
ylim_scatter <- c(min(c(old_slope, 0)) * 1.35, max(c(truth_slope, fixed_slope, old_slope, min_riv_slope)) * 1.10)

plot_scatter_panel(
  x = truth_slope,
  y = old_slope,
  main = "Truth vs Old",
  ylab = "Old slope (m/m)",
  xlab = "Truth slope (m/m)",
  cols = reach_cols[reach_names],
  labels = reach_names,
  min_line = min_riv_slope,
  xlim_panel = xlim_scatter,
  ylim_panel = ylim_scatter
)

plot_scatter_panel(
  x = truth_slope,
  y = fixed_slope,
  main = "Truth vs Fixed",
  ylab = "Fixed slope (m/m)",
  xlab = "Truth slope (m/m)",
  cols = reach_cols[reach_names],
  labels = reach_names,
  min_line = min_riv_slope,
  xlim_panel = xlim_scatter,
  ylim_panel = ylim_scatter
)
graphics::legend(
  "bottomright",
  legend = c("1:1 line", "y = 0", "y = MINRIVSLOPE"),
  lty = c(2, 3, 2),
  lwd = c(1.3, 1.0, 1.0),
  col = c("black", "#777777", "#4D4D4D"),
  bty = "n",
  cex = 0.82
)
graphics::mtext("Slope: Truth vs Old (left) and Truth vs Fixed (right)", side = 3, outer = TRUE, line = 0.2, font = 2)
grDevices::dev.off()

open_png(fig8_path)
graphics::par(mfrow = c(2, 2), mar = c(4.2, 4.8, 3.0, 1.2), oma = c(0, 0, 1.5, 0), mgp = c(2.6, 0.8, 0), bty = "l")

slope_diff_vals <- c(`Truth vs Fixed` = fixed_slope_max_abs, `Truth vs Old` = old_slope_max_abs)
slope_bp <- graphics::barplot(
  slope_diff_vals,
  col = c(fixed_col, old_col),
  border = NA,
  log = "y",
  yaxt = "n",
  ylim = c(1e-8, max(slope_diff_vals) * 2.5),
  ylab = "Max abs slope diff (m/m, log scale)",
  main = "Panel 1: Slope Error"
)
graphics::axis(2, at = c(1e-8, 1e-6, 1e-4, 1e-2), labels = c("1e-8", "1e-6", "1e-4", "1e-2"), las = 1)
graphics::text(slope_bp, slope_diff_vals * c(1.9, 1.15), labels = fmt_sci(slope_diff_vals, 2), cex = 0.82, font = 2)
graphics::box()

point_diff_vals <- c(`Truth vs Fixed` = fixed_xy_max, `Truth vs Old` = old_xy_max)
point_bp <- graphics::barplot(
  point_diff_vals,
  col = c(fixed_col, old_col),
  border = NA,
  ylim = c(0, max(point_diff_vals) * 1.25 + 25),
  ylab = "Max endpoint XY diff (m)",
  main = "Panel 2: Point Error"
)
graphics::text(
  point_bp,
  pmax(point_diff_vals, 0) + max(point_diff_vals) * 0.04 + 8,
  labels = c(paste0(fmt_dec(fixed_xy_max, 1), " m"), paste0(fmt_dec(old_xy_max, 1), " m")),
  cex = 0.82,
  font = 2
)
graphics::box()

graphics::plot.new()
graphics::plot.window(xlim = c(0, 4.3), ylim = c(0, 6.6))
panel_title("Panel 3: Acceptance Checks")

row_labels <- c(
  "Fixed slope ~= truth",
  "Old slope diverges >20%",
  "Fixed/old locked fields identical",
  "Slope-only touches block1 col4 only",
  "Point-only touches block3 only"
)
row_status <- c(
  acceptance$fixed_slope_matches_truth_near_zero$pass,
  acceptance$old_slope_differs_from_truth$pass,
  acceptance$fixed_old_locked_fields_identical$pass,
  acceptance$slope_only_changes_only_block1_col4$pass,
  acceptance$point_only_changes_only_block3$pass
)
row_detail <- c(
  sprintf("%s <= %s", fmt_sci(acceptance$fixed_slope_matches_truth_near_zero$max_abs_diff, 2), fmt_sci(acceptance$fixed_slope_matches_truth_near_zero$tolerance, 1)),
  sprintf("%d reaches, max rel %.1f%%", length(num_vec(acceptance$old_slope_differs_from_truth$reaches_gt_20pct)), 100 * acceptance$old_slope_differs_from_truth$max_rel_diff),
  "down/type/length",
  "block1 col4 only",
  "block3 only"
)

graphics::rect(0.02, 5.7, 4.28, 6.45, col = "#D9EDF7", border = NA)
graphics::text(0.12, 6.05, "Check", adj = 0, font = 2, cex = 0.86)
graphics::text(2.30, 6.05, "Status", adj = 0, font = 2, cex = 0.86)
graphics::text(2.95, 6.05, "Evidence", adj = 0, font = 2, cex = 0.86)

for (i in seq_along(row_labels)) {
  y_top <- 5.6 - (i - 1) * 1.02
  y_bot <- y_top - 0.82
  fill_col <- if (row_status[i]) "#EAF6E9" else "#FDE0DD"
  status_col <- if (row_status[i]) "#2A7F3B" else "#B2182B"
  graphics::rect(0.02, y_bot, 4.28, y_top, col = fill_col, border = "#D0D0D0")
  graphics::text(0.12, (y_top + y_bot) / 2, row_labels[i], adj = 0, cex = 0.80)
  graphics::text(2.30, (y_top + y_bot) / 2, if (row_status[i]) "PASS" else "FAIL", adj = 0, cex = 0.82, font = 2, col = status_col)
  graphics::text(2.95, (y_top + y_bot) / 2, row_detail[i], adj = 0, cex = 0.76)
}
graphics::box()

graphics::plot.new()
graphics::plot.window(xlim = c(0, 1), ylim = c(0, 1))
panel_title("Panel 4: Key Numbers")
summary_lines <- c(
  sprintf("Generated: %s", compare_json$generated_at),
  sprintf("Fixed slope max abs diff: %s", fmt_sci(fixed_slope_max_abs, 2)),
  sprintf("Old slope max abs diff: %s", fmt_sci(old_slope_max_abs, 2)),
  sprintf("Fixed slope max rel diff: %.3f%%", 100 * fixed_slope_max_rel),
  sprintf("Old slope max rel diff: %.1f%%", 100 * old_slope_max_rel),
  sprintf("Fixed max endpoint XY diff: %s m", fmt_dec(fixed_xy_max, 1)),
  sprintf("Old max endpoint XY diff: %s m", fmt_dec(old_xy_max, 1)),
  sprintf("Old max From-point shift: %s m (%s)", fmt_dec(max(old_from_stats$dist_m), 1), old_from_stats$Reach[which.max(old_from_stats$dist_m)]),
  sprintf("Old slopes: %d zero, %d negative, %d wrong positive", old_zero_count, old_negative_count, old_wrong_positive_count),
  sprintf("Acceptance: %d / %d pass", sum(row_status), length(row_status))
)
graphics::text(0.02, seq(0.92, 0.11, length.out = length(summary_lines)), labels = summary_lines, adj = c(0, 0.5), cex = 0.86)
graphics::box()

graphics::mtext("Phase 2 Summary Dashboard", side = 3, outer = TRUE, line = 0.2, font = 2)
grDevices::dev.off()

generated <- c(fig5_path, fig6_path, fig7_path, fig8_path)
info <- file.info(generated)

cat("Generated Phase 2 figures in:", normalizePath(fixture_dir, winslash = "/", mustWork = TRUE), "\n")
for (i in seq_along(generated)) {
  cat(
    sprintf(
      " - %s (%.1f KB)\n",
      basename(generated[i]),
      info$size[i] / 1024
    )
  )
}
