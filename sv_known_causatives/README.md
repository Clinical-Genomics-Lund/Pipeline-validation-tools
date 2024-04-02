# Evaluating workflows SV performance

This workflow consists of the following steps:

1. Retrieve known causative/non-causative variants
2. Run the evaluated pipeline
3. Identify whether correct known calls
4. Summarize the results

![Schematics](/img/pipeline_evaluation_tools_schematics.drawio.png)

## 1. Prepare manually curated variants

You will need a collection of manually curated variants, i.e. where a specific variant is known to be present.

* A collection of known variants summarized in a summary table (CSV)
* VCF files containing the variants

### Summary table

The known variants should be summarized in a CSV file in the following format.

| label  | chr  | pos     | type |
| ------ | ---- | ------- | ---- |
| label1 | chr7 | 2000100 | DEL  |
| label2 | chr2 | 1010100 | DEL  |

Below it is named `summary_table.csv`.

### Collect VCF files

Retrieve the VCF files. If stored on the Isilon backup server (i.e. you are working at CMD in Lund), you might do something like the following (make sure to adapt it to your use case):

```bash
vcf_basedir="<path to your vcfs>"
cat summary.csv | while read entry; do
    label=$(echo ${entry} | cut -f1 -d",")
    path="${vcf_basedir}/${label}.sv.scored.sorted.vcf.gz"
    cp ${path} /path/to/local/baseline
done
```

The end result should be a folder with each of your VCF files, i.e.:

```
baseline/
  label1.sv.scored.sorted.vcf.gz
  label2.sv.scored.sorted.vcf.gz
```

### Preparing the files

These files consists of subsets of the VCFs with only the baseline variants.

You can extract these subsets using the utility script `setup_reference_data.sh` (assuming `tabix` in path and `bgzipped` VCF files).

This will yield a folder with the references.

```bash
utils/1_setup_reference_data.sh sv_validation_samples.csv output
```

The reference only needs to be generated once per sample.

## 2. Execute the evaluation run

### Preparing input CSVs

To run all the samples, we need one samplesheet per sample. These can be generated using the `2_generate_samplesheet.sh` script, and a samplesheet template looking as such:

```
sample,lane,fastq_1,fastq_2,sex,phenotype,paternal_id,maternal_id,case_id
giab_sample,1,<FW>,<RV>,1,2,,,giab_full
```

The script inserts the correct paths at the `<FW>` and `<RV>` slots in the sample sheet.

The end results is a folder containing CSV files for each sample.

Example run:

```bash
utils/2_generate_samplesheet.sh template.csv fastq_folder/ samplesheets_out/
```

## Executing the run

A run for each of the input CSVs can be executed using the `start_run.sh` script.

```bash
start_run.sh csvs_dir/ out_base/ /path/to/main.nf /work/basedir/
```

* `csvs_dir/` - The folder containing each of the sample CSVs produced in the previous step
* `out_base/` - The base folder for the output runs
* `/path/to/main.nf` - The Nextflow script to execute for each of the samples
* `/work/basedir` - The location for the work folders (one will be produced for each sample)

## Evaluating the results

* FIXME: Optional output path for the final evaluation matrix

Evaluation of the results assumes that you have completed the runs in the previous step.
The evaluation checks each result file for whether they contain the expected structural variants. It then outputs a summary of the findings.

### Inputs

* `in_csv` is the file outlined above linking results and reference locations.
* `output_dir` the SVDB query results will be written for debugging

Example of the `in_csv` input format. The label is used in the output for the file names. The results is a full result VCF in which you will be looking for the expected SVs. The baseline is the prepared reference VCFs containing only the SVs that you are looking for.

| label   | results               | baseline           |
| ------- | --------------------- | ------------------ |
| sample1 | `/res/sample1.vcf.gz` | `/ref/sample1.vcf` |
| sample2 | `/res/sample2.vcf.gz` | `/ref/sample2.vcf` |
| sample3 | `/res/sample3.vcf.gz` | `/ref/sample3.vcf` |
| sample4 | `/res/sample4.vcf.gz` | `/ref/sample4.vcf` |

### Running the evaluation

The command is executed as such.

```
bash evaluate_run.sh in_csv output_dir
```

For it to run it requires you to have SVDB available in the PATH. If running it through a Singularity container, you can execute it as such:

```
singularity run -B /fs1 <container path> bash evaluate_run.sh in_csv output_dir
```

### Outputs

It will output a summary table to STDOUT. If you want to pretty-print it, you can pipe it into the `column` command as such:

```
singularity run -B /fs1 <container path> bash evaluate_run.sh in_csv output_dir | column -s$'\t' -t
```

The output will look something like the following:

```
label        type  chr        pos                len      type        callers
sA           base  9          30000000           -1000    DEL         gatk-manta-tiddit
sA           run   chr9       30000001           -999     DEL         gatk-manta-tiddit
sB_double    base  X          40000000           100      DUP:TANDEM  manta-tiddit-gatk
sB_double    run   chrX,chrX  40000000,40000000  110      DUP:TANDEM  manta-tiddit-gatk
sC_false     base  X          50000000           499      DUP:TANDEM  manta-tiddit-gatk
sC_false     run   -          -                  -        -           -
```
