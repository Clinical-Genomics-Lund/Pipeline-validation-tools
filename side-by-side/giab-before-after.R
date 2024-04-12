library(vcfR)
library(tidyverse)

source("util.R")


side_by_side <- function(vcf_before, vcf_after, run_name) {


  # Timestamped output dir    
  output_dir <- get_output_dirpath(run_name)
  
  message(paste("Saving output to: ", output_dir))
  
  
  message("Computing some general stats")
  bind_rows(
    vcf_stats(vcf_before) |> mutate(run="before") |> select(run, everything()),
    vcf_stats(vcf_after) |> mutate(run="after") |> select(run, everything())
  ) |> 
    write_tsv(file.path(output_dir, "summary_vcf-stats.tsv"))
  
  message("Running rank-score comparison")
  compare_rank_scores(vcf_before, vcf_after, output_dir)
    

  message("Checking for variants missing from one run to other")
  missingness_result <- missingness_analysis(vcf_before, vcf_after)
  write_tsv(missingness_result, file.path(output_dir, "variants-missing-between-runs.tsv"), na = ".")
  
  missingness_result |> 
    group_by(only_present_in_run) |> 
    rename("uniquely_present_in_run" = only_present_in_run)  |> 
    summarise(count = n()) |> 
    write_tsv(file.path(output_dir, "summary_variants-missing-between-runs.tsv"), na = ".")
    
  message("Filtering out rank components of variants with differing rank scors")
  diffing_rank_results <- deeper_look_at_diffing_rank_scores(vcf_before, vcf_after)
  write_tsv(diffing_rank_results, file.path(output_dir, "rank-results_all-diffing-variants.tsv"))
  
  high_ranking_diffs <- diffing_rank_results |> 
    group_split(CHROM, POS, REF, ALT) |> 
    map_df(function(x) {
      
      scores <- sort(x$rank_score, decreasing = TRUE)
      
      if(!(scores[1] >= 17 && scores[2] < 17) ){
        return(tibble())
      }
      
      x$score_diff <- scores[1] - scores[2]
      x$highest_score <- scores[1]
      return(x)
    })
  
  if(nrow(high_ranking_diffs) > 0) {
    message("Filtering out variants that move across the score threshold between both runs")
    high_ranking_diffs |> 
      arrange(desc(score_diff)) |> 
      write_tsv(file.path(output_dir, "rank-results_variants-jumping-threshold.tsv"))
    
  }
  
  message("Checking info-field annotation coverage")
  info_field_completeness(vcf_before, vcf_after)   |> 
    write_tsv(file.path(output_dir, "info-fields_annotation-coverage.tsv"))
  
  info_field_completeness(vcf_before, vcf_after)   |> 
    filter(freq_before != freq_after) |> 
    write_tsv(file.path(output_dir, "info-fields_annotation-coverage_only-diffs.tsv"))
}

get_output_dirpath <- function(run_name) {
  
  time_now <- now()
  timestamp <- format(time_now, "%Y%m%d_%H%M%S")
  
  output_dir <- paste0("results/before-after/", paste(run_name, timestamp, sep = "_"))
  if(!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }
  
  output_dir
  
}

vcf_stats <- function(vcf) {
  stats <- tibble(
    n_variants = nrow(vcf@fix),
    n_snvs = count_snvs(vcf),
    n_indels = count_indels(vcf),
    n_mitochondrial_variants = sum(vcf@fix[,1] == "M")
  )
  
  scores <- as_tibble(vcf@fix[,1]) |> 
    rename(CHROM = 1) |> 
    mutate(score = get_rankscores(vcf))
  
  stats$mean_rank_score_all <-  mean(scores$score, na.rm = TRUE) |> round(1)
  stats$mean_rank_score_mito <- scores |> filter(CHROM == "M") |> pull(score) |> mean(na.rm=TRUE) |> round(1)
  stats$n_variants_above_17 <- scores |> filter(score >= 17) |> nrow()
  stats$n_mito_variants_above_17 <- scores |> filter(CHROM == "M" & score >= 17) |> nrow()
  stats
  }

count_snvs <- function(vcf) {
  vcf@fix[,c(4,5)] |> as_tibble() |> filter(str_length(REF) == str_length(ALT)) |> nrow()
}

