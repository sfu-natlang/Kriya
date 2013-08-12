## This program extracts a Synchronous CFG rules from the word alignments of a parallel corpus ##

import sys

# Constants
max_phr_len = 10              # Maximum phrase length
tot_src_terms = 7             # Total no of terms (terminals & non-terminals incl) in source side
X1_only = False               # Flag for deciding whether to generate one non-termianl or two non-terminal rules
weight_rules = False          # When distributing the unit-count among the rules, should it be weighted by the # of rule occurrences
tight_phrases_only = True     # Restrict the rule extraction strictly to tighter phrases

# Global Variables
rule_indx = 1
tot_rules_derived = 0

srcWrds = []
tgtWrds = []
ruleDict = {}
alignDoD = {}
revAlignDoD = {}
sentInitDoD = {}
ppairRulesSet = set([])

tgtCntDict = {}
ruleIndxCntDict = {}
fAlignDoD = {}
rAlignDoD = {}


def readPhraseSpan(spanFile, outFile, tgtFile):
    'Reads the input phrase span file for src & tgt sentences, alignment and initial phrases'

    global tight_phrases_only
    global ruleDict, ruleIndxCntDict, tgtCntDict
    global srcWrds, tgtWrds
    sent_count = 0
    phrLst = []

    print "Reading the span file :", spanFile
    inF = open(spanFile, 'r')
    for line in inF:
        line = line.strip()
        if line.startswith('LOG: SRC: '):             # Read the source sentence
            src = line.replace('LOG: SRC: ', '')
            srcWrds = src.split()
        elif line.startswith('LOG: TGT: '):           # Read the target sentence
            tgt = line.replace('LOG: TGT: ', '')
            tgtWrds = tgt.split()
        elif line.startswith('LOG: ALT: '):           # Read the source-target alignment
            align = line.replace('LOG: ALT: ', '')
            for align_pos in align.split():
                m = align_pos.split('-')
                try:                                  # Store forward alignments
                    alignDoD[m[0]][m[1]] = 1
                except KeyError:
                    alignDoD[m[0]] = {}
                    alignDoD[m[0]][m[1]] = 1
                try:                                  # Store reverse alignments
                    revAlignDoD[m[1]][m[0]] = 1
                except KeyError:
                    revAlignDoD[m[1]] = {}
                    revAlignDoD[m[1]][m[0]] = 1
        elif line.startswith('LOG: PHRASES_BEGIN:'): continue
        elif line.startswith('LOG: PHRASES_END:'):    # End of the current sentence; now extract rules from it
            xtractRules()

            # For every extracted rule call the function compFeatureCounts() to:
            #   i. convert the word positions in the rules into lexical entries, and
            #   ii. find the alignment for the rule and compute the joint count p(s, t)
            for rule in ruleDict.keys(): compFeatureCounts(rule)

            # Clear the variables at the end of current sentence
            alignDoD.clear()
            revAlignDoD.clear()
            ruleDict.clear()
            sentInitDoD.clear()
            sent_count += 1
            if sent_count % 1000 == 0:
                print "Sentences processed : %6d ..." % sent_count
        else:
            unaligned_edge = False
            phrLst = [ int(x) for x in line.split() ]

            # If the boundary term of source or target phrase has an unaligned word, ignore the phrase-pair
            # Earlier bug fixed on March '09
            # Unless the tight-phrase options is set to False
            if not alignDoD.has_key( str(phrLst[0]) ) or not revAlignDoD.has_key( str(phrLst[2]) ) or \
                 not alignDoD.has_key( str(phrLst[1]) ) or not revAlignDoD.has_key( str(phrLst[3]) ):
                if tight_phrases_only: continue
                else: unaligned_edge = True

            sphr_len = phrLst[1] - phrLst[0] + 1      # Find length of source phrase and its span
            init_phr_pair = (' '.join( [str(x) for x in xrange(phrLst[0], phrLst[1]+1) ] ), \
                             ' '.join( [str(x) for x in xrange(phrLst[2], phrLst[3]+1)] ) )
            if unaligned_edge:
                ruleDict[init_phr_pair] = 1.0
                continue

            # Create a dict of dict for storing initial phrase pairs (tuples of source and target spans)
            if not sentInitDoD.has_key(sphr_len):
                sentInitDoD[sphr_len] = {}
            sentInitDoD[sphr_len][init_phr_pair] = 1

    inF.close()

    # Write the rule counts, forward and reverse alignments to files
    with open(outFile, 'w') as oF:
        for rule in sorted( ruleIndxCntDict.iterkeys() ):
            r_indx, rule_count = ruleIndxCntDict[rule]
            f_alignments = ' ## '.join( fAlignDoD[r_indx].keys() )
            r_alignments = ' ## '.join( rAlignDoD[r_indx].keys() )
            oF.write( "%s ||| %g ||| %s ||| %s\n" % (rule, rule_count, r_alignments, f_alignments) )

    with open(tgtFile, 'w') as tF:
        for tgt in sorted( tgtCntDict.iterkeys() ):
            tF.write( "%s ||| %g\n" % (tgt, tgtCntDict[tgt]) )

    return None


