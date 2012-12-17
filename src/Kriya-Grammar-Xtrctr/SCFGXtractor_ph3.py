## This program is the phase-III of the SCFG rules extraction ##
## It estimates the forward (P(s|t)) and reverse (P(t|s)) probabilities using relative frequency estimation ##

import codecs
import os
import sys
import heapq
import math
import time
from datetime import timedelta

min_lprob = -13.8155        # for log (natural)
max_lprob = -0.000100005
tgt_trie = None
rulesLst = []
tgtCntDict = {}

def loadTgtCnts(tgtFile):
    '''Loads target counts in a dict'''

    global tgtCntDict
    tot_rules = 0
    tot_time = 0.0
    tgtCntDict = {}

    print "Reading target counts and loading the counts in a dict ..."
    rF = codecs.open(tgtFile, 'r', 'utf-8')
    t_beg = time.time()
    while True:
        line = rF.readline()
        line = line.strip()
        if line == '': break

        tot_rules += 1
        (tgt, r_cnt) = line.split(' ||| ')
        tgtCntDict[tgt] = float( r_cnt )

        # track progress (for every ten million rules)
        if (tot_rules % 10000000) == 0:
	    t_taken = time.time() - t_beg
            tot_time += t_taken
            print "Processed %8d rules in time %s" % ( tot_rules, timedelta(seconds=t_taken) )
	    t_beg = time.time()

    rF.close()
    tot_time += time.time() - t_beg
    print "Total # of unique rules processed   : %d" % tot_rules
    print "Total time taken                    : %s" % timedelta(seconds=tot_time)

def writeFeats(ruleFile, outFile):

    global rulesLst
    tot_rules = 0
    tot_time = 0.0
    prev_src = ''
    src_cnt = 0.0
    rulesLst = []

    print "\n\nComputing source cnt and feature values before writing them to file ..."
    rF = codecs.open(ruleFile, 'r', 'utf-8')
    oF = codecs.open(outFile, 'w', 'utf-8')
    t_beg = time.time()
    while True:
        line = rF.readline()
        line = line.strip()
        if line == '': break

        tot_rules += 1
        (src_rule, tgt_rule, r_cnt, r_lprob, f_lprob) = line.split(' ||| ')
        rule_cnt = float(r_cnt)
        r_lex_prob = float(r_lprob)
        f_lex_prob = float(f_lprob)

        if prev_src != src_rule and tot_rules > 1:
            # New unique src_rule found; flush the rulesLst into file
            flush2File(src_cnt, oF)

            # Clear the src_cnt and rulesLst for next unique source rule
            src_cnt = 0.0
            del rulesLst[:]

        src_cnt += rule_cnt
        prev_src = src_rule
        rulesLst.append( (src_rule, tgt_rule, rule_cnt, r_lex_prob, f_lex_prob) )

        # tracking progress (for every million rules)
        if (tot_rules % 1000000) == 0:
	    t_taken = time.time() - t_beg
            tot_time += t_taken
            print "Processed %d million rules in %.4f sec" % (tot_rules / 1000000, t_taken)
	    t_beg = time.time()

    # flush the final rule after the last line is read
    flush2File(src_cnt, oF)

    rF.close()
    oF.close()
    tot_time += time.time() - t_beg
    print "Total # of unique rules processed   : %d" % tot_rules
    print "Total time taken                    : %f" % tot_time

def flush2File(src_cnt, oF):
    '''Flush the rules accumulated so far to the file'''

    global rulesLst
    global tgtCntDict

    for (src, tgt, r_cnt, r_lprob, f_lprob) in rulesLst:
        tgt_cnt = tgtCntDict[tgt]
        if ( abs(tgt_cnt - r_cnt) < 0.0001 ):
            tgt_cnt = r_cnt

        if r_cnt == 0.0:        # use min_lprob if r_cnt is zero
            r_p = min_lprob
            f_p = min_lprob
            #print "Log:: Rule: %s ||| %s :: rule_cnt is zero\n" % (src, tgt, r_cnt)
        else:
            if r_cnt == tgt_cnt: r_p = max_lprob
            else: r_p = math.log( r_cnt/ tgt_cnt )
            if r_cnt == src_cnt: f_p = max_lprob
            else: f_p = math.log( r_cnt/ src_cnt )

        if f_lprob == 0.0: f_lp = min_lprob
        elif f_lprob == 1.0: f_lp = max_lprob
        else: f_lp = math.log( f_lprob )

        if r_lprob == 0.0: r_lp = min_lprob
        elif r_lprob == 1.0: r_lp = max_lprob
        else: r_lp = math.log( r_lprob )

        if (f_p > 0.0 or r_p > 0.0 or f_lp > 0.0 or r_lp > 0.0):         # Check that the log-prob values are in fact negative
            print "** ", src, " ||| ", tgt, " :: ", src_cnt, tgt_cnt, r_cnt, " : ", f_lprob, r_lprob
            assert (f_p < 0.0), "ERROR: *1 - Log-prob value for forward prob is Positive : %g. Exiting!!\n" % (f_p)
            assert (r_p < 0.0), "ERROR: *2 - Log-prob value for reverse prob is Positive : %g. Exiting!!\n" % (r_p)
            assert (f_lp < 0.0), "ERROR: *3 - Log-prob value for forward lexical prob is Positive : %g. Exiting!!\n" % (f_lp)
            assert (r_lp < 0.0), "ERROR: *4 - Log-prob value for reverse lexical prob is Positive : %g. Exiting!!\n" % (r_lp)

        # Write the features to the file
        oF.write( "%s ||| %s ||| %g %g %g %g\n" % (src, tgt, r_p, r_lp, f_p, f_lp) )

def main():
    ruleFile = sys.argv[1]
    outFile = os.path.dirname(ruleFile) + "/" + sys.argv[2]
    tgtFile = os.path.dirname(ruleFile) + "/tgt_rules.all.out"

    loadTgtCnts(tgtFile)
    writeFeats(ruleFile, outFile)

if __name__ == '__main__':
    main()

