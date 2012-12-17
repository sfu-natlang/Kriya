## Identify the source phrases in the given dev/test set and filter the rule file for the source phrases ##
## The filtering is done independently for each eactracted rule file ##

__author__="bsa33"
__date__ ="$Feb 18, 2010 1:27:38 PM$"

import codecs
import os
import sys
import math
from myTrie1 import SimpleSuffixTree

MAX_PHR_LEN = 10
TOT_TERMS = 5
new_trie = None
srcRulesSet = set([])

def loadTrie(ruleFile):
    '''Loads the Suffix Trie with rules from ruleFile'''

    global new_trie
    prev_src = ''

    print 'Loading phrases from data file : %s ...\n' % ruleFile
    with codecs.open(ruleFile, 'r', 'utf-8') as iF:
        for line in iF:
            line = line.strip()

            (src, _) = line.split(' ||| ', 1)
            if prev_src != src:
                prev_src = src
                if new_trie is None:
                    new_trie = SimpleSuffixTree(src, TOT_TERMS)
                else:
                    new_trie.addText(src)

#    new_trie.printFullTree()
    return None

def filterRules(dataFile):
    '''Filter the partial rule file for the specified dev/test set before computing p(f|e) and p(e|f)'''

    global new_trie
    global MAX_PHR_LEN
    global srcRulesSet

    with codecs.open(dataFile, 'r', 'utf-8') as rF:
        print 'Filtering rules for file : %s ...\n' % dataFile
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
                        if rule[0] in srcRulesSet: continue
                        srcRulesSet.add(rule[0])

def writeRules(ruleFile, tempOutFile):

    global srcRulesSet

    print 'Filtering rules from file : %s ...\n' % ruleFile
    with codecs.open(tempOutFile, 'w', 'utf-8') as tF:
        with codecs.open(ruleFile, 'r', 'utf-8') as rF:
            for line in rF:
                line = line.strip()
                (src, _) = line.split(' ||| ', 1)
                if src in srcRulesSet:
                    tF.write( "%s\n" % (line) )

def main():
    global TOT_TERMS
    devFile = sys.argv[1]        # source file of dev/test set
    file_indx = sys.argv[2]
    inDir = sys.argv[3]
    outDir = sys.argv[4]
    if len(sys.argv) == 6:
        TOT_TERMS = int(sys.argv[5])

    if not inDir.endswith('/'): inDir += '/'
    if not outDir.endswith('/'): outDir += '/'

    ruleFile = inDir + str(file_indx) + ".out"
    tempOutFile = outDir + str(file_indx) + ".out"
    print ruleFile
    print tempOutFile

    # load the development set phrases to a suffix trie
    loadTrie(ruleFile)

    # filter the consolidated rules that match phrases in trie into tempFile
    filterRules(devFile)

    # write the filtered rules (identified earlier by filterRules)
    writeRules(ruleFile, tempOutFile)

if __name__ == "__main__":
    main()

