## This program extracts a Synchronous CFG rules from the word alignments of a parallel corpus ##

import sys
from zgc import zgc

# Constants
max_phr_len = 10              # Maximum phrase length
#tot_lex_term = 4              # Maximum no of lexical terms in Glue rules
max_non_term = 2              # Maximum no of non-terminals in rules 
tot_src_terms = 7             # Total no of terms (terminals & non-terminals incl) in source side
X1_only = False               # Flag for deciding whether to generate one non-termianl or two non-terminal rules
weight_rules = False          # When distributing the unit-count among the rules, should it be weighted by the # of rule occurrences
tight_phrases_only = True     # Restrict the rule extraction strictly to tighter phrases

# Global Variables
rule_indx = 1
tot_rules_derived = 0

srcWrds = []
tgtWrds = []
srcSentlen = 0
tgtSentLen = 0
ruleDict = {}                 # dictionary of rules for each sentence, ruleDict[(src, tgt)] = estimated rule count (1.0 for initial phrase pairs at the begining)
ruleDoD = {}                  # dictionary of rules for each span, ruleDict[(i, j)] = {(src, tgt):1,...}
nonTermRuleDoD = {}           # dictionary of rules for each span, which just contains non-terminals on target side
alignDoD = {}                 # Dict of dict to store fwd alignments
revAlignDoD = {}              # Dict of dict to store rev alignments
sentInitDoD = {}              # Dict of dict for storing initial phrase pairs, sentInitDoD[src_len] = {(src,tgt):1,...} (tuples of source and target spans)
rightTgtPhraseDict = {}
tgtPhraseDict = {}
ppairRulesSet = set([])

tgtCntDict = {}
ruleIndxCntDict = {}
fAlignDoD = {}
rAlignDoD = {}


def readSentAlign(spanFile, outFile, tgtFile):
    'Reads the input phrase span file for src & tgt sentences, alignment and initial phrases'

    global tight_phrases_only, nonTermRuleDoD
    global ruleDict, ruleIndxCntDict, tgtCntDict, phrPairLst, tgtPhraseDict
    global srcWrds, tgtWrds, srcSentlen, tgtSentLen, rightTgtPhraseDict, sentInitDoD
    sent_count = 0
    phrLst = []
    aTupLst = []

    print "Reading the span file :", spanFile
    inF = open(spanFile, 'r')
    for line in inF:
        line = line.strip()
        if line.startswith('LOG: SRC: '):             # Read the source sentence
            src = line.replace('LOG: SRC: ', '')
            srcWrds = src.split()
            srcSentlen = len(srcWrds)
        elif line.startswith('LOG: TGT: '):           # Read the target sentence
            tgt = line.replace('LOG: TGT: ', '')
            tgtWrds = tgt.split()
            tgtSentLen = len(tgtWrds)
        elif line.startswith('LOG: ALT:'):           # Read the source-target alignment
            align = line.replace('LOG: ALT:', '')
            align = align.strip()
            for align_pos in align.split():
                m = align_pos.split('-')
                e = -1 if m[0] == 'Z' else int(m[0])
                f = -1 if m[1] == 'Z' else int(m[1])
                aTupLst.append((e, f))
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
            align_tree = zgc(max_phr_len)
            phrPairLst = align_tree.getAlignTree(srcSentlen, tgtSentLen, aTupLst)
            if max_phr_len >= srcSentlen and not ((0, srcSentlen-1),(0, tgtSentLen-1)) in phrPairLst:
                phrPairLst.append(((0, srcSentlen-1),(0, tgtSentLen-1)))
            sentInitDoD = {}
            tgtPhraseDict = {}
            nonTermRuleDoD = {}
            for ppair in phrPairLst:
                unaligned_edge = False
                # If the boundary term of source or target phrase has an unaligned word, ignore the phrase-pair
                # Earlier bug fixed on March '09
                # Unless the tight-phrase options is set to False
                if not alignDoD.has_key( str(ppair[0][0]) ) or not revAlignDoD.has_key( str(ppair[1][0]) ) or \
                        not alignDoD.has_key( str(ppair[0][1]) ) or not revAlignDoD.has_key( str(ppair[1][1]) ):
                    if tight_phrases_only: continue
                    else: unaligned_edge = True                
                
                
                init_phr_pair = (' '.join( [str(x) for x in xrange(ppair[0][0], ppair[0][1]+1) ] ), \
                        ' '.join( [str(x) for x in xrange(ppair[1][0], ppair[1][1]+1)] ) )
                if unaligned_edge:
                    ruleDict[init_phr_pair] = 1.0
                    continue
                
                # Create a dict of dict for storing initial phrase pairs (tuples of source and target spans)
                tphr_len = ppair[1][1] - ppair[1][0] + 1
                if not sentInitDoD.has_key(tphr_len):
                    sentInitDoD[tphr_len] = {}
                sentInitDoD[tphr_len][ppair] = init_phr_pair
                tgtPhraseDict[ppair[1]] = ppair
                nonTermRuleDoD[ppair[1]] = {}
                nonTermRuleDoD[ppair[1]][("X__1","X__1")] = 1
            computeRightTgtPhr()
            xtractRules()
            #printSentRules()
            
            # For every extracted rule call the function compFeatureCounts() to:
            #   i. convert the word positions in the rules into lexical entries, and
            #   ii. find the alignment for the rule and compute the joint count p(s, t)
            for rule in ruleDict.keys(): compFeatureCounts(rule)            
            
            # Clear the variables at the end of current sentence
            alignDoD.clear()
            revAlignDoD.clear()
            ruleDict.clear()
            ruleDoD.clear()
            sentInitDoD.clear()
            rightTgtPhraseDict.clear()
            tgtPhraseDict.clear()
            nonTermRuleDoD.clear()
            del aTupLst[:]
            sent_count += 1
            print sent_count
            if sent_count % 1000 == 0:
                print "Sentences processed : %6d ..." % sent_count
        else:
            continue  #temporary
           
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

