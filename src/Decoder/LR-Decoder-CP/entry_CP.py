## @author baskaran

import sys

import settings
from lmKENLM import KENLangModel
from lmSRILM import SRILangModel

class Entry(object):
    '''Individual entries in the cells of the parse triangle/ rules list'''

    __slots__ = "score", "lm_heu", "src", "tgt", "featVec", "tgt_elided", "depth_hier", "inf_cell", "inf_entry", "bp", "cand_score", "lm_right", "unc_spans", "fc", "cover", "tm4_score", "sign"
 
    def __init__(self, score, lm_heu, src, tgt, featVec, tgt_elided, rule_depth=0, inf_cell=(), inf_entry=None, bp=(), cand_score=0.0, r_lm_state=None):
        self.score = score
        self.lm_heu = lm_heu
        self.src = src
        self.tgt = tgt
        self.featVec = featVec[:]
        self.tgt_elided = tgt_elided
        self.depth_hier = rule_depth
        self.inf_cell = inf_cell
        self.inf_entry = inf_entry                                      # Entry object for the consequent entry
        self.bp = bp                                                    # List of entry objects of the antecedents
        self.cand_score = cand_score
        self.lm_right = r_lm_state
	self.unc_spans = None
	self.cover = None
	self.fc = None
        self.tm4_score = None
	self.sign = None
  
    def setRuleCover(self):
	ll = []
	for sp in self.unc_spans:
		ll += [i for i in range(sp[0][0], sp[0][1])]
	self.cover = set(ll)

    def setCoverage(self, new_spans, parent=None):
	if parent == None:
		self.unc_spans = new_spans[:]
		self.fc = 0
		ll = []
		for sp in new_spans:
			#ll += [i for i in range(sp[0][0], sp[0][1])]
			self.fc += sp[2]
		self.cover = set(ll)
		if settings.opts.hyp_sign == 0:
			self.sign = (self.tgt, frozenset(self.cover))
		elif settings.opts.hyp_sign == 1:
			self.sign = (self.tgt_elided, frozenset(self.cover))
		elif settings.opts.hyp_sign == 2:
			tmpLst = []
			for l in self.unc_spans:
				if l[0][0] < 0: continue
				tmpLst.append((l[0][0],l[0][1]))
			self.sign = (self.tgt_elided, tuple(tmpLst))
		
		return
	parent_spans = parent.unc_spans[1:]
	uncovered_span = parent.unc_spans[0]
	spans = []
	hFeat = 0
	ll = []
	fc = 0
	for sp in new_spans:
		spans.append((sp[0], uncovered_span[1]+1, sp[2]))
		ll += [i for i in range(sp[0][0], sp[0][1])]
		fc += sp[2]
	fc -= uncovered_span[2]
	filled = [i for i in range(uncovered_span[0][0], uncovered_span[0][1])]
	#newset = set( (i for i in xrange()) ) - set(ll)
	newSet = set(filled) - set(ll)
	self.cover = newSet | parent.cover

	if len(spans)==0:
            if  len(parent_spans)>0 and len(parent_spans[0]) == 3:
                hFeat = abs(uncovered_span[1] - parent_spans[0][1])+1
                try:
                        dommy=((-0.5, -0.5), parent_spans[1][1], 0, hFeat)
			workingIndex = 0
			while len(parent_spans[workingIndex]) == 3: workingIndex += 1
                        new_unc_spans = parent_spans[:workingIndex]+[dommy]
                        if len(parent_spans)>workingIndex+1:
                                new_unc_spans += parent_spans[workingIndex+1:]    #uncovered spans
                except:
                        print  "error in dommy spans1:  ", parent_spans
                        exit(1)
            elif len(parent_spans)>0:
                hFeat = abs(uncovered_span[1] - parent_spans[0][1])
                workingIndex = 0
                while workingIndex < len(parent_spans) and len(parent_spans[workingIndex]) != 3:
                        hFeat = max(hFeat+1, parent_spans[workingIndex][3])
                        workingIndex += 1
                if workingIndex < len(parent_spans):
                        try:
				start_real_span_ind = workingIndex
				while len(parent_spans[workingIndex]) == 3: workingIndex += 1
                                dommy=((-0.5, -0.5), parent_spans[workingIndex][1], 0, hFeat+1)
	                        new_unc_spans = parent_spans[start_real_span_ind:workingIndex]+[dommy]
                                if len(parent_spans)>workingIndex+1:
                                        new_unc_spans += parent_spans[workingIndex+1:]                       #uncovered spans
                        except:
                                print "error in dommy spans2:  ", parent_spans
                                #print >>stderr, "error in dommy spans2:  ", parent_spans
                                exit(1)
                else:
                        hFeat=0
                        new_unc_spans = []
	    else:
		#print fc, parent.fc
		new_unc_spans = []
	else:
        	dommy = ((-0.5, -0.5), uncovered_span[1], 0, 0)
	        new_unc_spans = spans+[dommy]+parent_spans                    #uncovered spans

	self.featVec[12] += -hFeat
	self.score += (-hFeat)* settings.opts.weight_h
	try:
		self.unc_spans = new_unc_spans
	except:
		print spans, len(spans)
		exit(1)
	self.fc = parent.fc + fc
	
	## debuging 
	#if len(new_unc_spans) == 0:
	 #   print "00000"
	  #  bp = parent
	   # while bp:
	#	bp.printIt()
	#	bp = bp.bp[0]

	## set signature
	if settings.opts.hyp_sign == 0:
		self.sign = (self.tgt, frozenset(self.cover))
	elif settings.opts.hyp_sign == 1:
		self.sign = (self.tgt_elided, frozenset(self.cover))
	elif settings.opts.hyp_sign == 2:
		tmpLst = []
		for l in self.unc_spans:
			if l[0][0] < 0: continue
			tmpLst.append((l[0][0],l[0][1]))
		self.sign = (self.tgt_elided, tuple(tmpLst))


    def recombineEntry(self, hyp_w_LM, wvec_lm):
        '''Hypothesis recombination: LM info from an existing hypothesis is copied into a new hypothesis with better score'''

	if settings.opts.hyp_sign != 0:
            return self.score + self.fc
        if self.tgt != hyp_w_LM.tgt or self.cover != hyp_w_LM.cover:                                       # sanity check ...
            print "ERROR (Serious): Entry objects have different target strings"
            print "   Current hyp  : ", self.tgt, self.cover
            print "   Existing hyp : ", hyp_w_LM.tgt, hyp_w_LM.cover
            print
            sys.exit(1)

        frag_lm_score = hyp_w_LM.featVec[6] - self.featVec[6]
        self.lm_heu = hyp_w_LM.lm_heu
        self.tgt_elided = hyp_w_LM.tgt_elided
        self.depth_hier = hyp_w_LM.depth_hier
        self.inf_cell = hyp_w_LM.inf_cell
        self.featVec[6] = hyp_w_LM.featVec[6]
        self.lm_right = hyp_w_LM.lm_right
	#self.fc = hyp_w_LM.fc		#should be the same

        #self.score += self.lm_heu + (wvec_lm * frag_lm_score)
        self.score += (wvec_lm * frag_lm_score)
        return self.score + self.fc

    def copyLMInfo(self, hyp_w_LM, wvec_lm):
        '''Copy the language model information from an existing hypothesis to a new one with the same target'''

	if settings.opts.hyp_sign != 0:
            return self.score + self.fc
        if self.tgt != hyp_w_LM.tgt or self.cover != hyp_w_LM.cover:                                       # sanity check ...
            print "ERROR (Serious): Entry objects have different target strings"
            print "   Current hyp  : ", self.tgt, self.cover
            print "   Existing hyp : ", hyp_w_LM.tgt, hyp_w_LM.cover
            print
            sys.exit(1)

        frag_lm_score = hyp_w_LM.featVec[6] - self.featVec[6]
        self.lm_heu = hyp_w_LM.lm_heu
        self.tgt_elided = hyp_w_LM.tgt_elided
        self.depth_hier = hyp_w_LM.depth_hier
        self.featVec[6] = hyp_w_LM.featVec[6]
        self.lm_right = hyp_w_LM.lm_right

        #self.score += self.lm_heu + (wvec_lm * frag_lm_score)
        self.score += (wvec_lm * frag_lm_score)
        return self.score + self.fc

    def copyEntry(self, other, span):
        other.score = self.score
        other.tm4_score = self.tm4_score
        other.lm_heu = self.lm_heu
        other.src = self.src
        other.tgt = self.tgt
        other.featVec = self.featVec[:]
        other.tgt_elided = self.tgt_elided
        other.depth_hier = self.depth_hier
        other.inf_cell = span
        other.inf_entry = None
        other.bp = ()
        other.cand_score = 0.0
        other.lm_right = self.lm_right
	other.fc = self.fc
	other.cover = self.cover
	other.unc_spans = self.unc_spans
	other.sign = self.sign

        return other

    def setInfCell(self, span):
        self.inf_cell = span

    def getInfCell(self):
        return self.inf_cell

    def getInfEntry(self):
        return self.inf_entry

    def getSign(self):
	return self.sign

    def getFeatVec(self):
        return ' '.join( map(lambda x: str(x), self.featVec) )

    def getBP(self):
        '''Returns the back-pointer of the current hypothesis'''

        return self.bp

    def getSrc(self):
        return self.src

    def getHypothesis(self):
        '''Remove the beginning and end sentence markers in the translation'''

        if self.tgt.startswith("<s>") and self.tgt.endswith("</s>"):
            return self.tgt[4:-5]
        elif self.tgt.startswith("<s>") and not self.tgt.endswith("</s>"):
            return self.tgt[4:]
        elif not self.tgt.startswith("<s>") and self.tgt.endswith("</s>"):
            return self.tgt[:-5]
        else: return self.tgt

    def printEntry(self):
        '''Prints the specific elements of the result'''

        feat_str = ''

        cand_hyp = self.getHypothesis()
        #if settings.opts.no_dscnt_UNKlm: lm_excl_UNK = self.featVec[6]
        #elif settings.opts.use_srilm: lm_excl_UNK = self.featVec[6] - SRILangModel.calcUNKLMScore(cand_hyp)
        #else: lm_excl_UNK = self.featVec[6] - KENLangModel.calcUNKLMScore(cand_hyp)
	lm_excl_UNK = self.featVec[6]

        if (settings.opts.no_glue_penalty):
            feats = ['lm:', 'wp:', 'tm:']
        else:
            feats = ['lm:', 'glue:', 'wp:', 'tm:']
	reorderFeats = []
	if settings.opts.weight_d != 0:
		feats.append('d:')
		reorderFeats.append(self.featVec[8])
	if settings.opts.weight_dg != 0:
		feats.append('dg:')
		reorderFeats.append(self.featVec[9])
	if settings.opts.weight_r != 0:
		feats.append('r:')
		reorderFeats.append(self.featVec[10])
	if settings.opts.weight_w != 0:
		feats.append('wd:')
		reorderFeats.append(self.featVec[11])
	if settings.opts.weight_h!= 0:
		feats.append('hd:')
		reorderFeats.append(self.featVec[12])
	reorder_str = ' '.join(map(lambda x: str(x), reorderFeats))
        tm_str = ' '.join( map(lambda x: str(x), self.featVec[0:5]) )
        if (settings.opts.zmert_nbest):
	    if (settings.opts.no_glue_penalty):	featLst = [lm_excl_UNK, self.featVec[5], tm_str]+reorderFeats
            else: featLst = [lm_excl_UNK, self.featVec[7], self.featVec[5], tm_str]+reorderFeats
	    feat_str = ' '.join( map(lambda x: str(x), featLst) )
        else:
	    if (settings.opts.no_glue_penalty):	featLst = [lm_excl_UNK, self.featVec[5], tm_str]+reorderFeats
            else: featLst = [lm_excl_UNK, self.featVec[7], self.featVec[5], tm_str]+reorderFeats
            feat_str = ' '.join( map(lambda x,y: x+' '+str(y), feats, featLst) )

        return cand_hyp, feat_str, self.cand_score

    def printPartialHyp(self):
	(cand_hyp, feat_str, cand_score) = self.printEntry()
	unc_span_str = ",".join([str(t) for t in self.unc_spans])
	try: signStr = ",".join([str(t) for t in self.sign[1]])
	except: signStr = "None"
	
	return  " ||| ".join([cand_hyp, feat_str, unc_span_str, str(self.score), str(self.fc), signStr])

    def getHypScore(self):
        return self.score

    def getFutureScore(self):
        return self.fc

    def getHeuScore(self, wvec_wp):
	'''Get the heuristic cost for terminal rules to compute future cost'''
	if self.tm4_score is None:
		self.tm4_score = self.featVec[0] * settings.feat.tm[0] + self.featVec[1] * settings.feat.tm[1] +\
			self.featVec[2] * settings.feat.tm[2] + self.featVec[3] * settings.feat.tm[3]
	return self.tm4_score + self.lm_heu
	#return self.score - (wvec_wp * self.featVec[5]) + self.lm_heu

    def getLMHeu(self):
        return self.lm_heu

    def getScoreSansLM(self, wvec_lm):
        #return self.score - self.lm_heu - (wvec_lm * self.featVec[6])
        return self.score - (wvec_lm * self.featVec[6])

    def scoreCandidate(self):
        self.cand_score = self.score + self.fc

    def scoreSentence(self):
        '''Get complete score for candidate including feature functions left-out during search'''

        self.cand_score = self.score

    def printIt(self):
        '''Print the entry (for debugging purposes)'''

        print "Score           :", self.score
        print "LM Heu          :", self.lm_heu
        print "Target          :", self.tgt
        print "Elided          :", self.tgt_elided
        print "Feat-vec        :", self.featVec
        print "Bpointer        :", self.bp[0]
        print "Parent rule     :", self.bp[1]
	unc_span_str = ",".join([str(t) for t in self.unc_spans])
        print "uncovered spans :", unc_span_str

def getInitHyp(sent_len, fc):
	init =  Entry(0, 0, "<s>", "<s>",[0 for i in settings.opts.U_lpTup[2]], "<s>") 
	init.setCoverage([((0,sent_len),0, fc)])
	return init
