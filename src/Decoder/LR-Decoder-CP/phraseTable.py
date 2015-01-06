## @author Maryam Siahbani (modified version of phraseTable.py in Kriya by Baskaran Sankaran)

import math
import operator
import sys
import time

import settings
from rule import Rule
from myTrie import SimpleSuffixTree
from glueTrie import SimpleSuffixTreeForGlue
from lmKENLM import KENLangModel
from lmSRILM import SRILangModel
from refPhrases import RefPhrases

featVec = []

class PhraseTable(object):
    '''Phrase table class for containing the SCFG rules and serving associated queries'''

    tot_rule_pairs = 0
    src_trie = None
    glue_trie = None
    ruleDict = {}
    gruleDict = {}
    phrasePairs = {}
    terminalRules = {}
    __slots__ = "wVec", "ttl", "pp_val", "ttlg"

    def __init__(self, TOT_TERMS):
        '''Loading rules from the phrase table and initializing their feature values'''

        from settings import feat
        self.wVec = feat
        self.ttl = settings.opts.ttl
        self.pp_val = math.log(2.718)
        self.ttlg = settings.opts.ttlg # for glue rules 

        tm_wgts_str = ' '.join( [str(x) for x in self.wVec.tm] )
	reorder_wgts_str = "d:"+str(self.wVec.d)+" dg:"+str(self.wVec.dg)+" r:"+str(self.wVec.r)+" w:"+str(self.wVec.w)+" h:"+str(self.wVec.h)
        sys.stderr.write( "Weights are : [%s] %g %g %g %s\n" % (tm_wgts_str, self.wVec.wp, self.wVec.glue, self.wVec.lm, reorder_wgts_str) )

        self.loadRules(settings.opts.max_phr_len)
	self.makeGlueRules(TOT_TERMS)

    def delPT(self):
        del PhraseTable.ruleDict
        del PhraseTable.gruleDict 
        PhraseTable.src_trie = None
        PhraseTable.glue_trie = None

    def loadRules(self, TOT_TERMS):
        '''Loads the filtered rules and filters them further by using the Suffix Tree of test data'''

        global featVec
        PhraseTable.tot_rule_pairs = 0
        prev_src = ''
        featVec = [0.0 for i in settings.opts.U_lpTup[2]]
	featVec[4] = self.pp_val
        uniq_src_rules = 0
        entriesLst = []
	PhraseTable.phrasePairs = {}
	lm_H = 0

        t_beg = time.time()
        rF = open(settings.opts.ruleFile, 'r')
        sys.stderr.write( "Loading SCFG rules from file     : %s\n" % (settings.opts.ruleFile) )
        try:
            for line in rF:
                line = line.strip()
                (src, tgt, probs) = line.split(' ||| ')[0:3]                       # For Kriya phrase table