def computeRightTgtPhr():
    ''' fill the table rightTgtPhraseDict. For each possible span it keeps the largest 
    subphrase which shares the right boundary on target side. '''
    
    global rightTgtPhraseDict, tgtSentLen, tgtPhraseDict, sentInitDoD
    rightTgtPhraseDict = {}
    for l in xrange(2, tgtSentLen+1):
        for i in xrange(0,tgtSentLen-l+1):
            j = i+l-1
            if l-1 in sentInitDoD and (i+1, j) in tgtPhraseDict:
                rightTgtPhraseDict[(i,j)] = tgtPhraseDict[(i+1, j)]
            elif (i+1, j) in rightTgtPhraseDict:
                rightTgtPhraseDict[(i,j)] = rightTgtPhraseDict[(i+1, j)]
            #if (i, j) in rightTgtPhraseDict:
            #    print (i, j), " : ", rightTgtPhraseDict[(i, j)]
            
def printSentRules():
    global sentInitDoD, ruleDoD, tgtSentLen, ruleDict
    for tphr_len in xrange(1, tgtSentLen+1):
        if tphr_len in sentInitDoD:
            print "\nTARGET LENGTH:  ", tphr_len, "\n"
            for phr_pair in sentInitDoD[tphr_len]:
                print "Rules extracted from: ", phr_pair, sentInitDoD[tphr_len][phr_pair]
                for rule in ruleDoD[phr_pair[1]]:
                    try:
                        print " ||| ".join([rule[0], rule[1], str(ruleDict[rule])])
                    except KeyError:
                        print " ||| ".join([rule[0], rule[1], "0"])

def xtractRules():
    ''' Extract the rules for different phrase lengths (from smallest to longest) '''
    global srcSentlen, tgtSentLen, sentInitDoD, ruleDoD, rightTgtPhraseDict
    for tphr_len in xrange(1, tgtSentLen+1):
        if sentInitDoD.has_key(tphr_len):
            for phr_pair in sentInitDoD[tphr_len]:
                tgt_tuple = phr_pair[1]
                ruleDoD[tgt_tuple] = {}                 #target side of the phrase pair
                genRule4Phrase(sentInitDoD[tphr_len][phr_pair], phr_pair)

