## This program extracts a Synchronous CFG rules from the word alignments of a parallel corpus ##

import sys
import re
import time

# Constants
MAX_PHR_LEN = 10                  # Maximum phrase length
TOT_TERMS = 7                     # Total no of terms (terminals & non-terminals incl) in source rule

# Global Variables
rule_indx = 1
tot_rules_derived = 0
X1_only = False                   # Flag for deciding whether to generate one non-termianl or two non-terminal rules
X__Max = 2

ruleDict = {}
alignDoD = {}                     # Dictionary for storing forward alignments
revAlignDoD = {}                  # Dictionary for storing reverse alignments
sentInitDoD = {}
sentTempDict = {}
sentFinalDict = {}

tgtCntDict = {}
ruleIndxCntDict = {}
fAlignDoD = {}
rAlignDoD = {}


def resourceStats():
    'Returns the CPU time to calculate the usage'
    return time.time()


def readPhraseSpan(spanFile, outFile, tgtFile):
    'Reads the input phrase span file for src & tgt sentences, alignment and initial phrases'

    global ruleIndxCntDict, tgtCntDict
    sent_count = 0
    srcWrds = []
    tgtWrds = []
    phrLst = []
    src_span = []
    tgt_span = []

    print "Reading the span file :", spanFile
    inF = open(spanFile, 'r')
    for line in inF:
        line = line.strip()

#	print line
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
        elif (line.split()[0]).isdigit():             # Read the initial phrase pairs (produced by moses script)
            phrLst = []
            src_span = []
            tgt_span = []
            for temp in line.split():
                phrLst += [int(temp)]

            # If the boundary term of source or target phrase has an unaligned word, ignore the phrase-pair
            # Earlier bug fixed on March '09
            if ( not alignDoD.has_key( str(phrLst[0]) ) or not revAlignDoD.has_key( str(phrLst[2]) ) or
                 not alignDoD.has_key( str(phrLst[1]) ) or not revAlignDoD.has_key( str(phrLst[3]) ) ):
                continue

            src_len = phrLst[1] - phrLst[0] + 1      # Find length of source phrase and its span
            src_span = ' '.join( map( lambda x: str(x), range(phrLst[0], phrLst[1]+1) ) )
            tgt_len = phrLst[3] - phrLst[2] + 1      # Find length of target phrase and its span
            tgt_span = ' '.join( map( lambda x: str(x), range(phrLst[2], phrLst[3]+1) ) )

            # Creating a dict of dict for storing source and target spans
            src_spanTuple = ()
            init_phr_pair = ()
            src_spanTuple = (phrLst[0], phrLst[1])
            init_phr_pair = (src_span, tgt_span)
            try:
                sentInitDoD[src_len][init_phr_pair] = 1
            except KeyError:
                sentInitDoD[src_len] = {}
                sentInitDoD[src_len][init_phr_pair] = 1
        elif line.startswith('LOG: PHRASES_END:'):    # End of the current sentence; now extract rules from it
            xtractRules()

            # For every extracted rule call the function compFeatureCounts() to:
            #   i. convert the word positions in the rules into lexical entries, and
            #   ii. find the alignment for the rule and compute the joint count p(s, t)
            for rPS_rule in ruleDict.keys():
                compFeatureCounts(rPS_rule, srcWrds, tgtWrds)

            # Clear the variables at the end of current sentence
            srcWrds = []
            tgtWrds = []
            alignDoD.clear()
            revAlignDoD.clear()
            ruleDict.clear()
            sentInitDoD.clear()
            sent_count += 1
            if sent_count % 2000 == 0:
                print "Sentences processed : %6d ..." % sent_count

    inF.close()
    # Write the rule counts, forward and reverse alignments to files
    oF = open(outFile, 'w')
    rules = ruleIndxCntDict.keys()
    rules.sort()
    for rule in rules:
        rPP_rule_indx, rule_count = ruleIndxCntDict[rule]
        f_alignments = ' ## '.join( fAlignDoD[rPP_rule_indx].keys() )
        r_alignments = ' ## '.join( rAlignDoD[rPP_rule_indx].keys() )
        oF.write( "%s ||| %g ||| %s ||| %s\n" % (rule, rule_count, r_alignments, f_alignments) )
    oF.close()

    tF = open(tgtFile, 'w')
    tgtSides = tgtCntDict.keys()
    tgtSides.sort()
    for tgt in tgtSides:
        tF.write( "%s ||| %g\n" % (tgt, tgtCntDict[tgt]) )
    tF.close()
    return None


