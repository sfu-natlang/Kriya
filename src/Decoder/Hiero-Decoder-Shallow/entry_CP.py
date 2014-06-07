## @author baskaran

import sys

import settings
from lmKENLM import KENLangModel
from lmSRILM import SRILangModel

class Entry(object):
    '''Individual entries in the cells of the parse triangle/ rules list'''

    __slots__ = "score", "lm_heu", "src", "tgt", "featVec", "tgt_elided", "depth_hier", "inf_cell", "inf_entry", "bp", "cand_score", "lm_right"
 
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

    def recombineEntry(self, hyp_w_LM, wvec_lm):
        '''Hypothesis recombination: LM info from an existing hypothesis is copied into a new hypothesis with better score'''

        if self.tgt != hyp_w_LM.tgt:                                          # sanity check ...
            print "ERROR (Serious): Entry objects have different target strings"
            print "   Current hyp  : ", self.tgt
            print "   Existing hyp : ", hyp_w_LM.tgt
            print
            sys.exit(1)

        frag_lm_score = hyp_w_LM.featVec[6] - self.featVec[6]
        self.lm_heu = hyp_w_LM.lm_heu
        self.tgt_elided = hyp_w_LM.tgt_elided
        self.depth_hier = hyp_w_LM.depth_hier
        self.inf_cell = hyp_w_LM.inf_cell
        self.featVec[6] = hyp_w_LM.featVec[6]
        self.lm_right = hyp_w_LM.lm_right

        self.score += self.lm_heu + (wvec_lm * frag_lm_score)
        return self.score

    def copyLMInfo(self, hyp_w_LM, wvec_lm):
        '''Copy the language model information from an existing hypothesis to a new one with the same target'''

        if self.tgt != hyp_w_LM.tgt:                                          # sanity check ...
            print "ERROR (Serious): Entry objects have different target strings"
            print "   Current hyp  : ", self.tgt
            print "   Existing hyp : ", hyp_w_LM.tgt
            print
            sys.exit(1)

        frag_lm_score = hyp_w_LM.featVec[6] - self.featVec[6]
        self.lm_heu = hyp_w_LM.lm_heu
        self.tgt_elided = hyp_w_LM.tgt_elided
        self.depth_hier = hyp_w_LM.depth_hier
        self.featVec[6] = hyp_w_LM.featVec[6]
        self.lm_right = hyp_w_LM.lm_right

        self.score += self.lm_heu + (wvec_lm * frag_lm_score)
        return self.score

    def copyEntry(self, other, span):
        other.score = self.score
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

        return other

    def setInfCell(self, span):
        self.inf_cell = span

    def getInfCell(self):
        return self.inf_cell

    def getInfEntry(self):
        return self.inf_entry

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
        if settings.opts.no_dscnt_UNKlm: lm_excl_UNK = self.featVec[6]
        elif settings.opts.use_srilm: lm_excl_UNK = self.featVec[6] - SRILangModel.calcUNKLMScore(cand_hyp)
        else: lm_excl_UNK = self.featVec[6] - KENLangModel.calcUNKLMScore(cand_hyp)

        if (settings.opts.no_glue_penalty):
            feats = ['lm:', 'wp:', 'tm:']
        else:
            feats = ['lm:', 'glue:', 'wp:', 'tm:']

        tm_str = ' '.join( map(lambda x: str(x), self.featVec[0:5]) )
        if (settings.opts.zmert_nbest):
            feat_str = ' '.join( map(lambda x: str(x), [lm_excl_UNK, self.featVec[5], tm_str]) ) if (settings.opts.no_glue_penalty) \
                        else ' '.join( map(lambda x: str(x), [lm_excl_UNK, self.featVec[7], self.featVec[5], tm_str]) )
        else:
            feat_str = ' '.join( map(lambda x,y: x+' '+str(y), feats, [lm_excl_UNK, self.featVec[5], tm_str]) ) if (settings.opts.no_glue_penalty) \
                        else ' '.join( map(lambda x,y: x+' '+str(y), feats, [lm_excl_UNK, self.featVec[7], self.featVec[5], tm_str]) )

        return cand_hyp, feat_str, self.cand_score

    def getHypScore(self):
        return self.score

    def getLMHeu(self):
        return self.lm_heu

    def getScoreSansLM(self, wvec_lm):
        return self.score - self.lm_heu - (wvec_lm * self.featVec[6])

    def scoreCandidate(self):
        self.cand_score = self.score

    def scoreSentence(self):
        '''Get complete score for candidate including feature functions left-out during search'''

        self.cand_score = self.score

    def printIt(self):
        '''Print the entry (for debugging purposes)'''

        print "Score    :", self.score
        print "LM Heu   :", self.lm_heu
        print "Target   :", self.tgt
        print "Elided   :", self.tgt_elided
        print "Feat-vec :", self.featVec
        print "Bpointer :", self.bp
