#! /bin/tcsh

# Requires Giza++ load it as modules or set the GIZA_DIR, MOSES_DIR environment variables
GIZA_DIR=
MOSES_DIR=
SCRIPTS_DIR=

set KRIYA_PXTR = </path/to/working/copy/of>/Kriya-Grammar-Xtrctr
set work_dir = </path/to/toy/framework/copy/>toy-fr-en

# Train the word alignments and extract phrase alignments
perl $KRIYA_PXTR/training-scripts/phr_xtract.pl $work_dir/toy.fr-en.config

# Now run the grammar extraction scripts in Kriya to get Hiero grammar
perl $KRIYA_PXTR/training-scripts/scfg_xtract.pl $work_dir/toy.fr-en.config