def xtractRules():
    '''Extracts the rules from the alignments of a sentence'''

    for xR_phr_len in range(MAX_PHR_LEN, 1, -1):
        if sentInitDoD.has_key(xR_phr_len):
            check4Subphrase(xR_phr_len)

    # Handling the rules where the length of source side is 1
    if sentInitDoD.has_key(1):
        for xR_rule in sentInitDoD[1]:
            if ruleDict.has_key(xR_rule):
                ruleDict[xR_rule] += 1.0
            else:
                ruleDict[xR_rule] = 1.0
#            print '%15s %15s : %g' % (xR_rule[0], xR_rule[1], ruleDict[xR_rule])


def check4Subphrase(c4Sp_phr_len):

    global TOT_TERMS
    global X1_only
    global tot_rules_derived
    for c4Sp_phr_pair in sentInitDoD[c4Sp_phr_len].keys():
        c4Sp_spanTuple = sentInitDoD[c4Sp_phr_len][c4Sp_phr_pair]
        c4Sp_s_span = c4Sp_phr_pair[0]
        c4Sp_t_span = c4Sp_phr_pair[1]

        # Use the global variable for counting the number of rules derived
        tot_rules_derived = 0

        c4Sp_rulesLst = []
        sentTempDict.clear()
        sentFinalDict.clear()

        # Constraint: Rules are limited to five non-terminals and terminals on source side
        # Initial phrase pairs having less than TOT_TERMS (default 5) terms in source side are added with weight 1.0
        if len(c4Sp_s_span.split()) <= TOT_TERMS:
            sentFinalDict[c4Sp_phr_pair] = 1

        # Do a breadth first search: search for all possible rules for a given initial phrase pair
        iterateInitPhrPairs(c4Sp_phr_len, c4Sp_s_span, c4Sp_t_span)
        c4Sp_rulesLst = sentTempDict.keys()
        while len(c4Sp_rulesLst) > 0:
            c4Sp_sub_phr_pair = c4Sp_rulesLst[0]

            c4Sp_s_span = c4Sp_sub_phr_pair[0]
            c4Sp_t_span = c4Sp_sub_phr_pair[1]
            srcRuleTerms = []
            srcRuleTerms = c4Sp_s_span.split()
            c4Sp_sub_phr_len = len( srcRuleTerms )

            # Constraint-1: Check if the source span already has 2 nonterminals, then do not process it further
	    nonTerminalPatterns = re.findall(r'X__[0-9]',c4Sp_s_span)
            if len(nonTerminalPatterns) == X__Max:
                pass
            # If the source span has 1 non-terminal, but further simplification is not possible
            elif c4Sp_s_span.find('X__1') != -1 and not isRuleDecomposable( srcRuleTerms ):
                pass
            else:
                iterateInitPhrPairs(c4Sp_sub_phr_len, c4Sp_s_span, c4Sp_t_span)

            if len(c4Sp_s_span.split()) <= TOT_TERMS:
                sentFinalDict[c4Sp_sub_phr_pair] = 0
            c4Sp_junk_considered = sentTempDict.pop(c4Sp_sub_phr_pair)
            c4Sp_rulesLst = []
            c4Sp_rulesLst = sentTempDict.keys()

        if tot_rules_derived > 0:
            c4Sp_rule_prob = float( 1.0 / tot_rules_derived )
        else:
            c4Sp_rule_prob = 0.0
#        c4Sp_rule_prob = 1.0 / len( sentFinalDict.keys() )

        for c4Sp_rule in sentFinalDict.keys():
            # Initial phrase-pairs having weight '1' are added with 'unit' counts
            if sentFinalDict[c4Sp_rule] == 1:
                if ruleDict.has_key(c4Sp_rule):
                    ruleDict[c4Sp_rule] += 1.0
                else:
                    ruleDict[c4Sp_rule] = 1.0

            # Derived phrase-pairs having fractional weights are added fractional counts
            if ruleDict.has_key(c4Sp_rule):
                ruleDict[c4Sp_rule] += c4Sp_rule_prob
            else:
                ruleDict[c4Sp_rule] = c4Sp_rule_prob
        #    print '%15s %15s : %g' % (c4Sp_rule[0], c4Sp_rule[1], ruleDict[c4Sp_rule])

        # Clear the dictionaries again to reduce the memory usage
        sentTempDict.clear()
        sentFinalDict.clear()