def xtractRules():
    ''' Extract the rules for different phrase lengths (from smallest to longest) '''

    for sphr_len in xrange(max_phr_len, 1, -1):
        if sentInitDoD.has_key(sphr_len):
            check4Subphrase(sphr_len)

    # Handle the rules of length (source side) 1
    sphr_len = 1
    if sentInitDoD.has_key(sphr_len):
        for init_phr_pair in sentInitDoD[sphr_len]:
            if ruleDict.has_key(init_phr_pair): ruleDict[init_phr_pair] += 1.0
            else: ruleDict[init_phr_pair] = 1.0
            #sys.stderr.write('    %s ||| %s ||| %g\n' % (init_phr_pair[0], init_phr_pair[1], ruleDict[init_phr_pair]))


def check4Subphrase(sphr_len):

    global tot_src_terms, X1_only, tot_rules_derived
    global ppairRulesSet
    ppairRulesDict = {}

    for phr_pair in sentInitDoD[sphr_len].keys():
        rule_cnt = 0.0
        tot_rules_derived = 0           # Clear the global variables for every phrase-pair
        ppairRulesSet.clear()
        ppairRulesDict.clear()

        # Constraint: Rules are limited to seven non-terminals and terminals on source side
        # Initial phrase pairs having less than TOT_TERMS (default 7) terms in source side are added to the set of rules
        if sphr_len <= tot_src_terms:
            tot_rules_derived += 1
            if ppairRulesDict.has_key(phr_pair): ppairRulesDict[phr_pair] += 1
            else: ppairRulesDict[phr_pair] = 1

        # Do a breadth-first search: extract all possible rules for the given initial phrase pair
        iterateInitPhrPairs(sphr_len, phr_pair)
        while ppairRulesSet:
            sub_phr_pair = ppairRulesSet.pop()
            sub_s_span, sub_t_span = sub_phr_pair
            sub_phr_slen = len( sub_s_span.split() )

            if sub_phr_slen <= tot_src_terms:
                if ppairRulesDict.has_key(sub_phr_pair): ppairRulesDict[sub_phr_pair] += 1
                else: ppairRulesDict[sub_phr_pair] = 1

            # Constraint-1: Check if the source span already has 2 nonterminals, then do not process it further
            if (X1_only and sub_s_span.find('X__1') != -1) or (sub_s_span.find('X__2') != -1):
                pass
            # If the source span has 1 non-terminal, but further simplification is not possible
            elif sub_s_span.find('X__1') != -1 and not isRuleDecomposable( sub_s_span ):
                pass
            else:
                iterateInitPhrPairs(sub_phr_slen, sub_phr_pair)

        # Distribute the unit count for each initial phrase-pair equally among the rules extracted from it
        if tot_rules_derived > 0: rule_cnt = 1.0/ tot_rules_derived

        # Weight each rule by the number of times it was observed
        for rule in ppairRulesDict.keys():
            weighted_cnt = rule_cnt
            if weight_rules: weighted_cnt *= ppairRulesDict[rule]
            if ruleDict.has_key(rule): ruleDict[rule] += weighted_cnt
            else: ruleDict[rule] = weighted_cnt
            #sys.stderr.write('    %s ||| %s ||| %g ||| %d\n' % (rule[0], rule[1], ruleDict[rule], ppairRulesDict[rule]))


