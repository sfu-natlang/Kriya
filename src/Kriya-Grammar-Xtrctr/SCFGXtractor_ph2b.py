## Merge the filtered rule files and consolidates the rule counts from different files ##
## Also computes forward & reverse lexical probs ##

import codecs
import os
import os.path
import sys
import heapq

# Global variables
null_term = ''
lexProbDict = {}

def loadLexProbDistrib(lexDFile):
    '''Loads the lexical probability distribution in dictionary lexProbDict'''

    print 'Loading lexical probability distribution (both forward and reverse) ...'
    global lexProbDict
    # The src & tgt lexemes and forward & reverse lexical probabilities are stored in dictionary as:
    # key: (src_word, tgt_word); value: (fwrd_lex_prob, rvrs_lex_prob)
    lexF = codecs.open(lexDFile, 'r', 'utf-8')
    for line in lexF:
        line = line.strip()
        src, tgt, f_prob, r_prob = line.split(' ||| ')
        lexProbDict[(src, tgt)] = (float(f_prob), float(r_prob))
    lexF.close()

def loadFwrdLexProbDistrib(lexDFile):
    '''Loads the forward lexical probability distribution in dictionary lexProbDict'''

    print 'Loading forward lexical probability distribution ...'
    global lexProbDict
    # The src & tgt lexemes and forward & reverse lexical probabilities are stored in dictionary as:
    # key: (src_word, tgt_word); value: (fwrd_lex_prob, rvrs_lex_prob)
    # Only forward lex prob is stored in lexProbDict now and reverse lex prob is updated later by loadRvrsLexProbDistrib()
    lexF = codecs.open(lexDFile, 'r', 'utf-8')
    line_cnt = 0
    for line in lexF:
        line = line.strip()
        try:
            tgt, src, f_prob = line.split()
        except ValueError:
            line_cnt += 1
            sys.stderr.write( "Encountered error in line # %d :: %s\n" % (line_cnt, line) )
            continue
        lexProbDict[(src, tgt)] = float(f_prob)
        line_cnt += 1
    lexF.close()

def loadRvrsLexProbDistrib(lexDFile):
    '''Updates lexProbDict with the reverse lexical probabilities'''

    print 'Loading reverse lexical probability distribution ...'
    global lexProbDict
    # Updates the lexProbDict with correct reverse lex prob
    lexF = codecs.open(lexDFile, 'r', 'utf-8')
    line_cnt = 0
    for line in lexF:
        line = line.strip()
        try:
            src, tgt, r_prob = line.split()
        except ValueError:
            line_cnt += 1
            sys.stderr.write( "Encountered error in line # %d :: %s\n" % (line_cnt, line) )
            continue
        try:
            f_prob = lexProbDict[(src, tgt)]
            lexProbDict[(src, tgt)] = ( f_prob, float(r_prob) )
            line_cnt += 1
        except KeyError:
            print "Key (%s, %s) not found in the lexProbDict." % (src, tgt)
            print "Check if the forward lexical probability has been loaded first. Exiting!!"
            sys.exit(1)
    lexF.close()

def read_n_merge(fileLst, outFile1, outFile2):
    '''Read entries from the individual files and merge counts on the fly'''

    total_rules = 0
    candLst = []
    ruleDict = {}
    fileTrackLst = [ 1 for file in fileLst ]
    stop_iteration = False

    print "Reading rules and merging their counts & alignments ..."
    fHLst = [ codecs.open(file, 'r', 'utf-8') for file in fileLst ]
    oF1 = codecs.open(outFile1, 'w', 'utf-8')
    oF2 = codecs.open(outFile2, 'w', 'utf-8')
    while True:
        stop_iteration = True
        for f_track in fileTrackLst:
            if f_track != 9:
                stop_iteration = False
                break

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
                continue

            (src, tgt, r_count, r_align, f_align) = line.split(' ||| ')
            rule = src + ' ||| ' + tgt
            r_count = float( r_count )

            if ruleDict.has_key(rule):
                oldTup = ruleDict[rule]
                valTup = (oldTup[0] + r_count, unifyAlignment(oldTup[1], f_align), \
                            unifyAlignment(oldTup[2], r_align), oldTup[3] + [indx])
                ruleDict[rule] = valTup
            else:
                valTup = (r_count, f_align, r_align, [indx])
                ruleDict[rule] = valTup
                heapq.heappush(candLst, rule)

        if len(candLst) == 0: continue

        popped_rule = heapq.heappop(candLst)
        (r_count, f_align, r_align, indxLst) = ruleDict.pop(popped_rule)
        lex_prob_inv = aggregateLexProb(popped_rule, f_align, 1)       # 1 (True) denotes inverse alignments
        lex_prob_dir = aggregateLexProb(popped_rule, r_align, 0)       # 0 (False) denotes direct alignments
        oF1.write( "%s ||| %g ||| %s ||| %s\n" % (popped_rule, r_count, f_align, r_align) )
        oF2.write( "%s ||| %g ||| %g ||| %g\n" % (popped_rule, r_count, lex_prob_inv, lex_prob_dir) )
        total_rules += 1
        for indx1 in indxLst:
            fileTrackLst[indx1] = 1

    for fH in fHLst:
        fH.close()
    oF1.close()
    oF2.close()
    print( "Total # of rules    : %d" % (total_rules) )