def isRuleDecomposable( iRD_srcRuleTerms ):

    iRD_last_indx = len( iRD_srcRuleTerms ) - 1
    prev_XSymbol = -1
    for iRD_term_indx, iRD_term in enumerate( iRD_srcRuleTerms ):
        if iRD_term.find('X__') >= 0:
            ## For a rule to be decomposable further it should have at least one-terminal word on
            ## either side of X__1, which can be written by X__2. Note that the two non-terminals can not
            ## occur next to each other in source side and so there should be at least one word in between.
            prev_XSymbol = iRD_term_indx
        if iRD_term_indx - prev_XSymbol > 0: #it should be changed (to 0) if we relaxed the rules!
            return True
    return False



def iterateInitPhrPairs(iIPP_phr_len, iIPP_s_span, iIPP_t_span):
    global tot_rules_derived
    for iIPP_sub_phr_len in range(iIPP_phr_len-1, 0, -1):

        if sentInitDoD.has_key(iIPP_sub_phr_len):

            for iIPP_sub_phr_pair in sentInitDoD[iIPP_sub_phr_len].keys():
                # Process the rule further only if its span is compatible to that of the target rule
                iIPP_subSpanTuple = sentInitDoD[iIPP_sub_phr_len][iIPP_sub_phr_pair]

                # Check constraint-2: The given phrases are sub-phrases of source and target spans
                src_side_compatible = checkRuleCompatibilityforSrc(iIPP_s_span, iIPP_sub_phr_pair[0])
                tgt_side_compatible = checkRuleCompatibilityforTgt(iIPP_t_span, iIPP_sub_phr_pair[1])
                if src_side_compatible and tgt_side_compatible:
                    iIPP_sub_s_span = iIPP_sub_phr_pair[0]
                    iIPP_sub_t_span = iIPP_sub_phr_pair[1]
                    
                    # If the sub spans are compatible with the given src & tgt spans then,
                    # compose the new rule. If the new rule satisfies filtering constraints then,
                    # it is added to the sentTempDict towards count
                    iIPP_rule = ''
                    iIPP_rule = checkConstraints(iIPP_s_span, iIPP_t_span, iIPP_sub_s_span, iIPP_sub_t_span)
                    if len(iIPP_rule) > 1:
                        sentTempDict[iIPP_rule] = 0

                    # Count all the rules derived so far, including those not satisfying filtering constraints
                    tot_rules_derived += 1
		#    print iIPP_s_span," , ", iIPP_t_span, "subphrases:\t\t", iIPP_sub_phr_pair


def checkRuleCompatibilityforTgt(cRC_rule, cRC_sub_rule):
    'Checks if the sub phrase is compatible with the bigger rule (for both src & tgt rules)'

    #cRC_rule_compatible = False
    #cRC_l_pad = ' ' + cRC_sub_rule          # Pad the string with a space on left side
    #cRC_r_pad = cRC_sub_rule + ' '          # Pad the string with a space on right side
    #cRC_b_pad = ' ' + cRC_sub_rule + ' '    # Pad the string with a space on either sides
    
    nonTerminalPatterns = re.findall(r'X__[0-9]',cRC_rule)
    end_rule = cRC_sub_rule[:]
    for nonTerm in nonTerminalPatterns:
	end_rule += ' '+nonTerm
    if cRC_rule.endswith(end_rule):
	return True

    return False

def checkRuleCompatibilityforSrc(cRC_rule, cRC_sub_rule):
    'Checks if the sub phrase is compatible with the bigger rule (for both src & tgt rules)'

    cRC_rule_compatible = False
    cRC_l_pad = ' ' + cRC_sub_rule          # Pad the string with a space on left side
    cRC_r_pad = cRC_sub_rule + ' '          # Pad the string with a space on right side
    cRC_b_pad = ' ' + cRC_sub_rule + ' '    # Pad the string with a space on either sides

    if cRC_rule.startswith(cRC_r_pad) or  cRC_rule.endswith(cRC_l_pad) or cRC_rule.find(cRC_b_pad) != -1:
    	cRC_rule_compatible = True
    return cRC_rule_compatible

