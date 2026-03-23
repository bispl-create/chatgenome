args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 5) {
  stop("Usage: Rscript render_qqman_association.R <association_path> <output_dir> <prefix> <qqman_repo_dir> <warnings_path>")
}

association_path <- args[[1]]
output_dir <- args[[2]]
prefix <- args[[3]]
qqman_repo_dir <- args[[4]]
warnings_path <- args[[5]]

dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
warnings <- character()

add_warning <- function(message) {
  warnings <<- c(warnings, message)
}

pick_column <- function(df, candidates) {
  lower_names <- tolower(colnames(df))
  for (candidate in candidates) {
    idx <- match(tolower(candidate), lower_names)
    if (!is.na(idx)) {
      return(colnames(df)[idx])
    }
  }
  return(NA_character_)
}

normalize_chr <- function(values) {
  cleaned <- gsub("^chr", "", as.character(values), ignore.case = TRUE)
  cleaned <- trimws(cleaned)
  cleaned[cleaned %in% c("X", "x")] <- "23"
  cleaned[cleaned %in% c("Y", "y")] <- "24"
  cleaned[toupper(cleaned) %in% c("M", "MT")] <- "25"
  suppressWarnings(as.numeric(cleaned))
}

read_association_table <- function(path) {
  if (grepl("\\.csv(\\.gz)?$", path, ignore.case = TRUE)) {
    return(read.csv(path, stringsAsFactors = FALSE, check.names = FALSE))
  }
  if (grepl("\\.gz$", path, ignore.case = TRUE)) {
    con <- gzfile(path, open = "rt")
    on.exit(close(con), add = TRUE)
    return(read.table(con, header = TRUE, sep = "\t", stringsAsFactors = FALSE, check.names = FALSE, comment.char = ""))
  }
  read.table(path, header = TRUE, sep = "\t", stringsAsFactors = FALSE, check.names = FALSE, comment.char = "")
}

source(file.path(qqman_repo_dir, "R", "qq.R"))
source(file.path(qqman_repo_dir, "R", "manhattan.R"))

assoc_df <- read_association_table(association_path)

snp_col <- pick_column(assoc_df, c("SNP", "rsid", "ID", "Marker", "marker", "hm_variant_id", "variant_id"))
chr_col <- pick_column(assoc_df, c("CHR", "Chromosome", "chrom", "chromosome", "hm_chrom"))
bp_col <- pick_column(assoc_df, c("BP", "POS", "Position", "position", "hm_pos", "base_pair_location"))
p_col <- pick_column(assoc_df, c("P", "p", "PVAL", "pval", "PVALUE", "pvalue", "p_value"))

required <- c(chr_col, bp_col, p_col)
if (any(is.na(required))) {
  stop("Association table must contain CHR, BP, and P columns for qqman.")
}

plot_df <- data.frame(
  CHR = normalize_chr(assoc_df[[chr_col]]),
  BP = suppressWarnings(as.numeric(assoc_df[[bp_col]])),
  P = suppressWarnings(as.numeric(assoc_df[[p_col]])),
  SNP = if (!is.na(snp_col)) as.character(assoc_df[[snp_col]]) else paste0("var_", seq_len(nrow(assoc_df))),
  stringsAsFactors = FALSE
)

plot_df <- plot_df[is.finite(plot_df$CHR) & is.finite(plot_df$BP) & is.finite(plot_df$P), , drop = FALSE]
plot_df <- plot_df[plot_df$P > 0 & plot_df$P <= 1, , drop = FALSE]

if (!nrow(plot_df)) {
  stop("Association table did not contain any valid CHR/BP/P rows for qqman.")
}

plot_df <- plot_df[order(plot_df$CHR, plot_df$BP), , drop = FALSE]

tryCatch(
  {
    png(filename = file.path(output_dir, paste0(prefix, ".qqman_manhattan.png")), width = 1600, height = 900, res = 160)
    manhattan(plot_df, main = "qqman Manhattan", col = c("#223f58", "#b26b1f"), cex = 0.55, cex.axis = 0.8)
    dev.off()
  },
  error = function(err) {
    add_warning(paste("qqman Manhattan plot failed:", err$message))
    if (dev.cur() > 1) {
      dev.off()
    }
  }
)

tryCatch(
  {
    png(filename = file.path(output_dir, paste0(prefix, ".qqman_qq.png")), width = 1000, height = 1000, res = 160)
    qq(plot_df$P, main = "qqman QQ", pch = 20, cex = 0.6, col = "#223f58")
    dev.off()
  },
  error = function(err) {
    add_warning(paste("qqman QQ plot failed:", err$message))
    if (dev.cur() > 1) {
      dev.off()
    }
  }
)

if (!length(warnings)) {
  warnings <- "No warnings."
}

writeLines(warnings, con = warnings_path)