count_indels <- function(vcf) {
  vcf@fix[,c(4,5)] |> as_tibble() |> filter(str_length(REF) != str_length(ALT)) |> nrow()
}

deeper_look_at_diffing_rank_scores <- function(vcf_before, vcf_after, output_dir) {
  
  message("Computing rank model breakdowns for all shared variants whose rank scores differ")
  message("Might take a while!")
  
  before_scores <-  vcf_before |> 
    process_vcf_into_rankscores() |> 
    mutate(run = "before")
  
  after_scores <-  vcf_after |>
    process_vcf_into_rankscores() |> 
    mutate(run = "after")
  
  rank_score_data <- bind_rows(before_scores, after_scores) |> 
    mutate(run = factor(run, levels =c("before", "after")))

  rm(before_scores)
  rm(after_scores)
  
  message("Fetching shared variants")
  shared_variants <- variants_in_common(vcf_before@fix, vcf_after@fix)  
  rank_score_data <- left_join(shared_variants, rank_score_data, by = c("CHROM", "POS", "REF", "ALT")) 
  
  message("Fetching variants whose rank scores differ b/w runs")
  diffing_rank_scores <- rank_score_data |> 
    group_by(CHROM, POS, REF, ALT, rank_score) |> 
    mutate(n = n()) |> 
    filter(n < 2) |> 
    select(-n) |> 
    ungroup()
  
  rm(rank_score_data)
  rm(shared_variants)
  
  rank_results_before <- get_rank_results(vcf_before) |> 
    mutate(run = "before")
  rank_results_after <- get_rank_results(vcf_after) |> 
    mutate(run = "after")
  
  rank_results <- bind_rows(rank_results_before, rank_results_after) |> 
    arrange(CHROM, POS, REF, ALT, desc(run)) |> 
    select(CHROM, POS, REF, ALT, run, everything()) |> 
    left_join(diffing_rank_scores, y = _, by = join_by(CHROM, POS, REF, ALT, run))
}


