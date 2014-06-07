#! /bin/bash

mert_dir=/cs/natlang-sw/Linux-x86_64/NL/MT/MOSES/SVN_20101028/bin   # Path of the extractor/mert binary
d_dir=<Decoder directory>                                           # Path of the decoder
curr_dir=<top-level directory of trained system>                    # Current directory
w_dir=$curr_dir/tuning/mert-kriya                                   # MERT Working directory

# Tuning set files
dev_src=$curr_dir/devset-sent
dev_ref=/cs/natlang-data/wmt11/ensemble/en-fr/lc-dev/all.en-fr.dev.fr
dev_scfg=$curr_dir/devset-rules
dev_split=<no of devset splits>

# Test set files
test_src=$curr_dir/testset-sent
test_ref=/cs/natlang-data/wmt11/ensemble/en-fr/lc-test/all.en-fr.test.fr
test_scfg=$curr_dir/testset-rules
test_split=<no of testset splits>

# LM and config files
lm=/cs/natlang-data/wmt11/bsa33/lm/all.en-fr.fr.binlm
glue=$curr_dir/tuning/kriya.glue
config=$curr_dir/tuning/kriya.ini

# MERT parameters/ flags
d_exec="$d_dir/decoder.py"                      # Decoder executable string
d_prefix="python"                               # Tells the moses-MERT how to run the decoder

q_flags="-l__mem=6gb,walltime=40:00"          # An over-estimate for qsub
node_filter="-l__nodes=1:ppn=1"
m_args="--sctype=BLEU"                          # Arguments for mert
mert_status=100
prev_jobid=0

## Optimize parameter weights on the devset with MERT ...
/usr/bin/env perl $d_dir/mert-scripts/mert-moses-new-hiero.pl --working-dir=$w_dir --nbest=100 --jobs=$dev_split --mertdir=$mert_dir --mertargs=$m_args --mertstatus=$mert_status --prevjobid=$prev_jobid --input=$dev_src --refs=$dev_ref --scfgpath=$dev_scfg --decoder-prefix=$d_prefix --decoder=$d_exec --queue-flags=$q_flags --nodes-prop=$node_filter --config=$config --lmfile=$lm
wait

# Clean-up by removing temporary files and directories
rm -rf $w_dir/mert*.W.* $w_dir/*.dat.gz $w_dir/tmp*

## Now decode the test set ...
log_dir=$curr_dir/log
mkdir -p "$log_dir"

test_dir=$w_dir/testset-decode
mkdir -p $test_dir/log

cp -fp $w_dir/moses.ini $test_dir/kriya.ini

scrpt_file="$test_dir/decode_test.sh"
cmd="/cs/natlang-sw/Linux-x86_64/NL/LANG/PYTHON/2.6.2/bin/python $d_dir/decoder.py --config $test_dir/kriya.ini --1b --inputfile $test_src/\$j.out --outputfile $test_dir/1best.\$j.out --glue-file $glue --ttable-file $test_scfg/\$j.out --lmodel-file $lm >& $test_dir/log/1best.\$j.log"
echo $cmd > $scrpt_file

for ((k = 1; k <= $test_split; k++)); do
    qsub -l mem=6gb,walltime=40:00 -e $log_dir -o $log_dir -v j=$k $scrpt_file
done