def getMaxNonTerm(cC_span):
	nonTerminalPatterns = re.findall(r'X__[0-9]',cC_span)
	if len(nonTerminalPatterns) > 0: 
		return (cC_span.find(nonTerminalPatterns[-1]),len(nonTerminalPatterns))
	else:
		return (-1,-1)

def checkConstraints(cC_s_span, cC_t_span, cC_sub_src, cC_sub_tgt):
    'Checks if the rules satisfy the filtering constraints; used to balance grammar size'

    # Return a default **empty** rule if any of the constraints is not satisifed
    cC_rule = ''

    # Substitute the nonterminal in both sides before checking the constraints
    # If the constraints are satisfied, then the modified rules are combined and returned
    (cC_XMAX_indx, cC_XMAX_value) = getMaxNonTerm(cC_s_span)
    nonTerminalPatterns = re.findall(r'X__[0-9]',cC_s_span)
    if cC_XMAX_indx != -1:
        # Check constraint-3: Rules are limited to five non-terminals and terminals on source side
        # Find the difference in length between the source phrase and sub-phrase,
        # if the length difference is more than TOT_TERMS (default 5), don't add it to the sentTempDict
        if ( len(cC_s_span.split()) - len(cC_sub_src.split()) + 1 ) > TOT_TERMS:
            return cC_rule

        # Constraint-4: The source side does **NOT** have two adjacent nonterminals
#        for index in range(1, cC_XMAX_value+1):
#		cC_X_follows = cC_sub_src + ' X__' + str(index)
#	        cC_X_preceeds = 'X__' + str(index) + ' ' + cC_sub_src
#	        if cC_s_span.startswith(cC_X_follows) or cC_s_span.find(' '+cC_X_follows) != -1 or cC_s_span.endswith(cC_X_preceeds) or cC_s_span.find(cC_X_preceeds+' ') != -1:    #Maryam: should be changed in case of relaxing constraint on adjucent NonTerms
#	           return cC_rule

        # If non-terminal X__1 occurs to the right of the current sub-phrase, rename X__1 to X__2 in
        # both source & target rules. In any synchronous rule, the source side will always have the
        # non-terminal X__2 following the X__1
        cC_r_pad = cC_sub_src + ' '
        cC_b_pad = ' ' + cC_sub_src + ' '
        cC_rep_str = ''
        for x_index,x_term in enumerate(nonTerminalPatterns):
		s_span_index = cC_s_span.find(x_term)
	        if cC_s_span.find(cC_b_pad, 0, s_span_index) != -1 or cC_s_span.startswith(cC_r_pad):
		    for new_x_index in range(len(nonTerminalPatterns), x_index, -1):
		            cC_s_span = cC_s_span.replace('X__'+str(new_x_index), 'X__'+str(new_x_index+1), 1)
        		    cC_t_span = cC_t_span.replace('X__'+str(new_x_index), 'X__'+str(new_x_index+1), 1)
	            cC_rep_str = 'X__'+str(x_index+1)
		    break
	if cC_rep_str == '':
		cC_rep_str = 'X__'+str(len(nonTerminalPatterns)+1)
    else:
        cC_rep_str = 'X__1'

    cC_s_side = replaceItem(cC_s_span, cC_sub_src, cC_rep_str)
    cC_t_side = replaceItem(cC_t_span, cC_sub_tgt, cC_rep_str)

    # Constraint-5: Both sides have atleast one terminal aligned with each other
    cC_srcTermLst = cC_s_side.split()
    cC_tgtTermLst = cC_t_side.split()
    cC_aligned_terminal = False

    for cC_pos in cC_srcTermLst:
        if alignDoD.has_key(cC_pos):
            for cC_tgt_align_pos in alignDoD[cC_pos].keys():
                try: 
                    cC_tgt_indx = cC_tgtTermLst.index(cC_tgt_align_pos)
                    cC_aligned_terminal = True
                    break
                except ValueError:
                    pass

            if cC_aligned_terminal:
                break

    if not cC_aligned_terminal:
        return cC_rule

    # If all the constraints are satisfied compose the rule as a tuple and return it
    cC_rule = (cC_s_side, cC_t_side)
    return cC_rule


