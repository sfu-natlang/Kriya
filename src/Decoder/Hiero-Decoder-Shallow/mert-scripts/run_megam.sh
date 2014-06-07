#! /bin/bash

optFile=$1

$MEGAM_DIR/megam.opt -fvals -nobias -norm2 binary $optFile
#$MEGAM_DIR/megam.opt -fvals -init $megamWgtsFile -norm2 binary $optFile