def isRuleDecomposable( s_span ):

    srcRuleTerms = s_span.split()
    try:
        term_indx = srcRuleTerms.index('X__1')
        if term_indx >= 2 or (len(srcRuleTerms) - 1 - term_indx) >= 2:
            return True
        else: return False
    except ValueError:
        if srcRuleTerms: return True       # decide for a terminal rule that doesn't have 'X__1'
        else: return False


def iterateInitPhrPairs(sphr_len, (s_span, t_span)):
    global tot_rules_derived
    global ppairRulesSet
    for sub_phr_slen in xrange(sphr_len-1, 0, -1):
        if not sentInitDoD.has_key(sub_phr_slen): continue

        for sub_phr_pair in sentInitDoD[sub_phr_slen].keys():
            # Process the rule further only if its span is compatible to that of the target rule
            subSpanTuple = sentInitDoD[sub_phr_slen][sub_phr_pair]

            # Check constraint-2: The given phrases are sub-phrases of source and target spans
            src_side_compatible = checkRuleCompatibility(s_span, sub_phr_pair[0])
            tgt_side_compatible = checkRuleCompatibility(t_span, sub_phr_pair[1])
            if src_side_compatible and tgt_side_compatible:
                sub_s_span, sub_t_span = sub_phr_pair

                # If the sub spans are compatible with the given src & tgt spans then,
                # compose the new rule. If the new rule satisfies filtering constraints then,
                # it is added to the ppairRulesSet towards count
                rule = checkConstraints(s_span, t_span, sub_s_span, sub_t_span)
                if rule is not None:
                    ppairRulesSet.add(rule)

                # Count all the rules derived so far, including those not satisfying filtering constraints
                tot_rules_derived += 1


def checkRuleCompatibility(rule, sub_rule):
    'Checks if the sub phrase is compatible with the bigger rule (for both src & tgt rules)'

    #l_pad = ' ' + sub_rule          # Pad the string with a space on left side
    #r_pad = sub_rule + ' '          # Pad the string with a space on right side
    #b_pad = ' ' + sub_rule + ' '    # Pad the string with a space on either sides
    # Assuming the above padded strings, the following conditions must be satisfied for rule to be compatible with a larger phrase:
    #   rule.startswith(r_pad) or rule.endswith(l_pad) or rule.find(b_pad) != -1

    if rule.startswith(sub_rule + ' ') or rule.endswith(' ' + sub_rule) or \
            rule.find(' ' + sub_rule + ' ') != -1:
        return True
    return False


def checkConstraints(src, tgt, sub_src, sub_tgt):
    ''' Checks if the rules satisfy the filtering constraints (without these the grammar would explode) '''

    # Return a default 'None' rule if any of the constraints is not satisifed

    # Substitute the nonterminal in both sides before checking the constraints
    # If the constraints are satisfied, then the modified rules are combined and returned
    X1_indx = src.find('X__1')
    if X1_indx != -1:
        # Check constraint-3: Rules are limited to five non-terminals and terminals on source side
        # Find the difference in length between the source phrase and sub-phrase,
        # if the length difference is more than TOT_TERMS (default 7), don't add it to the rulesTempSet
        if ( len(src.split()) - len(sub_src.split()) + 1 ) > tot_src_terms:
            return None

        # Constraint-4: The source side does **NOT** have two adjacent nonterminals
        #   The sub phrase should not be next to the existing non-terminal (X__1)
        adj_X1_right = sub_src + ' X__1'
        adj_X1_left = 'X__1 ' + sub_src
        if src.startswith(adj_X1_right) or src.find(' '+adj_X1_right) != -1 or \
           src.endswith(adj_X1_left) or src.find(adj_X1_left+' ') != -1:
            return None

        # If non-terminal X__1 occurs to the right of the current sub-phrase, rename X__1 to X__2 in
        # both source & target rules. In any synchronous rule, the source side will always have the
        # non-terminal X__2 following the X__1
        if src.startswith(sub_src+' ') or src.find(' '+sub_src+' ', 0, X1_indx) != -1:
            src = src.replace('X__1', 'X__2', 1)
            tgt = tgt.replace('X__1', 'X__2', 1)
            rep_str = 'X__1'
        else: rep_str = 'X__2'
    else:
        rep_str = 'X__1'

    s_side = replaceItem(src, sub_src, rep_str)
    t_side = replaceItem(tgt, sub_tgt, rep_str)

    # Constraint-5: Both sides have atleast one terminal aligned with each other
    tgtTermLst = t_side.split()
    aligned_terminal = False
    for pos in s_side.split():
        if not alignDoD.has_key(pos): continue
        for tgt_align_pos in alignDoD[pos].keys():
            try: 
                tgtTermLst.index(tgt_align_pos)
                aligned_terminal = True
                break
            except ValueError:
                pass

        # If all the constraints are satisfied compose the rule as a tuple and return it
        if aligned_terminal:
            return (s_side, t_side)

    return None