#                (src, tgt, f_align, r_align, probs) = line.split(' ||| ')     # For Moses phrase table
		src = src.strip()
		tgt = tgt.strip()
                if settings.opts.force_decode and not PhraseTable.tgtMatchesRef(tgt): continue
                if settings.opts.one_nt_decode and src.find('X__2') >= 0: continue
                PhraseTable.tot_rule_pairs += 1

                if prev_src != src:
                    uniq_src_rules += 1
                    if PhraseTable.src_trie is None:
                        PhraseTable.src_trie = SimpleSuffixTree(src,TOT_TERMS)
                    else:
                        PhraseTable.src_trie.addText(src)

                self.buildFeatVec(probs, tgt)

                if len(prev_src) > 0 and prev_src != src:
                    entriesLst.sort(key=operator.attrgetter("prob_e_f"), reverse=True)
                    PhraseTable.ruleDict[prev_src] = []
		    ## store terminal rules to generate glue rules
		    if prev_src.find("X__") < 0: PhraseTable.terminalRules[prev_src]=0
                    tgt_options = 0
                    for pt_item_obj in entriesLst:
                        entry_obj = pt_item_obj.entry_item
                        entry_obj.lm_heu = self.wVec.lm * self.getLMHeuScore(entry_obj.tgt)
                        entry_obj.completeInfo()
                        PhraseTable.ruleDict[prev_src].append( entry_obj )
                        tgt_options += 1
                        if(self.ttl > 0 and tgt_options >= self.ttl): break
                    del entriesLst[:]

                #entriesLst.append( PTableItem(featVec[2], Rule(0.0, 0.0, src, tgt, featVec)) )
                entriesLst.append( PTableItem(featVec[0], Rule(0.0, 0.0, src, tgt, featVec)) )
                prev_src = src

            # Handle the last rule
            entriesLst.sort(key=operator.attrgetter("prob_e_f"), reverse=True)
            PhraseTable.ruleDict[prev_src] = []
	    ## store terminal rules to generate glue rules
	    if prev_src.find("X__") < 0: PhraseTable.terminalRules[prev_src]=0
            tgt_options = 0
            for pt_item_obj in entriesLst:
                entry_obj = pt_item_obj.entry_item
                lm_score = self.wVec.lm * self.getLMHeuScore(entry_obj.tgt)
                entry_obj.lm_heu = lm_score
                entry_obj.completeInfo()
                PhraseTable.ruleDict[prev_src].append( entry_obj )
                tgt_options += 1
                if(self.ttl > 0 and tgt_options >= self.ttl): break
            del entriesLst[:]

        finally:
            rF.close()
            t_end = time.time()
            sys.stderr.write( "Unique source rules found                     : %d\n" % (uniq_src_rules) )
            sys.stderr.write( "Total pairs of SCFG rules loaded              : %d\n" % (PhraseTable.tot_rule_pairs) )
            sys.stderr.write( "Time taken for loading rules in dict and Trie : %1.3f sec\n\n" % (t_end - t_beg) )

        return None

    def buildFeatVec(self, probs, tgt_rule):
        '''Build the feature vector from a string of probs and add to it phrase & word penalty and glue score'''

        # All feature values must be represented as log-probs in base 'e'
        # Any log-prob in base '10' must be converted to base 'e' by dividing it by math.log10(math.exp(1)) i.e 0.434294
        global featVec
        term_count = 0

        # add the TM features
        featVec = [float(x) for x in probs.split()]                              # For using Kriya PT (for base-e log probs)

        # now add phrase penalty and word penalty to the featVec
	term_count=0
	tgtReordering = 0
	for w in tgt_rule.split():
	    if not w.startswith("X__"):
		term_count += 1 
	    elif w!="X__"+str(term_count): tgtReordering = 1
        featVec += [self.pp_val, -term_count, 0, 0] 
	fLen = len(featVec)
	for i in range(len(settings.opts.U_lpTup[2]) - fLen):
            featVec.append(0)
	featVec[10] = tgtReordering ## feature "r"

    def makeGlueRules(self, TOT_TERMS):  
        '''Loads the glue rules along with their feature values'''
        prev_src = ''
	glue_rule_pairs = 0
        uniq_src_rules = 0
        entriesLst = []
        t_beg = time.time()
	ppenalty = self.wVec.tm[4]*self.pp_val         

        try:
            #for src in PhraseTable.terminalRules:
            for src in PhraseTable.ruleDict:
		entriesLst = PhraseTable.ruleDict[src]
		nonTermNo = -1
		if src in PhraseTable.terminalRules:
		    tgts = [' X__1', ' X__1', ' X__1 X__2', ' X__2 X__1']	
		    srcs = ['X__1 '+ src, src+' X__1', 'X__1 '+ src+' X__2']		      
		elif settings.opts.glue_type > 0:
		    nonTermNo = getLastNonTremNumber(src)
		    if nonTermNo < 0: continue
		    if nonTermNo == 0: 
			if src[:-5] in PhraseTable.terminalRules: continue
			if settings.opts.glue_type == 1:
			    tgts = ['']	
			    srcs = [src]
			else:
			    tgts = ['', ' X__3']	
			    srcs = [src, src+' X__3']
		    else:
			tgts = [' X__'+str(nonTermNo+1)]	
			srcs = [src+tgts[0]]
                else: continue

		for src_index,glue_src in enumerate(srcs): 
		    #if nonTermNo == 0 and src_index == 0: continue
		    #if nonTermNo > 0 and glue_src.endswith("X__2"): continue
		    if settings.opts.one_nt_decode and glue_src.find('X__2') >= 0: continue
		    sortFlag = False
		    if glue_src in PhraseTable.gruleDict:
			sortFlag = True
			continue
		    else:   uniq_src_rules += 1
		    tmpRuleLst =  []
		    tgt_pf = tgts[src_index] 
		    
		    tgt_options = 0
		    for entry_obj in entriesLst:
			if nonTermNo == 0 and src_index == 0 and entry_obj.tgt.split()[-1] != entry_obj.src.split()[-1]: continue  ## rules like: <A X2/A' X1> cannot be used as glue rule
			if nonTermNo == 0 and src_index == 1 and entry_obj.tgt.split()[-1] == entry_obj.src.split()[-1]: continue  ## rules like: <A X2/A' X2> does not need X3
			PhraseTable.tot_rule_pairs += 1
			glue_rule_pairs += 1
			featVec = entry_obj.featVec[:]
			featVec[settings.opts.glue_penalty] = 1
			featVec[4] = 0
			#score = entry_obj.score + self.wVec.glue - ppenalty				
			entry_objCpy = Rule(0, entry_obj.lm_heu, glue_src, entry_obj.tgt + tgt_pf, featVec)
			entry_objCpy.completeInfo()
			tmpRuleLst.append( entry_objCpy )
			if src_index == 2:
			    PhraseTable.tot_rule_pairs += 1  
			    glue_rule_pairs += 1
			    featVec = entry_objCpy.featVec[:]
			    featVec[10] = 1                             ## it is a rule with reordered nonterminals: <X1 src X2/tgt X2 X1>
			    entry_objCpy = Rule(0, entry_obj.lm_heu, glue_src, entry_obj.tgt + tgts[src_index+1], featVec)
			    entry_objCpy.completeInfo()
			    tmpRuleLst.append( entry_objCpy )
			tgt_options += 1
			if(tgt_options >= self.ttlg): 
			    tgt_options = 0
			    break
		    if sortFlag:
			newEntries = []
			tgtLst = []
			for ruleLst in [PhraseTable.gruleDict[glue_src], tmpRuleLst]:
			    for entry_obj in ruleLst:
				try:
				    tgtInd = tgtLst.index(entry_obj.tgt)
				    glue_rule_pairs -= 1
				    PhraseTable.tot_rule_pairs -= 1
				    if newEntries[tgtInd].prob_e_f > entry_obj.featVec[0]: continue
				    newEntries[tgtInd] = PTableItem(entry_obj.featVec[0], entry_obj)
				    tgtLst[tgtInd] = entry_obj.tgt
				    continue
				except:
				    pass
				newEntries.append( PTableItem(entry_obj.featVec[0], entry_obj) )
				tgtLst.append(entry_obj.tgt)
			newEntries.sort(key=operator.attrgetter("prob_e_f"), reverse=True)
			PhraseTable.gruleDict[glue_src] = []
			for entry_pair in newEntries:
			    PhraseTable.gruleDict[glue_src].append(entry_pair.entry_item)	    
		    else:		    
			if PhraseTable.glue_trie is None:
			    PhraseTable.glue_trie = SimpleSuffixTreeForGlue(glue_src,TOT_TERMS)
			else:
			    if glue_src in PhraseTable.gruleDict: print "exist previously!!: ",glue_src
			    PhraseTable.glue_trie.addText(glue_src)
			PhraseTable.gruleDict[glue_src] = tmpRuleLst
				
	finally:
	    t_end = time.time()
            sys.stderr.write( "Glue rule - ttable limit                     : %d\n" % (self.ttlg) )
            sys.stderr.write( "Unique source rules found                     : %d\n" % (uniq_src_rules) )
            sys.stderr.write( "Total pairs of SCFG rules loaded              : %d\n" % (glue_rule_pairs) )
            sys.stderr.write( "Time taken for loading rules in dict and Trie : %1.3f sec\n\n" % (t_end - t_beg) )

    @classmethod
    def tgtMatchesRef(cls, tgt_phr):
        '''Check whether phrases in the target rules match the reference(s)'''

        tgtToks = tgt_phr.split()
        tgt_i = 0
        beg_pos = 0
        for tgt_tok in tgtToks:
            if tgt_tok == "X__1" or tgt_tok == "X__2":
                if tgt_i > 0 and tgt_i > beg_pos:
                    rule_phr = ' '.join( tgtToks[beg_pos:tgt_i] )
                    if not RefPhrases.isValidRefPhr(rule_phr):
                        return False
                beg_pos = tgt_i + 1
            tgt_i += 1

        if tgt_i > beg_pos:
            rule_phr = ' '.join( tgtToks[beg_pos:tgt_i] )
            if not RefPhrases.isValidRefPhr(rule_phr):
                return False
        return True

    @classmethod
    def getUnigramLMScore(cls, tgt_rule):
	''' Compute the LM Heuristic score (unigrams) for the target phrase '''
	lm_H = 0.0
	if settings.opts.no_lm_score: return lm_H
	for tgt_term in tgt_rule.split():
	    if tgt_term != 'X__1' and tgt_term != 'X__2':
		if settings.opts.use_srilm: lm_H += SRILangModel.queryLM(tgt_term, 1)  # for SRILM wrapper
		else: lm_H += KENLangModel.queryLM(tgt_term, 1)  # for KENLM wrapper
	return lm_H        

    @classmethod
    def getLMHeuScore(cls, tgt_rule):
	''' Compute the LM score for the target phrase '''
	if settings.opts.no_lm_score: return 0.0
        tgtLx = tgt_rule[:]
        if tgt_rule.find("X__") > -1:
	    tgtLx = tgt_rule[0:tgt_rule.find("X__")].strip()

	tgt_words = tgtLx.split()
        lmorder = settings.opts.n_gram_size

	tmp_phrase = ""
	lm_H = 0.0
	for i in range(len(tgt_words)):
	    if i == lmorder - 1 : break
	    tmp_phrase = " ".join(tgt_words[0:i+1])
	    if settings.opts.use_srilm: lm_H += SRILangModel.queryLM(tgt_words[0:i+1], i+1)  # for SRILM wrapper
	    else: lm_H += KENLangModel.queryLM(tmp_phrase, i+1)  # for KENLM wrapper 
		
	if len(tgt_words) >= lmorder:
	    if settings.opts.use_srilm: lm_H += SRILangModel.queryLM(tgt_words, len(tgt_words))  # for SRILM wrapper
	    else: lm_H += KENLangModel.queryLM(tgtLx, len(tgt_words))  # for KENLM wrapper 
 
        #lmorder = settings.opts.n_gram_size if len(tgt_words) >= settings.opts.n_gram_size else len(tgt_words)
	#lm_H = 0.0
	#for tgt_term in tgt_rule.split():
	#    if tgt_term != 'X__1' and tgt_term != 'X__2':
	#	if settings.opts.use_srilm: lm_H += SRILangModel.queryLM(tgt_term, 1)  # for SRILM wrapper
	#	else: lm_H += KENLangModel.queryLM(tgt_term, 1)  # for KENLM wrapper
	return lm_H        

    @classmethod
    def tgtMatchesRefSent(cls, tgt_phr, sent_id):
        '''Check whether phrases in the target rules match the current set of reference sentence(s)'''

        tgtToks = tgt_phr.split()
        tgt_i = 0
        beg_pos = 0
        for tgt_tok in tgtToks:
            if tgt_tok == "S__1" or tgt_tok == "X__1" or tgt_tok == "X__2":
                if tgt_i > 0 and tgt_i > beg_pos:
                    rule_phr = ' '.join( tgtToks[beg_pos:tgt_i] )
                    if not RefPhrases.isValidRefPhrNSent(sent_id, rule_phr):
                        return False
                beg_pos = tgt_i + 1
            tgt_i += 1

        if tgt_i > beg_pos:
            rule_phr = ' '.join( tgtToks[beg_pos:tgt_i] )
            if not RefPhrases.isValidRefPhrNSent(sent_id, rule_phr):
                return False
        return True

    @classmethod
    def hasRule(cls, src_phr):
        '''Helper function for checking whether rules are found for a given source rule'''

        return src_phr in cls.ruleDict

    @classmethod
    def hasgRule(cls, src_phr):
        '''Helper function for checking whether glue rules are found for a given source rule'''

        return src_phr in cls.gruleDict

    @classmethod
    def getRuleEntries(cls, src_phr, sent_indx):
        '''Helper function for returning the rule entries for a given source rule'''

	## log
        #print "Total entries in ruleDict : ", len( cls.ruleDict[src_phr] )
        if False: #settings.opts.force_decode:
            ruleLst = []
            for tgt_entry in cls.ruleDict.get(src_phr, []):
                if cls.tgtMatchesRefSent(tgt_entry.tgt, sent_indx):
                    ruleLst.append( tgt_entry )
	    gruleLst = []
	    for tgt_entry in cls.gruleDict.get(src_phr, []):
		if cls.tgtMatchesRefSent(tgt_entry.tgt, sent_indx):
		    gruleLst.append( tgt_entry )	    
            return ruleLst, gruleLst
        else:
            return cls.ruleDict.get(src_phr, []), cls.gruleDict.get(src_phr, [])

    @classmethod
    def addUNKRule(cls, src_phr, entries):
	if src_phr not in PhraseTable.ruleDict and src_phr not in PhraseTable.gruleDict:
	    PhraseTable.src_trie.addText(src_phr)
	if src_phr not in PhraseTable.ruleDict:
            cls.ruleDict[src_phr] = []
	cls.ruleDict[src_phr] += entries

    @classmethod
    def addUNKGRule(cls, src_phr, entries):
	if src_phr not in PhraseTable.ruleDict and src_phr not in PhraseTable.gruleDict:
	    PhraseTable.glue_trie.addText(src_phr)	
	if src_phr not in PhraseTable.gruleDict:
            cls.gruleDict[src_phr] = []
        cls.gruleDict[src_phr] += entries
	
    @classmethod
    def findConsistentRules(cls, src_span, isGlue=False):
	if isGlue: return SimpleSuffixTreeForGlue.matchPattern(cls.glue_trie, src_span)
        return SimpleSuffixTree.matchPattern(cls.src_trie, src_span)

    @classmethod
    def getTotalRules(cls):
        return cls.tot_rule_pairs
    
    @classmethod
    def createUNKRule(cls, src_phr):
	featVec = settings.opts.U_lpTup[2][:]
	featVec[settings.opts.lm_index] = 0
	lm_score = settings.feat.lm * cls.getLMHeuScore(src_phr)
	featVec[settings.opts.word_penalty] = -len(src_phr.split())
	
        rule_obj = Rule(0, lm_score, src_phr, src_phr, featVec, src_phr)
	rule_obj.completeInfo()
	
	cls.addUNKRule(src_phr, [rule_obj])

	feat_Vec = featVec[:]
	featVec[settings.opts.glue_penalty] = 1
	featVec[4] = 0 ##it is a glue rule not regular rule
	
	tgts = [' X__1', ' X__1', ' X__1 X__2', ' X__2 X__1']
	srcs = ['X__1 '+ src_phr, src_phr+' X__1', 'X__1 '+ src_phr+' X__2']
    
	for index, src in enumerate(srcs):
	    gEntries = []
	    rEntries = []
	    tgt = src_phr+tgts[index]
	    gEntries.append( Rule(0, lm_score, src, tgt, featVec))
	    gEntries[-1].completeInfo()
	    rEntries.append( Rule(0, lm_score, src, tgt, feat_Vec))
	    rEntries[-1].completeInfo()
	    if index == 2:
		tgt = src_phr+tgts[index+1]
		gEntries.append( Rule(0, lm_score, src, tgt, featVec))
		gEntries[-1].completeInfo()
		rEntries.append( Rule(0, lm_score, src, tgt, feat_Vec))
		rEntries[-1].completeInfo()
	    cls.addUNKGRule(src, gEntries)
	    cls.addUNKRule(src, rEntries)
	return rule_obj

class PTableItem(object):
    '''Phrase table item class for temporarily handling  SCFG rules and serving associated queries'''

    __slots__ = "prob_e_f", "entry_item"

    def __init__(self, p_ef, e_obj):
        self.prob_e_f = p_ef
        self.entry_item = e_obj


def getLastNonTremNumber(src):
    ''' if last term is a non-terminal    : 0
        if no non-term                    : -1
        otherwise                         : bigest nonterminal'''
    src_w = src.split()
    #if len(src_w) == settings.opts.max_span_size: return -1
    if src_w[-1].startswith("X__"): 
	return 0
    bigestNonTerm = -1
    for w in src_w:
	if w.startswith("X__"):
	    bigestNonTerm = int(w[3:])
    return bigestNonTerm
