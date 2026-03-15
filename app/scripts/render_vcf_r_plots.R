args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 5) {
  stop("Usage: Rscript render_vcf_r_plots.R <vcf_path> <output_dir> <prefix> <density_bin_size> <warnings_path>")
}

vcf_path <- args[[1]]
output_dir <- args[[2]]
prefix <- args[[3]]
density_bin_size <- as.numeric(args[[4]])
warnings_path <- args[[5]]

suppressPackageStartupMessages({
  library(vcfR)
  library(CMplot)
  library(ggplot2)
})

dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
setwd(output_dir)

warnings <- character()

add_warning <- function(message) {
  warnings <<- c(warnings, message)
}

render_density_plot <- function(fix_df) {
  snp_id <- ifelse(fix_df$ID == "." | fix_df$ID == "", paste0(fix_df$CHROM, ":", fix_df$POS), fix_df$ID)
  density_map <- data.frame(
    SNP = snp_id,
    Chromosome = as.character(fix_df$CHROM),
    Position = as.numeric(fix_df$POS),
    stringsAsFactors = FALSE
  )

  tryCatch(
    {
      CMplot(
        density_map,
        plot.type = "d",
        bin.size = density_bin_size,
        file = "png",
        dpi = 180,
        file.output = TRUE,
        file.name = paste0(prefix, "_density"),
        col = c("#223f58", "#8b5a1e", "#245d3d", "#8a4b27")
      )
    },
    error = function(err) {
      add_warning(paste("CMplot density plot skipped:", err$message))
    }
  )
}

render_qual_plot <- function(fix_df) {
  qual_values <- suppressWarnings(as.numeric(fix_df$QUAL))
  qual_values <- qual_values[is.finite(qual_values)]
  if (!length(qual_values)) {
    add_warning("QUAL histogram skipped: no numeric QUAL values were found.")
    return(invisible(NULL))
  }

  plot_df <- data.frame(QUAL = qual_values)
  plot_obj <- ggplot(plot_df, aes(x = QUAL)) +
    geom_histogram(bins = 30, fill = "#223f58", color = "#f8f3ea") +
    labs(title = "QUAL Histogram", x = "QUAL", y = "Variant count") +
    theme_minimal(base_size = 14)
  ggsave(filename = paste0(prefix, ".qual_histogram.png"), plot = plot_obj, width = 8, height = 5, dpi = 180)
}

render_variant_class_plot <- function(fix_df) {
  alt_first <- sub(",.*$", "", fix_df$ALT)
  ref_len <- nchar(fix_df$REF)
  alt_len <- nchar(alt_first)
  class_values <- ifelse(
    grepl("^<", alt_first) | alt_first == "*",
    "symbolic",
    ifelse(ref_len == 1 & alt_len == 1, "snv", "indel")
  )

  plot_df <- as.data.frame(table(class_values), stringsAsFactors = FALSE)
  colnames(plot_df) <- c("variant_class", "count")
  plot_obj <- ggplot(plot_df, aes(x = variant_class, y = count, fill = variant_class)) +
    geom_col(show.legend = FALSE) +
    scale_fill_manual(values = c(indel = "#8b5a1e", snv = "#223f58", symbolic = "#245d3d")) +
    labs(title = "Variant Class", x = NULL, y = "Variant count") +
    theme_minimal(base_size = 14)
  ggsave(filename = paste0(prefix, ".variant_class.png"), plot = plot_obj, width = 7, height = 5, dpi = 180)
}

render_missingness_plot <- function(vcf_obj) {
  if (ncol(vcf_obj@gt) <= 1) {
    add_warning("Sample missingness plot skipped: no genotype sample columns were found.")
    return(invisible(NULL))
  }

  gt_matrix <- extract.gt(vcf_obj, element = "GT", as.numeric = FALSE)
  if (is.null(gt_matrix) || !length(gt_matrix)) {
    add_warning("Sample missingness plot skipped: genotype matrix could not be extracted.")
    return(invisible(NULL))
  }

  is_missing <- gt_matrix == "./." | gt_matrix == ".|." | gt_matrix == "." | gt_matrix == "" | is.na(gt_matrix)
  sample_missing <- colMeans(is_missing)
  plot_df <- data.frame(sample = names(sample_missing), missing_rate = as.numeric(sample_missing))
  plot_obj <- ggplot(plot_df, aes(x = reorder(sample, missing_rate), y = missing_rate)) +
    geom_col(fill = "#8f5a1b") +
    coord_flip() +
    labs(title = "Sample Missingness", x = NULL, y = "Missing genotype rate") +
    theme_minimal(base_size = 14)
  ggsave(filename = paste0(prefix, ".missingness.png"), plot = plot_obj, width = 8, height = 5, dpi = 180)
}

vcf_obj <- read.vcfR(vcf_path, verbose = FALSE)
fix_df <- as.data.frame(getFIX(vcf_obj), stringsAsFactors = FALSE)

if (!nrow(fix_df)) {
  stop("No VCF records were available for plotting.")
}

render_density_plot(fix_df)
render_qual_plot(fix_df)
render_variant_class_plot(fix_df)
render_missingness_plot(vcf_obj)

if (!length(warnings)) {
  warnings <- "No warnings."
}

writeLines(warnings, con = warnings_path)
