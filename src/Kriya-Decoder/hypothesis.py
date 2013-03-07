## @author baskaran

import sys

import settings
from featureManager import FeatureManager
from languageModelManager import LanguageModelManager

class Hypothesis(object):
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

    def recombineEntry(self, hyp_w_LM):
        '''Hypothesis recombination: LM info from an existing hypothesis is copied into a new hypothesis with better score'''

        if self.tgt != hyp_w_LM.tgt:                                          # sanity check ...
            print "ERROR (Serious): Entry objects have different target strings"
            print "   Current hyp  : ", self.tgt
            print "   Existing hyp : ", hyp_w_LM.tgt
            print
            sys.exit(1)

        self.lm_heu = hyp_w_LM.lm_heu
        self.tgt_elided = hyp_w_LM.tgt_elided
        self.depth_hier = hyp_w_LM.depth_hier
        self.inf_cell = hyp_w_LM.inf_cell
        self.lm_right = hyp_w_LM.lm_right

        lm_score_diff, self.featVec = LanguageModelManager.copyLMScores(hyp_w_LM.featVec, self.featVec[:])
        self.score += self.lm_heu + lm_score_diff
        return self.score

    def copyLMInfo(self, hyp_w_LM):
        '''Copy the language model information from an existing hypothesis to a new one with the same target'''

        if self.tgt != hyp_w_LM.tgt:                                          # sanity check ...
            print "ERROR (Serious): Entry objects have different target strings"
            print "   Current hyp  : ", self.tgt
            print "   Existing hyp : ", hyp_w_LM.tgt
            print
            sys.exit(1)

        self.lm_heu = hyp_w_LM.lm_heu
        self.tgt_elided = hyp_w_LM.tgt_elided
        self.depth_hier = hyp_w_LM.depth_hier
        self.lm_right = hyp_w_LM.lm_right

        lm_score_diff, self.featVec = LanguageModelManager.copyLMScores(hyp_w_LM.featVec, self.featVec[:])
        self.score += self.lm_heu + lm_score_diff        
        return self.score

    @classmethod
    def createFromRule(cls, r_item, span):
        return Hypothesis(r_item.score, r_item.lm_heu, r_item.src, r_item.tgt, \
                          r_item.featVec[:], r_item.tgt, 0, span, None, (), 0.0, None)

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

        cand_hyp = self.getHypothesis()        
        feat_str = FeatureManager.formatFeatureVals(cand_hyp, self.featVec)
        return cand_hyp, feat_str, self.cand_score

    def getHypScore(self):
        return self.score

    def getLMHeu(self):
        return self.lm_heu

    def getScoreSansLM(self):
        return self.score - self.lm_heu - LanguageModelManager.getLMScore(self.featVec)

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
