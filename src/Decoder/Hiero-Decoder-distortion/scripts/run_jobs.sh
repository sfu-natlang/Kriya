#! /bin/bash

#pdir=/cs/grad2/bsa33/Hiero-Decoder
#qsub -l nodes=r1s26c10 -v dd=$pdir -e log/ -o log/ decode.sh

pdir=/cs/grad2/bsa33/svnroot/bsa33/src/Hiero-Decoder/pre-process
#qsub -v dd=$pdir -e log/ -o log/ rjob_1.sh

j=1
for i in job_*.sh; do
    echo $j : $i
    qsub -l arch=x86_64 -l mem=2gb -l walltime=00:20:00 -m a -M bsa33@sfu.ca -v dd=$pdir -e log/ -o log/ $i
    j=`expr $j + 1`
done
