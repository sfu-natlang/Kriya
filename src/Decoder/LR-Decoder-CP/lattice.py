## @author Maryam Siahbani

import sys, operator

import settings
from phraseTable import PhraseTable

INF = 100000000

class Lattice(object):
    '''(phrase/rule)-lattice, 2D table. (not to be confused with search chart)'''

    fc_table = {}
    spanToRuleDict = {}
    ruleLookUpTable = {}
    this = None
    
    #__slots__ = "sent_indx", "sent", "wordsLst", "sent_len", "sh_order", "relaxed_decoding", "wordSpans", "fc_type"

    def __init__(self, sent_indx, p_sent, relaxed=False):
	Lattice.this = self
        Lattice.spanToRuleDict = {}
        Lattice.ruleLookUpTable = {}
        Lattice.fc_table = {}
        self.sent_indx = sent_indx
        self.sent = p_sent
        self.relaxed_decoding = relaxed
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
	
    @staticmethod
    def clear():
	'''Clear the static data-structures'''
	del Lattice.fc_table
	for sp in Lattice.spanToRuleDict.itervalues():
	    sp = ''
	del Lattice.spanToRuleDict
	for sp in Lattice.ruleLookUpTable.itervalues():
	    sp = ''
	del Lattice.ruleLookUpTable
	Lattice.this = None	
	
    def __del__(self):
        '''Clear the data-structures'''

        del self.wordsLst[:]
        self.wordSpans.clear()

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
	## log
        #self.printFutureCostTable()

    def compFullLM(self): ## TODO: ??
        for key in Lattice.fc_table:
            Lattice.fc_table[key].lm = PhraseTable.getLMScore(Lattice.fc_table[key].tgt)
            Lattice.fc_table[key].cost = Lattice.fc_table[key].cost - Lattice.fc_table[key].lm_heu + Lattice.fc_table[key].lm

    def compFutureCostTableMoses(self, moreLMComputation=False):
        for phr_len in xrange(1,self.sent_len+1):
            for start_ind in xrange(self.sent_len-phr_len+1):
                end_ind = start_ind + phr_len
                key = (start_ind, end_ind)
                for mid_ind in xrange(start_ind+1, end_ind):
                    val_phr1 = Lattice.fc_table[(start_ind,mid_ind)].cost
                    val_phr2 = Lattice.fc_table[(mid_ind,end_ind)].cost
                    if val_phr1+val_phr2 > Lattice.fc_table[key].cost:
                        tgt = Lattice.fc_table[(start_ind,mid_ind)].tgt +" "+ Lattice.fc_table[(mid_ind,end_ind)].tgt
                        lm_heu = Lattice.fc_table[(start_ind,mid_ind)].lm_heu + Lattice.fc_table[(mid_ind,end_ind)].lm_heu
                        tm_cost = val_phr1+val_phr2 - lm_heu
                        if moreLMComputation:	lm_heu = PhraseTable.getLMHeuScore(tgt)
                        if lm_heu+tm_cost > Lattice.fc_table[key].cost:
                            Lattice.fc_table[key].cost = lm_heu+tm_cost
                            Lattice.fc_table[key].tgt = tgt
                            Lattice.fc_table[key].lm_heu = lm_heu

    def initFutureCost(self):
        Lattice.fc_table = {}
        for phr_len in xrange(1,self.sent_len+1):
            for start_ind in xrange(self.sent_len-phr_len+1):
                end_ind = start_ind + phr_len
                key = (start_ind,end_ind)
                Lattice.fc_table[key] = FuturePT(-INF, "", 0)
                phrase = self.wordSpans[key]
 
                if PhraseTable.hasRule(phrase):
                    phraseEntities = PhraseTable.getRuleEntries(phrase, self.sent_indx)
                    for entity in phraseEntities[0]:
                        if Lattice.fc_table[key].cost < entity.getHeuScore(): #5tm for future cost
                            Lattice.fc_table[key].cost = entity.getHeuScore()
                            Lattice.fc_table[key].tgt = entity.tgt
                            Lattice.fc_table[key].lm_heu = entity.getLMHeu()

                elif phr_len <= settings.opts.max_phr_len:
                    flag = False
                    for w in self.wordsLst[start_ind:end_ind]:
                        if PhraseTable.hasRule(w):
                            flag = True
                            break
                    if not flag:
			rule = PhraseTable.createUNKRule(phrase)
                        Lattice.fc_table[key].cost = rule.getHeuScore()
                        Lattice.fc_table[key].tgt = phrase
                        Lattice.fc_table[key].lm_heu = rule.getLMHeu()

    def compFutureCostTableHierarchy(self,moreLMComputation=False):
        self.initFutureCost()
        for phr_len in xrange(1,self.sent_len+1):
            for start_ind in xrange(self.sent_len-phr_len+1):
                end_ind = start_ind + phr_len
                key = (start_ind, end_ind)
                self.__getRuleSpans(key)
                ruleDict = self.spanToRuleDict[key]
                for r in ruleDict:
                    tgtRules = PhraseTable.getRuleEntries(r, self.sent_indx)
                    if phr_len <= settings.opts.max_phr_len and PhraseTable.hasRule(r):
                        tgtRules = tgtRules[0]
                    elif PhraseTable.hasgRule(r):
                        tgtRules = tgtRules[1]
                    else: continue
                    if len(ruleDict[r]) == 0: 
                        continue
                    span_costs = sum([Lattice.fc_table[(s1,s2)].cost for (s1,s2) in ruleDict[r]])
                    span_lm_heu = sum([Lattice.fc_table[(s1,s2)].lm_heu for (s1,s2) in ruleDict[r]])
                    span_phr = " ".join([Lattice.fc_table[(s1,s2)].tgt for (s1,s2) in ruleDict[r]])
                    for rule in tgtRules:
                        estimated = span_costs+rule.getHeuScore()
                        if Lattice.fc_table[key].cost < estimated:
                            lm_heu = span_lm_heu +rule.getLMHeu()
                            tm_cost = estimated - lm_heu
                            tgt = rule.tgt[:rule.tgt.find(" X__")] if rule.tgt.find(" X__") > 0 else rule.tgt
                            tgt = tgt + " " + span_phr
                            if moreLMComputation:	lm_heu = PhraseTable.getLMHeuScore(tgt)
                            if Lattice.fc_table[key].cost < lm_heu+tm_cost:
                                Lattice.fc_table[key].cost = lm_heu+tm_cost
                                Lattice.fc_table[key].tgt = tgt
                                Lattice.fc_table[key].lm_heu = lm_heu

    def printFutureCostTable(self):
        for s in range(0, self.sent_len):
            for e in range(s+1, self.sent_len+1):
                print '(',s,',',e,')', "\t", str(Lattice.fc_table[(s,e)])

	    
    @staticmethod
    def getFutureCost(spans):
        future_Cost = sum([Lattice.fc_table[span].cost for span in spans])
        return future_Cost

    def __getRuleSpans(self, (i, j)):
        '''Get the list of rules that match the phrase corresponding to the given span'''
        if (i,j) not in Lattice.spanToRuleDict: 
            Lattice.spanToRuleDict[(i,j)] = {}
            span_phrase = self.wordSpans[(i,j)]
	    matchLst = PhraseTable.findConsistentRules(span_phrase, True)
	    if abs(i-j) <= settings.opts.max_phr_len: matchLst += PhraseTable.findConsistentRules(span_phrase)

            for match in matchLst:
		#if len(match[1])%2 != 0:
		#    print "Err in getRuleSpans", match[0], match[1]
		#    exit(1)		
                spans = []
                rule = match[0]
		if rule in Lattice.spanToRuleDict[(i,j)]: continue
                for xind in range(0,len(match[1]),2):
                    span = (match[1][xind]+i, match[1][xind+1]+i+1) ##TODO: be careful!!
                    if span == (i,j): continue
                    spans.append(span)
                Lattice.spanToRuleDict[(i,j)][rule] = spans ## TODO: it should be tuple or list?
	
    def matchRule(self, (start, end)):
        if (start, end) in Lattice.ruleLookUpTable: return
	## log: add log info here
        rulesNo = 0
	grulesNo = 0
        Lattice.ruleLookUpTable[(start,end)]={}
	self.__getRuleSpans((start,end))
	ruleDict = Lattice.spanToRuleDict[(start, end)]	
	for src_side in ruleDict:
	    regRules, glueRules = PhraseTable.getRuleEntries(src_side, self.sent_indx)
	    n=len(regRules)
	    if (end - start) <= settings.opts.max_phr_len and n > 0:
		s_len = regRules[0].src_len
		if s_len not in Lattice.ruleLookUpTable[(start,end)]:      Lattice.ruleLookUpTable[(start,end)][s_len] = {}
		Lattice.ruleLookUpTable[(start,end)][s_len][src_side]=regRules
		rulesNo+=n
	    else:
		s_len = glueRules[0].src_len
		if s_len not in Lattice.ruleLookUpTable[(start,end)]:      Lattice.ruleLookUpTable[(start,end)][s_len] = {}
		if src_side not in Lattice.ruleLookUpTable[(start,end)][s_len]: Lattice.ruleLookUpTable[(start,end)][s_len][src_side]=[]
		Lattice.ruleLookUpTable[(start,end)][s_len][src_side]+=glueRules
		grulesNo+=len(glueRules)
	##log
	#print (start, end),  "glue:", grulesNo, " \t rules:",rulesNo
        if grulesNo == 0 and rulesNo == 0:
	    sys.stderr.write("           INFO  :: Matching rules: No matching rule found for span (%d, %d).\n" % (start,end))
            exit(1)

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
