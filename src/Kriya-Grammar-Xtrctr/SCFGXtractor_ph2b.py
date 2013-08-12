# Merge the filtered rule files and consolidate their counts
# Also compute forward & reverse lexical probs

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
    lexF = open(lexDFile, 'r')
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
    lexF = open(lexDFile, 'r')
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
    lexF = open(lexDFile, 'r')
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

def mergeTgtCounts(fileLst, tgtFile):
    '''Read target counts from individual files and merge counts on the fly'''

    total_rules = 0
    candLst = []
    tgtDict = {}
    fileTrackLst = [ 1 for file in fileLst ]
    stop_iteration = False

    print "Reading target rules and merging their counts ..."
    fHLst = [ open(file, 'r') for file in fileLst ]
    oF = open(tgtFile, 'w')
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

            (tgt, r_cnt) = line.split(' ||| ')
            r_count = float( r_cnt )

            if tgtDict.has_key(tgt):
                for indx1, cand in enumerate( candLst ):
                    if cand[0] == tgt:
                        r_count_new = cand[1] + r_count
                        indxLst = cand[2] + [indx]
                        candLst[indx1] = (tgt, r_count_new, indxLst)
                        break
            else:
                tgtDict[tgt] = 1
                candLst.append( (tgt, r_count, [indx]) )

        if len(candLst) == 0: continue

        heapq.heapify(candLst)
        (tgt, r_count, indxLst) = heapq.heappop(candLst)
        oF.write( "%s ||| %g\n" % (tgt, r_count) )
        total_rules += 1
        tgtDict.pop(tgt)
        for indx1 in indxLst:
            fileTrackLst[indx1] = 1

    for fH in fHLst:
        fH.close()
    oF.close()
    print( "Total # of rules : %d" % (total_rules) )

def read_n_merge(fileLst, outFile1, outFile2):
    '''Read entries from the individual files and merge counts on the fly'''

    total_rules = 0
    candLst = []
    ruleDict = {}
    fileTrackLst = [ 1 for file in fileLst ]
    stop_iteration = False

    print "Reading rules and merging their counts & alignments ..."
    fHLst = [ open(file, 'r') for file in fileLst ]
    oF1 = open(outFile1, 'w')
    oF2 = open(outFile2, 'w')
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
                valTup = (oldTup[0] + r_count, unifyAlignment(oldTup[1], r_align), oldTup[2] + [indx])
                ruleDict[rule] = valTup
            else:
                valTup = (r_count, r_align, [indx])
                ruleDict[rule] = valTup
                heapq.heappush(candLst, rule)

        if len(candLst) == 0: continue

        popped_rule = heapq.heappop(candLst)
        (r_count, r_align, indxLst) = ruleDict.pop(popped_rule)
        src, tgt = popped_rule.split(' ||| ')                   # calcLexProb() expects ruleT
        srcW = src.split(' ')
        tgtW = tgt.split(' ')
        f_lex_prob = aggregateLexProb(srcW, tgtW, r_align, 1)       # 1 (True) denotes forward alignments
        r_lex_prob = aggregateLexProb(srcW, tgtW, r_align, 0)       # 0 (False) denotes reverse alignments
        oF1.write( "%s ||| %g ||| %s ||| %s\n" % (popped_rule, r_count, r_align, f_align) )
        oF2.write( "%s ||| %g ||| %g ||| %g\n" % (popped_rule, r_count, r_lex_prob, f_lex_prob) )
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

    alignment_found = False
    for prev_align in align_str.split(' ## '):
        if prev_align == curr_align:
            alignment_found = True
            break

    if alignment_found:
        return align_str
    else:
        return align_str + ' ## ' + curr_align

def getAlignTupLst(alignments):
    aTupLst = []

    for ind_alignment in alignments.split(' ## '):
        aTup = []
        for i in xrange(0, len(ind_alignment), 2):
            s_pos, t_pos = ind_alignment[i], ind_alignment[i+1]
            s_pos = -1 if s_pos == 'Z' else int(s_pos)
            t_pos = -1 if t_pos == 'Z' else int(t_pos)
            aTup.append( (s_pos, t_pos) )
        aTupLst.append( tuple(aTup) )

    return aTupLst

def aggregateLexProb(srcW, tgtW, align_str, align_direction):
    '''Aggregates the lexical probabilities of multiple alignments for a given rule and calculate its average/ worst lexical prob'''

    worst_lex_prob = float('inf')
    aTupLst = getAlignTupLst(align_str)
    for aTups in aTupLst:
        lex_prob = calcLexProb(srcW, tgtW, aTups, align_direction)
        if lex_prob < worst_lex_prob:
            worst_lex_prob = lex_prob

    return worst_lex_prob

def getUnalignedIndices(p_len, phrWrds, alignTups, tup_indx):
    wordAlignSet = set([])

    for aTup in alignTups:
        if aTup[tup_indx] == -1: continue
        if aTup[tup_indx] not in wordAlignSet:
            wordAlignSet.add( aTup[tup_indx] )

    for i in xrange(p_len):
        if phrWrds[i].startswith('X__'): continue
        if i not in wordAlignSet:
            if tup_indx == 0: alignTups.append( (i, -1) )
            else: alignTups.append( (-1, i) )

    return tuple(alignTups)

def calcLexProb(srcWrds, tgtWrds, aTups, align_direction):
    '''Calculates the lexical probability for the given rule and its alignment'''

    global null_term
    global lexProbDict
    lex_prob = 1.0
    countLst = []
    probLst = []
    alignPosDict = {}

    alignTups = getUnalignedIndices(len(srcWrds), tuple(srcWrds), list(aTups), 0)
    alignTups = getUnalignedIndices(len(tgtWrds), tuple(tgtWrds), list(alignTups), 1)

    # Initialize the count and prob lists based on the alignment direction
    p_len = len(srcWrds) if align_direction else len(tgtWrds)
    for i in xrange(0, p_len):
        countLst.append(0)
        probLst.append(0.0)

    for i, j in alignTups:
        # Get source and target words from the alignment
        src_wrd = null_term if i == -1 else srcWrds[i]
        tgt_wrd = null_term if j == -1 else tgtWrds[j]
        lexT = (src_wrd, tgt_wrd)

        # Count the alignments depending on the alignment direction and
        # incrementally compute the lexical probability
        if align_direction:
            pos2count = i
            prob = lexProbDict[lexT][0]
        else:
            pos2count = j
            prob = lexProbDict[lexT][1]

        if alignPosDict.has_key(pos2count):
            countLst[pos2count] += 1
            probLst[pos2count] += prob
        else:
            alignPosDict[pos2count] = 1
            countLst[pos2count] = 1
            probLst[pos2count] = prob

    for indx, sum_prob in enumerate( probLst ):
        if sum_prob > 0.0:
            align_count = countLst[indx]
            lex_prob *= sum_prob / float( align_count )

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
    tgtFileLst = []
    for file in os.listdir(inDir):
        if file.startswith("tgt"): is_tgt_file = True
        else: is_tgt_file = False

        file = inDir + file
        if os.path.isfile(file):
            if is_tgt_file: tgtFileLst.append(file)
            else: fileLst.append(file)

    outFile1 = outDir + 'rules_cnt_align.out'
    outFile2 = outDir + 'rules_cnt_lprob.out'
    tgtFile = outDir + 'tgt_rules.all.out'

    #mergeTgtCounts(tgtFileLst, tgtFile)
    read_n_merge(fileLst, outFile1, outFile2)

if __name__ == '__main__':
    main()

