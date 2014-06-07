#! /bin/bash

run=$1
tune_dir=$2
scrpt_dir="$( cd "$( dirname "$0" )" && pwd )"

w_dir=$tune_dir/devset-run$run
mkdir $w_dir
perl $scrpt_dir/get_1best.pl $tune_dir/run$run.nbest.out $w_dir/dev.out.en

echo "Iteration #$run" >> $tune_dir/scores.dev.log
$scrpt_dir/collate_dev.sh $w_dir >> $tune_dir/scores.dev.log
echo "" >> $tune_dir/scores.dev.log