def unifyAlignment(align_str, curr_align):
    '''Unifies the current alignment with existing alignments'''

    tempAlignDict = {}
    for align in curr_align.split(' ## '):
        #nalign = normalizeAlignment(align)
        tempAlignDict[align] = 1

    for align in align_str.split(' ## '):
        #nalign = normalizeAlignment(align)
        if not tempAlignDict.has_key(align):
            tempAlignDict[align] = 1

    return ' ## '.join(tempAlignDict.keys())

def normalizeAlignment(align):
    nalign = ''
    for i in range(0, len(align), 2):
        if align[i] != 'Z' and align[i+1] != 'Z':
            nalign += align[i:i+2]
    return nalign

def aggregateLexProb(rule, align_str, align_direction):
    '''Aggregates the lexical probabilities of multiple alignments for a given rule and calculate its average/ worst lexical prob'''

    worst_lex_prob = float('inf')
    #align_count = 0
    #lex_prob_sum = 0.0
    ruleT = rule.split(' ||| ')                   # calcLexProb() expects ruleT
    for align_indx in align_str.split(' ## '):
        lex_prob = calcLexProb(ruleT, align_indx, align_direction)
        if lex_prob < worst_lex_prob:
            worst_lex_prob = lex_prob
        #lex_prob_sum += calcLexProb(ruleT, align_indx, align_direction)
        #align_count += 1

    #return lex_prob_sum / float(align_count)
    return worst_lex_prob

def calcLexProb(ruleT, align_indx, align_direction):
    '''Calculates the lexical probability for the given rule and its alignment'''

    global null_term
    global lexProbDict
    lex_prob = 1.0
    srcWrds = []
    tgtWrds = []
    countLst = []
    probLst = []
    alignPosDict = {}

    srcWrds = ruleT[0].split()
    tgtWrds = ruleT[1].split()

    #print "Rule  :", ruleT
    #print "Align :", align_indx
    #print "Direc :", align_direction

    # Initialize the count and prob lists based on the alignment direction
    plen = len(srcWrds) if align_direction else len(tgtWrds)
    for i in range(0, plen):
        countLst.append(0)
        probLst.append(0.0)

    for i in range(0, len(align_indx), 2):
        # Get source and target words from the alignment
        if align_indx[i] == 'Z':
            src_wrd = null_term
        else:
            indx = int( align_indx[i] )
            src_wrd = srcWrds[indx]

        if align_indx[i+1] == 'Z':
            tgt_wrd = null_term
        else:
            indx = int( align_indx[i+1] )
            tgt_wrd = tgtWrds[indx]

        if lexProbDict.has_key( (src_wrd, tgt_wrd) ): lexT = (src_wrd, tgt_wrd)
        elif lexProbDict.has_key( (null_term, tgt_wrd) ): lexT = (null_term, tgt_wrd)
        elif lexProbDict.has_key( (src_wrd, null_term) ): lexT = (src_wrd, null_term)
        # Count the alignments depending on the alignment direction and
        # incrementally compute the lexical probability
        if align_direction:
            pos2count = int( align_indx[i] )
            prob = lexProbDict[lexT][1]
        else:
            pos2count = int( align_indx[i + 1] )
            prob = lexProbDict[lexT][0]

        if alignPosDict.has_key(pos2count):
            countLst[pos2count] += 1
            probLst[pos2count] += prob
        else:
            alignPosDict[pos2count] = 1
            countLst[pos2count] = 1
            probLst[pos2count] = prob

    #print "Probs : ", probLst
    #print "Counts: ", countLst
    for indx, sum_prob in enumerate( probLst ):
        if sum_prob > 0.0:
            align_count = countLst[indx]
            lex_prob *= sum_prob / float( align_count )
    #        print "    ", lex_prob, " <== ", sum_prob, " ** ", align_count
    #print

    return lex_prob

def main():

    global null_term

    tot_args = len(sys.argv)
    inDir = sys.argv[1]
    outDir = sys.argv[2]
    last_arg = sys.argv[tot_args-1]

    if tot_args > 4 and os.path.isfile(sys.argv[4]):
        single_lex_file = False
        fwrdLexDist = sys.argv[3]
        rvrsLexDist = sys.argv[4]
        null_term = 'NULL'
    else:
        lexDFile = sys.argv[3]
        single_lex_file = True
        null_term = '-NULL-'

    if single_lex_file:
        loadLexProbDistrib(lexDFile)
    else:
        loadFwrdLexProbDistrib(fwrdLexDist)
        loadRvrsLexProbDistrib(rvrsLexDist)

    if not inDir.endswith('/'): inDir += '/'
    if not outDir.endswith('/'): outDir += '/'
    fileLst = []
    for file in os.listdir(inDir):
        if file.startswith("tgt"): continue
        file = inDir + file
        if os.path.isfile(file):
            fileLst.append(file)

    outFile1 = outDir + 'rules_cnt_align.out'
    outFile2 = outDir + 'rules_cnt_lprob.out'

    read_n_merge(fileLst, outFile1, outFile2)

if __name__ == '__main__':
    main()

