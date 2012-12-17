#! /bin/bash

terJarFile=$1
refTERFile=$2
hypTERFile=$3
ter_pre=$4

$JAVA_HOME/bin/java -Xmx3g -jar $terJarFile -r $refTERFile -h $hypTERFile -o sum -n $ter_pre