def replaceItem(full_str, p_match, rep_str):

    if len( p_match.split() ) > 1:   # If p_match has just more than element, replace it directly
        return full_str.replace(p_match, rep_str, 1)
    else:   # else, iterate over the elements in full_str to find p_match to replace it with rep_str
        tmpLst = []
        for tok in full_str.split():
            if tok == p_match:
                tmpLst.append(rep_str)
            else:
                tmpLst.append(tok)
        return ' '.join(tmpLst)


def compFeatureCounts(rule):
    'Convert to lexical rule and find the alignment for the entries in the rule. Also compute feature counts P(s|t), P(t|s), P_w(s|t) and P_w(t|s)'

    global srcWrds, tgtWrds
    global fAlignDoD, rAlignDoD
    srcLexLst = []
    tgtLexLst = []
    alignLst = []

    sPosLst = rule[0].split()
    tPosLst = rule[1].split()
    # Convert the word positions in source side of the rule to corresponding lexemes
    item_indx = 0
    for s_tok in sPosLst:
        if s_tok.startswith('X__'):
            srcLexLst.append(s_tok)
        else:
            srcLexLst.append(srcWrds[int(s_tok)])
            # Find the forward alignment for the lexemes in the rule
            alignment = getFwrdAlignment(item_indx, s_tok, tPosLst)
            alignLst.append(alignment)
            #if len(alignment) > 0:
            #    alignLst.append(alignment)
        item_indx += 1
    fAlignment = ' '.join(alignLst)

    # Convert the word positions in target side of the rule to corresponding lexemes
    del alignLst[:]
    item_indx = 0
    for t_tok in tPosLst:
        if t_tok.startswith('X__'):
            tgtLexLst.append(t_tok)
        else:
            tgtLexLst.append(tgtWrds[int(t_tok)])
            # Find the reverse alignment for the lexemes in the rule
            alignment = getRvrsAlignment(item_indx, t_tok, sPosLst)
            alignLst.append(alignment)
            #if len(alignment) > 0:
            #    alignLst.append(alignment)
        item_indx += 1
    rAlignment = ' '.join(alignLst)

    # Get the lexical rule and add its count from the current sentence to total count so far
    curr_rindx = updateRuleCount(' '.join(srcLexLst), ' '.join(tgtLexLst), rule)

    # Update forward and reverse alignment dicts
    f_align_indx = getAlignIndex(fAlignment)
    r_align_indx = getAlignIndex(rAlignment)
    if not fAlignDoD.has_key(curr_rindx):
        fAlignDoD[curr_rindx] = {}
        rAlignDoD[curr_rindx] = {}
    if not fAlignDoD[curr_rindx].has_key(f_align_indx):
        fAlignDoD[curr_rindx][f_align_indx] = 1
    if not rAlignDoD[curr_rindx].has_key(r_align_indx):
        rAlignDoD[curr_rindx][r_align_indx] = 1


