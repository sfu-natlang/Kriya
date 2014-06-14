# Combined code of phases 2 and 3; replaces SCFGXtractor_ph2.py and SCFGXtractor_ph3.py
# Identify the source phrases in the given dev/test set and filter the rule file for the source phrases
# Get the total counts for the target phrases that co-occur with the filtered source phrases and write them in a temp file

__author__="bsa33"
__date__ ="$Feb 18, 2010 1:27:38 PM$"

import os
import sys
import heapq
import math
import time
from datetime import timedelta
#from myTrie1 import SimpleSuffixTree
#from extendedTrie import SimpleSuffixTree
from TrieMultNT import SimpleSuffixTree

MAX_PHR_LEN = 10
TOT_TERMS = 5
new_trie = None
srcRuleDict = {}
tgtCntDict = {}


def loadTrie(ruleFile):
    '''Loads the Suffix Trie with rules from ruleFile'''

    global new_trie
    prev_src = ''
    iF = open(ruleFile, 'r')

    print 'Loading phrases from data file : %s ...\n' % ruleFile
    for line in iF:
        line = line.strip()

        (src, _) = line.split(' ||| ', 1)
        if prev_src != src:
            prev_src = src
            if new_trie is None:
                new_trie = SimpleSuffixTree(src, TOT_TERMS)
            else:
                new_trie.addText(src)

    iF.close()
#    new_trie.printFullTree()
    return None


def filterRules(dataFile):
    '''Filter the partial rule file for the specified dev/test set before computing p(f|e) and p(e|f)'''

    global new_trie
    global MAX_PHR_LEN
    global srcRuleDict

    rF = open(dataFile, 'r')
    print 'Filtering rules for file : %s ...\n' % dataFile
    try:
        for line in rF:
            line = line.strip()
            words = []
            words = line.split()

            for i in range ( len(words) ):
                for j in range(i, i + MAX_PHR_LEN):
                    if j >= len(words): break
                    phr = ' '.join( words[i:j+1] )
                    rulesLst = []

                    # @type new_trie SimpleSuffixTree
                    rulesLst = new_trie.matchPattern(phr)
                    for rule in rulesLst:
                        if srcRuleDict.has_key(rule[0]): continue
                        else: srcRuleDict[rule[0]] = 1

    finally:
        rF.close()


def writeRules(ruleFile, tempOutFile):

    global srcRuleDict
    global tgtCntDict
    tgt_rule_cnt = 0
    tgtCntDict = {}

    rF = open(ruleFile, 'r')
    tF = open(tempOutFile, 'w')
    print 'Filtering rules from file : %s ...\n' % ruleFile
    try:
        for line in rF:
            line = line.strip()

            (src, tgt, _) = line.split(' ||| ', 2)
            if srcRuleDict.has_key(src):
                tF.write( "%s\n" % (line) )
                if not tgtCntDict.has_key(tgt):
                    tgt_rule_cnt += 1
                    tgtCntDict[tgt] = 0.0

    finally:
        rF.close()
        tF.close()
        print "Unique # of tgt_rules found in set :%d" % ( tgt_rule_cnt )


def updateTgtCnts(tgtFile, tempTgtFile):

    global tgtCntDict

    rF = open(tgtFile, 'r')
    print 'Updating target counts from file : %s ...\n' % tgtFile
    try:
        for line in rF:
            line = line.strip()

            (tgt, r_cnt) = line.split(' ||| ')
            if tgtCntDict.has_key(tgt):
                tgtCntDict[tgt] += float( r_cnt )

    finally:
        rF.close()

    print 'Writing target counts to file : %s ...\n' % tempTgtFile
    gF = open(tempTgtFile, 'w')
    tgtRules = []
    tgtRules = tgtCntDict.keys()
    tgtRules.sort()
    for tgt in tgtRules:
        gF.write( "%s ||| %g\n" % (tgt, tgtCntDict[tgt]) )
    gF.close()


def main():
    global TOT_TERMS
    devFile = sys.argv[1]        # source file of dev/test set
    file_indx = sys.argv[2]
    inDir = sys.argv[3]
    outDir = sys.argv[4]
    if len(sys.argv) == 6:
        TOT_TERMS = int(sys.argv[5])
    if len(sys.argv) == 7:
        MAX_PHR_LEN = int(sys.argv[6])

    if not inDir.endswith('/'): inDir += '/'
    if not outDir.endswith('/'): outDir += '/'

    ruleFile = inDir + str(file_indx) + ".out"
    tgtFile = inDir + "tgt." + str(file_indx) + ".out"
    tempOutFile = outDir + str(file_indx) + ".out"
    tempTgtFile = outDir + "tgt." + str(file_indx) + ".out"
    print ruleFile
    print tgtFile
    print tempOutFile
    print tempTgtFile

    # load the development set phrases to a suffix trie
    loadTrie(ruleFile)

    # filter the consolidated rules that match phrases in trie into tempFile
    filterRules(devFile)

    # write the filtered rules (identified earlier by filterRules)
    writeRules(ruleFile, tempOutFile)

    # update tgtCntDict with counts and write them to tempTgtFile
    updateTgtCnts(tgtFile, tempTgtFile)


if __name__ == "__main__":
    main()

