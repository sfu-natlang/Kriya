## Reimplemetation of Parse class with LM integration and Cube Pruning ##

import sys

import settings
from cell import Cell
from entry_CP import Entry
from entry_CP import getInitHyp
from lazyMerge_CP import Lazy
from phraseTable import PhraseTable
import operator

# Global variables
consObjsLst = []                # List of consequent-rule objects for a particular cell
INF = 100000000

class Parse(object):
    '''Parse class contains method for parsing a given source sentence'''

    chartDict = {}
    fc_table = {}
    spanToRuleDict = {}
    spanToGlueRuleDict = {}

    __slots__ = "sent_indx", "sent", "refsLst", "wordsLst", "sent_len", "sh_order", "relaxed_decoding", "wordSpans", "ruleLookUpTable", "fc_type", "glueRuleLookUpTable"

    def __init__(self, sent_indx, p_sent, relaxed=False, refs=[]):
        Parse.spanToRuleDict = {}
        Parse.spanToGlueRuleDict = {}
        Parse.chartDict = {}
        self.ruleLookUpTable = {}
        self.glueRuleLookUpTable = {}
        self.sent_indx = sent_indx
        self.sent = p_sent
        self.relaxed_decoding = relaxed
        self.refsLst = refs
        self.wordsLst = p_sent.split()
        self.sent_len = len( self.wordsLst )
        self.sh_order = settings.opts.sh_order
        self.fc_type = settings.opts.future_cost
        if (self.relaxed_decoding):
            sys.stderr.write("INFO: Relaxing to full Hiero decoding for sentence# %d as Shallow-%d decoding failed." % (sent_indx, self.sh_order))
        self.wordSpans = {}
        for i in range(self.sent_len):
            for j in range(i+1,self.sent_len+1):
                self.wordSpans[(i,j)] = " ".join(self.wordsLst[i:j])
        self.compFutureCostTable()

    def __del__(self):
        '''Clear the data-structures'''

        for chart_cell in Parse.chartDict.itervalues():
            chart_cell = ''
        del Parse.chartDict
        del self.wordsLst[:]
        del self.refsLst[:]
        self.wordSpans.clear()
        del Parse.fc_table
        #Parse.spanToRuleDict.clear()
        for sp in Parse.spanToRuleDict.itervalues():
            sp = ''
        del Parse.spanToRuleDict
        for sp in Parse.spanToGlueRuleDict.itervalues():
            sp = ''
        del Parse.spanToGlueRuleDict
        for sp in self.ruleLookUpTable.itervalues():
            sp = ''
        del self.ruleLookUpTable
        for sp in self.glueRuleLookUpTable.itervalues():
            sp = ''
        del self.glueRuleLookUpTable
        #self.ruleLookUpTable.clear()

    def compFutureCostTable(self):
        """ compute future cost based on the tpy:
                0:	Moses using just terminal rules
                1:	Moses using both hierarchy and terminal rules
                2:	apply type 0 but add some computations: for each span compute full lm cost 
                	for target phrases obtained by combining smaller spans
                3:	apply type 1 but add some computations: for each span compute full lm cost 
                	for target phrases obtained by combining rules with smaller spans 
        """
        self.initFutureCost()
        moreLMComputation = False
        if self.fc_type == 2 or self.fc_type == 3:
            moreLMComputation = True
        if self.fc_type == 0 or self.fc_type == 2:
            self.compFutureCostTableMoses(moreLMComputation)
        elif self.fc_type == 1 or self.fc_type == 3:
            self.compFutureCostTableHierarchy(moreLMComputation)
        #self.printFutureCostTable()

    def compFullLM(self):
        for key in self.fc_table:
            self.fc_table[key].lm = PhraseTable.getLMScore(self.fc_table[key].tgt)
            self.fc_table[key].cost = self.fc_table[key].cost - self.fc_table[key].lm_heu + self.fc_table[key].lm

    def compFutureCostTableMoses(self, moreLMComputation=False):
        for phr_len in xrange(1,self.sent_len+1):
            for start_ind in xrange(self.sent_len-phr_len+1):
                end_ind = start_ind + phr_len
                key = (start_ind, end_ind)
                for mid_ind in xrange(start_ind+1, end_ind):
                    val_phr1 = Parse.fc_table[(start_ind,mid_ind)].cost
                    val_phr2 = Parse.fc_table[(mid_ind,end_ind)].cost
                    #if val_phr1+val_phr2 > Parse.fc_table[key].cost:
                    if 1:
                        tgt = Parse.fc_table[(start_ind,mid_ind)].tgt +" "+ Parse.fc_table[(mid_ind,end_ind)].tgt
                        lm_heu = Parse.fc_table[(start_ind,mid_ind)].lm_heu + Parse.fc_table[(mid_ind,end_ind)].lm_heu
                        tm_cost = val_phr1+val_phr2 - lm_heu
                        if moreLMComputation:	lm_heu = PhraseTable.getLMHeuScore(tgt)
                        if lm_heu+tm_cost > Parse.fc_table[key].cost:
                            Parse.fc_table[key].cost = lm_heu+tm_cost
                            Parse.fc_table[key].tgt = tgt
                            Parse.fc_table[key].lm_heu = lm_heu

    def initFutureCost(self):
        Parse.fc_table = {}
        for phr_len in xrange(1,self.sent_len+1):
            for start_ind in xrange(self.sent_len-phr_len+1):
                end_ind = start_ind + phr_len
                key = (start_ind,end_ind)
                Parse.fc_table[key] = FuturePT(-INF, "", 0)
                phrase = self.wordSpans[(start_ind,end_ind)]
 
                if PhraseTable.hasRule(phrase):
                    phraseEntities = PhraseTable.getRuleEntries(phrase, self.sent_indx)
                    for entity in phraseEntities:
                        if Parse.fc_table[key].cost < entity.getHeuScore(settings.opts.weight_wp): #5tm for future cost
                            Parse.fc_table[key].cost = entity.getHeuScore(settings.opts.weight_wp)
                            #Parse.fc_table[key].tgt = entity.getHypothesis()
                            Parse.fc_table[key].tgt = entity.tgt
                            Parse.fc_table[key].lm_heu = entity.getLMHeu()

                elif phr_len <= settings.opts.max_phr_len:
                    flag = False
                    for w in self.wordsLst[start_ind:end_ind]:
                        if PhraseTable.hasRule(w):
                            flag = True
                            break
                    if not flag:
                        unkFeat = settings.opts.U_lpTup[2][:]
                        lm_score = PhraseTable.getLMHeuScore(phrase)
                        unkFeat[settings.opts.lm_index] = lm_score
                        unkFeat[settings.opts.word_penalty] = 0
                        score = settings.getScores(unkFeat)    
                        Parse.fc_table[key].cost = score[0] + score[1]
                        Parse.fc_table[key].tgt = phrase 
                        Parse.fc_table[key].lm_heu = lm_score
                        unkFeat[settings.opts.word_penalty] = -phr_len
                        self.addUNKRule(phrase, unkFeat)

    def compFutureCostTableHierarchy(self,moreLMComputation=False):
        self.initFutureCost()
        for phr_len in xrange(1,self.sent_len+1):
            for start_ind in xrange(self.sent_len-phr_len+1):
                end_ind = start_ind + phr_len
                key = (start_ind, end_ind)
                phrase = self.wordSpans[(start_ind,end_ind)]
                self.__getRuleSpans((start_ind, end_ind), phrase)
                ruleDict = Parse.spanToRuleDict[key]
                for r in ruleDict:
                    if phr_len <= settings.opts.max_phr_len and PhraseTable.hasRule(r):
                        tgtRules = PhraseTable.getRuleEntries(r, self.sent_indx)
                    elif PhraseTable.hasgRule(r):
                        tgtRules = PhraseTable.getgRuleEntries(r)
                    else: continue
                    if len(ruleDict[r]) == 0: 
                        continue
                    span_costs = sum([Parse.fc_table[(s1,s2)].cost for (s1,s2) in ruleDict[r]])
                    span_lm_heu = sum([Parse.fc_table[(s1,s2)].lm_heu for (s1,s2) in ruleDict[r]])
                    span_phr = " ".join([Parse.fc_table[(s1,s2)].tgt for (s1,s2) in ruleDict[r]])
                    for rule in tgtRules:
                        estimated = span_costs+rule.getHeuScore(settings.opts.weight_wp)
                        if Parse.fc_table[key].cost < estimated:
                            lm_heu = span_lm_heu +rule.getLMHeu()
                            tm_cost = estimated - lm_heu
                            tgt = rule.tgt[:rule.tgt.find(" X__")] if rule.tgt.find(" X__") > 0 else rule.tgt
                            tgt = tgt + " " + span_phr
                            if moreLMComputation:	lm_heu = PhraseTable.getLMHeuScore(tgt)
                            if Parse.fc_table[key].cost < lm_heu+tm_cost:
                                Parse.fc_table[key].cost = lm_heu+tm_cost
                                Parse.fc_table[key].tgt = tgt
                                Parse.fc_table[key].lm_heu = lm_heu

    def printFutureCostTable(self):
        for s in range(0, self.sent_len):
            for e in range(s+1, self.sent_len+1):
                print '(',s,',',e,')', "\t", str(self.fc_table[(s,e)])

    def addUNKRule(self, src_phr, featVec):
        score = settings.getScores(featVec)
        p_score = score[1]
        lm_score = score[0]

        featVec[settings.opts.lm_index] = 0
        feat_Vec = featVec[:]
        featVec[settings.opts.glue_penalty] = 1
        featVec[4] = 0 ##it is a glue rule not regular rule
        gp_score = settings.getScores(featVec)[1]

        tgt_phr = src_phr[:]
        rEntries = []
        rEntries.append (Entry(p_score, lm_score, src_phr, tgt_phr, feat_Vec, tgt_phr))
        PhraseTable.addUNKRule(src_phr, rEntries)

        tgts = [' X__1', ' X__1', ' X__1 X__2', ' X__2 X__1']
        srcs = ['X__1 '+ src_phr, src_phr+' X__1', 'X__1 '+ src_phr+' X__2']

        for index, src in enumerate(srcs):
            gEntries = []
            rEntries = []
            tgt = src_phr+tgts[index]
            gEntries.append( Entry(gp_score, lm_score, src, tgt, featVec, tgt))
            rEntries.append( Entry(p_score, lm_score, src, tgt, feat_Vec, tgt))
            if index == 2:
                tgt = src_phr+tgts[index+1]
                gEntries.append( Entry(gp_score, lm_score, src, tgt, featVec, tgt))
                rEntries.append( Entry(p_score, lm_score, src, tgt, feat_Vec, tgt))
            PhraseTable.addUNKGRule(src, gEntries)
            PhraseTable.addUNKRule(src, rEntries)

    def getFutureCost(self, UNC_spans):
        future_Cost = 0
        for span in UNC_spans:
            if span[0][0] >= 0:
                future_Cost += Parse.fc_table[span[0]].cost
        return future_Cost

    def parse(self):
        'Parse the sentence passed in the argument'

        final_cell = False

        # Phase-1: Initialization
        # Fill the initial stack (or chartDict) with null hypothesis 
        p_i = 0
        #print "Stack:", p_i
        if self.sent_len == 1:
                final_cell = True
        Parse.chartDict[0] = Cell()
        init_hypothesis = getInitHyp(self.sent_len, Parse.fc_table[(0,self.sent_len)].cost)
        self.__flush2Cell(0, [init_hypothesis])     # Flush the entries to the cell
        #Parse.chartDict[0].printCell('X', self.sent_indx)

        # Phase-2: Filling the stacks
        # Iterate through all stacks each corresponds to number of covered words (1,sent_len)
        total_cubes = 0 #for statistics
        total_groups = 0
        for p_s in range(1, self.sent_len+1):
            Parse.chartDict[p_s] = Cell()
            if ( p_s == self.sent_len ):
                    final_cell = True
            cube_indx = 0
            merge_obj = Lazy(self.sent_indx, p_s, final_cell)
            for p_j in range(max(0, p_s - settings.opts.fr_rule_terms), p_s):
                p_l = p_s - p_j
                #print "\nFilling stack:", p_s, "\tSpan length:", p_l
                for unc_span in Parse.chartDict[p_j].table:
			(start, end) = unc_span
	                self.__matchRule( unc_span, self.wordSpans[unc_span])
			hypsLst = Parse.chartDict[p_j].getHyps(unc_span, p_s) 
			if len(hypsLst) ==0:
				print "No hyp!!", (start, end), p_l
			#print "uncovered span:", (start, end), "\t number of hyps: ", len(hypsLst)
			#for hyp in hypsLst:
				#print hyp.tgt
			
			if p_l in self.ruleLookUpTable[(start,end)]:
			    for src_rule in self.ruleLookUpTable[(start,end)][p_l]:
				if len(self.ruleLookUpTable[(start,end)][p_l][src_rule]) == 0:
					continue
					print "No rule!!"
					print src_rule
					print (start, end)
				#print "\nsource rule: ", src_rule
				# set the source side rule and span for the current cube
				spanTuple=Parse.spanToRuleDict[(start, end)][src_rule]
				Lazy.setSourceInfo( merge_obj, cube_indx, src_rule, spanTuple, 0, self.refsLst )
				# add the consequent item to the cube as its first dimension
				Lazy.add2Cube(merge_obj, cube_indx, hypsLst)  ## order is important, the first list is hypothesis
            			Lazy.add2Cube(merge_obj, cube_indx, self.ruleLookUpTable[(start,end)][p_l][src_rule])
				cube_indx += 1

			if p_l in self.glueRuleLookUpTable[(start,end)]:
			    for src_rule in self.glueRuleLookUpTable[(start,end)][p_l]:
				if len(self.glueRuleLookUpTable[(start,end)][p_l][src_rule]) == 0:
					continue
					print "No glue rule!!"
					print src_rule
					print (start, end)
				#print "\nsource rule: ", src_rule
				# set the source side rule and span for the current cube
				spanTuple=Parse.spanToGlueRuleDict[(start, end)][src_rule]
				isSet = False
				if src_rule.endswith("X__2 X__3"): isSet = True
				Lazy.setSourceInfo( merge_obj, cube_indx, src_rule, spanTuple, 0, self.refsLst, isSet)
				# add the consequent item to the cube as its first dimension
				Lazy.add2Cube(merge_obj, cube_indx, hypsLst)  ## order is important, the first list is hypothesis
            			Lazy.add2Cube(merge_obj, cube_indx, self.glueRuleLookUpTable[(start,end)][p_l][src_rule])
				cube_indx += 1

            total_cubes += cube_indx
            tgtLst = Lazy.mergeProducts(merge_obj)
            self.__flush2Cell(p_s, tgtLst)   # Flush the entries to the cell
            #print "\n\n Stack:", p_s, "\tnew hyps:"
            #for hyp in tgtLst:
                 #print hyp.printPartialHyp()
            merge_obj = ''  # Important: This clears the mem-obj and calls the garbage collector on Lazy()
            #if settings.opts.force_decode:
            #    if len(tgtLst) == 0:
             #       sys.stderr.write("           INFO  :: Force decode mode: No matching candidate found for cell (0, %d).\n" % (p_s))

            total_groups += len(Parse.chartDict[p_s].table)
            #print "stack:\t", p_s, " has ", cube_indx, ' cubes and ', len(Parse.chartDict[p_s].table), " groups"

        #print "sent len:  ", self.sent_len, "\t\tavg cubes:  %1.3g\t\tavg groups:  %1.3g" % ((total_cubes*1.0)/self.sent_len, (total_groups*1.0)/self.sent_len )
        if len(Parse.chartDict[p_s]) == 0:
            sys.stderr.write("           INFO  :: Force decode mode: No matching candidate found.")
            Parse.chartDict[p_s].printNBest(None, self.sent_indx)       # Print the N-best derivations in the last cell
            return 0
            #return 99
        Parse.chartDict[p_s].printNBest(None, self.sent_indx)       # Print the N-best derivations in the last cell
        if settings.opts.trace_rules > 0:
            Parse.chartDict[p_s].printTrace(self.sent)        # Prints the translation trace for the top-3 entries
        return 1

    def __getRuleSpans(self, (i, j), span_phrase, isGlue=False):
        '''Get the list of rules that match the phrase corresponding to the given span'''
        if (not isGlue and not Parse.spanToRuleDict.has_key((i,j))) or (isGlue and not Parse.spanToGlueRuleDict.has_key((i,j))): 
            tmpRuleDict = {}

            if isGlue: matchLst = PhraseTable.findConsistentGlueRules(span_phrase)
            else: matchLst = PhraseTable.findConsistentRules(span_phrase)

            for match in matchLst:
                spans = []
                rule = match[0]
                if len(match[1])%2 != 0:
                    print "Err in getRuleSpans", match[0], match[1]
                    exit(1)
                for xind in range(0,len(match[1]),2):
                    span = (match[1][xind]+i, match[1][xind+1]+i+1) ##TODO: be careful!!
                    if span == (i,j): continue
                    spans.append(span)
                tmpRuleDict[rule] = tuple( spans )

            if isGlue: Parse.spanToGlueRuleDict[(i,j)] = tmpRuleDict
            else: Parse.spanToRuleDict[(i,j)] = tmpRuleDict

    def __matchRule(self, (start, end), source_phrase):
        if self.ruleLookUpTable.has_key((start, end)): return

        if (end-start) <= 0:
            print "Error in span ", start,end
            exit(1)

        rulesNo = 0
        self.ruleLookUpTable[(start,end)]={}
        self.glueRuleLookUpTable[(start,end)]={}
        if (end - start) <= settings.opts.max_phr_len:
            self.__getRuleSpans((start,end),source_phrase)
            ruleDict = self.spanToRuleDict[(start, end)]
            for key in ruleDict.keys():
                s_len = 0
                ruleLst = []
                for word in key.strip().split():
                    if not word.startswith("X__"): s_len += 1
                if not self.ruleLookUpTable[(start,end)].has_key(s_len): self.ruleLookUpTable[(start,end)][s_len] = {}
                #if (PhraseTable.ruleDict.has_key(key)) :
                for entity in PhraseTable.getRuleEntries(key, self.sent_indx):	
                    rulesNo+=1
                    spans = list(Parse.spanToRuleDict[(start,end)][key])
                    rule = expandRule(key, entity, start, end, spans, False)
                    #self.ruleLookUpTable[(start,end)][s_len][key].append(rule)
                    ruleLst.append(rule)
                if len(ruleLst) > 0:
                    #ruleLst.sort(key=operator.attrgetter("score"), reverse=True)
                    self.ruleLookUpTable[(start,end)][s_len][key]=ruleLst

        grulesNo = 0
        #if (len(self.ruleLookUpTable[(start,end)])==0 or (end- start) >= settings.opts.max_phr_len) :
        #if (len(self.ruleLookUpTable[(start,end)])==0:
        if True:
            self.__getRuleSpans((start,end),source_phrase, True)
            ruleDict = self.spanToGlueRuleDict[(start, end)]
            for key in ruleDict.keys():
                if (end-start) < settings.opts.max_phr_len and key in self.spanToRuleDict[(start, end)]: continue
                s_len = 0
                ruleLst = []
                for word in key.strip().split():
                    if not word.startswith("X__"): s_len += 1
                if not self.glueRuleLookUpTable[(start,end)].has_key(s_len): self.glueRuleLookUpTable[(start,end)][s_len] = {}
                #if PhraseTable.gruleDict.has_key(key):
                for entity in PhraseTable.getgRuleEntries(key):
                    spans = list(Parse.spanToGlueRuleDict[(start,end)][key])
                    if key.endswith("X__2 X__3"):
                        startLastSpan = spans[1][0]
                        endLastSpan = spans[2][1]
                        firstSpan = spans[0]
                        for splitPoint in xrange(startLastSpan+1,min(startLastSpan+settings.opts.max_span_size +1, endLastSpan)):
                            spans[0] = firstSpan
                            spans[1] = (startLastSpan, splitPoint)
                            spans[2] = (splitPoint, endLastSpan)
                            rule = expandRule(key, entity, start, end, spans, True)
                            if rule:
                                grulesNo+=1
                                ruleLst.append(rule)
                    else:
                        rule = expandRule(key, entity, start, end, spans, True)
                        if rule:
                            grulesNo+=1
                            ruleLst.append(rule)
                            #self.ruleLookUpTable[(start,end)][s_len][key].append(rule)
                if len(ruleLst) > 0:
                    #ruleLst.sort(key=operator.attrgetter("score"), reverse=True)
                    self.glueRuleLookUpTable[(start,end)][s_len][key]=ruleLst

        if len(self.glueRuleLookUpTable[(start,end)]) == 0 and len(self.ruleLookUpTable[(start,end)]) == 0 :
            print "error in loading rules, undefined span: ", (start, end)
            exit(1)
        #print (start, end),  "glue:", grulesNo, " \t rules:",rulesNo

    def __getRulesFromPT(self, s_rule, span):
        ''' Get the rules from the Phrase table and create new entry object for each rule returned by phrase table '''

        tgtLst = PhraseTable.getRuleEntries(s_rule, self.sent_indx)
        newTgtLst = []
        for rule_entry in tgtLst:
            new_entry = Entry(0.0, 0.0, '','', [], '')
            new_entry = Entry.copyEntry(rule_entry, new_entry, span)
            newTgtLst.append(new_entry)

        return newTgtLst

    def __flush2Cell(self, stackNo, tgtLst):
        '''Flush the entries (dictionary entries/ candidate hypotheses) to the cell'''
	#hypDict = {}
	#for item in tgtLst:	
	#	if len(item.unc_span) > 0:	key = (item.unc_span[0][0], self.wordSpans[item.unc_span[0][0]])
	#	else: key = ((), "")
	#	if key not in hypDict:		hypDict[key] = []
	#	hypDict[key].append(item)
	#for key in hypDict:
	#        Parse.chartDict[stackNo].add2Cell(key, hypDict[key])
	Parse.chartDict[stackNo].addAllCands(tgtLst)
	Parse.chartDict[stackNo].sortAllCand()
	Parse.chartDict[stackNo].groupCands()

