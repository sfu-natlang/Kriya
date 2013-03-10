## Reimplemetation of Parse class with LM integration and Cube Pruning ##

import sys

import settings
from cell import Cell
from hypothesis import Hypothesis
from featureManager import FeatureManager
from lazyMerge_CP import Lazy
from phraseTable import PhraseTable
from ruleItem import RuleItem

# Global variables
consObjsLst = []                # List of consequent-rule objects for a particular cell

class Parse(object):
    '''Parse class contains method for parsing a given source sentence'''

    chartDict = {}

    __slots__ = "sent_indx", "sent", "refsLst", "wordsLst", "sent_len", "sh_order", "relaxed_decoding"

    def __init__(self, sent_indx, p_sent, relaxed=False, refs=[]):
        Parse.chartDict = {}
        self.sent_indx = sent_indx
        self.sent = p_sent
        self.relaxed_decoding = relaxed
        self.refsLst = refs
        self.wordsLst = p_sent.split()
        self.sent_len = len( self.wordsLst )
        self.sh_order = settings.opts.sh_order
        if (self.relaxed_decoding):
            sys.stderr.write("INFO: Relaxing to full Hiero decoding for sentence# %d as Shallow-%d decoding failed." % (sent_indx, self.sh_order))

    def __del__(self):
        '''Clear the data-structures'''

        for chart_cell in Parse.chartDict.itervalues():
            chart_cell = ''
        del Parse.chartDict
        del self.wordsLst[:]
        del self.refsLst[:]

    def parse(self):
        'Parse the sentence passed in the argument'

        global consObjsLst
        final_cell = False
        glueSrcLst = ['X__1', 'S__1 X__2']

        # Phase-1: Initialization
        # Fill the initial axioms in the chartDict (Dict of dict) in corresponding word positions
        p_i = 0
        for p_word in self.wordsLst:
#            print "Span:", p_i, p_i, "\tSpan length: 1"
            if ( p_i == 0 and self.sent_len == 1 ):
                final_cell = True
            Parse.chartDict[(p_i, p_i)] = Cell()

            # if the word is UNK; add it to ruleDict as: X -> <w_i, w_i> with default prob
            if not PhraseTable.hasRule(p_word):
                (unk_score, unk_lm_heu, unk_featVec) = FeatureManager.unkRuleTup
                PhraseTable.addUNKRule( p_word, RuleItem.initUNKRule(p_word, unk_featVec, unk_score, unk_lm_heu) )

            # Known (X -> <w_i, w_t>) or unknown (X -> <w_i, w_i>) rules are now flushed to the chart
            self.__flush2Cell( (p_i, p_i), ('X', p_word), 0, self.__getRulesFromPT(p_word, (p_i, p_i)) )     # Flush the entries to the cell
            #Parse.chartDict[(p_i, p_i)].printCell('X', self.sent_indx)

            # Add the glue rule S --> <X__1, X__1> in cell (0, 0)
            if p_i == 0:
                p_src = glueSrcLst[0]
                self.__getGlueRuleSpans((p_i, p_i), p_src)
                if consObjsLst:
                    Parse.chartDict[(p_i, p_i)].setSTree()
                    self.__reduceCell((p_i, p_i), 'S', 'S', final_cell)   # Compute the n-best list from the parse forest
                    if settings.opts.force_decode:
                        force_dec_status = Parse.chartDict[(0, p_i)].forceDecodePrune(self.refsLst, final_cell)
                        if final_cell and not force_dec_status:
                            sys.stderr.write("           INFO  :: Force decode mode: No matching candidate found for cell (0, %d). Aborting!!\n" % (p_i))
                            return 0
                    #Parse.chartDict[(0, p_i)].printCell('S', self.sent_indx)

            p_i += 1

        # Phase-2: Filling the CKY table
        # Iterate through all possible spans of length 2 thro' M (maximum phrase length)
        for p_l in range(1, self.sent_len):
            for p_j in range(p_l, self.sent_len):
                p_i = p_j - p_l
