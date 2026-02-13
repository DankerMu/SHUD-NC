# rSHUD shud.river() 索引错配 Bug 验证指南

## Bug 概述

`rSHUD` 包的 `shud.river()` 函数存在索引错配问题：
- `xy` 表来自原始几何（N 行 unique 顶点）
- `ft` 索引来自简化后几何（M 行 unique 端点）
- 用 M 范围的索引去查 N 行的表 → 端点坐标/高程错配

## 验证步骤

### 1. 准备测试数据

```r
library(rSHUD)
library(sp)
library(raster)

# 创建简单 Y 形河网（3 条河段）
set.seed(42)
coords_list <- list(
  cbind(x = c(0, 10, 20, 30, 40, 50, 50),
        y = c(0, 10, 20, 30, 40, 50, 60) + runif(7, -2, 2)),
  cbind(x = c(50, 60, 70, 80, 90, 100, 100),
        y = c(60, 70, 80, 90, 95, 100, 100) + runif(7, -2, 2)),
  cbind(x = c(50, 40, 30, 20, 10, 0, 0),
        y = c(60, 70, 80, 90, 95, 100, 100) + runif(7, -2, 2))
)
lines_list <- lapply(coords_list, Line)
lines_obj <- Lines(lines_list, ID = "river")
sp_river <- SpatialLines(list(lines_obj))

# 创建 DEM（高程 = y 坐标）
dem <- raster(nrows = 10, ncols = 10,
              xmn = -5, xmx = 105, ymn = -5, ymx = 105)
dem[] <- matrix(rep(seq(0, 100, length.out = 10), 10), 10, 10, byrow = TRUE)
```

### 2. 提取关键中间变量

```r
# 模拟 shud.river() 内部逻辑
xy <- data.frame(extractCoords(sp_river))  # 原始 unique 顶点表
N <- nrow(xy)

# FromToNode 内部会简化几何
ft <- FromToNode(sp_river, simplify = TRUE)[, 2:3]
M <- max(ft)

cat("N (原始 unique 顶点数):", N, "\n")
cat("M (简化后 unique 端点数/ft 最大值):", M, "\n")
cat("ft 索引范围: [", min(ft), ",", max(ft), "]\n")
```

### 3. 验证索引错配

```r
# 检查 ft 索引是否超出合理范围
# 如果 M < N，则 ft 索引只能访问 xy 的前 M 行
cat("\n=== 索引错配检测 ===\n")
cat("ft 索引用于查询 xy 表（", N, "行），但 ft 最大值仅为", M, "\n")

if (M < N) {
  cat("⚠️ 存在索引错配风险：ft 索引范围 [1,", M, "] 无法覆盖 xy 全部", N, "行\n")
} else {
  cat("✓ 索引范围匹配\n")
}
```

### 4. 对比真实端点 vs buggy 端点

```r
# 获取每条河段的真实首尾端点
n_seg <- length(sp_river@lines[[1]]@Lines)
true_from <- matrix(NA, n_seg, 2)
true_to <- matrix(NA, n_seg, 2)

for (i in 1:n_seg) {
  coords <- sp_river@lines[[1]]@Lines[[i]]@coords
  true_from[i, ] <- coords[1, ]
  true_to[i, ] <- coords[nrow(coords), ]
}

# buggy 端点（shud.river() 实际使用的）
buggy_from <- as.matrix(xy[ft[, 1], ])
buggy_to <- as.matrix(xy[ft[, 2], ])

# 计算偏差
dist_from <- sqrt(rowSums((true_from - buggy_from)^2))
dist_to <- sqrt(rowSums((true_to - buggy_to)^2))

cat("\n=== 端点坐标偏差 ===\n")
cat("From 端点偏差: min=", min(dist_from), ", max=", max(dist_from), "\n")
cat("To 端点偏差: min=", min(dist_to), ", max=", max(dist_to), "\n")

n_from_wrong <- sum(dist_from > 0.1)
n_to_wrong <- sum(dist_to > 0.1)
cat("From 错配数:", n_from_wrong, "/", n_seg, "\n")
cat("To 错配数:", n_to_wrong, "/", n_seg, "\n")
```

### 5. 验证坡度计算

```r
# 真实坡度
z_true_from <- raster::extract(dem, true_from)
z_true_to <- raster::extract(dem, true_to)
length_seg <- sapply(1:n_seg, function(i) {
  LineLength(sp_river@lines[[1]]@Lines[[i]])
})
slope_true <- (z_true_from - z_true_to) / length_seg

# buggy 坡度（shud.river() 实际计算的）
z_buggy_from <- raster::extract(dem, buggy_from)
z_buggy_to <- raster::extract(dem, buggy_to)
slope_buggy <- (z_buggy_from - z_buggy_to) / length_seg

cat("\n=== 坡度对比 ===\n")
cat("真实坡度:", round(slope_true, 4), "\n")
cat("Buggy坡度:", round(slope_buggy, 4), "\n")
cat("坡度差异:", round(slope_buggy - slope_true, 4), "\n")

# 负坡度统计
cat("\n真实负坡度数:", sum(slope_true < 0), "/", n_seg, "\n")
cat("Buggy负坡度数:", sum(slope_buggy < 0), "/", n_seg, "\n")
```

### 6. 验证修复方案

```r
# 修复：显式传入 coord=xy 并设置 simplify=FALSE
ft_fixed <- FromToNode(sp_river, coord = xy, simplify = FALSE)[, 2:3]

fixed_from <- as.matrix(xy[ft_fixed[, 1], ])
fixed_to <- as.matrix(xy[ft_fixed[, 2], ])

dist_from_fixed <- sqrt(rowSums((true_from - fixed_from)^2))
dist_to_fixed <- sqrt(rowSums((true_to - fixed_to)^2))

cat("\n=== 修复后验证 ===\n")
cat("修复后 From 偏差: max=", max(dist_from_fixed), "\n")
cat("修复后 To 偏差: max=", max(dist_to_fixed), "\n")

if (max(dist_from_fixed) < 0.1 && max(dist_to_fixed) < 0.1) {
  cat("✓ 修复有效：端点坐标偏差归零\n")
} else {
  cat("⚠️ 修复后仍有偏差\n")
}
```

## 预期结果

如果 bug 存在，应观察到：
1. `M < N`（简化后端点数 < 原始顶点数）
2. `dist_from` 和 `dist_to` 存在非零偏差
3. `slope_buggy` 与 `slope_true` 存在差异
4. buggy 负坡度数 > 真实负坡度数（支流段高程关系翻转）
5. 修复后偏差归零

## Bug 根因

R 惰性求值机制导致 `FromToNode(sp, coord = extractCoords(sp, unique=TRUE), simplify=TRUE)` 中：
- `coord` 默认参数在 `simplify` 之后才被求值
- 此时 `sp` 已被简化，`coord` 变成简化后的端点表（M 行）
- 但 `shud.river()` 的 `xy` 是原始顶点表（N 行）
- 用 M 范围索引查 N 行表 → 系统性错配
