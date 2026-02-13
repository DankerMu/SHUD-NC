#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE)

suppressPackageStartupMessages({
  library(sf)
  library(terra)
  library(sp)
  library(raster)
})

get_script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) < 1) {
    return(normalizePath(getwd()))
  }
  script_path <- sub("^--file=", "", file_arg[1])
  dirname(normalizePath(script_path))
}

# ----------------------------------------------------------------------
# Helper functions copied from test_index_mismatch.R
# ----------------------------------------------------------------------

rowMatch <- function(x, m) {
  n <- length(x)
  nc <- ncol(m)
  if (n != nc) {
    return(FALSE)
  }
  y <- m * 1
  for (i in seq_len(nc)) {
    y[, i] <- (m[, i] - x[i])
  }
  apply(y, 1, FUN = function(x) {
    all(x == 0)
  })
}

extractCoords <- function(x, unique = TRUE, aslist = FALSE) {
  spl <- methods::as(x, "SpatialLines")
  spp <- methods::as(spl, "SpatialPoints")
  pts <- sp::coordinates(spp)
  if (unique) {
    return(unique(pts))
  }
  pts
}

xy2ID <- function(xy, coord) {
  if (!(is.matrix(xy) || is.data.frame(xy))) {
    xy <- matrix(xy, ncol = 2)
  }
  ng <- nrow(xy)
  id <- rep(0, ng)
  for (i in seq_len(ng)) {
    dd <- which(rowMatch(xy[i, ], coord))
    if (length(dd) > 0) {
      id[i] <- dd
    }
  }
  id
}

NodeIDList <- function(sp, coord = extractCoords(sp, unique = TRUE)) {
  pt.list <- unlist(sp::coordinates(sp), recursive = FALSE)
  lapply(pt.list, function(x) {
    xy2ID(x, coord = coord)
  })
}

FromToNode <- function(sp, coord = extractCoords(sp, unique = TRUE), simplify = TRUE) {
  if (simplify) {
    ext <- raster::extent(sp)
    tol <- (ext[2] - ext[1]) * 0.01
    old_s2 <- sf::sf_use_s2()
    on.exit(suppressMessages(sf::sf_use_s2(old_s2)), add = TRUE)
    suppressMessages(sf::sf_use_s2(FALSE))
    sp.sf <- sf::st_as_sf(sp)
    sp.sf <- sf::st_simplify(sp.sf, preserveTopology = FALSE, dTolerance = tol)
    sp <- methods::as(sp.sf, "Spatial")
  }
  id.list <- NodeIDList(sp, coord = coord)
  frto <- cbind(
    unlist(lapply(id.list, function(x) x[1])),
    unlist(lapply(id.list, function(x) x[length(x)]))
  )
  frto <- cbind(seq_len(length(sp)), frto)
  colnames(frto) <- c("ID", "FrNode", "ToNode")
  rbind(frto)
}

simplify_sp_lines <- function(sp) {
  ext <- raster::extent(sp)
  tol <- (ext[2] - ext[1]) * 0.01
  old_s2 <- sf::sf_use_s2()
  on.exit(suppressMessages(sf::sf_use_s2(old_s2)), add = TRUE)
  suppressMessages(sf::sf_use_s2(FALSE))
  sp.sf <- sf::st_as_sf(sp)
  sp.sf <- sf::st_simplify(sp.sf, preserveTopology = FALSE, dTolerance = tol)
  methods::as(sp.sf, "Spatial")
}

get_segment_parts <- function(sp) {
  sl <- methods::as(sp, "SpatialLines")
  lapply(sl@lines, function(one_line) {
    lapply(one_line@Lines, function(seg) {
      seg@coords[, 1:2, drop = FALSE]
    })
  })
}

segment_endpoints <- function(sp) {
  seg_parts <- get_segment_parts(sp)
  first_xy <- do.call(rbind, lapply(seg_parts, function(parts) {
    parts[[1]][1, 1:2, drop = FALSE]
  }))
  last_xy <- do.call(rbind, lapply(seg_parts, function(parts) {
    p <- parts[[length(parts)]]
    p[nrow(p), 1:2, drop = FALSE]
  }))
  colnames(first_xy) <- c("X", "Y")
  colnames(last_xy) <- c("X", "Y")
  list(from = first_xy, to = last_xy)
}

