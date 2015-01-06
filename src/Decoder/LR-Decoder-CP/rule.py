## @author: Maryam

import sys

import settings
from lmKENLM import KENLangModel
from lmSRILM import SRILangModel

class Rule(object):
    '''Structure to save rules/phrases'''
    __slots__ = "score", "lm_heu", "src", "tgt", "featVec", "tgt_elided", "lm_right", "src_len", "tm4_score", "dist"
    
    def __init__(self, score, lm_heu, src, tgt, featVec, tgt_elided='', sign=None, r_lm_state=None):
        self.score = score
        self.lm_heu = lm_heu
        self.src = src
        self.tgt = tgt
        self.featVec = featVec[:]
	self.tgt_elided = tgt_elided
        self.lm_right = r_lm_state
	
    def completeInfo(self):
	self.tm4_score = self.featVec[0] * settings.feat.tm[0] + self.featVec[1] * settings.feat.tm[1] +\
	    self.featVec[2] * settings.feat.tm[2] + self.featVec[3] * settings.feat.tm[3]
	self.score = self.tm4_score + \
	    (settings.feat.tm[4] * self.featVec[4])+ (settings.feat.wp * self.featVec[5]) + \
	    (settings.feat.glue * self.featVec[7] + settings.feat.r * self.featVec[10])	
	self.src_len = 0
	for w in self.src.split():
	    if not w.startswith("X__"): self.src_len += 1
	self.dist = Distortion(self.src, self.tgt)
	xInd = self.tgt.find("X__")
	self.tgt_elided = self.tgt[:xInd].strip() if xInd > 0 else self.tgt
	
    def isGlue(self):
	return self.featVec[settings.opts.glue_penalty]

    def copyRule(self, other):
        other.score = self.score
        other.tm4_score = self.tm4_score
        other.lm_heu = self.lm_heu
        other.src = self.src
        other.tgt = self.tgt
	other.tgt_elided = self.tgt_elided
        other.featVec = self.featVec[:]
        other.lm_right = self.lm_right
	other.src_len = self.src_len
	other.dist = self.dist
        return other

    def getScore(self):
        return self.score

    def getHeuScore(self):
	'''Get the heuristic cost for terminal rules to compute future cost'''
	return self.tm4_score + self.lm_heu
	    
    def getLMHeu(self):
        return self.lm_heu

    def __str__(self):
        '''Prints the specific elements of the result'''

        feat_str = ''
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

        return  " ||| ".join([self.src, self.tgt, feat_str, str(self.score)])
    
class Distortion():
    '''A structure to save span information for rules to accelerate computation of distortion'''
    __slots__ = "xDict", "dist"
    def __init__(self, src, tgt):
        ind = 0
        spans = {}
        s = 0
        orders = []
        for i,w in enumerate(src.split()):
            if w.startswith("X__"):
                spans[ind] = (s,i)
                spans[ind+1] = w
                s=i+1
                orders.append(ind)
                ind+=2
        spans[ind] = (s,len(src.split()))
	## check if there is terminal at the end of the source side
        if spans[ind][0] < spans[ind][1]: orders.append(ind)

        xDict = {}
        for w in tgt.split():
            if w.startswith("X__"):
                orders.append(int(w[3:])*2-1)  ## index of each nonterminal is based on the fact that it is sorted on the src side and there is no adjacent nonterminal on the src side
                xDict[w] = 0
        orders.append(ind+1)  ## dommy span for the end of the main span

        self.dist = 0
        for i in range(1, len(orders)):
            for j in range(min(orders[i], orders[i-1]+1), max(orders[i], orders[i-1]+1)):
                if spans[j] in xDict: xDict[spans[j]] += 1
                else: self.dist += spans[j][1] - spans[j][0]

        ## save the dictionary with integer keys
        self.xDict = {}
        for x in xDict:
            self.xDict[int(x[3:])] = xDict[x]

    def get(self, spans):
        d = 0
        for i,s in enumerate(spans):
            d += s*self.xDict[i+1]
        return self.dist + d
