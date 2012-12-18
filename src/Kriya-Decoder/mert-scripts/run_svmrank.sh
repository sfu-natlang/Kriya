#! /bin/bash

optFile=$1
modelFile=$2

$SVMRANK_DIR/svm_rank_learn -c 0.01 $optFile $modelFile
