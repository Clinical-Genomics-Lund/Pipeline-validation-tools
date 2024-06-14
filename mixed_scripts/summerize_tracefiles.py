import pandas as pd
from pprint import pprint
import os
import re

"""
This script can summerize 4 different resource usages from nextflow-tracefiles
peak vmem
cpu usage
read
write
Usage:
Edit folder_path to where your trace-files are located
Edit file_ending to $assay.trace.txt to limit to only one type of assay (will do weird things else)
Please note that assays that have a shift in dsl1 -> dsl2 will produce funny outputs. Try to limit this
by selecting relevant trace-files in a separate folder before running script
"""


def simplify_processname(pname: str):
    """ remove lab-ids """
    pname = pname.split(' ')
    pname = pname[0]
    return pname

def bytesized(mem: str):
    """ convert mem usage to bytes """
    if mem == "-":
        return int(0)
    elif mem == '0' or mem == 0:
        return int(0)
    size_byte = 0
    mem = mem.split(' ')
    size = float(mem[0])
    size_unit = mem[1]
    if len(size_unit) > 1:
        if size_unit.startswith('K'):
            size_byte = size * 1024
        elif size_unit.startswith('M'):
            size_byte = size * 1024 * 1024
        elif size_unit.startswith('G'):
            size_byte = size * 1024 * 1024 * 1024
    else:
        size_byte = mem[0]
    return int(size_byte)

def cpu_touchup(cpu: str):
    """ remove % sign, return float """
    if cpu == "-":
        return int(0)
    cpu_clean = float(re.sub(r'%', '', cpu))
    return cpu_clean

folder_path = '/fs1/viktor/trace-data/'
file_ending = 'GMSMyeloidv1-0.trace.txt'
files = [f for f in os.listdir(folder_path) if f.endswith(file_ending)]
files = [os.path.join(folder_path, f) for f in files]

# for testing
#files = [ '', '']

tot_merge_list = []
sample = { 'cpu': {},'vmem' :  {}, 'wchar':  {}, 'rchar' :  {}, }
for f in files:
    df = pd.read_csv(f, delimiter='\t')
    print(f)
    df['name_simple']    = df['name'].apply(simplify_processname)
    df['peak_vmem_byte'] = df['peak_vmem'].apply(bytesized)
    df['rchar_byte']     = df['rchar'].apply(bytesized)
    df['wchar_byte']     = df['wchar'].apply(bytesized)
    df['cpu']            = df['%cpu'].apply(cpu_touchup)

    summary_mem   = df.groupby('name_simple')['peak_vmem_byte'].max().reset_index()
    summary_rchar = df.groupby('name_simple')['rchar_byte'].max().reset_index()
    summary_wchar = df.groupby('name_simple')['wchar_byte'].max().reset_index()
    summary_cpu   = df.groupby('name_simple')['cpu'].max().reset_index()

    df_merged = pd.merge(summary_mem,summary_rchar, on=['name_simple'])
    df_merged = pd.merge(df_merged,summary_wchar, on=['name_simple'])
    df_merged = pd.merge(df_merged,summary_cpu, on=['name_simple'])
    tot_merge_list.append(df_merged)

    ## Somewhat ugly  way to store max values per file and process
    for process in df_merged['name_simple']:
        file_max_vmem  = df_merged[df_merged['name_simple'] == process]['peak_vmem_byte'].values[0]
        file_max_cpu   = df_merged[df_merged['name_simple'] == process]['cpu'].values[0]
        file_max_rchar = df_merged[df_merged['name_simple'] == process]['rchar_byte'].values[0]
        file_max_wchar = df_merged[df_merged['name_simple'] == process]['wchar_byte'].values[0]
        # VMEM
        if process in sample['vmem']:
            if file_max_vmem > sample['vmem'][process]['max']:
                sample['vmem'][process]['max'] = file_max_vmem
                sample['vmem'][process]['file'] = f
        else:
            tmp = { 'max': file_max_vmem, 'file': f}
            sample['vmem'][process] = tmp
        # CPU
        if process in sample['cpu']:
            if file_max_cpu > sample['cpu'][process]['max']:
                sample['cpu'][process]['max'] = file_max_cpu
                sample['cpu'][process]['file'] = f
        else:
            tmp = { 'max': file_max_cpu, 'file': f}
            sample['cpu'][process] = tmp
        #RCHAR
        if process in sample['rchar']:
            if file_max_rchar > sample['rchar'][process]['max']:
                sample['rchar'][process]['max'] = file_max_rchar
                sample['rchar'][process]['file'] = f
        else:
            tmp = { 'max': file_max_rchar, 'file': f}
            sample['rchar'][process] = tmp
        #WCHAR
        if process in sample['wchar']:
            if file_max_wchar > sample['wchar'][process]['max']:
                sample['wchar'][process]['max'] = file_max_wchar
                sample['wchar'][process]['file'] = f
        else:
            tmp = { 'max': file_max_wchar, 'file': f}
            sample['wchar'][process] = tmp        

    