def expandRule(src, entity, start, end, spans, isGlue):
	distortion = 0
	width = 0
	reOrder = 0
        X_1_tgt = entity.tgt.find('X__1')
	tgt_end_ind = len(entity.tgt)
#	if isGlue: spans = list(Parse.spanToGlueRuleDict[(start,end)][src])
#	else: spans = list(Parse.spanToRuleDict[(start,end)][src])
	if X_1_tgt >= 0:
		X1=abs(spans[0][1]-spans[0][0])
		tgt_end_ind = X_1_tgt
	        X_2_tgt = entity.tgt.find('X__2')
                if isGlue and spans[0][0] == start and X1 > settings.opts.dist_limit:
			return None
		if X_2_tgt >= 0:
			width = X1
			X2=abs(spans[1][1]-spans[1][0])
			T1=abs(spans[1][0]-spans[0][1])
	        	if entity.tgt.endswith('X__3'): T2=abs(spans[2][0]-spans[1][1])
			else: 				T2=abs(end-spans[1][1])
			if (X_1_tgt - X_2_tgt) > 0:
                		if isGlue and X2 > settings.opts.dist_limit:
					return None
				width = X2
				reOrder = 1
				tgt_end_ind = X_2_tgt
				#spans.reverse()
				sp0 = spans[0]
				spans[0] = spans[1]
				spans[1] = sp0
				if T2 >0:  distortion = T2+2*X2+X1+T1
				else:      distortion = X2+X1+T1
			else:
				if T2 >0:  distortion = T2+X2+X1+2*T1
				else:      distortion = X1+2*T1
		else:
			T1=abs(end-spans[0][1])
			if T1 >0: distortion = X1+T1

        rule = Entry(0.0, 0.0, '','', [], '')
        rule = Entry.copyEntry(entity, rule, ())	##these are just rules not the hypotheses
	rule.tgt_elided = entity.tgt[0:tgt_end_ind].strip()
	rule.tgt = rule.tgt_elided
	rule.unc_spans = []
	for sp in spans:
		rule.unc_spans.append((sp,0,Parse.fc_table[sp].cost))
	index = 8
	if isGlue:	rule.featVec[9] = -distortion
	else:	rule.featVec[8] = -distortion
	rule.featVec[10] = -reOrder
	rule.featVec[11] = -width
	#rule.score += entity.wp	## already added in phraseTable.py
	rule.score += rule.featVec[8]*settings.opts.weight_d + rule.featVec[9]*settings.opts.weight_dg +\
		rule.featVec[10]*settings.opts.weight_r + rule.featVec[11]*settings.opts.weight_w
	#TODO: make sure that weights have been correctly set!!
	#TODO: h should be added during decoding
	rule.setRuleCover()

	return rule

class FuturePT(object):
    '''phrase table class for saving best possible target phrases for each span'''

    __slots__ = "lm", "tgt", "cost", "lm_heu"

    def __init__(self, c, tgt, lm_h):
        self.tgt = tgt
        self.cost = c
	self.lm_heu = lm_h
    def setLM(self, lm):
	self.lm = lm
    def __getitem__(self):
	return self.cost
    def __str__(self):
	return str(self.cost)+"\t"+self.tgt

