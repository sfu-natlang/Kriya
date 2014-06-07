#! /bin/bash

d_dir=/cs/grad2/bsa33/svnroot/bsa33/src/Hiero-Decoder
work_dir=/cs/natlang-expts/bsa33/wmt10/en-es/training/mert-lm-compatible/kriya-zmert
dev_src_dir=/cs/natlang-expts/bsa33/wmt10/en-es/training/devset-sent

cfg=$work_dir/kriya.ini
glue=$work_dir/kriya.glue
scfg_dir=/cs/natlang-expts/bsa33/wmt10/en-es/training/devset-rules
lang_model=/cs/natlang-data/wmt10/lm/all_w_un.es.lm

nb_size=100

tot_jobs=26
sent_per_job=200

/usr/bin/env perl $d_dir/mert-scripts/decode_with_kriya.pl -config=$cfg -rule_dir=$scfg_dir -lmfile=$lang_model -n-best-size=$nb_size -input-dir=$dev_src_dir -output-dir=$work_dir -jobs=$tot_jobs -sent-per-job=$sent_per_job &

wait($!)