def updateRuleCount(mc_src, mc_tgt, rule):
    ''' Updates rule and target counts '''

    global rule_indx, ruleDict, ruleIndxCntDict, tgtCntDict
    if not tgtCntDict.has_key(mc_tgt):
        tgtCntDict[mc_tgt] = 0
    tgtCntDict[mc_tgt] += ruleDict[rule]

    mc_key = mc_src + ' ||| ' + mc_tgt              # ' ||| ' is the delimiter separating items in the key/value
    if ruleIndxCntDict.has_key(mc_key):
        curr_rindx, curr_cnt = ruleIndxCntDict[mc_key]
        ruleIndxCntDict[mc_key] = ( curr_rindx, curr_cnt + ruleDict[rule] )
    else:
        ruleIndxCntDict[mc_key] = (rule_indx, ruleDict[rule])
        curr_rindx = rule_indx
        rule_indx += 1
    return curr_rindx


def getAlignIndex(align_str):

    tmpLst = align_str.split(' ')
    tmpLst.sort()
    aindx = ''.join(tmpLst)
    return aindx.replace('-', '')


def getFwrdAlignment(item_indx, s_pos, tPosLst):
    'Computes the alignment and lexical weights in forward direction'

    alignLst = []
    if alignDoD.has_key(s_pos):
        alignKeyLst = alignDoD[s_pos].keys()
        alignKeyLst.sort()
        for t_pos in alignKeyLst:
            try:
                # Get the alignment and append it to the list
                alignment = str(item_indx) + '-' + str(tPosLst.index(t_pos))
                alignLst.append(alignment)
            except ValueError:
                pass
    else:
        alignLst.append( str(item_indx) + '-Z' )     # 'Z' represents 'NULL' (i.e. word is unaligned)

    return ' '.join(alignLst)


def getRvrsAlignment(item_indx, t_pos, sPosLst):
    'Computes the alignment and lexical weights in reverse direction'

    alignLst = []
    if revAlignDoD.has_key(t_pos):
        alignKeyLst = revAlignDoD[t_pos].keys()
        alignKeyLst.sort()
        for s_pos in alignKeyLst:
            try:
                # Get the alignment and append it to the list
                alignment = str(sPosLst.index(s_pos)) + '-' + str(item_indx)
                alignLst.append(alignment)
            except ValueError:
                pass
    else:
        alignLst.append( 'Z-' + str(item_indx) )     # 'Z' represents 'NULL' (i.e. word is unaligned)

    return ' '.join(alignLst)


def main():

    global tight_phrases_only
    global tot_src_terms
    global X1_only
    if len(sys.argv) < 4 and len(sys.argv) > 6:
        print 'Usage: python %s <file_index> <dataDir> <outDir> [Total_terms on Fr side (def 7)] [True/False] [True/False]' % (sys.argv[0])
        print 'Exiting!!\n'
        sys.exit()

    file_indx = sys.argv[1]
    dDir = sys.argv[2]
    oDir = sys.argv[3]

    if len(sys.argv) > 4:
        tot_src_terms = int(sys.argv[4])
        if len(sys.argv) == 6 and sys.argv[5] != 'True' and sys.argv[5] != 'False':
            print "Last argument should be a boolean True/False indicating one/two non-terminal case"
            sys.exit(1)
        if len(sys.argv) == 6 and sys.argv[5] == 'True':    # True specifies that only one non-terminal is extracted; set False for two non-terminal case
            X1_only = True
        if len(sys.argv) == 7 and sys.argv[6] == 'False':   # False relaxes the tight phrase pairs constraint and enables the model to extract rules from loose phrases as well
            tight_phrases_only = False

    print "Using the French side total terms to be :", tot_src_terms
    print "Enforcing tight phrase-pairs constraint :", tight_phrases_only
    if not dDir.endswith("/"): dDir += "/"
    if not oDir.endswith("/"): oDir += "/"

    spanFile = dDir + file_indx + '.outspan'
    outFile  = oDir + file_indx + '.out'
    tgtFile  = oDir + 'tgt.' + file_indx + '.out'
    readPhraseSpan(spanFile, outFile, tgtFile)


if __name__ == '__main__':
    main()
