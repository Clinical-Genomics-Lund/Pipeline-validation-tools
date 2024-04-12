library(tidyverse)

VCF_OUTPUT_NAME <- "output/vcf/snvs_external-variants.vcf"

# Dummy sample id:
sample_id = "1212-12"

# "G:\Pat-CMD\Validering och verifiering av undersöksmetoder\WGS\Verifiering i samband med hemtagning (WGS singel genlista och MPS 1-2 gener), 2022\Bearbetad data, underlag för rapport\Alla varianter_externt lab.xlsx"
varianter <- readxl::read_xlsx("Alla varianter_externt lab.xlsx", sheet = "WithRankScore")

# Create dummy INFO and FORMAT fields
# some of the nextflow_wgs genmod processes require the presence of a GT field for any samples
# even if it's a single
vcf_base <- varianter |> 
  mutate(ID=".", 
         FILTER =".", 
         QUAL =7777.7, 
         INFO = paste0("Classification=", Classification, ";FOO=1"), 
         FORMAT ="GQ:GT")  

vcf_base[[sample_id]] <- "30:0/1"
  
vcf_base <- vcf_base |> 
  select(
    `#CHROM` = `VCF CHROM`, 
    POS = `VCF POS`, 
    ID, 
    REF= `VCF REF`, 
    ALT = `VCF ALT`, 
    QUAL, 
    FILTER, 
    INFO, 
    FORMAT, 
    !!sample_id) |> 
  arrange(`#CHROM`, POS) 

tmp_vcf <- tempfile()

vcf_base |> 
  write_tsv(tmp_vcf)

final_vcf <- file(VCF_OUTPUT_NAME, "w")

header <- readLines("vcf.header")
writeLines(header, final_vcf)

vcf_records <- readLines(tmp_vcf)
writeLines(vcf_records, final_vcf)
close(final_vcf)

file.remove(tmp_vcf)
