#! /bin/bash

megamWgtsFile=$1
optFile=$2

/cs/natlang-sw/Linux-x86_64/NL/LTOOLS/MEGAM/0.92/megam.opt -fvals -nobias -norm2 binary $optFile
#/cs/natlang-sw/Linux-x86_64/NL/LTOOLS/MEGAM/0.92/megam.opt -fvals -init $megamWgtsFile -norm2 binary $optFile
