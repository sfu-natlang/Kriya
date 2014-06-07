## This program is the phase-III of the SCFG rules extraction ##
## It estimates the forward (P(s|t)) and reverse (P(t|s)) probabilities using relative frequency estimation ##

import os
import sys
import heapq
import math
import time
from datetime import timedelta

#min_lprob = -6.0           # for log10
#max_lprob = -0.000434
min_lprob = -13.8155        # for log (natural)
max_lprob = -0.000100005
tgt_trie = None
candLst = []
rulesLst = []
ruleDict = {}
tgtCntDict = {}

def splitTgtCounts(ruleFile, rules_per_file, tmpDir):
    '''Splits the rule file and creates temporary files with fixed number of rules in temporary directory'''

    global tgtCntDict
    tot_time = 0.0
    tot_rules = 0
    file_indx = 1
    tgtCntDict = {}

    print "Reading rule file and splitting it ..."
    rF = open(ruleFile, 'r')
    t_beg = time.time()
    while True:
        line = rF.readline()
        line = line.strip()
        if line == '': break

        (src, tgt, r_cnt, r_lprob, f_lprob) = line.split(' ||| ')
        if tgtCntDict.has_key(tgt): tgtCntDict[tgt] += float(r_cnt)
        else: tgtCntDict[tgt] = float(r_cnt)
        tot_rules += 1

        if (tot_rules % rules_per_file) == 0:
            # create temporary output file and flush target rules
            tmpOutFile = tmpDir + "/tgt_rules." + str(file_indx) + ".out"
            flush2TempFile(tmpOutFile)
            t_taken = time.time() - t_beg
            tot_time += t_taken
            print "Time taken for creating set %d : %s" % ( file_indx, timedelta(seconds=t_taken) )
            file_indx += 1
            t_beg = time.time()

    rF.close()

    # flush the last set of target rules read
    tmpOutFile = tmpDir + "/tgt_rules." + str(file_indx) + ".out"
    flush2TempFile(tmpOutFile)
    t_taken = time.time() - t_beg
    tot_time += t_taken
    print "Time taken for creating set %d : %s" % ( file_indx, timedelta(seconds=t_taken) )
    print "Total time taken               : %s" % ( timedelta(seconds=tot_time) )

def flush2TempFile(tmpOutFile):

    global tgtCntDict
    tOF = open(tmpOutFile, 'w')

    # write the sorted target counts to the file
    rulesLst = []
    rulesLst = tgtCntDict.keys()
    rulesLst.sort()
    for tgt_rule in rulesLst:
        tOF.write( "%s ||| %g\n" % (tgt_rule, tgtCntDict[tgt_rule]) )
    tOF.close()
    rulesLst = []
    tgtCntDict = {}

def readNMerge(fileLst, outFile):
    '''Read entries from the individual files and merge counts on the fly'''

    global candLst
    global ruleDict
    total_rules = 0
    fileTrackLst = [ 1 for file in fileLst ]
    stop_iteration = False

    print "Reading rules and merging their counts ..."
    fHLst = [ open(file, 'r') for file in fileLst ]
    oF = open(outFile, 'w')
    while True:
        if stop_iteration:
            break

        for indx, f_track in enumerate( fileTrackLst ):
            if f_track == 0 or f_track == 9:
                continue

            fileTrackLst[indx] = 0
            line = fHLst[indx].readline()
            line = line.strip()
            if line == '':
                fileTrackLst[indx] = 9          # Set 9 if 'EOF' is reached
                stop_iteration = True
                continue

            stop_iteration = False
            (tgt_rule, r_count) = line.split(' ||| ')
            r_count = float( r_count )

            if ruleDict.has_key(tgt_rule):
                mergeValues(tgt_rule, r_count, [indx], 1)
            else:
                ruleDict[tgt_rule] = 1
                mergeValues(tgt_rule, r_count, [indx], 0)

        heapq.heapify(candLst)
        if len(candLst) == 0: continue
        (tgt_rule, r_count, indxLst) = heapq.heappop(candLst)
        oF.write( "%s ||| %g\n" % (tgt_rule, r_count) )
        total_rules += 1
        ruleDict.pop(tgt_rule)
        for indx1 in indxLst:
            fileTrackLst[indx1] = 1
            stop_iteration = False

    for fH in fHLst:
        fH.close()
    oF.close()
    print( "Total # of rules : %d" % (total_rules) )