def genRule4Phrase(phrPairStr, (src_tuple, tgt_tuple)):
    global ruleDict, ruleDoD, sentInitDoD, rightTgtPhraseDict, ppairRulesSet, tgtPhraseDict
    
    ruleDoD[tgt_tuple] = {}   
    ppairRulesSet = set()
    if checkRuleConfigure(phrPairStr):
        #ruleDoD[tgt_tuple][phrPairStr] = 1         # we do not need to add terminal rules to ruleDoD :-?
        #ruleDict[phrPairStr] = 1.0
        ppairRulesSet.add(phrPairStr)
        
    (startP, endP) = tgt_tuple
    curr_rule_lst = set()
    curr_rule_lst.add(phrPairStr)         # it is a set, because current rule can be more than one rule (if there is unaligned src words)
    
    while endP >= startP:
        if (startP, endP) not in rightTgtPhraseDict:  break
        rtgt_phr_span = rightTgtPhraseDict[(startP, endP)]
        # generating rules by replacing the right most sub-phrase with its rules
        substituteRuleSet(curr_rule_lst, rtgt_phr_span)       
        # updating current rule list by replacing whole sub-phrase with one (or list of) non-terminal
        curr_rule_lst = substituteRuleSet(curr_rule_lst, rtgt_phr_span, "X")        
        
        if curr_rule_lst is None or len(curr_rule_lst) == 0: # it is not possible to generate more rule
            break
        endP = rtgt_phr_span[1][0] - 1

    # distribute unit rule count among rules extracted from this phrase pair
    ruleNo = len(ppairRulesSet)
    if ruleNo == 0: 
        return 
    ruleCount = 1.0/float(ruleNo)
    for rule in ppairRulesSet:
        if rule[1].startswith("X__"):
            nonTermRuleDoD[tgt_tuple][rule] = 1
            continue    #target side does not have any terminal
        if not checkRuleConfigure(rule): continue
        ruleDoD[tgt_tuple][rule] = 1
        if rule in ruleDict: ruleDict[rule] += ruleCount
        else: ruleDict[rule] = ruleCount
    if phrPairStr in ppairRulesSet and ruleCount < 1.0:
        ruleDict[phrPairStr] += 1.0
        
    # updating right most tgt phrase for this tgt
    rightTgtPhraseDict[tgt_tuple] = (src_tuple, tgt_tuple)
        
def checkRuleConfigure((src_phr, tgt_phr), isNonTerm=False):
    'Checks if the rule configuration is compatible with the constraints (for both src & tgt sides)'
    global max_non_term, tot_src_terms
    # source lenght
    if len(src_phr.split()) > tot_src_terms: return False
    # no of non-terminals
    if isNonTerm and tgt_phr.startswith("X__"): return True
    max_x = findMaxNonTerm(src_phr)
    if max_x > max_non_term:  return False 
    return True

