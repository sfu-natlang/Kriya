
import sys

import operator
import settings
from entry_CP import Entry


class Cell(object):
    '''Class for representing individual cells of the parse triangle'''

    __slots__ = "table", "top_X_level", "has_X_tree", "has_S_tree", "sent_scored", "fullTable"

    def __init__(self):
        self.table = {}
        self.top_X_level = 0
        self.has_X_tree = False
        self.has_S_tree = False
        self.sent_scored = False
	self.fullTable = []

    def __del__(self):
        del self.table
	del self.fullTable

    def __len__(self):
	return len(self.fullTable)

    def add2Cell(self, key, entryLst):
        '''Adds the derived entries along with the key in the corresponding cell of the table'''

        if not self.table.has_key(key): self.table[key] = []
        for entry in entryLst:
            self.table[key].append( entry )
	    entry.scoreCandidate()
	    if self.fullTable[-1].cand_score < entry.cand_score:
		self.sent_scored = False
	    self.fullTable.append(entry)

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
        '''Prune the rules entries (lexical cells); it is not used in LR-Heiro'''

        if self.table.keys() is not None:
            for key in self.table.iterkeys():
                if len(self.table[key]) > settings.opts.ttl:
                    del self.table[key][settings.opts.ttl:]

    def forceDecodePrune(self, refsLst, last_cell=False):
        '''Prune the top-level cells for force decoding'''

	newTable = []
        for cand in self.fullTable:
                matches_ref = False
                cand_tgt = Entry.getHypothesis(cand)
                for ref_i in refsLst:
                    if (not last_cell and ref_i.startswith(cand_tgt)) or (last_cell and ref_i == cand_tgt):
                        matches_ref = True
                        break
                if matches_ref:
			newTable.append(cand)
	del self.fullTable
	self.fullTable = newTable
	self.groupCands()	#update self.table
        # If all the entries are deleted, then there will be no S derivations in the cell; set has_S_tree as False
        #if len(self.fullTable) == 0: self.setSTree(False)
        #return self.has_S_tree
        if len(self.fullTable) == 0: return False
	return True

    def printCell(self, sent_indx):
        '''Print the entries of the cell in sorted order (for debugging)'''

	self.sortAllCand()
        print "*  Total entries in cell : %d" % ( len(self.fullTable) )
        i = 0
        for entry in self.fullTable:
            (cand, feat_str, cand_score) = Entry.printEntry(entry)
            print "**  %s ||| %s ||| %f ||| %f ||| %s" % ( cand, feat_str, cand_score, Entry.getHypScore(entry), self.getBPTrace(entry) )
            i += 1
            if i == 5: break
        print

    def getBPTrace(self, entry):
        '''Get the Back-Pointer trace'''

        bp_trace = []
        hypTraceStack = []
        hypTraceStack.append(entry)

        while ( hypTraceStack ):
            trace_entry = hypTraceStack.pop(0)
            for back_pointer in Entry.getBP(trace_entry):
                hypTraceStack.insert(0, back_pointer)
            inf_entry = Entry.getInfEntry(trace_entry)
            bp_trace += (Entry.getInfCell(trace_entry),)

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
                for back_pointer in Entry.getBP(trace_entry):
                    hypTraceStack.insert(0, back_pointer)
                inf_entry = Entry.getInfEntry(trace_entry)
                if inf_entry is not None:
                    src = Entry.getSrc(inf_entry)
                    tgt = Entry.getHypothesis(inf_entry)
                else:
                    src = Entry.getSrc(trace_entry)
                    tgt = Entry.getHypothesis(trace_entry)

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

    def printTrace(self,  src_sent):
        '''Prints the trace for top entries (as defined by settings.opts.trace_rules) in the cell (for debugging)'''

        traceFile = settings.opts.outFile + ".trace"
        tF = open(traceFile, 'a')

        nbest_cnt = 0
        hypTraceStack = []
	self.sortAllCand()
        for entry in self.fullTable[:]:

            tF.write("TRACE_BEGIN\n")
            hypTraceStack.append(entry)
            tF.write( "#Input  :: %s\n" % (src_sent) )
            tF.write( "#Output :: %s ||| %s\n" % (Entry.getHypothesis(entry), Entry.getFeatVec(entry)) )

            while ( hypTraceStack ):
                trace_entry = hypTraceStack.pop(0)
                for back_pointer in Entry.getBP(trace_entry):
                    hypTraceStack.insert(0, back_pointer)
                inf_entry = Entry.getInfEntry(trace_entry)
                if inf_entry is not None:   # partial hypotheses
		    tF.write("partial hyp:\t%s\n" %(Entry.printPartialHyp(trace_entry)))
                else:                       # rules
                    tF.write( "rule:\t\t%s ||| %s\n" % ( Entry.getSrc(trace_entry),Entry.printPartialHyp(trace_entry)) )

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
	if len(self.fullTable ) == 0:
	        oF.write( "UNKNOWN_TRANSLATION_TAG\n" )
	        oF.close()
		return
	#self.sent_scored = False
        self.sortAllCand()
        entriesLst = []
        if settings.opts.nbest_extremum == 0:
            nbest_2_produce = settings.opts.nbest_limit
            entriesLst = self.fullTable[:]
        else:
            nbest_2_produce = 2 * settings.opts.nbest_extremum
            # Get nbest_extreumum best and worst entries from the nbest-list
            #if len( self.table[tgt_key][:] ) >= settings.opts.nbest_limit:
            #    entriesLst = self.table[tgt_key][0:settings.opts.nbest_extremum] + \
            #                    self.table[tgt_key][settings.opts.nbest_limit-settings.opts.nbest_extremum:settings.opts.nbest_limit]
            #elif len( self.table[tgt_key][:] ) >= nbest_2_produce:
            if len( self.fullTable ) >= nbest_2_produce:
                entriesLst = self.fullTable[0:settings.opts.nbest_extremum] + self.fullTable[-settings.opts.nbest_extremum:]
            else: entriesLst = self.fullTable[:]

        for entry in entriesLst:
            if not settings.opts.nbest_format:
                oF.write( "%s\n" % Entry.getHypothesis(entry) )
            else:
                (cand, feat_str, cand_score) = Entry.printEntry(entry)
                oF.write( "%d||| %s ||| %s ||| %f\n" % ( sent_indx, cand, feat_str, cand_score ) )
                #if not settings.opts.use_unique_nbest:
                #    oF.write( "%d||| %s ||| %s ||| %f\n" % ( sent_indx, cand, feat_str, cand_score ) )
                #elif settings.opts.use_unique_nbest and not uniq_tgtDict.has_key(cand):
                #    uniq_tgtDict[cand] = 1
                #    oF.write( "%d||| %s ||| %s ||| %f\n" % ( sent_indx, cand, feat_str, cand_score ) )

            nbest_cnt += 1
            if nbest_cnt == nbest_2_produce: break  # stop after producing required no of items
        oF.close()

    def addAllCands(self, entryLst):
	for entry in entryLst:
		self.fullTable.append(entry)
	#self.sent_scored = True
	self.sent_scored = False

    def sortAllCand(self):
	if self.sent_scored: return
	for entry in self.fullTable:
		Entry.scoreCandidate(entry)
	self.fullTable.sort(key=operator.attrgetter("cand_score"), reverse=True)
	self.sent_scored = True

    def groupCands(self):
	if not self.sent_scored:
		self.sortAllCand()
	keys = self.table.keys()
	for key in keys:
		del self.table[key]
	self.table = {}
        for item in self.fullTable:    
               if len(item.unc_spans) > 0:      key = item.unc_spans[0][0]
               else: key = ()
               if key not in self.table:          self.table[key] = []
               self.table[key].append(item)
	
    def calcCandScore(self, cell_type):
        '''Calculates the candidate scores for the entries given a left NT (for printNBest)'''

        tgt_key = ''

        for key in self.table.iterkeys():
            if key[0] == cell_type:
                # If the sentence scores were caculated earlier; return tgt_key as key
                if self.sent_scored:
                    tgt_key = key
                    break

                # Compute the candidate score for every derivation
                for entry in self.table[key]:
                    Entry.scoreCandidate(entry)

                # Sort the entries based on the candidate score
                self.sort4CandScore(key)
                tgt_key = key
                break
        if tgt_key == '':
            raise RuntimeWarning, "Decoder did not produce derivations of the specified type in the present cell"
        return tgt_key

    def calcSentScore(self, cell_type):
        '''Calculates the sentence scores (in the last cell) for the entries given a left NT'''

        tgt_key = ''

        for key in self.table.iterkeys():
            if key[0] == cell_type:
                # Compute the candidate score for every derivation
                for entry in self.table[key]:
                    Entry.scoreSentence(entry)

                # Sort the entries based on the candidate score
                self.sort4CandScore(key)
                tgt_key = key
                break
        if tgt_key == '':
            raise RuntimeWarning, "Decoder did not produce derivations of the specified type in the present cell"

        self.sent_scored = True
        return tgt_key

    def sort4CandScore(self, key):
        '''Sort the cell entries based on their candidate scores for a given key'''

        self.table[key].sort(key=operator.attrgetter("cand_score"), reverse=True)

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

    def getHyps(self, key, stackInfo):
        '''Given the key, get the list of hypothesis with corresponding uncovered span'''
	#hypLst = []
	#for item in self.table[key]:
	#	newItem = Entry(0.0, 0.0, '','', [], '')
	#	newItem = Entry.copyEntry(item, newItem, stackInfo)
	#	hypLst.append(newItem)
	#return hypLst
	return self.table[key]
