args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 4) {
  stop("Usage: Rscript render_cmplot_association.R <association_path> <output_dir> <prefix> <warnings_path>")
}

association_path <- args[[1]]
output_dir <- args[[2]]
prefix <- args[[3]]
warnings_path <- args[[4]]

suppressPackageStartupMessages({
  library(CMplot)
})

dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
setwd(output_dir)

warnings <- character()

add_warning <- function(message) {
  warnings <<- c(warnings, message)
}

read_association_table <- function(path) {
  if (grepl("\\.csv$", path, ignore.case = TRUE)) {
    return(read.csv(path, stringsAsFactors = FALSE, check.names = FALSE))
  }
  read.table(path, header = TRUE, sep = "\t", stringsAsFactors = FALSE, check.names = FALSE, comment.char = "")
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

assoc_df <- read_association_table(association_path)

snp_col <- pick_column(assoc_df, c("SNP", "rsid", "ID", "Marker", "marker"))
chr_col <- pick_column(assoc_df, c("CHR", "Chromosome", "chrom", "chromosome"))
bp_col <- pick_column(assoc_df, c("BP", "POS", "Position", "position"))
p_col <- pick_column(assoc_df, c("P", "p", "PVAL", "pval", "PVALUE", "pvalue"))

required <- c(snp_col, chr_col, bp_col, p_col)
if (any(is.na(required))) {
  stop("Association table must contain SNP, CHR, BP, and P columns.")
}

pmap <- data.frame(
  SNP = assoc_df[[snp_col]],
  Chromosome = assoc_df[[chr_col]],
  Position = suppressWarnings(as.numeric(assoc_df[[bp_col]])),
  P = suppressWarnings(as.numeric(assoc_df[[p_col]])),
  stringsAsFactors = FALSE
)

pmap <- pmap[is.finite(pmap$Position) & is.finite(pmap$P), , drop = FALSE]
pmap <- pmap[pmap$P > 0 & pmap$P <= 1, , drop = FALSE]

if (!nrow(pmap)) {
  stop("Association table did not contain any valid Position/P rows.")
}

tryCatch(
  {
    CMplot(
      pmap,
      plot.type = "m",
      LOG10 = TRUE,
      threshold = c(5e-8, 1e-5),
      threshold.col = c("#8b1e1e", "#8f5a1b"),
      file.output = TRUE,
      file = "png",
      file.name = paste0(prefix, "_manhattan"),
      dpi = 180,
      col = c("#223f58", "#8b5a1e", "#245d3d", "#8a4b27")
    )
  },
  error = function(err) {
    add_warning(paste("Manhattan plot failed:", err$message))
  }
)

tryCatch(
  {
    CMplot(
      pmap,
      plot.type = "q",
      LOG10 = TRUE,
      conf.int = TRUE,
      file.output = TRUE,
      file = "png",
      file.name = paste0(prefix, "_qq"),
      dpi = 180,
      col = c("#223f58")
    )
  },
  error = function(err) {
    add_warning(paste("QQ plot failed:", err$message))
  }
)

if (!length(warnings)) {
  warnings <- "No warnings."
}

writeLines(warnings, con = warnings_path)