def substituteRuleSet(main_rule_lst, sub_ppair_span, isNonTerm = None):
    ''' input: a list of main rules and a subphrase [if isNonTerm == 'X' substituting subphrase with a list of non-terminals]
        task:  substituting subphrase with its rules in the main rules
               updating the final main rules by substituting the subphrase with a non-terminal
               returning updated main rules (or None, if it is not possible)'''
    
    global ppairRulesSet, ruleDoD, nonTermRuleDoD

    len_tgt_phr = sub_ppair_span[1][1] - sub_ppair_span[1][0] +1
    sub_phr = sentInitDoD[len_tgt_phr][sub_ppair_span]                        # retrive subphrase using its span        
    update_rule_lst = set()
    if isNonTerm: local_rule_dict = nonTermRuleDoD[sub_ppair_span[1]]
    else:         local_rule_dict = ruleDoD[sub_ppair_span[1]]
    
    for main_rule in main_rule_lst:
        max_x = findMaxNonTerm(main_rule[0])
        if not isNonTerm and max_x >= max_non_term:       # rule cannot have more non-terminal
            continue
    
        left_bound_src = main_rule[0].find(sub_phr[0])                            # find boundaries subphrase on src side 
        right_bound_src = left_bound_src + len(sub_phr[0])
        left_bound_tgt = main_rule[1].find(sub_phr[1])                            # find boundaries subphrase on tgt side
        right_bound_tgt = left_bound_tgt + len(sub_phr[1])
    
        # left and right part of main rule (for later rule construction)
        right_src_main = main_rule[0][right_bound_src:].strip()                   
        right_tgt_main = main_rule[1][right_bound_tgt:].strip()
        left_src_main = main_rule[0][:left_bound_src].strip()
        left_tgt_main = main_rule[1][:left_bound_tgt].strip()
    
        start_x = findMaxNonTerm(main_rule[0], 0, left_bound_src)
        
        # check if the first (last) term in right (left) part of source rule is non-terminal (to check the filtering constraints)
        right_non_term = True if right_src_main.startswith("X__") else False
        left_non_term = True if left_src_main.endswith("X__"+str(start_x)) else False
    
        for rule in local_rule_dict:
            mid_x = findMaxNonTerm(rule[0])
            if mid_x == 0 or (not isNonTerm and (mid_x+max_x) > max_non_term): continue        # (does not create new rule) or (more than maximum non-terminals)
        
            #check adjacent non-terminals on src side
            if not isNonTerm and ( (right_non_term and rule[0].endswith("X__"+str(mid_x))) or \
               (left_non_term and rule[0].startswith("X__1")) ):
                continue
        
            mid_src_phr = updateNonTerms(rule[0], start_x)
            mid_tgt_phr = updateNonTerms(rule[1], start_x)
            
            right_src_phr = updateNonTerms(right_src_main, mid_x)
            right_tgt_phr = updateNonTerms(right_tgt_main, mid_x, start_x)
            new_rule = ((" ".join([left_src_main, mid_src_phr, right_src_phr]).strip()), \
                        " ".join([left_tgt_main, mid_tgt_phr, right_tgt_phr]).strip())
            #if checkRuleConfigure(new_rule, isNonTerm):
            if (right_non_term and rule[0].endswith("X__"+str(mid_x))) or \
                      (left_non_term and rule[0].startswith("X__1")):
                pass
            else:
                ppairRulesSet.add(new_rule)      
                update_rule_lst.add(new_rule)
                
            # if the subphrase is replaced with just non-terminal:
            #    check if the first two nonterminals on the target side can be merge 
            #    (if there are just unaligned words between corresponding non-terminals on the src side)
            if isNonTerm:
                new_rule_lst = iterativeMerge(new_rule, start_x+1)
                for new_rule in new_rule_lst:
                    #if checkRuleConfigure(new_rule, isNonTerm):
                    ppairRulesSet.add(new_rule)
                    update_rule_lst.add(new_rule)
            
    return update_rule_lst


def iterativeMerge(rule, no_x):
    '''Check if begining nonterminals in target side of rule can be merged to create different rules'''
    global alignDoD
    curr_rule = rule
    new_rules = set()
    
    first_x = curr_rule[1].find("X__")   # tgt might start with some terminal term
    if first_x < 0 : return new_rules
    
    while True:
        t_words = curr_rule[1][first_x:].split()
        if len(t_words) < 2: break    
        find_phr_flag = False
        max_x = int(t_words[0][3:])
        min_x = max_x
        for i in xrange(1,len(t_words)):
            x_ind = int(t_words[i][3:])
            if x_ind < min_x: min_x = x_ind
            elif x_ind > max_x: max_x = x_ind
            new_r = mergeNonTerms(curr_rule, t_words[:i+1], min_x, max_x)
            if new_r:
                new_rules.add(new_r)
                find_phr_flag = True
                break
        if not find_phr_flag: return new_rules
        curr_rule = new_r
    return new_rules

