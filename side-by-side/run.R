source("giab-before-after.R")

# Confirmed causatives dry run ----------------------------------------------------------------


vcf_before <- read.vcfR("data/dry/1212-12.live.vcf.gz")
vcf_after <- read.vcfR("data/dry/1212-12.validation.vcf.gz")


side_by_side(vcf_before, vcf_after, run_name = "dry-run_blueprint-variants")


# GIAB trio -----------------------------------------------------------------------------------

vcf_before <- read.vcfR("data/trio/production_giab-trio.scored.vcf.gz")
vcf_after  <- read.vcfR("data/trio/validation_giab-trio.scored.vcf.gz")

message("Running side-by-side analysis for giab trios")
side_by_side(vcf_before, vcf_after, run_name = "wgs_giab-trio")


# GIAB trio mito only -------------------------------------------------------------------------

vcf_before <- only_mito_variants(vcf_before)
vcf_after  <- only_mito_variants(vcf_after)

message("Running side-by-side analysis for giab trio MT variants")
side_by_side(vcf_before, vcf_after, run_name = "wgs_giab-trio-mito")


# GIAB singles --------------------------------------------------------------------------------


message("Running side-by-side analysis for giab singles")

vcf_before <- read.vcfR("data/single/production_single_giab.scored.vcf.gz")
vcf_after <- read.vcfR("data/single/verification_single_giab.scored.vcf.gz")

side_by_side(vcf_before, vcf_after, run_name = "wgs_giab-single")


# GIAB single mito ----------------------------------------------------------------------------

vcf_before <- only_mito_variants(vcf_before)
vcf_after  <- only_mito_variants(vcf_after)

message("Running side-by-side analysis for giab single MT variants")
side_by_side(vcf_before, vcf_after, run_name = "wgs_giab-single-mito")



# WIP: ----------------------------------------------------------------------------------------

# Categorized rank scores by classification in dry run set

# dry_run_rank_scores <- rank_score_by_classification_comparison(vcf_before, vcf_after)
# 
# dry_run_rank_scores |> 
#   mutate(run = fct(run, levels =c("before", "after"))) |> 
#   filter(classification != "Benign") |> 
#   filter(classification != "Likely Benign") |> 
#   filter(classification != "Undefined Significance") |> 
#   ggplot(aes(x = run, y = rank_score)) + 
#   geom_boxplot() + 
#   facet_wrap(~classification)
# 
# 
# rank_score_by_clnsg_mod(vcf_before, vcf_after) |> 
#   mutate(run = fct(run, levels =c("before", "after"))) |> 
#   ggplot(aes(x = fct_reorder(classification, rank_score), y = rank_score, fill = run)) + geom_boxplot()
#   
