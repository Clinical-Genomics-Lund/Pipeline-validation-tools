source("constants.R")

library(tidyverse)
library(furrr)
get_tidy_info <- function(vcf) {
  parsed_info <- vcf@fix |>
    as_tibble()
  
  plan(multisession)
  parsed_info$INFO |>
    future_map(function(info_row) {
      info_row |>
        map( ~ str_split(.x, ";")) |>
        map( ~ str_split(.x[[1]], "=")) |>
        map(function(x) {
          map_df(x, ~ tibble(key = .x[1], value = .x[2]))
        })
    },
    .progress = TRUE)
  plan(sequential)
  
  rowwise() |>
    group_split() |>
    head()
  map_dfr(function(vcf_row) {
    vcf_row$INFO <- str_split(vcf_row$INFO, ";", simplify = TRUE)
    parsed_info <- str_split(vcf_row$INFO, "=") |>
      map_df( ~ tibble(key = .x[1], value = .x[2])) |>
      pivot_wider(names_from = key, values_from = value)
    
    vcf_row |>
      select(-INFO) |>
      bind_cols(parsed_info)
  },
  .progress = TRUE)
  
  csq_keys <- get_csq_keys(vcf)
  
  if (length(csq_keys) > 0) {
    message("Parsing CSQ fields")
    parsed_info$CSQ <- parsed_info$CSQ |>
      map(parse_csq, csq_keys, .progress = TRUE)
  }
  
  
  rank_score_keys <- rank_score_keys(vcf)
  
  parsed_info
}

get_csq_keys <- function(vcf) {
  vcf@meta[str_detect(vcf@meta, "CSQ")] |>
    str_split_i("Format: ", 2) |>
    str_remove('\">') |>
    str_split_1('\\|')
}

parse_csq <- function(csq_str, csq_keys) {
  csq |>
    str_split_1(",") |>
    map_dfr(function(x) {
      y <- str_split_1(x, "\\|") |>
        setNames(csq_keys)
      enframe(y) |>
        pivot_wider(values_from = value, names_from = name)
    })
}

get_rankscores <- function(vcf) {
  vcf@fix[, 8] |>
    str_extract("RankScore=.+;") |>
    str_extract(":.+") |>
    str_remove_all(":")  |>
    str_remove_all(";") |>
    as.integer()
}

get_rank_results <- function(vcf) {
  rank_components <- rank_score_keys(vcf)
  meta_data <- get_id_cols(vcf)
  
  rank_data <- vcf@fix[, 8] |>
    str_extract("RankResult=.+;{0,1}") |>
    str_remove_all("RankResult=") |>
    str_remove_all(";$") |>
    tibble(rank_components = _) |>
    separate(rank_components, into = rank_components, sep = "\\|")
  
  msc <- get_msc(vcf)
  
  bind_cols(meta_data, rank_data) |>
    left_join(x = _, msc, by = join_by(CHROM, POS, REF, ALT))
  
}

get_id_cols <- function(vcf) {
  CHROM <- vcf@fix[, 1]
  POS <- as.integer(vcf@fix[, 2])
  ID <-  vcf@fix[, 3]
  REF <- vcf@fix[, 4]
  ALT <- vcf@fix[, 5]
  
  tibble(CHROM, POS, REF, ALT)
  
}

get_msc <- function(vcf) {
  meta <- get_id_cols(vcf)
  
  msc <- getINFO(vcf) |>
    str_extract("most_severe_consequence=[0-9a-zA-Z_]+;") |>
    str_split_i("=", 2) |>
    str_remove(";") |>
    tibble(most_severe_consequence = _)
  
  bind_cols(meta, msc)
}

variants_in_common <- function(vcf_fix, vcf_fix2) {
  f <- function(x)
    select(as_tibble(x), CHROM, POS, REF, ALT)
  
  bind_rows(f(vcf_fix), f(vcf_fix2)) |>
    mutate(POS = as.integer(POS)) |>
    group_by(CHROM, POS, REF, ALT) |>
    summarise(n = n()) |>
    filter(n > 1) |>
    select(-n)
}


process_vcf_into_rankscores <- function(vcf) {
  base_vcf <- get_id_cols(vcf)
  base_vcf$rank_score <- get_rankscores(vcf)
  base_vcf
}

add_plot_score_threshold_lines <-
  function(gg, score_threshold = 17) {
    gg +
      geom_hline(yintercept = score_threshold) +
      geom_vline(xintercept  = score_threshold)
  }

info_fields_defined_in_vcf_header <- function(vcf) {
  vcf@meta |>
    keep( ~ (str_starts(.x, "##INFO"))) |>
    str_remove("^##INFO=<ID=") |>
    str_split_i(",", 1)
}


get_variant_meta <- function(vcf, chrom, pos, ref, alt) {
  meta <- as_tibble(vcf@fix) |>
    filter(CHROM == chrom, POS == pos, REF == ref, ALT == alt)  |>
    mutate(POS = as.integer(POS))
  
  parsed_info <- parse_info_row(meta$INFO)
  
  bind_cols(meta, parsed_info) |>
    select(-INFO)
  
}

parse_info_row <- function(info_row) {
  parsed_info_row <- info_row |>
    str_split_1(";") |>
    tibble(x = _) |>
    separate(x, c("key", "value"), sep = "=") |> pivot_wider(names_from = key, values_from = value)
  
  parsed_info_row$CSQ <- str_split(parsed_info_row$CSQ, ",")
  parsed_info_row
  
}

rank_score_keys <- function(vcf) {
  rank_score_info <-
    vcf@meta[str_starts(vcf@meta, "##INFO=<ID=RankResult")] |>
    str_split_1(",")
  
  rank_score_info[str_starts(rank_score_info, "Description")] |>
    str_split_i('"', 2) |>
    str_split_1("\\|")
}

get_rank_result <-
  function(vcf,
           chrom,
           pos,
           ref,
           alt,
           rank_model_components = NULL) {
    if (is.null(rank_model_components)) {
      rank_model_components <- rank_score_keys(vcf)
    }
    
    meta <- get_variant_meta(vcf, chrom, pos, ref, alt)
    rank_result <- as.integer(str_split_1(meta$RankResult, "\\|"))
    rank_df <- rank_result |>
      setNames(rank_model_components) |>
      t() |>
      as.data.frame() |>
      as_tibble()
    
    rank_df$rank_result_sum <- rank_df |>
      select(all_of(rank_model_components)) |>
      unlist() |>
      sum()
    
    meta |>
      select(CHROM, POS, REF, ALT, most_severe_consequence) |>
      bind_cols(rank_df) |>
      select(everything(), most_severe_consequence)
    
  }

only_mito_variants <- function(vcf, mito_chr_name = "M") {
  vcf[getCHROM(vcf) == mito_chr_name]
}