def mergeValues(rule, r_count, indxLst, rule_exists):
    '''Adds/ merges the values in the heap'''

    global candLst
    if not rule_exists:
        candLst.append( (rule, r_count, indxLst) )
    else:
        for indx, cand in enumerate( candLst ):
            if cand[0] == rule:
                r_count_new = cand[1] + r_count
                indxLst += cand[2]
                candLst[indx] = (rule, r_count_new, indxLst)
                break

def loadTgtCnts2Dict(consTgtFile):
    '''Loads target counts in a dict'''

    global tgtCntDict
    tot_rules = 0
    tot_time = 0.0
    tgtCntDict = {}

    print "Reading target counts and loading the counts in a dict ..."
    rF = open(consTgtFile, 'r')
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
    rF = open(ruleFile, 'r')
    oF = open(outFile, 'w')
    t_beg = time.time()
    while True:
        line = rF.readline()
        line = line.strip()
        if line == '': break

        tot_rules += 1
        (src_rule, tgt_rule, r_cnt, r_lprob, f_lprob) = line.split(' ||| ')
        rule_cnt = float(r_cnt)
        f_lex_prob = float(f_lprob)
        r_lex_prob = float(r_lprob)

        if prev_src != src_rule and tot_rules > 1:
            # New unique src_rule found; flush the rulesLst into file
            flush2File(src_cnt, oF)

            # Clear the src_cnt and rulesLst for next unique source rule
            src_cnt = 0.0
            rulesLst = []

        src_cnt += rule_cnt
        prev_src = src_rule
        rulesLst.append( (src_rule, tgt_rule, rule_cnt, f_lex_prob, r_lex_prob) )

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
        if ( tgt_cnt < r_cnt ):
            tgt_cnt = r_cnt
            #print "Log:: Rule: %s ||| %s :: tgt_cnt (%e) is smaller than r_cnt (%e)\n" % (src, tgt, tgt_cnt, r_cnt)

        # Compute the 4 features
        if r_cnt == 0.0:        # use min_lprob if r_cnt is zero
            f_p = min_lprob
            r_p = min_lprob
        else:
            if r_cnt == tgt_cnt: f_p = max_lprob    # use max_lprob if prob = 1 (for fwrd prob)
            else: f_p = math.log( r_cnt/ tgt_cnt )
            if r_cnt == src_cnt: r_p = max_lprob    # use max_lprob if prob = 1 (for rvrs prob)
            else: r_p = math.log( r_cnt/ src_cnt )

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
        oF.write( "%s ||| %s ||| %g %g %g %g\n" % (src, tgt, r_p, f_p, r_lp, f_lp) )

def main():
    ruleFile = sys.argv[1]
    outFile = sys.argv[2]
#    rules_per_file = int(sys.argv[3])

    # create a temporary directory for storing temporary files
#    tmpDir = os.path.dirname(ruleFile) + "/target_rules_split/"
#    if not os.path.exists(tmpDir): os.mkdir(tmpDir)

#    # split the target rules in different files each having 'rules_per_file' rules
#    splitTgtCounts(ruleFile, rules_per_file, tmpDir)

#    fileLst = []
#    for file in os.listdir(tmpDir):
#        file = tmpDir + file
#        if os.path.isfile(file):
#            fileLst.append(file)

    # merge the target counts from the temporary files in the fileLst
    consTgtFile = os.path.dirname(ruleFile) + "/tgt_rules.all.out"
#    readNMerge(fileLst, consTgtFile)

    # load target counts into dict
    loadTgtCnts2Dict(consTgtFile)

    # compute and write the features in the outFile
    outFile = os.path.dirname(ruleFile) + "/" + outFile
    writeFeats(ruleFile, outFile)

if __name__ == '__main__':
    main()