compare_rank_scores <- function(vcf_before, vcf_after, output_dir) {
  
  before_scores <-  vcf_before |> 
    process_vcf_into_rankscores() |> 
    mutate(run = "before")
  
  after_scores <-  vcf_after |>
    process_vcf_into_rankscores() |> 
    mutate(run = "after")
  
  rank_score_data <- bind_rows(before_scores, after_scores) |> 
    mutate(run = factor(run, levels =c("before", "after")))
    
  # GC
  rm(before_scores)
  rm(after_scores)
  
  rank_score_data |> 
    group_by(run) |> 
    summarise(
      n_variants_over_threshold = n(),
      mean_rank_score_over_threhsold = round(mean(rank_score), 3)
    ) |> 
    write_tsv(file.path(output_dir, "summary_rank-scores_all-variants.tsv"))
  
  rank_score_data |> 
    filter(rank_score >= 17) |> 
    group_by(run) |> 
    summarise(
      n_variants_over_threshold = n(),
      mean_rank_score_over_threhsold = round(mean(rank_score), 3)
      ) |> 
    write_tsv(file.path(output_dir, "summary_rank-scores_high-ranking-variants.tsv"))

  # Compare distribution of rank scores for all variants
  
  rank_score_stats <- rank_score_data |> 
    group_by(run) |> 
    summarise(mean = mean(rank_score))
  
  rank_score_data |> 
    ggplot(aes(x = rank_score, fill = run)) + 
    geom_histogram() +
    geom_vline(xintercept = 17, color = "black") +
    geom_vline(rank_score_stats, mapping = aes(xintercept = mean), linetype = "dashed") +
    facet_wrap(~run) +
    theme(legend.position = "bottom") +
    labs(caption = now())
  
  ggsave(file.path(output_dir, "plot_rank-scores_distribution-all.png"))
    
  # compare distribution of rank scores for variants w/ score > 10
  rank_score_stats <- rank_score_data |> 
    filter(rank_score >= 10) |> 
    group_by(run) |> 
    summarise(mean = mean(rank_score))
  
  rank_score_data |> 
    filter(rank_score >= 10) |> 
    ggplot(aes(x = rank_score, fill = run)) + 
    geom_histogram() + 
    geom_vline(xintercept = 17) +
    facet_wrap(~run) +
    theme(legend.position = "bottom") +
    ggtitle("Rank scores above score 10") +
    labs(caption = now()) 
  
  ggsave(file.path(output_dir, "plot_rank-scores_distribution-above-score-10.png"))

  shared_variants <- variants_in_common(vcf_before@fix, vcf_after@fix)  
  
  rank_score_data <- left_join(shared_variants, rank_score_data, by = join_by(CHROM, POS, REF, ALT))
  
  diffing_rank_scores <- rank_score_data |> 
    group_by(CHROM, POS, REF, ALT, rank_score) |> 
    mutate(n = n()) |> 
    filter(n < 2) |> 
    select(-n)

  rank_score_wide <- rank_score_data |> 
    pivot_wider(id_cols = c(CHROM, POS, REF, ALT), names_from = run, values_from = rank_score, names_prefix = "rankscore_")
  
  nbr_variants_in_common <- nrow(rank_score_wide)
  
  rank_score_wide |>   
    group_by(rankscore_before, rankscore_after) |> 
    summarize(n = n()) |> 
    ggplot(aes(x = rankscore_before, y = rankscore_after, size = n, color = n)) + 
    geom_abline(color = "black") +
    geom_hline(yintercept = 17, color = "pink", linetype = "longdash", size = 1) +
    geom_vline(xintercept = 17 , color = "pink",linetype = "longdash", size = 1) + 
    geom_point() + 
    ggtitle("SNV/indel rank scores before/after",
            paste("N = ", nbr_variants_in_common)) + 
    labs(caption = now())

    ggsave(file.path(output_dir, "plot_rank-scores_scatter-all.png"))

  nbr_variants_high_score <- rank_score_wide |> 
    filter(rankscore_before >= 17 | rankscore_after >= 17) |> 
    nrow()
      
  rank_score_wide |> 
    filter(rankscore_before >= 17 | rankscore_after >= 17) |> 
    group_by(rankscore_before, rankscore_after) |> 
    summarize(n = n()) |> 
    ggplot(aes(x = rankscore_before, y = rankscore_after, fill = n, label = n)) + 
    geom_abline(color = "pink", alpha = 1, size = 1) +
    geom_hline(yintercept = 17, color = "pink", linetype = "longdash", size = 1) +
    geom_vline(xintercept = 17 , color = "pink",linetype = "longdash", size = 1) + 
    geom_tile(alpha = .75) + 
    geom_text(color = "white", size = 3) +
    ggtitle("SNV/indel rank scores before/after",
            paste("Only variants with score ≥ 17 in either of runs", "\nN = ", nbr_variants_high_score)) +
    labs(caption= now()) 
  ggsave(file.path(output_dir, "plot_rank-scores_scatter-only-high-rank.png"))
  
  
}

missingness_analysis <- function(vcf_before, vcf_after) {

  before <- as_tibble(vcf_before@fix) |> 
    mutate(run = "before")
  
  after <- as_tibble(vcf_after@fix) |> 
    mutate(run = "after")
    
  bind_rows(before, after) |> 
    group_by(CHROM, POS, REF, ALT) |> 
    mutate(n = n()) |> 
    filter(n < 2) |> 
    rename(only_present_in_run = run) |> 
    select(only_present_in_run, everything(), -n)
  
}

pct_complete_info_field_annotations_in_vcf <- function(vcf) {
  
  n_variants <- nrow(vcf@fix)
  n_mt_variants <- sum(vcf@fix[,1] == "M")
    
  
  x <- getINFO(vcf) |> 
    str_split(";") |> 
    map(~str_split_i(.x, "=", 1)) |> 
    unlist() |> 
    table() |> 
    as.data.frame()  
  x |> 
    rowwise() |> 
    mutate(n_total = if_else(Var1 %in% MITO_ONLY_INFO_FIELDS, n_mt_variants, n_variants)) |> 
    mutate(Freq = ((Freq / n_total)*100) |> round(2))  |> 
    mutate(Var1 = as.character(Var1)) |> 
    rename("info_key" = Var1) |> 
    select(-n_total) 
    
}

info_field_completeness <- function(vcf_before, vcf_after) {
  
  freq <- full_join(
    pct_complete_info_field_annotations_in_vcf(vcf_before) |> rename("freq_before" = Freq),
    pct_complete_info_field_annotations_in_vcf(vcf_after) |> rename("freq_after" = Freq),
    by = join_by(info_key)
  ) |> 
    arrange(info_key)
  
  freq  
}
