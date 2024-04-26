library(tidyverse)
library(jsonlite)

VCF_OUTPUT_NAME <- "output/vcf/snvs_dismissed-variants.vcf"
VARIANT_DUMP_JSON <- "all-dimissed-variants.json"

dismissed_snv_variants <- jsonlite::read_json(VARIANT_DUMP_JSON) |> 
  keep(~ (.x$category == "snv")) |> 
  map_df(function(variant) {
    variant_out <- tibble(
      CHROM = variant$chrom, 
      POS = variant$position,
      ID = ".",
      REF = variant$reference,
      ALT = variant$alternative,
      QUAL = variant$quality,
      FILTER = ".",
      INFO = paste0("RankScoreAtDismissal=", variant$rank_score, ";"),
      FORMAT = "GT:GQ:AD:RD",
      rank_score_at_dismissal = variant$rank_score
      )
    
    sample_data = paste(
      "0/1",
      99,
      35,
      35,
      sep = ":"
    )
    
    if (variant$chrom == "M") {
      variant_out$FILTER = "PASS"
    }
    
    variant_out$SAMPLE = sample_data
    variant_out
  }) |> 
  arrange(CHROM, POS) 

dismissed_snv_variants |> 
  group_by(CHROM, POS, REF, ALT) |> 
  summarise(nbr_dismissals = n()) |> 
  arrange(-nbr_dismissals)

dismissed_snv_variants <- unique(dismissed_snv_variants)

# hist(dismissed_snv_variants$rank_score_at_dismissal, breaks = seq(-10, 30, by = 2))
# nrow(dismissed_snv_variants)

# Dummy sample id:
sample_id = "1212-12"


# Create dummy INFO and FORMAT fields
# some of the nextflow_wgs genmod processes require the presence of a GT field for any samples
# even if it's a single
vcf_base <- dismissed_snv_variants |> 
  select(
    `#CHROM` = CHROM,
    POS,
    ID,
    REF,
    ALT,
    QUAL,
    FILTER,
    INFO,
    FORMAT,
    )


vcf_base[[sample_id]] <- dismissed_snv_variants$SAMPLE

vcf_tmp <- tempfile()

vcf_base |> 
  write_tsv(vcf_tmp)

final_vcf <- file(VCF_OUTPUT_NAME, "w")

header <- readLines("vcf.header")
writeLines(header, final_vcf)

vcf_records <- readLines(vcf_tmp)
writeLines(vcf_records, final_vcf)
close(final_vcf)

file.remove(vcf_tmp)