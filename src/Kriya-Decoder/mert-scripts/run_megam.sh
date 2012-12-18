#! /bin/bash

megamWgtsFile=$1
optFile=$2

$MEGAM_DIR/megam.opt -fvals -nobias -norm2 binary $optFile
#$MEGAM_DIR/megam.opt -fvals -init $megamWgtsFile -norm2 binary $optFile
