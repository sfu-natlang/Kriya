#! /usr/bin/python

# Filters the rules for smaller subsets based on the suffix-tree implementation
# This is an improvement over older way as in cache_rules.py

__author__="bsa33"
__date__ ="$Dec 2, 2009 12:21:07 PM$"

import math
import os
import sys
import time

sys.path.append( os.path.dirname(sys.path[0]) )
from myTrie import SimpleSuffixTree

# Global variables
max_lprob = -0.000100005                             # max log prob (for prob = 1)
unk_lprob = -13.8155                                 # unknown log prob (also for zero probs)
MAX_SPAN_LEN = 10
TOT_TERMS = 5
phrDict = {}
ruleDict = {}
new_trie = None

def loadTrie(ruleFile):

    global new_trie
    global TOT_TERMS
    prev_src = ''

    rF = open(ruleFile, 'r')
    print "Loading rules from file %s into Trie" % (ruleFile)
    for line in rF:
        line = line.strip()
        itemsLst = []
        itemsLst = line.split(' ||| ')
        src = itemsLst[0]
        if prev_src != src:
            if new_trie is None:
                new_trie = SimpleSuffixTree(src, TOT_TERMS)
            else:
                new_trie.addText(src)
        prev_src = src

    rF.close()
#    new_trie.printFullTree()
    return None

def processPhrases(inFile):
    '''Reads the text file and processes the phrases'''

    global new_trie
    global phrDict
    global ruleDict
    phrDict = {}

    t_tot = 0.0
    p_tot = 0
    iF = open(inFile, 'r')
    print 'Processing phrases from file : %s' % inFile
    try:
        for line in iF:
            line = line.strip()

            wLst = line.split()
            for i in range( len(wLst) ):
                for j in range(i, i + MAX_SPAN_LEN):
                    if j >= len(wLst): break
                    src = ' '.join(wLst[i:j+1])
                    if phrDict.has_key(src): continue
                    else: phrDict[src] = 1
                    matchLst = []
                    t_beg = time.time()
                    matchLst = new_trie.matchPattern(src)
                    t_end = time.time()
                    t_tot += t_end - t_beg
                    p_tot += 1
                    for match in matchLst:
                        if not ruleDict.has_key(match[0]):
                            ruleDict[match[0]] = 1

    finally:
        iF.close()
        print "Unique phrases processed : %4d" % (p_tot)
        print "Total time taken         : %f" % (t_tot)
        print "Average time taken       : %f" % (t_tot/ p_tot)

    return None

def writeFilteredRules(ruleFile, filtFile):

    global ruleDict

    rF = open(ruleFile, 'r')
    oF = open(filtFile, 'w')
    print "Filtering rules from file %s into %s" % (ruleFile, filtFile)
    try:
        for line in rF:
            line = line.strip()
            (src, _) = line.split(' ||| ', 1)
            if ruleDict.has_key(src):
#                feat_str = getLogProb(prob_str, tgt)
#                oF.write("%s ||| %s ||| %s\n" % (src, tgt, feat_str))
#                oF.write("%s ||| %s ||| %s\n" % (src, tgt, prob_str))
                oF.write("%s\n" % (line))

    finally:
        rF.close()
        oF.close()

def getLogProb(prob_str, tgt_rule):
    '''Get the log probability from a string of probs, terminal counts and heuristic prob'''

    global featVec
    global max_lprob
    global unk_lprob
    featVec = []

    for prob in prob_str.split(' '):
        prob = float(prob)                               # Type cast to float
        if prob < 0.0: l_prob = prob
        elif prob == 0.0: l_prob = unk_lprob
        elif prob == 1.0: l_prob = max_lprob
        else:
            l_prob = math.log( prob )                    # get negative log-prob
        featVec.append( l_prob )

    # this part is now commented and the idea is to compute them in run time (at least temporarily)
    # now add the phrase and word penalties to the featVec
#    term_count = 0
#    for tgt_term in tgt_rule.split(' '):
#        if not tgt_term.startswith('X__'):
#            term_count += 1
#    featVec.append( math.exp(-1) )                       # add phrase penalty
#    featVec.append( -math.exp(-term_count) )              # add word penalty

    return ' '.join( map( lambda x: '%6f' % x, featVec ) )

def main():
    global TOT_TERMS
    file_indx = sys.argv[1]

    if file_indx == 'None':             # if file_indx is None; sent_file is directly specified
        ruleFile = sys.argv[2]
        sentFile = sys.argv[3]
        filtFile = sys.argv[4]
    else:                               # else sent_file is obtained from sent_dir and file_indx
        ruleFile = sys.argv[2]
        sent_dir = sys.argv[3]
        rule_dir = sys.argv[4]
        if not sent_dir.endswith('/'): sent_dir = sent_dir + '/'
        if not rule_dir.endswith('/'): rule_dir = rule_dir + '/'
        sentFile = sent_dir + file_indx + '.out'
        filtFile = rule_dir + file_indx + '.out'

    if len(sys.argv) == 6:
        TOT_TERMS = int(sys.argv[5])

    loadTrie(ruleFile)
    processPhrases(sentFile)

    # write the filtered rules of the dev/test set
    writeFilteredRules(ruleFile, filtFile)

if __name__ == "__main__":
    main()
