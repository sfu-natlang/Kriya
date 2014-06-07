#! /bin/bash

optFile=$1
modelFile=$2

/home/baskaran/software/LTOOLS/SVM-RANK/svm_rank_learn -c 0.01 $optFile $modelFile
