#! /bin/bash

mert_dir=/cs/natlang-sw/Linux-x86_64/NL/MT/MOSES/SVN_20101028/bin   # Path of the extractor/mert binary
d_dir=<Decoder directory>                                           # Path of the decoder
curr_dir=<top-level directory of trained system>                    # Current directory
w_dir=$curr_dir/tuning/mert-kriya                                   # MERT Working directory

mkdir -p "$curr_dir/scripts"
mkdir -p "$curr_dir/log"

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

q_flags="-l__mem=2gb,walltime=1:00:00"          # An over-estimate for qsub
node_filter="-l__nodes=1:ppn=1"
m_args="--sctype=BLEU"                          # Arguments for mert
mert_status=100
prev_jobid=0

## Run MERT on the devset for tuning weights ...
/usr/bin/env perl $d_dir-New/mert-scripts/mert-moses-new-hiero2.pl --working-dir=$w_dir --nbest=100 --jobs=$dev_split --mertdir=$mert_dir --mertargs=$m_args --mertstatus=$mert_status --prevjobid=$prev_jobid --no-filter-phrase-table --input=$dev_src --refs=$dev_ref --scfgpath=$dev_scfg --decoder-prefix=$d_prefix --decoder=$d_exec --queue-flags=$q_flags --nodes-prop=$node_filter --config=$config --lmfile=$lm
wait

# Clean-up by removing temporary files and directories
rm $w_dir/gmon.out $w_dir/*.dat.gz
rmdir $w_dir/tmp*

## Now decode the test set ...
w_dir1=$curr_dir/tuning/testset-decode
mkdir -p $w_dir1/log

cp -fp $w_dir/moses.ini $w_dir1/kriya.ini
if [ ! $? -eq 0 ]; then exit 5; fi
wait

jobids=''
for ((k = 1; k <= $test_split; k++)); do
    scrpt_file="$curr_dir/scripts/decode_test.$k.sh"

    cmd="python $d_dir/decoder.py --config $w_dir1/kriya.ini --1b --inputfile $test_src/$k.out --outputfile $w_dir1/1best.$k.out --glue-file $glue --ttable-file $test_scfg/$k.out --lmodel-file $lm >& $w_dir1/log/1best.$k.log"
    echo $cmd > $scrpt_file

    jobid=`qsub -l mem=2gb,walltime=01:00:00 -e $curr_dir/log/ -o $curr_dir/log/ $scrpt_file` 
    jobids=$jobids:$jobid
done

scrpt_file=$curr_dir/scripts/eval.sh
echo "rm -f $w_dir1/top" > $scrpt_file
echo "for ((i=1; i<=$test_split; i++)); do cat $w_dir1/1best.\$i.out >> $w_dir1/top; done" >> $scrpt_file
echo "bleumain $w_dir1/top $test_ref > $w_dir1/result.bleu" >> $scrpt_file
echo "tail -n 1 $w_dir1/result.bleu >> $curr_dir/result.bleu" >> $scrpt_file
qsub -W depend=afterok:${jobids:1} -l mem=500mb,walltime=10:00 -N eval $scrpt_file

