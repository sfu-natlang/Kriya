## @author: Maryam

import sys

import settings
from cover import defaultSign
from lmKENLM import KENLangModel
from lmSRILM import SRILangModel

class Entry(object):
    '''Individual entries in the cells of the parse triangle'''

    __slots__ = "score", "tgt", "featVec", "tgt_elided", "depth_hier", "inf_cell", "inf_entry", "bp", "cand_score", "lm_right", "sign"
 
    def __init__(self, score, tgt, featVec, tgt_elided, sign=None, rule_depth=0, inf_cell=(), inf_entry=None, bp=(), cand_score=0.0, r_lm_state=None):
        self.score = score
        self.tgt = tgt
        self.featVec = featVec[:]
	self.tgt_elided = tgt_elided
	self.sign = sign
        self.depth_hier = rule_depth
        self.inf_cell = inf_cell
        self.inf_entry = inf_entry                                      # Entry object for the consequent entry
        self.bp = bp                                                    # List of entry objects of the antecedents
        self.cand_score = cand_score
        self.lm_right = r_lm_state
	
    def groupSign(self):
	return self.sign.cover

    def copyEntry(self, other):
        other.score = self.score
        other.tgt = self.tgt
	other.tgt_elided = self.tgt_elided
        other.featVec = self.featVec[:]
        other.depth_hier = self.depth_hier
        other.inf_entry = None
        other.bp = ()
        other.cand_score = 0.0
        other.lm_right = self.lm_right

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
	return  " ||| ".join([cand_hyp, feat_str, str(self.score), str(self.sign.future_cost), str(self.sign)])

    def getHypScore(self):
        return self.score

    def getFutureScore(self):
        return self.sign.future_cost

    def getHeuScore(self):
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
        self.cand_score = self.score + self.sign.future_cost

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
	

def getInitHyp(sent_len):
	return Entry(0, "<s>",[0 for i in settings.opts.U_lpTup[2]], "<s>", defaultSign(sent_len)) 