segment_label_points <- function(sp) {
  seg_parts <- get_segment_parts(sp)
  do.call(rbind, lapply(seg_parts, function(parts) {
    pts <- do.call(rbind, parts)
    c(mean(pts[, 1]), mean(pts[, 2]))
  }))
}

segment_lengths <- function(sp) {
  seg_parts <- get_segment_parts(sp)
  sapply(seg_parts, function(parts) {
    sum(sapply(parts, function(coords) {
      if (nrow(coords) < 2) {
        return(0)
      }
      dxy <- coords[-1, , drop = FALSE] - coords[-nrow(coords), , drop = FALSE]
      sum(sqrt(rowSums(dxy^2)))
    }))
  })
}

format_pct <- function(x, digits = 1) {
  sprintf(paste0("%.", digits, "f%%"), x * 100)
}

open_png <- function(path, width, height, res = 150) {
  os_name <- tolower(Sys.info()["sysname"])

  if (grepl("darwin", os_name)) {
    try_quartz <- try(
      quartz(
        file = path,
        type = "png",
        width = width / res,
        height = height / res,
        dpi = res
      ),
      silent = TRUE
    )
    if (!inherits(try_quartz, "try-error")) {
      return(invisible(TRUE))
    }
  }

  ok <- try(
    png(filename = path, width = width, height = height, units = "px", res = res, type = "cairo"),
    silent = TRUE
  )
  if (!inherits(ok, "try-error")) {
    return(invisible(TRUE))
  }

  png(filename = path, width = width, height = height, units = "px", res = res)
  invisible(TRUE)
}

set_png_dpi <- function(paths, res = 150) {
  sips_bin <- Sys.which("sips")
  if (!nzchar(sips_bin)) {
    return(invisible(FALSE))
  }

  for (p in paths) {
    if (!file.exists(p)) {
      next
    }
    suppressWarnings(system2(
      sips_bin,
      args = c(
        "--setProperty", "dpiWidth", as.character(res),
        "--setProperty", "dpiHeight", as.character(res),
        p
      ),
      stdout = FALSE,
      stderr = FALSE
    ))
  }
  invisible(TRUE)
}

pad_range <- function(x, frac = 0.08) {
  xr <- range(x, finite = TRUE)
  if (length(xr) < 2 || !all(is.finite(xr))) {
    return(c(0, 1))
  }
  span <- xr[2] - xr[1]
  if (span <= 0) {
    pad <- max(1, abs(xr[1]) * frac)
    return(c(xr[1] - pad, xr[2] + pad))
  }
  c(xr[1] - span * frac, xr[2] + span * frac)
}

map_diff_color <- function(x) {
  pal <- grDevices::colorRampPalette(c("#2DC937", "#E7B416", "#CC3232"))(100)
  out <- rep("grey60", length(x))
  ok <- is.finite(x)
  if (!any(ok)) {
    return(out)
  }
  xr <- range(x[ok])
  if (abs(xr[2] - xr[1]) < 1e-12) {
    out[ok] <- pal[60]
    return(out)
  }
  idx <- floor((x[ok] - xr[1]) / (xr[2] - xr[1]) * 99) + 1
  idx <- pmin(100, pmax(1, idx))
  out[ok] <- pal[idx]
  out
}

case_specs <- list(
  list(id = "mock1_y_shape", file = "mock1_y_shape.rds", short = "Mock1", label = "Mock1: Y-shape"),
  list(id = "mock2_tree", file = "mock2_tree.rds", short = "Mock2", label = "Mock2: Tree"),
  list(id = "mock3_qhh_subset", file = "mock3_qhh_subset.rds", short = "Mock3", label = "Mock3: QHH subset")
)

script_dir <- get_script_dir()
mock_dir <- script_dir