assay = pd.concat(tot_merge_list,ignore_index=True)

# VMEM TOTALS #
tot_vmem_max = assay.groupby('name_simple')['peak_vmem_byte'].max().reset_index()
tot_vmem_max = tot_vmem_max.rename( columns={ 'peak_vmem_byte' : 'max_peak_vmem'} )
tot_vmem_mean = assay.groupby('name_simple')['peak_vmem_byte'].mean().reset_index()
tot_vmem_mean = tot_vmem_mean.rename( columns={ 'peak_vmem_byte' : 'mean_peak_vmem'} )
tot_vmem_min = assay.groupby('name_simple')['peak_vmem_byte'].min().reset_index()
tot_vmem_min = tot_vmem_min.rename( columns={ 'peak_vmem_byte' : 'min_peak_vmem'} )
# CPU TOTALS #
tot_cpu_max = assay.groupby('name_simple')['cpu'].max().reset_index()
tot_cpu_max = tot_cpu_max.rename( columns={ 'cpu' : 'max_cpu'} )
tot_cpu_mean = assay.groupby('name_simple')['cpu'].mean().reset_index()
tot_cpu_mean = tot_cpu_mean.rename( columns={ 'cpu' : 'mean_cpu'} )
tot_cpu_min = assay.groupby('name_simple')['cpu'].min().reset_index()
tot_cpu_min = tot_cpu_min.rename( columns={ 'cpu' : 'min_cpu'} )
# RHCAR TOTALS #
tot_rchar_max = assay.groupby('name_simple')['rchar_byte'].max().reset_index()
tot_rchar_max = tot_rchar_max.rename( columns={ 'rchar_byte' : 'max_rchar'} )
tot_rchar_mean = assay.groupby('name_simple')['rchar_byte'].mean().reset_index()
tot_rchar_mean = tot_rchar_mean.rename( columns={ 'rchar_byte' : 'mean_rchar'} )
tot_rchar_min = assay.groupby('name_simple')['rchar_byte'].min().reset_index()
tot_rchar_min = tot_rchar_min.rename( columns={ 'rchar_byte' : 'min_rchar'} )
# WCHAR TOTALS #
tot_wchar_max = assay.groupby('name_simple')['wchar_byte'].max().reset_index()
tot_wchar_max = tot_wchar_max.rename( columns={ 'wchar_byte' : 'max_wchar'} )
tot_wchar_mean = assay.groupby('name_simple')['wchar_byte'].mean().reset_index()
tot_wchar_mean = tot_wchar_mean.rename( columns={ 'wchar_byte' : 'mean_wchar'} )
tot_wchar_min = assay.groupby('name_simple')['wchar_byte'].min().reset_index()
tot_wchar_min = tot_wchar_min.rename( columns={ 'wchar_byte' : 'min_wchar'} )

# merge that shit
# mem
tot_merge = pd.merge(tot_vmem_max, tot_vmem_min, on=['name_simple'])
tot_merge = pd.merge(tot_merge, tot_vmem_mean, on=['name_simple'])
tot_merge = pd.merge(tot_merge, tot_vmem_min, on=['name_simple'])
# cpu
tot_merge = pd.merge(tot_merge, tot_cpu_max, on=['name_simple'])
tot_merge = pd.merge(tot_merge, tot_cpu_min, on=['name_simple'])
tot_merge = pd.merge(tot_merge, tot_cpu_mean, on=['name_simple'])
# rchar
tot_merge = pd.merge(tot_merge, tot_rchar_max, on=['name_simple'])
tot_merge = pd.merge(tot_merge, tot_rchar_min, on=['name_simple'])
tot_merge = pd.merge(tot_merge, tot_rchar_mean, on=['name_simple'])
# wchar
tot_merge = pd.merge(tot_merge, tot_wchar_max, on=['name_simple'])
tot_merge = pd.merge(tot_merge, tot_wchar_min, on=['name_simple'])
tot_merge = pd.merge(tot_merge, tot_wchar_mean, on=['name_simple'])

# table
pprint(tot_merge)
# this could probably be printed prettier or converted to dataframe too and added to tot_merge
pprint(sample)
