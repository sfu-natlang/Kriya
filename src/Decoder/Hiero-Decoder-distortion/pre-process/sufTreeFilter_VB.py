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
MAX_SPAN_LEN = 10
TOT_TERMS = 5
rulesSet = set([])
new_trie = None

def loadTrie(ruleFile, sentFile, filtFile):

    global new_trie
    global TOT_TERMS
    prev_src = ''
    line_cnt = 0
    line_from = 0
    interim_process = False

    print "Loading rules from file %s into Trie" % (ruleFile)
    with open(ruleFile, 'r') as rF:
        for line in rF:
            line = line.strip()
            line_cnt += 1
            if (line_cnt % 1000000) == 0:
                interim_process = True

            (src, _) = line.split(' |||| ', 1)
            if prev_src != src:
                if interim_process:
                    processPhrases(sentFile)
                    writeFilteredRules(line_from, line_cnt, ruleFile, filtFile)
                    interim_process = False
                    line_from = line_cnt
                    new_trie = None

                if new_trie is None:
                    new_trie = SimpleSuffixTree(src, TOT_TERMS)
                else:
                    new_trie.addText(src)
            prev_src = src

    if new_trie:
        processPhrases(sentFile)
        writeFilteredRules(line_from, line_cnt, ruleFile, filtFile)

#    new_trie.printFullTree()
    return None

def processPhrases(inFile):
    '''Reads the text file and processes the phrases'''

    global new_trie
    global rulesSet
    rulesSet = set([])
    phrasesSet = set([])

    print 'Processing phrases from file : %s' % inFile
    with open(inFile, 'r') as iF:
        for line in iF:
            line = line.strip()
            wLst = line.split()
            for i in range( len(wLst) ):
                for j in range(i, i + MAX_SPAN_LEN):
                    if j >= len(wLst): break
                    src = ' '.join(wLst[i:j+1])
                    if src in phrasesSet: continue
                    phrasesSet.add(src)

    p_tot = 0
    t_beg = time.time()
    for src in phrasesSet:
        matchLst = []
        matchLst = new_trie.matchPattern(src)
        p_tot += 1
        for match in matchLst:
            if match[0] in rulesSet: continue
            rulesSet.add(match[0])
    t_tot = time.time() - t_beg
    print "Unique phrases processed : %4d" % (p_tot)
    print "Total time taken         : %f" % (t_tot)
    print "Average time taken       : %f" % (t_tot/ p_tot)

    return None

def writeFilteredRules(line_from, line_to, ruleFile, filtFile):

    global rulesSet
    l_cnt = 0
    skip_rules = True
    rulesDict = {}
    print "Lines from/ to :", line_from, "/ ", line_to

    print "Filtering rules from file %s into %s" % (ruleFile, filtFile)
    with open(ruleFile, 'r') as rF:
        for line in rF:
            if l_cnt == line_from: skip_rules = False
            if l_cnt == line_to: break

            l_cnt += 1
            if skip_rules: continue

            line = line.strip()
            #(src_rule, _) = line.split(' ||| ', 1)
            (src_rule, rest) = line.split(' |||| ')
            if src_rule in rulesSet:
                (tgt_rule, r_prior, r_count) = rest.split(' ||| ')
                rule = src_rule + ' ||| ' + tgt_rule
                rulesDict[rule] = r_prior

    with open(filtFile, 'a') as oF:
        for rule in sorted( rulesDict.keys() ):
            oF.write("%s ||| %s\n" % (rule, rulesDict[rule]))
    rulesDict.clear()

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

    loadTrie(ruleFile, sentFile, filtFile)
    #processPhrases(sentFile)
    ## write the filtered rules of the dev/test set
    #writeFilteredRules(ruleFile, filtFile)

if __name__ == "__main__":
    main()