calc_case_metrics <- function(spec) {
  path <- file.path(mock_dir, spec$file)
  if (!file.exists(path)) {
    stop("Missing input file: ", path)
  }
  dat <- readRDS(path)
  sl <- dat$sl
  dem <- dat$dem

  xy_orig <- extractCoords(sl)
  xy_simp <- extractCoords(simplify_sp_lines(sl))
  ft_buggy <- FromToNode(sl, simplify = TRUE)[, 2:3, drop = FALSE]
  wrong_from <- xy_orig[ft_buggy[, 1], , drop = FALSE]
  wrong_to <- xy_orig[ft_buggy[, 2], , drop = FALSE]

  ends <- segment_endpoints(sl)
  right_from <- ends$from
  right_to <- ends$to

  eps <- 1e-9
  mismatch_flag <- rowSums(abs(wrong_from - right_from) > eps) > 0
  mismatch_row_rate <- sum(mismatch_flag) / nrow(ft_buggy)

  z_right_from <- raster::extract(dem, right_from)
  z_wrong_from <- raster::extract(dem, wrong_from)
  z_right_to <- raster::extract(dem, right_to)
  z_wrong_to <- raster::extract(dem, wrong_to)

  seg_len <- segment_lengths(sl)
  seg_len[seg_len <= 0] <- NA_real_

  fixed_slope <- (z_right_from - z_right_to) / seg_len
  buggy_slope <- (z_wrong_from - z_wrong_to) / seg_len

  data.frame(
    id = spec$id,
    short = spec$short,
    label = spec$label,
    n_segments = length(sl),
    N_orig = nrow(xy_orig),
    M_simp = nrow(xy_simp),
    mismatch_row_rate = mismatch_row_rate,
    stringsAsFactors = FALSE
  ) -> summary_row

  list(
    spec = spec,
    sl = sl,
    dem = dem,
    summary = summary_row,
    label_points = segment_label_points(sl),
    wrong_from = wrong_from,
    wrong_to = wrong_to,
    right_from = right_from,
    right_to = right_to,
    mismatch_flag = mismatch_flag,
    z_right_from = z_right_from,
    z_wrong_from = z_wrong_from,
    fixed_slope = fixed_slope,
    buggy_slope = buggy_slope,
    slope_abs_diff = abs(fixed_slope - buggy_slope),
    mean_abs_elev_diff = mean(abs(z_wrong_from - z_right_from), na.rm = TRUE)
  )
}

case_data <- lapply(case_specs, calc_case_metrics)

fig1_path <- file.path(mock_dir, "fig1_river_overview.png")
open_png(fig1_path, width = 1200, height = 400, res = 150)
par(mfrow = c(1, 3), mar = c(3.5, 3.5, 3.5, 1), mgp = c(2.1, 0.7, 0), cex.main = 0.95)
for (one in case_data) {
  n_seg <- one$summary$n_segments[1]
  seg_cols <- grDevices::rainbow(n_seg, s = 0.85, v = 0.9)
  plot(
    one$sl,
    col = seg_cols,
    lwd = 2,
    axes = TRUE,
    xlab = "X",
    ylab = "Y",
    main = sprintf("%s\nSegments=%d", one$spec$label, n_seg)
  )
  text(
    x = one$label_points[, 1],
    y = one$label_points[, 2],
    labels = seq_len(n_seg),
    col = seg_cols,
    cex = 0.75,
    pos = 3
  )
}
dev.off()

fig2_paths <- c(
  mock1_y_shape = file.path(mock_dir, "fig2a_mismatch_mock1.png"),
  mock2_tree = file.path(mock_dir, "fig2b_mismatch_mock2.png"),
  mock3_qhh_subset = file.path(mock_dir, "fig2c_mismatch_mock3.png")
)

for (one in case_data) {
  out_path <- fig2_paths[[one$spec$id]]
  open_png(out_path, width = 900, height = 700, res = 150)
  par(mar = c(3.8, 3.8, 4, 1), mgp = c(2.2, 0.7, 0))
  plot(
    one$sl,
    col = "grey70",
    lwd = 2,
    axes = TRUE,
    xlab = "X",
    ylab = "Y",
    main = sprintf(
      "%s From-node Index Mismatch\nMismatch rate=%s (%d/%d)",
      one$spec$label,
      format_pct(one$summary$mismatch_row_rate[1], digits = 1),
      sum(one$mismatch_flag),
      one$summary$n_segments[1]
    )
  )

  idx_arrow <- which(one$mismatch_flag)
  if (length(idx_arrow) > 0) {
    for (k in idx_arrow) {
      arrows(
        x0 = one$right_from[k, 1],
        y0 = one$right_from[k, 2],
        x1 = one$wrong_from[k, 1],
        y1 = one$wrong_from[k, 2],
        col = "red3",
        lwd = 1,
        lty = 2,
        length = 0.08
      )
    }
  }

  points(one$right_from[, 1], one$right_from[, 2], pch = 21, bg = "chartreuse3", col = "darkgreen", cex = 1.1)
  points(one$wrong_from[, 1], one$wrong_from[, 2], pch = 4, col = "red3", cex = 1.2, lwd = 1.4)
  text(one$right_from[, 1], one$right_from[, 2], labels = seq_len(one$summary$n_segments[1]), pos = 3, cex = 0.65)

  legend(
    "topleft",
    legend = c("River segments", "Correct From endpoint", "Wrong From endpoint", "Offset arrow (correct->wrong)"),
    col = c("grey60", "darkgreen", "red3", "red3"),
    lty = c(1, NA, NA, 2),
    lwd = c(2, NA, 1.4, 1),
    pch = c(NA, 21, 4, NA),
    pt.bg = c(NA, "chartreuse3", NA, NA),
    bty = "n",
    cex = 0.85
  )
  dev.off()
}

