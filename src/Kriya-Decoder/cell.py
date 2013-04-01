
import operator
import sys

from featureManager import FeatureManager
from hypothesis import Hypothesis
import settings

class Cell(object):
    '''Class for representing individual cells of the parse triangle'''

    __slots__ = "table", "top_X_level", "has_X_tree", "has_S_tree", "sent_scored"

    def __init__(self):
        self.table = {}
        self.top_X_level = 0
        self.has_X_tree = False
        self.has_S_tree = False
        self.sent_scored = False

    def add2Cell(self, key, entryLst):
        '''Adds the derived entries along with the key in the corresponding cell of the table'''

        if not self.table.has_key(key): self.table[key] = []
        for entry in entryLst:
            self.table[key].append( entry )

    def setTopXLevel(self, top_X_rule_depth):
        self.top_X_level = top_X_rule_depth

    def setXTree(self, status=True):
        self.has_X_tree = status

    def setSTree(self, status=True):
        self.has_S_tree = status

    def check4LeftNT(self, left_side):
        '''Checks if any of the entries in the cell has non-terminal 'X' or 'S' on left-side'''
        '''Obselete: replaced by flags: has_X_tree and has_S_tree'''

        for key in self.table.iterkeys():
            if key[0] == left_side: return True
        return False

    def pruneRules(self):
        '''Prune the rules entries (lexical cells)'''

        if self.table.keys() is not None:
            for key in self.table.iterkeys():
                if len(self.table[key]) > settings.opts.ttl:
                    del self.table[key][settings.opts.ttl:]

    def forceDecodePrune(self, refsLst, last_cell=False):
        '''Prune the top-level cells for force decoding'''

        left_side = 'S'             # forceDecodePrune() can only be used in 'S' cells for 'S' derivations
        for key in self.table.iterkeys():
            if key[0] != left_side: continue
            cand_indx = 0
            for cand in self.table[key][:]:
                matches_ref = False
                cand_tgt = Hypothesis.getHypothesis(cand)
                for ref_i in refsLst:
                    if (not last_cell and ref_i.startswith(cand_tgt)) or (last_cell and ref_i == cand_tgt):
                        matches_ref = True
                        break
                if not matches_ref: del self.table[key][cand_indx]
                else: cand_indx += 1

            # If all the entries are deleted, then there will be no S derivations in the cell; set has_S_tree as False
            if not self.table[key]: self.has_S_tree = False
        return self.has_S_tree

    def printCell(self, cell_type, sent_indx):
        '''Print the entries of the cell in sorted order (for debugging)'''

        if ((cell_type == 'X' and not self.has_X_tree) or (cell_type == 'S' and not self.has_S_tree)):
            return None

        tgt_key = self.calcCandScore(cell_type)
        print "*  Total entries in cell : %d" % ( len(self.table[tgt_key]) )
        i = 0
        for ent_obj in self.table[tgt_key][:]:
            (cand, feat_str) = ent_obj.printEntry()
            print "**  %s ||| %s ||| %g ||| %g ||| %s" % ( cand, feat_str, ent_obj.getScoreSansLmHeu(), \
                                                           ent_obj.score, self.getBPTrace(ent_obj) )
            i += 1
            if i == 5: break
        print

    def getBPTrace(self, ent_obj):
        '''Get the Back-Pointer trace'''

        bp_trace = []
        hypTraceStack = []
        hypTraceStack.append(ent_obj)

        while ( hypTraceStack ):
            trace_entry = hypTraceStack.pop(0)
            for back_pointer in trace_entry.bp:
                hypTraceStack.insert(0, back_pointer)
            bp_trace += (trace_entry.inf_cell,)

        return bp_trace

    def trackRulesUsed(self, cell_type):
        '''Track the rules used in the top-k translations in the last cell'''

        cand_cnt = 0
        hypTraceStack = []
        rulesUsedDict = {}
        tgt_key = self.calcCandScore(cell_type)
        for entry in self.table[tgt_key][:]:

            hypTraceStack.append(entry)
            while ( hypTraceStack ):
                trace_entry = hypTraceStack.pop(0)
                for back_pointer in trace_entry.bp:
                    hypTraceStack.insert(0, back_pointer)
                inf_rule = trace_entry.inf_rule
                if inf_rule is not None:
                    src = inf_rule.src
                    tgt = inf_rule.tgt
                else:
                    src = trace_entry.src
                    tgt = trace_entry.getHypothesis()

                rule = src + " ||| " + tgt
                if ( rulesUsedDict.has_key(rule) ): rulesUsedDict[rule] += 1
                else: rulesUsedDict[rule] = 1
            cand_cnt += 1
            del hypTraceStack[:]
            if cand_cnt >= settings.opts.trace_rules: break

        traceFile = settings.opts.outFile + ".trace"
        tF = open(traceFile, 'a')
        for rule, r_cnt in sorted(rulesUsedDict.iteritems(), key=operator.itemgetter(1)):
            tF.write( "%s ||| %d\n" % (rule, r_cnt) )
        tF.close()

    def printTrace(self, cell_type, src_sent):
        '''Prints the trace for top entries (as defined by settings.opts.trace_rules) in the cell (for debugging)'''

        traceFile = settings.opts.outFile + ".trace"
        tF = open(traceFile, 'a')

        nbest_cnt = 0
        hypTraceStack = []
        tgt_key = self.calcCandScore(cell_type)
        for entry in self.table[tgt_key][:]:

            tF.write("TRACE_BEGIN\n")
            hypTraceStack.append(entry)
            tF.write( "#Input  :: %s\n" % (src_sent) )
            tF.write( "#Output :: %s ||| %s\n" % (Hypothesis.getHypothesis(entry), Hypothesis.getFeatVec(entry)) )

            while ( hypTraceStack ):
                trace_entry = hypTraceStack.pop(0)
                for back_pointer in trace_entry.bp:
                    hypTraceStack.insert(0, back_pointer)
                inf_rule = trace_entry.inf_rule
                if inf_rule is not None:    # Non-leaf nodes in derivation
                    tF.write( "%s ||| %s ||| %s ||| %s\n" % ( inf_rule.src, inf_rule.tgt, Hypothesis.getFeatVec(trace_entry), trace_entry.inf_cell ) )
                else:                       # Leaf nodes in derivation
                    tF.write( "%s ||| %s ||| %s |||| %s\n" % ( trace_entry.src, Hypothesis.getHypothesis(trace_entry), Hypothesis.getFeatVec(trace_entry), trace_entry.inf_cell ) )

            tF.write("TRACE_END\n")
            nbest_cnt += 1
            del hypTraceStack[:]
            if nbest_cnt == settings.opts.trace_rules: break
        tF.close()

    def printNBest(self, cell_type, sent_indx):
        '''Print the N-best list for the goal symbol'''

        nbest_cnt = 0
        #uniq_tgtDict = {}
        oF = open(settings.opts.outFile, 'a')

        tgt_key = self.calcCandScore(cell_type)
        entriesLst = []
        if settings.opts.nbest_extremum == 0:
            nbest_2_produce = settings.opts.nbest_limit
            entriesLst = self.table[tgt_key][:]
        else:
            nbest_2_produce = 2 * settings.opts.nbest_extremum
            # Get nbest_extreumum best and worst entries from the nbest-list
            #if len( self.table[tgt_key][:] ) >= settings.opts.nbest_limit:
            #    entriesLst = self.table[tgt_key][0:settings.opts.nbest_extremum] + \
            #                    self.table[tgt_key][settings.opts.nbest_limit-settings.opts.nbest_extremum:settings.opts.nbest_limit]
            #elif len( self.table[tgt_key][:] ) >= nbest_2_produce:
            if len( self.table[tgt_key][:] ) >= nbest_2_produce:
                entriesLst = self.table[tgt_key][0:settings.opts.nbest_extremum] + self.table[tgt_key][-settings.opts.nbest_extremum:]
            else: entriesLst = self.table[tgt_key][:]

        for entry in entriesLst:
            if not settings.opts.nbest_format:
                oF.write( "%s\n" % entry.getHypothesis() )
            else:
                (cand, feat_str) = entry.printEntry()
                oF.write( "%d||| %s ||| %s ||| %g\n" % ( sent_indx, cand, feat_str, entry.score ) )
                #if not settings.opts.use_unique_nbest:
                #    oF.write( "%d||| %s ||| %s ||| %g\n" % ( sent_indx, cand, feat_str, entry.score ) )
                #elif settings.opts.use_unique_nbest and not uniq_tgtDict.has_key(cand):
                #    uniq_tgtDict[cand] = 1
                #    oF.write( "%d||| %s ||| %s ||| %g\n" % ( sent_indx, cand, feat_str, entry.score ) )

            nbest_cnt += 1
            if nbest_cnt == nbest_2_produce: break  # stop after producing required no of items
        oF.close()

    def calcCandScore(self, cell_type):
        '''Calculates the candidate scores for the entries given a left NT (for printNBest)'''

        tgt_key = ''

        for key in self.table.iterkeys():
            if key[0] == cell_type:
                # If the sentence scores were caculated earlier; return tgt_key as key
                if self.sent_scored:
                    tgt_key = key
                    break

                # Sort the entries based on the candidate score
                self.sort4CandScore(key)
                tgt_key = key
                break
        if tgt_key == '':
            raise RuntimeWarning, "Decoder did not produce derivations of the specified type in the present cell"
        return tgt_key

    def sort4CandScore(self, key):
        '''Sort the cell entries based on their candidate scores for a given key'''

        self.table[key].sort(key=operator.attrgetter("score"), reverse=True)

    def check4MaxDepthXRules(self, max_depth):
        """ Checks the cell for X rules of maximum depth. Shallow-n decoding allows only max depth X antecedents for S items
        """

        left_side = "X"
        for key in self.table.iterkeys():
            if key[0] != left_side: continue

            for entry in self.table[key]:
                if entry.depth_hier == max_depth: return True

        return False

    def getXLevelStats(self, sh_order):
        """ Checks and return the stats about the levels for different X-rules in the current span.
            This is used only for Shallow-n Hiero, particularly in X productions.
            Returns a list of boolean flags for each level of X-rules in the current span upto the top_X_level.
            Each flag can be True (if at least one terminal 'X' entry is found) or false (otherwise).
        """

        left_side = "X"
        for key in self.table.iterkeys():
            if key[0] != left_side: continue

            found_levels = 0
            curr_depth = self.top_X_level + 1 if self.top_X_level < sh_order else sh_order
            XLevels = [False for i in xrange(curr_depth)]
            for entry in self.table[key]:
                entry_depth = entry.depth_hier
                if entry_depth < curr_depth:
                    try:
                        if not XLevels[entry_depth]:
                            XLevels[entry_depth] = True
                            found_levels += 1
                    except IndexError:
                        sys.stderr.write("ERROR: Index Out of Range error in cell.py : 291\n")
                        sys.stderr.write("       Index %d exceeds the size of array XLevels (%d). Exiting!!\n" % (entry_depth, curr_depth))
                        sys.exit(1)
                if (found_levels == curr_depth): break

            return XLevels

    def getTupLst4NT(self, left_side, nt_depth):
        '''Given the left-side of the rule, get the list of tuples (of probabilities, target and back-pointers)'''

        for key in self.table.iterkeys():
            if key[0] == left_side:
                if not settings.opts.shallow_hiero or nt_depth == -1:
                    return self.table[key][:]
                else:
                    entriesLst = []
                    for entry in self.table[key]:
                        if (entry.depth_hier == nt_depth): entriesLst.append( entry )
                    return entriesLst
