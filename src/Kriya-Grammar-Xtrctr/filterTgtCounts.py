# Online SCFG rules extraction routine: Getting target phrases & their counts
# Given a set of source phrases (that were filtered for a the given dev/test set) get the
# relevant target phrases and their total counts from the set of consolidated target rules

__author__="Baskaran Sankaran, Majid Razmara"
__date__ ="$Aug 15, 2010 3:27:38 PM$"

import sys

tgtSet = set([])

def loadTgtDict(filtRuleFile):

    global tgtSet
    tgt_rule_cnt = 0
    print 'Loading target rules from filtered rules file : %s ...\n' % filtRuleFile
    with open(filtRuleFile, 'r') as rF:
        for line in rF:
            line = line.strip()
            (_, tgt, _) = line.split(' ||| ', 2)
            if tgt not in tgtSet:
                tgtSet.add(tgt)
                tgt_rule_cnt += 1

    print "Unique # of tgt_rules found in set :%d" % ( tgt_rule_cnt )

def getTgtCnts(tgtFile, tempTgtFile):

    global tgtSet
    print 'Filtering target counts from : %s into : %s ...\n' % (tgtFile, tempTgtFile)
    with open(tempTgtFile, 'w') as oF:
        with open(tgtFile, 'r') as tF:
            for line in tF:
                line = line.strip()
                (tgt, _) = line.split(' ||| ', 1)
                if tgt in tgtSet:
                    oF.write('%s\n' % line)
                    tgtSet.remove(tgt)
                    if not tgtSet: break

def main():
    tgtFile = sys.argv[1]
    filtRuleFile = sys.argv[2]
    tempTgtFile = sys.argv[3]
    print filtRuleFile
    print tgtFile
    print tempTgtFile

    # Read the filtered rules file and load tgtDict
    loadTgtDict(filtRuleFile)

    # Get target rules counts and write them to tempTgtFile
    getTgtCnts(tgtFile, tempTgtFile)

if __name__ == "__main__":
    main()