def mergeNonTerms(rule, t_words, min_x, max_x):
    ''' Replacing a list of non-terminals t-words (with max and min nonterminals given) in the given rule '''
    curr_x = "X__"+str(min_x)
    next_x = "X__"+str(max_x)
    s = rule[0].find(curr_x)+5
    e = rule[0].find(next_x)-1    
    aligned = False
    for w in rule[0][s:e].strip().split():
        if w in alignDoD or (w.startswith("X__") and w not in t_words):
            aligned = True
            break
    if aligned: return None
    # find the right and left part of src (including the min non-terminal of the phrase)
    right_src = rule[0][min(e+6, len(rule[0])):].strip()
    right_src = updateNonTerms(right_src, min_x-max_x)
    left_src = rule[0][:s].strip()
    # find the right and left part of tgt     
    s = rule[1].find(t_words[0])
    e = rule[1].find(t_words[-1])+5
    right_tgt = rule[1][min(e, len(rule[1])):].strip()
    right_tgt = updateNonTerms(right_tgt, min_x-max_x, min_x)
    left_tgt = rule[1][:s].strip()
    return (" ".join([left_src,right_src]).strip(), " ".join([left_tgt, curr_x, right_tgt]).strip())
            
def updateNonTerms(phrase, add_x, start_x=0):
    if add_x == 0 or phrase.find("X__") < 0:
        return phrase
    tmpLst = []
    for w in phrase.split():
        if w.startswith("X__") and int(w[3:]) > start_x:
            tmpLst.append("X__"+str(add_x+int(w[3:])))
        else:
            tmpLst.append(w)    
    return " ".join(tmpLst)

def findMaxNonTerm(phrase, s=None, e=None):
    '''Find the index of bigest non-terminal in phrase[s:e] (the whole phase if s or e is not defined)'''
    if s !=None and e != None:
        start_x = phrase.rfind("X__", s, e)
    else: start_x = phrase.rfind("X__")
    
    if start_x > -1: start_x = int(phrase[start_x+3:min(start_x+5, len(phrase))])
    else: start_x = 0
    
    return start_x
        
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
    global tot_src_terms, max_non_term, max_phr_len
    global X1_only
    if len(sys.argv) < 4 or len(sys.argv) > 8:
        print 'Usage: python %s <file_index> <dataDir> <outDir> [max phrase length (def 10)] [Total_terms on Fr side (def 7)] [max non-terminals (def 2)] [True/False]' % (sys.argv[0])
        print 'Exiting!!\n'
        sys.exit()

    file_indx = sys.argv[1]
    dDir = sys.argv[2]
    oDir = sys.argv[3]

    if len(sys.argv) > 4:
        max_phr_len = int(sys.argv[4])
        if max_phr_len < 0: max_phr_len = 200               # all phrase pairs
        if len(sys.argv) > 5: 
            tot_src_terms = int(sys.argv[5])
        if len(sys.argv) > 6: 
            max_non_term = int(sys.argv[6])        
        if len(sys.argv) == 8 and sys.argv[7] != 'True' and sys.argv[7] != 'False':
            print "Last argument should be a boolean True/False indicating tight/loose phrase pairs case"
            sys.exit(1)
        if len(sys.argv) == 8 and sys.argv[7] == 'False':   # False relaxes the tight phrase pairs constraint and enables the model to extract rules from loose phrases as well
            tight_phrases_only = False
            
    print "Using the maximum phrse lenght             :", max_phr_len
    print "Using the French side total terms to be    :", tot_src_terms
    print "Using the mximum no of non-terminals to be :", max_non_term
    print "Enforcing tight phrase-pairs constraint    :", tight_phrases_only
    if not dDir.endswith("/"): dDir += "/"
    if not oDir.endswith("/"): oDir += "/"

    spanFile = dDir + file_indx + '.outspan'
    outFile  = oDir + file_indx + '.out'
    tgtFile  = oDir + 'tgt.' + file_indx + '.out'
    readSentAlign(spanFile, outFile, tgtFile)


if __name__ == '__main__':
    main()