def replaceItem(rI_string, rI_match, rI_replacement):

    if len( rI_match.split() ) > 1:   # If rI_match has just more than element, replace it directly
        return rI_string.replace(rI_match, rI_replacement, 1)
    else:   # else, iterate over the elements in rI_string to find rI_match to replace it with rI_replacement
        rI_tmpLst = []
        for rI_tmp in rI_string.split():
            if rI_tmp == rI_match:
                rI_tmpLst.append(rI_replacement)
            else:
                rI_tmpLst.append(rI_tmp)
        return ' '.join( rI_tmpLst )


def compFeatureCounts(cFC_rule, cFC_srcWrds, cFC_tgtWrds):
    'Convert to lexical rule and find the alignment for the entries in the rule. Also compute feature counts P(s|t), P(t|s), P_w(s|t) and P_w(t|s)'

    mc_src = ''
    mc_tgt = ''
    cFC_fAlignment = ''
    cFC_rAlignment = ''
    cFC_srcLexLst = []
    cFC_tgtLexLst = []
    global fAlignDoD, rAlignDoD

    cFC_srcPosLst = cFC_rule[0].split()
    cFC_tgtPosLst = cFC_rule[1].split()
    # Convert the word positions in source side of the rule to corresponding lexemes
    cFC_alignLst = []
    for cFC_src_indx, cFC_src_pos in enumerate( cFC_srcPosLst ):
	if re.search('^X__',cFC_src_pos) is not None : 
            cFC_rep_str = cFC_src_pos
        else:
            cFC_rep_str = cFC_srcWrds[int(cFC_src_pos)]

            # Find the forward alignment for the lexemes in the rule
            cFC_alignment = getFwrdAlignment(cFC_src_indx, cFC_src_pos, cFC_tgtPosLst)
            if len(cFC_alignment) > 0:
                cFC_alignLst.append(cFC_alignment)

        cFC_srcLexLst.append(cFC_rep_str)
    cFC_fAlignment = ' '.join(cFC_alignLst)

    # Convert the word positions in target side of the rule to corresponding lexemes
    cFC_alignLst = []
    for cFC_tgt_indx, cFC_tgt_pos in enumerate( cFC_tgtPosLst ):
	if re.search('^X__',cFC_tgt_pos) is not None : 
            cFC_rep_str = cFC_tgt_pos
        else:
            cFC_rep_str = cFC_tgtWrds[int(cFC_tgt_pos)]

            # Find the reverse alignment for the lexemes in the rule
            cFC_alignment = getRvrsAlignment(cFC_tgt_indx, cFC_tgt_pos, cFC_srcPosLst)
            if len(cFC_alignment) > 0:
                cFC_alignLst.append(cFC_alignment)

        cFC_tgtLexLst.append(cFC_rep_str)
    cFC_rAlignment = ' '.join(cFC_alignLst)

    # Get the lexical rule and add its count from the current sentence to total count so far
    mc_src = ' '.join(cFC_srcLexLst)
    mc_tgt = ' '.join(cFC_tgtLexLst)
    curr_rindx = updateRuleCount(mc_src, mc_tgt, cFC_rule)

    # Update forward and reverse alignment dicts
    f_align_indx = getAlignIndex(cFC_fAlignment)
    r_align_indx = getAlignIndex(cFC_rAlignment)
    if not fAlignDoD.has_key(curr_rindx):
        fAlignDoD[curr_rindx] = {}
        rAlignDoD[curr_rindx] = {}
    if not fAlignDoD[curr_rindx].has_key(f_align_indx):
        fAlignDoD[curr_rindx][f_align_indx] = 1
    if not rAlignDoD[curr_rindx].has_key(r_align_indx):
        rAlignDoD[curr_rindx][r_align_indx] = 1


def updateRuleCount(mc_src, mc_tgt, uRID_rule):
    '''Updates rule and target counts'''

    global rule_indx, ruleIndxCntDict, tgtCntDict
    if not tgtCntDict.has_key(mc_tgt):
        tgtCntDict[mc_tgt] = 0
    tgtCntDict[mc_tgt] += ruleDict[uRID_rule]

    mc_key = mc_src + ' ||| ' + mc_tgt              # ' ||| ' is the delimiter separating items in the key/value
    if ruleIndxCntDict.has_key(mc_key):
        curr_rindx, curr_cnt = ruleIndxCntDict[mc_key]
        ruleIndxCntDict[mc_key] = ( curr_rindx, curr_cnt + ruleDict[uRID_rule] )
    else:
        ruleIndxCntDict[mc_key] = (rule_indx, ruleDict[uRID_rule])
        curr_rindx = rule_indx
        rule_indx += 1
    return curr_rindx