fig3_path <- file.path(mock_dir, "fig3_elevation_diff.png")
open_png(fig3_path, width = 1200, height = 500, res = 150)
par(mfrow = c(1, 3), mar = c(4.5, 4, 3.8, 1), mgp = c(2.2, 0.7, 0), cex.main = 0.9)
for (one in case_data) {
  z_mat <- rbind(one$z_right_from, one$z_wrong_from)
  colnames(z_mat) <- seq_len(ncol(z_mat))
  ylim <- pad_range(z_mat, frac = 0.12)
  barplot(
    z_mat,
    beside = TRUE,
    col = c("palegreen3", "tomato2"),
    border = NA,
    ylim = ylim,
    names.arg = seq_len(one$summary$n_segments[1]),
    xlab = "Segment ID",
    ylab = "Elevation (m)",
    main = sprintf("%s\nMean elev. diff=%.2f m", one$spec$label, one$mean_abs_elev_diff)
  )
  legend(
    "topright",
    legend = c("Correct elev. (z_right)", "Wrong elev. (z_wrong)"),
    fill = c("palegreen3", "tomato2"),
    bty = "n",
    cex = 0.8
  )
}
dev.off()

fig4_path <- file.path(mock_dir, "fig4_slope_comparison.png")
open_png(fig4_path, width = 1200, height = 500, res = 150)
par(mfrow = c(1, 3), mar = c(4.2, 4.2, 3.6, 1), mgp = c(2.2, 0.7, 0), cex.main = 0.92)
for (one in case_data) {
  keep <- is.finite(one$fixed_slope) & is.finite(one$buggy_slope)
  if (!any(keep)) {
    plot.new()
    title(main = sprintf("%s\nSlope comparison (no valid points)", one$spec$label))
    next
  }
  xs <- one$fixed_slope[keep]
  ys <- one$buggy_slope[keep]
  ds <- one$slope_abs_diff[keep]
  cols <- map_diff_color(ds)

  xy_lim <- pad_range(c(xs, ys), frac = 0.08)
  plot(
    xs,
    ys,
    pch = 16,
    col = cols,
    xlim = xy_lim,
    ylim = xy_lim,
    xlab = "Fixed slope",
    ylab = "Buggy slope",
    main = sprintf("%s\nSlope scatter comparison", one$spec$label)
  )
  abline(a = 0, b = 1, lty = 2, lwd = 1.2, col = "black")
  legend(
    "topleft",
    legend = c("1:1 reference", "Small diff", "Large diff"),
    lty = c(2, NA, NA),
    pch = c(NA, 16, 16),
    col = c("black", "#2DC937", "#CC3232"),
    bty = "n",
    cex = 0.8
  )
}
dev.off()

summary_df <- do.call(rbind, lapply(case_data, function(one) one$summary))
summary_df$ratio_NM <- summary_df$N_orig / summary_df$M_simp

fig5_path <- file.path(mock_dir, "fig5_summary.png")
open_png(fig5_path, width = 800, height = 600, res = 150)
par(mfrow = c(2, 1), mar = c(4.2, 4, 3.5, 1), mgp = c(2.2, 0.7, 0))

