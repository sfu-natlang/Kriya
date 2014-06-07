#! /bin/bash

lang=$1
score_in=$2
score_out=$3
eval_in=$4
eval_out=$5

$JAVA_HOME/bin/java -Xmx2g -jar $METEOR_JAR - - -l $lang -t hter -stdio < $score_in > $score_out

cat $score_out | sed -e 's/^/EVAL ||| /' > $eval_in

$JAVA_HOME/bin/java -Xmx2g -jar $METEOR_JAR - - -l $lang -t hter -stdio < $eval_in > $eval_out