def getAlignIndex(gAI_align_str):

    gAI_tmpLst = gAI_align_str.split(' ')
    gAI_tmpLst.sort()
    gAI_aindx = ''.join( gAI_tmpLst )
    return gAI_aindx.replace('-', '')


def getFwrdAlignment(gFA_src_indx, gFA_src_pos, gFA_tgtPosLst):
    'Computes the alignment and lexical weights in forward direction'

    gFA_alignLst = []
    if alignDoD.has_key(gFA_src_pos):
        gFA_alignKeyLst = []
        gFA_alignKeyLst = alignDoD[gFA_src_pos].keys()
        gFA_alignKeyLst.sort()
        for gFA_aligned_tgt_pos in gFA_alignKeyLst:
            try:
                # Get the alignment and append it to the list
                gFA_rule_indx = gFA_tgtPosLst.index(gFA_aligned_tgt_pos)
                gFA_alignment = str(gFA_src_indx) + '-' + str(gFA_rule_indx)
                gFA_alignLst.append( gFA_alignment )
            except ValueError:
                pass
    else:
        gFA_alignment = str(gFA_src_indx) + '-Z'     # 'Z' represents 'NULL' (i.e. word is unaligned)
        gFA_alignLst.append( gFA_alignment )

    gFA_rule_alignment = ' '.join(gFA_alignLst)
    return gFA_rule_alignment


def getRvrsAlignment(gRA_tgt_indx, gRA_tgt_pos, gRA_srcPosLst):
    'Computes the alignment and lexical weights in reverse direction'

    gRA_alignLst = []
    if revAlignDoD.has_key(gRA_tgt_pos):
        gRA_alignKeyLst = []
        gRA_alignKeyLst = revAlignDoD[gRA_tgt_pos].keys()
        gRA_alignKeyLst.sort()
        for gRA_aligned_src_pos in gRA_alignKeyLst:
            try:
                # Get the alignment and append it to the list
                gRA_rule_indx = gRA_srcPosLst.index(gRA_aligned_src_pos)
                gRA_alignment = str(gRA_rule_indx) + '-' + str(gRA_tgt_indx)
                gRA_alignLst.append( gRA_alignment )
            except ValueError:
                pass
    else:
        gRA_alignment = 'Z-' + str(gRA_tgt_indx)     # 'Z' represents 'NULL' (i.e. word is unaligned)
        gRA_alignLst.append( gRA_alignment )

    gRA_rule_alignment = ' '.join(gRA_alignLst)
    return gRA_rule_alignment


def main():

    global TOT_TERMS
    global X1_only
    global X__Max
    if len(sys.argv) < 4 and len(sys.argv) > 6:
        print 'Usage: python %s <file_index> <dataDir> <outDir> [Total_terms on Fr side (def 5)] [True/False]' % (sys.argv[0])
        print 'Exiting!!\n'
        sys.exit()

    file_indx = sys.argv[1]
    dDir = sys.argv[2]
    oDir = sys.argv[3]

    if len(sys.argv) > 4:
        TOT_TERMS = int(sys.argv[4])
        if len(sys.argv) == 6 and (int(sys.argv[5]) >= 10 or int(sys.argv[5] < 1)): #Maryam
            print "Last argument should be an int indicating the maximum number of non-terminals" #Maryam
            sys.exit(1)
        #if len(sys.argv) == 6 and sys.argv[5] == 'True':  # True specifies that only one non-terminal is extracted; set False for two non-terminal case
         #   X1_only = True
        if len(sys.argv) == 6:  # sys.argv[5] specifies the No of non-terminal we can have in the rules (Maryam)
            X__Max = int(sys.argv[5])

    print "Using the French side total terms to be :", TOT_TERMS
    if not dDir.endswith("/"): dDir += "/"
    if not oDir.endswith("/"): oDir += "/"

    spanFile = dDir + file_indx + '.outspan'
    outFile  = oDir + file_indx + '.out'
    tgtFile  = oDir + 'tgt.' + file_indx + '.out'
    readPhraseSpan(spanFile, outFile, tgtFile)


if __name__ == '__main__':
    main()
