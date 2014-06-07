#! /bin/bash

if [[ -z "${1}" ]] ; then
    echo "Provide the working directory relative to current path"
    exit
fi

eval_scrpt=/home/baskaran/software/scripts/mteval-v11b.pl

ref_dir=/home/baskaran/ar-en/training/mta-data              # References directory
#ref_dir=/home/baskaran/ar-en/training/mta-pre-processed    # References directory
w_dir=$1                                                    # Working directory

test_src=$ref_dir/sgm-files/dev.ar-en.src.sgm
test_ref=$ref_dir/sgm-files/dev.ar-en.ref.sgm
test_ref_pl=$ref_dir/dev.mtev06.tok.en

#perl /home/baskaran/software/MT/MOSES/SVN_20101028/scripts/generic/multi-bleu.perl $test_ref_pl < $w_dir/dev.out.en

perl /home/baskaran/software/MT/MOSES/SVN_20101028/scripts/tokenizer/detokenizer.perl -l en < $w_dir/dev.out.en > $w_dir/dev.out.detok.en

#perl /home/baskaran/software/MT/MOSES/SVN_20101028/scripts/ems/support/wrap-xml.perl $test_ref en SFU < $w_dir/dev.out.detok.en > $w_dir/dev.out.ar-en.tstsgm
perl /home/baskaran/software/scripts/wrap-xml-src.perl en $test_src SFU < $w_dir/dev.out.detok.en > $w_dir/dev.out.ar-en.tst.sgm

perl $eval_scrpt -b -r $test_ref -s $test_src -t $w_dir/dev.out.ar-en.tst.sgm > $w_dir/dev.out.lc.bleu

java -Xmx3g -jar $TER_DIR/tercom-0.8.0.jar -r $test_ref -h $w_dir/dev.out.ar-en.tst.sgm -o sum -n $w_dir/dev.out.ter >& $w_dir/dev.out.ter.log

~/software/LANG/PYTHON/3.2.3/bin/python3 ~/software/MT/Kriya/Hiero-Decoder-Shallow/mert-scripts/RIBES.py -r $ref_dir/dev.mtev06.tok.en0 -r $ref_dir/dev.mtev06.tok.en1 -r $ref_dir/dev.mtev06.tok.en2 -r $ref_dir/dev.mtev06.tok.en3 $w_dir/dev.out.en > $w_dir/dev.out.ribes.log

java -Xmx2g -jar $METEOR_JAR $w_dir/dev.out.ar-en.tst.sgm $test_ref -l en -norm -sgml -t hter -f $w_dir/meteor > $w_dir/dev.out.meteor.log

echo "BLEU Score    : `grep 'BLEU score' $w_dir/dev.out.lc.bleu | grep -oE '[0-9.]+'`"
echo "METEOR Score  : `grep 'Final score' $w_dir/dev.out.meteor.log | grep -oE '[0-9.]+'`"
echo "RIBES score   : `head -n 1 $w_dir/dev.out.ribes.log | grep -oE '[0-9.]+' | head -1`"
echo "TER Score     : `grep 'Total TER' $w_dir/dev.out.ter.log | grep -oE '[0-9.]+' | head -1`"