top_mat <- rbind(summary_df$N_orig, summary_df$M_simp)
colnames(top_mat) <- summary_df$short
bp_top <- barplot(
  top_mat,
  beside = TRUE,
  col = c("steelblue3", "darkorange2"),
  border = NA,
  ylab = "Row count",
  main = "Coord table size: Original N vs Simplified M"
)
text(
  x = colMeans(bp_top),
  y = apply(top_mat, 2, max) * 1.05,
  labels = sprintf("N/M=%.1f", summary_df$ratio_NM),
  cex = 0.85
)
legend(
  "topright",
  legend = c("N_orig", "M_simp"),
  fill = c("steelblue3", "darkorange2"),
  bty = "n",
  cex = 0.85
)

bot_vals <- summary_df$mismatch_row_rate * 100
bp_bot <- barplot(
  matrix(bot_vals, nrow = 1),
  beside = TRUE,
  col = "firebrick2",
  border = NA,
  names.arg = summary_df$short,
  ylim = c(0, max(bot_vals) * 1.25),
  ylab = "Mismatch rate (%)",
  main = "FromToNode Row-level Index Mismatch Rate"
)
text(
  x = bp_bot,
  y = bot_vals + max(1, max(bot_vals) * 0.05),
  labels = sprintf("%.1f%%", bot_vals),
  cex = 0.9
)
legend("topright", legend = "mismatch_row_rate", fill = "firebrick2", bty = "n", cex = 0.85)
dev.off()

draw_topology_panel <- function(one, from_xy, to_xy, row_label) {
  n_seg <- one$summary$n_segments[1]
  seg_cols <- grDevices::rainbow(n_seg, s = 0.85, v = 0.9)

  panel_title <- if (identical(row_label, "Buggy")) {
    sprintf(
      "%s - Buggy\nMismatch rate=%s",
      one$spec$short,
      format_pct(one$summary$mismatch_row_rate[1], digits = 1)
    )
  } else {
    sprintf("%s - Fixed", one$spec$short)
  }

  plot(
    one$sl,
    col = "grey70",
    lwd = 2,
    axes = TRUE,
    xlab = "X",
    ylab = "Y",
    main = panel_title
  )

  ok <- is.finite(from_xy[, 1]) & is.finite(from_xy[, 2]) & is.finite(to_xy[, 1]) & is.finite(to_xy[, 2])
  if (any(ok)) {
    arrows(
      x0 = from_xy[ok, 1],
      y0 = from_xy[ok, 2],
      x1 = to_xy[ok, 1],
      y1 = to_xy[ok, 2],
      col = seg_cols[ok],
      lwd = 1.5,
      length = 0.08
    )

    mid_x <- (from_xy[ok, 1] + to_xy[ok, 1]) / 2
    mid_y <- (from_xy[ok, 2] + to_xy[ok, 2]) / 2
    text(
      x = mid_x,
      y = mid_y,
      labels = which(ok),
      col = seg_cols[ok],
      cex = 0.7,
      pos = 3
    )
  }

  points(from_xy[, 1], from_xy[, 2], pch = 21, bg = "chartreuse3", col = "darkgreen", cex = 1.0)
  points(to_xy[, 1], to_xy[, 2], pch = 24, bg = "dodgerblue2", col = "navy", cex = 1.0)
}

fig6_path <- file.path(mock_dir, "fig6_topology_comparison.png")
open_png(fig6_path, width = 1200, height = 800, res = 150)
par(mfrow = c(2, 3), mar = c(3.6, 3.6, 3.8, 1.2), mgp = c(2.2, 0.7, 0), cex.main = 0.92)

for (one in case_data) {
  draw_topology_panel(one, one$wrong_from, one$wrong_to, row_label = "Buggy")
}
for (one in case_data) {
  draw_topology_panel(one, one$right_from, one$right_to, row_label = "Fixed")
}
dev.off()

cat("Generated figures:\n")
all_fig_paths <- c(
  fig1_path,
  fig2_paths[["mock1_y_shape"]],
  fig2_paths[["mock2_tree"]],
  fig2_paths[["mock3_qhh_subset"]],
  fig3_path,
  fig4_path,
  fig5_path,
  fig6_path
)
set_png_dpi(all_fig_paths, res = 150)

cat(" -", fig1_path, "\n")
cat(" -", fig2_paths[["mock1_y_shape"]], "\n")
cat(" -", fig2_paths[["mock2_tree"]], "\n")
cat(" -", fig2_paths[["mock3_qhh_subset"]], "\n")
cat(" -", fig3_path, "\n")
cat(" -", fig4_path, "\n")
cat(" -", fig5_path, "\n")
cat(" -", fig6_path, "\n")