#                print "\nSpan:", p_i, p_j, "\tSpan length:", p_l + 1
                # If the span length is greater than the 'maximum phrase length' skip to next iteration of p_l
                if p_l >= settings.opts.max_phr_len and p_i != 0: break

                Parse.chartDict[(p_i, p_j)] = Cell()
                p_cell_type = 'X'
                p_left_nt = 'X'
                if ( p_i == 0 and p_j == self.sent_len - 1 ):
                    final_cell = True
                if p_l < settings.opts.max_phr_len:
                    self.__getRuleSpans( p_i, p_j, ' '.join(self.wordsLst[p_i:p_j+1]) )

                if consObjsLst:
                    self.__reduceCell((p_i, p_j), p_cell_type, p_left_nt, final_cell)
                    #Parse.chartDict[(p_i, p_j)].printCell('X', self.sent_indx)

                # For span beginning at '0' (top row in the parse triangle), add items of the form [S, i, j]:w to chart
                # Glue rules are: S --> (X__1, X__1) and S --> (S__1 X__2, S__1 X__2)
                # Sentence boundary markers <s> and </s> are added in Cube-Pruning step (lazyMerge_CP.py)
                if p_i == 0:
                    p_cell_type = 'S'
                    p_left_nt = 'S'
                    for p_src in glueSrcLst: self.__getGlueRuleSpans((p_i, p_j), p_src)

                    if consObjsLst:
                        Parse.chartDict[(p_i, p_j)].setSTree()
                        self.__reduceCell((p_i, p_j), p_cell_type, p_left_nt, final_cell)
                    if settings.opts.force_decode:
                        force_dec_status = Parse.chartDict[(p_i, p_j)].forceDecodePrune(self.refsLst, final_cell)
                        if final_cell and not force_dec_status:
                            sys.stderr.write("           INFO  :: Force decode mode: No matching candidate found for cell (0, %d). Aborting!!\n" % (p_j))
                            return 0
                    #Parse.chartDict[(p_i, p_j)].printCell('S', self.sent_indx)

        p_j = self.sent_len - 1
        if not Parse.chartDict[(0, p_j)].has_S_tree:
            return 99
        Parse.chartDict[(0, p_j)].printNBest('S', self.sent_indx)       # Print the N-best derivations in the last cell
        if settings.opts.trace_rules > 0:
            #Parse.chartDict[(0, p_j)].trackRulesUsed('S')               # Track the rules used in the top-k translations
            Parse.chartDict[(0, p_j)].printTrace('S', self.sent)        # Prints the translation trace for the top-3 entries
        return 1

    def __getRuleSpans(self, i, j, span_phrase):
        '''Get the list of rules that match the phrase corresponding to the given span'''

        global consObjsLst
        matchLst = PhraseTable.findConsistentRules(span_phrase)

        for match in matchLst:
            rule = match[0]
            ## Terminal rule
            if len(match[1]) == 0:
                consObjsLst.append( ConsequentRule(rule) )

            ## Hierarchical rule with 1 NT
            elif len(match[1]) == 2:
                span1 = (match[1][0]+i, match[1][1]+i)
                if not Parse.chartDict[span1].has_X_tree: continue

                if settings.opts.shallow_hiero and not self.relaxed_decoding:     # for Shallow-n hiero
                    x_level = -1
                    for x_level_status in Parse.chartDict[span1].getXLevelStats(self.sh_order):
                        x_level += 1
                        if not x_level_status: continue
                        consObjsLst.append( ConsequentRule(rule, x_level, span1, (), x_level) )
                elif not settings.opts.shallow_hiero or self.relaxed_decoding:    # for Full-hiero/ relaxed decoding
                    consObjsLst.append( ConsequentRule(rule, 0, span1) )

            ## Hierarchical rule with 2 NTs
            elif len(match[1]) == 4:
                span1 = (match[1][0]+i, match[1][1]+i)
                span2 = (match[1][2]+i, match[1][3]+i)
                if not Parse.chartDict[span1].has_X_tree or not Parse.chartDict[span2].has_X_tree: continue

                if settings.opts.shallow_hiero and not self.relaxed_decoding:     # for Shallow-n hiero
                    X1Levels = Parse.chartDict[span1].getXLevelStats(self.sh_order)
                    X2Levels = Parse.chartDict[span2].getXLevelStats(self.sh_order)

                    x1_level = -1
                    top_x2_level = len(X2Levels) - 1
                    if X2Levels[top_x2_level]:
                        for x1_level_status in X1Levels:
                            x1_level += 1
                            if not x1_level_status or x1_level > top_x2_level: continue
                            consObjsLst.append( ConsequentRule(rule, top_x2_level, span1, span2, x1_level, top_x2_level) )

                    x2_level = -1
                    top_x1_level = len(X1Levels) - 1
                    if X1Levels[top_x1_level]:
                        for x2_level_status in X2Levels:
                            x2_level += 1
                            if not x2_level_status or x2_level > top_x1_level: continue
                            consObjsLst.append( ConsequentRule(rule, top_x1_level, span1, span2, top_x1_level, x2_level) )
                elif not settings.opts.shallow_hiero or self.relaxed_decoding:    # for Full-hiero/ relaxed decoding
                    consObjsLst.append( ConsequentRule(rule, 0, span1, span2) )

    def __getGlueRuleSpans(self, span, rule):
        '''Checks if the glue rule is consistent with the given span'''

        global consObjsLst
        if rule == 'X__1' and Parse.chartDict[span].has_X_tree:     ## for rule: S --> (X__1, X__1)
            if settings.opts.shallow_hiero and not self.relaxed_decoding:     # for Shallow-n hiero
                if settings.opts.free_glue:
                    consObjsLst.append( ConsequentRule(rule, 0, span) )
                elif Parse.chartDict[span].check4MaxDepthXRules(self.sh_order):
                    consObjsLst.append( ConsequentRule(rule, 0, span, (), self.sh_order) )
            elif not settings.opts.shallow_hiero or self.relaxed_decoding:    # for Full-hiero/ relaxed decoding
                consObjsLst.append( ConsequentRule(rule, 0, span) )
        else:
            """ S glue-rules: 'S --> [S__1 X__2]' and 'S --> <S__1 X__2>'
                These glue rules might have different sets of constituent spans possible.
                eg: (0,2) having (0,0)(1,2) & (0,1)(2,2). All such spans are combined as tuples in a list
            """
            for i in range( span[0], span[1] ):                     ## for  rule: S --> (S__1 X__2, S__1 X__2) or
                span1 = (span[0], i)                                ##      rule: S --> (S__1 X__2, X__2 S__1) or
                span2 = (i+1, span[1])                              ##      rule: X --> (X__1 X__2, X__1 X__2)

                # For 'S' glue rules it is enough to check the S and X antecedent spans
                if rule.startswith('S__1') and ( Parse.chartDict.has_key(span1) and Parse.chartDict[span1].has_S_tree ) and \
                        Parse.chartDict.has_key(span2) and Parse.chartDict[span2].has_X_tree:
                    if settings.opts.shallow_hiero and not self.relaxed_decoding:     # for Shallow-n hiero
                        if settings.opts.free_glue:
                            consObjsLst.append( ConsequentRule(rule, 0, span1, span2) )
                        elif Parse.chartDict[span2].check4MaxDepthXRules(self.sh_order):
                            consObjsLst.append( ConsequentRule(rule, 0, span1, span2, -1, self.sh_order) )
                    elif not settings.opts.shallow_hiero or self.relaxed_decoding:    # for Full-hiero/ relaxed decoding
                        consObjsLst.append( ConsequentRule(rule, 0, span1, span2) )

    def __reduceCell(self, span, cell_type, rule_nt, final_cell):
        '''Reduce the cell entries to merge products and build translations'''

        global consObjsLst          # Consequent Rules are to be processed in order: check 'X' rules and then 'S' rules

        src_side = ' '.join( self.wordsLst[span[0]:span[1]+1] ) # Get the source side of the span
        merge_obj = Lazy(self.sent_indx, span, cell_type, final_cell)
        cube_indx = 0
        cell_max_X_depth = 0
        for conseq_obj in consObjsLst:
            rule = conseq_obj.rule
            cube_depth_hier = 0 if (not conseq_obj.spanTup or cell_type == 'S') else conseq_obj.top_X_level + 1
            ruleRHSLst = self.__getRulesFromPT(rule, span)
            if not ruleRHSLst: continue

            # Set the maximum depth of the current Cell
            if cell_type == 'X' and cube_depth_hier > cell_max_X_depth: cell_max_X_depth = cube_depth_hier

            # set the source side rule and span for the current cube
            Lazy.setSourceInfo( merge_obj, cube_indx, rule, conseq_obj.spanTup, cube_depth_hier, self.refsLst )
            # add the consequent item to the cube as its first dimension
            Lazy.add2Cube( merge_obj, cube_indx, ruleRHSLst )

            # add the rules for the sub-spans
            if rule.find('X__1') != -1 or rule.startswith('S__1'):  # process the rules having a non-terminal
                s_indx = 0
                for rterm in rule.split():
                    if rterm.startswith('X__'): left_side = 'X'
                    elif rterm.startswith('S__'): left_side = 'S'
                    else: continue
              
                    # add the antecedent item(s) of the sub-spans in the derivation
                    s_span = conseq_obj.spanTup[s_indx]
                    s_depth = conseq_obj.depth1 if s_indx == 0 else conseq_obj.depth2
                    Lazy.add2Cube( merge_obj, cube_indx, Parse.chartDict[s_span].getTupLst4NT(left_side, s_depth) )
                    s_indx += 1
            cube_indx += 1

        tgtLst = Lazy.mergeProducts(merge_obj)
        self.__flush2Cell( span, (rule_nt, src_side), cell_max_X_depth, tgtLst)   # Flush the entries to the cell
        merge_obj = ''  # Important: This clears the mem-obj and calls the garbage collector on Lazy()
        del consObjsLst[:]

    def __getRulesFromPT(self, s_rule, span):
        ''' Get the rules from the Phrase table and create new entry object for each rule returned by phrase table '''

        tgtLst = PhraseTable.getRuleEntries(s_rule, self.sent_indx)
        newTgtLst = []
        for r_item in tgtLst:
            new_entry = Hypothesis.createFromRule(r_item, span)
            newTgtLst.append(new_entry)

        return newTgtLst

    def __flush2Cell(self, span, key, cell_max_X_depth, tgtLst):
        '''Flush the entries (dictionary entries/ candidate hypotheses) to the cell'''

        if tgtLst:
            if key[0] == 'S': Parse.chartDict[span].setSTree()
            elif key[0] == 'X':
                Parse.chartDict[span].setXTree()
                Parse.chartDict[span].setTopXLevel(cell_max_X_depth)

        Parse.chartDict[span].add2Cell(key, tgtLst)


class ConsequentRule(object):

    __slots__ = "rule", "spanTup", "top_X_level", "depth1", "depth2"

    def __init__(self, rule, top_rule_level=0, span1=(), span2=(), depth1=-1, depth2=-1):
        self.rule = rule
        self.top_X_level = top_rule_level
        self.depth1 = depth1
        self.depth2 = depth2

        spanLst = []
        if span1: spanLst.append(span1)
        if span2: spanLst.append(span2)
        self.spanTup = tuple( spanLst )
