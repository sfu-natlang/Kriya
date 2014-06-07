#PBS -l mem=15gb
#PBS -l walltime=08:00:00
#PBS -m bea
#PBS -M bsa33@sfu.ca

/usr/bin/python $dd/decoder.py 11
